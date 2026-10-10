# -*- coding: utf-8 -*-
"""
L9-012 住院药房 · 长期医嘱自动摆药与计划关联

「计划关联」在本系统里落在三层上：

    药房工作台接口            库
    ─────────────────────    ─────────────────────────────
    queryOrderSummary(医嘱汇总)  PHA_DISPENSE_APPLY（该摆药单的明细）
    queryDrugSummary(药品汇总)   PHA_DISPENSE_APPLY 按药品 SUM
    医嘱明细的 ORDER_ID         MED_IP_ORDER（住院）/ MED_OP_ORDER（门诊）

⚠️ **关键口径：`PHA_DISPENSE_APPLY.ORDER_ID` 指向两张不同的医嘱表**
   有床号（住院发药）→ `MED_IP_ORDER`；无床号（门诊发药）→ `MED_OP_ORDER`。
   只 JOIN `MED_IP_ORDER` 会得出「57/73 医嘱关联断裂」的**假缺陷** —— 我第一版就是这么误报的：
   那张表的 ORDER_ID 只从 4363 起（更早的被清），而明细里 3667~4362 段的单其实在门诊表里。
   两张表都 LEFT JOIN 后实测 73 条 = 门诊 57 + 住院 16，**零悬挂**。

⚠️ **数量口径**：`APPLY_QTY` 是**最小单位**的数量，医嘱 `QTY` 是**包装单位**的数量，
   换算率 = 同单位时 1、跨单位时 `PACKAGE_QTY`（实测 医嘱 2盒 × 24粒/盒 = 摆药 48粒）。
   **但 `APPLY_QTY == 医嘱 QTY` 这个等式整体上不成立**，三种正当情形都会破坏它，硬断言必假报失败：
     ① 单位换算（48粒 vs 2盒）② 部分发放（门诊医嘱 3袋、实际只发 1 袋）③ 全退（有效明细一正一负，净 0）。
   真正成立的不变量是**不得超发**（净发放量换算回医嘱单位 ≤ 医嘱量），本用例断言的是它。

断言：
  ① 医嘱汇总接口（按 摆药单×状态）逐行 == 库该单该状态的有效明细
     （drugId / drugName / drugSpecs / 数量 / 单价 / 金额）
  ② 药品汇总接口（按摆药单）逐药品 == 库该单按药品 SUM(数量) / SUM(金额)
  ③ 每条明细都能挂回**对应表**的源医嘱（零悬挂），且用法/频次/状态与医嘱一致
  ④ 不得超发：按 ORDER_ID 汇总有效明细的净发放量，换算回医嘱单位后 **≤ 医嘱量**
     （**不要**断言 `APPLY_QTY == 医嘱 QTY` —— 见下方口径说明，那个等式根本不成立）
  ⑤ 长期医嘱确实参与摆药（存在由 CZ/ZC 派生的明细）—— 防空跑
  ⑥ 退药行成对：同 ORDER_ID 下负数量行必有等量正数量镜像
"""
import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn, _rows_of

# 摆药单状态码 → 接口枚举名（服务端拼写：已发药是 OUTPUTTED，三个 T）
_STATE_NAME = {"1": "SENT", "2": "PRINTED", "3": "DISPENSED", "4": "OUTPUTTED"}
_STORAGE_DEPT = 910125          # 西药房


def _f(x: Any, nd: int = 2):
    try:
        return round(float(x), nd)
    except Exception:
        return None


def flow_L9_012(ctx: Ctx) -> LoopResult:
    res = LoopResult(case_id="L9-012", title="住院药房·长期医嘱自动摆药与计划关联")
    t0 = time.time()
    try:
        tl = ctx.get("/faith/pharmacy/inDispense/queryTerminalList",
                     {"storageDeptId": _STORAGE_DEPT, "deptId": _STORAGE_DEPT})
        terms = _rows_of(tl)
        if not terms:
            res.status = "未执行"
            res.note = "西药房(910125)没有配置住院调配终端，无法核对摆药"
            return res
        terminal_id = terms[0].get("terminalId")

        conn = _oracle_conn()
        cur = conn.cursor()

        # ---- 库里：单 × 状态 的**有效**明细 ---------------------------------
        cur.execute("""SELECT dispense_bill_id, apply_state, drug_id, drug_name, drug_specs,
                              apply_qty, apply_unit, charge_price, apply_cost,
                              bed_no, order_id
                         FROM pha_dispense_apply
                        WHERE dispense_bill_id IS NOT NULL AND valid_flag = '1'""")
        db: Dict[Any, List[Dict[str, Any]]] = {}
        for (bid, st, did, dname, dspec, qty, unit, price, cost, bed, oid) in cur.fetchall():
            db.setdefault((int(bid), str(st)), []).append({
                "drugId": str(did), "drugName": str(dname),
                "drugSpecs": (None if dspec is None else str(dspec)),
                "qty": _f(qty, 3), "unit": unit,
                "price": _f(price), "cost": _f(cost),
                "bedNo": bed, "orderId": (int(oid) if oid is not None else None)})
        if not db:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有「已挂摆药单且有效」的发药明细，构不成比对"
            return res

        bills = sorted({k[0] for k in db})

        # ---- ③ 挂回源医嘱（分表）+ ④ 换算自洽 + ⑤ 长期医嘱参与 ------------
        # ⚠️ `PHA_DISPENSE_APPLY` **没有 ORDER_STATE 列**（只有 ORDER_ID/ORDER_TYPE/
        #    ORDER_USAGE_NAME/ORDER_FREQUENCY_NAME），状态要从源医嘱表取。
        cur.execute("""SELECT d.output_apply_id, d.order_id, d.bed_no,
                              d.drug_name, d.apply_qty, d.apply_unit,
                              d.order_usage_name, d.order_frequency_name,
                              i.usage_name, i.freq_name, i.order_state, i.item_name, i.order_type,
                              o.usage_name, o.freq_name, o.order_state, o.item_name, o.order_type
                         FROM pha_dispense_apply d
                         LEFT JOIN med_ip_order i
                                ON i.order_id = d.order_id AND d.bed_no IS NOT NULL
                         LEFT JOIN med_op_order o
                                ON o.order_id = d.order_id AND d.bed_no IS NULL
                        WHERE d.order_id IS NOT NULL""")
        link_rows = cur.fetchall()

        cur.execute("""SELECT d.order_id, MAX(d.apply_unit), SUM(d.apply_qty),
                              MAX(NVL(i.qty, o.qty)), MAX(NVL(i.qty_unit, o.qty_unit)),
                              MAX(NVL(i.package_qty, o.package_qty))
                         FROM pha_dispense_apply d
                         LEFT JOIN med_ip_order i
                                ON i.order_id = d.order_id AND d.bed_no IS NOT NULL
                         LEFT JOIN med_op_order o
                                ON o.order_id = d.order_id AND d.bed_no IS NULL
                        WHERE d.order_id IS NOT NULL AND d.valid_flag = '1'
                        GROUP BY d.order_id""")
        conv_rows = cur.fetchall()

        cur.execute("""SELECT d.order_id, d.apply_qty
                         FROM pha_dispense_apply d
                        WHERE d.order_id IS NOT NULL AND d.valid_flag = '1'""")
        mirror_rows = cur.fetchall()

        cur.execute("SELECT type_id, type_name, classify_type FROM med_bd_order_type")
        otype_dict = {str(r[0]): (str(r[1]), str(r[2])) for r in cur.fetchall()}
        conn.close()

        ev: Dict[str, Any] = {"终端": {"terminalId": terminal_id,
                                       "名称": terms[0].get("terminalName")},
                              "摆药单数": len(bills),
                              "库里有效明细条数": sum(len(v) for v in db.values())}

        bad: List[str] = []

        # ---- ①② 接口汇总 vs 库 -------------------------------------------
        pairs_checked = pairs_ok = 0
        drug_checked = drug_ok = 0
        samples: List[Dict[str, Any]] = []
        for bid in bills:
            states = sorted({s for (b, s) in db if b == bid})
            for st in states:
                want = db.get((bid, st)) or []
                name = _STATE_NAME.get(st)
                if name is None:
                    continue
                body = [{"dispenseBillId": bid, "storageDeptId": _STORAGE_DEPT,
                         "terminalId": terminal_id, "dispenseState": name,
                         "nodeType": "BILL", "nodeLevel": 1}]
                r1 = ctx.post("/faith/pharmacy/inDispense/queryOrderSummary", body)
                r2 = ctx.post("/faith/pharmacy/inDispense/queryDrugSummary", body)
                got = _rows_of(r1)
                pairs_checked += 1
                api = sorted(
                    (str(x.get("drugId")), str(x.get("drugName")),
                     str(x.get("drugSpecs") or ""), _f(x.get("chargeQty"), 3),
                     _f(x.get("unitPrice")), _f(x.get("totalCost")))
                    for x in got)
                ora = sorted((x["drugId"], x["drugName"], str(x["drugSpecs"] or ""),
                              x["qty"], x["price"], x["cost"]) for x in want)
                if r1.get("code") != 200:
                    bad.append(f"①单{bid} {name}: 医嘱汇总接口异常 {str(r1)[:90]}")
                elif api == ora:
                    pairs_ok += 1
                else:
                    bad.append(f"①单{bid} {name}: 医嘱汇总 {len(api)} 行 ≠ 库 {len(ora)} 行"
                               f"（接口首行 {api[:1]} / 库首行 {ora[:1]}）")

                # ② 药品汇总
                agg: Dict[Any, List[float]] = {}
                for x in want:
                    a = agg.setdefault((x["drugId"], x["drugName"]), [0.0, 0.0])
                    a[0] += (x["qty"] or 0.0)
                    a[1] += (x["cost"] or 0.0)
                ora_d = sorted((k[0], k[1], _f(v[0], 3), _f(v[1]))
                               for k, v in agg.items())
                api_d = sorted((str(x.get("drugId")), str(x.get("drugName")),
                                _f(x.get("totalQty"), 3), _f(x.get("totalCost")))
                               for x in _rows_of(r2))
                drug_checked += 1
                if api_d == ora_d:
                    drug_ok += 1
                else:
                    bad.append(f"②单{bid} {name}: 药品汇总 {api_d} ≠ 库 {ora_d}")
                if len(samples) < 5:
                    samples.append({"单": bid, "状态": name, "库行数": len(ora),
                                    "接口首行": api[:1]})
        ev["①医嘱汇总比对"] = {"组合数": pairs_checked, "一致": pairs_ok, "样例": samples}
        ev["②药品汇总比对"] = {"组合数": drug_checked, "一致": drug_ok}

        # ---- ③ 挂回源医嘱（分表）-----------------------------------------
        dangling = 0
        usage_diff = []
        types: Dict[str, int] = {}
        for r in link_rows:
            oid, dbed = r[1], r[2]
            dusage, dfreq = r[6], r[7]
            if dbed is not None:          # 住院：MED_IP_ORDER 的列在 8~12
                src_usage, src_freq, src_name, src_type = r[8], r[9], r[11], r[12]
            else:                         # 门诊：MED_OP_ORDER 的列在 13~17
                src_usage, src_freq, src_name, src_type = r[13], r[14], r[16], r[17]
            if src_name is None:          # 两张医嘱表都查不到 = 悬挂
                dangling += 1
                continue
            t = str(src_type or "?")
            types[t] = types.get(t, 0) + 1
            if (str(dusage or "") != str(src_usage or "")
                    or str(dfreq or "") != str(src_freq or "")):
                usage_diff.append({"orderId": oid, "明细": (dusage, dfreq),
                                   "医嘱": (src_usage, src_freq)})
        ev["③医嘱关联"] = {"明细总数": len(link_rows), "悬挂(挂不上源医嘱)": dangling,
                            "用法/频次与医嘱不符条数": len(usage_diff),
                            "不符样例": usage_diff[:3]}
        if dangling:
            bad.append(f"③有 {dangling} 条发药明细挂不回源医嘱（住院 MED_IP_ORDER / 门诊 MED_OP_ORDER 都查不到）")
        if usage_diff:
            bad.append(f"③有 {len(usage_diff)} 条明细的用法/频次与源医嘱不一致，例：{usage_diff[0]}")

        # ---- ④ 不得超发 ----------------------------------------------------
        # 按 ORDER_ID 汇总（不是逐条明细！一条医嘱可以分次发放，逐条比对必假报）。
        over: List[Dict[str, Any]] = []
        partial: List[Dict[str, Any]] = []
        for (oid, aunit, net, qty, qunit, pkg) in conv_rows:
            if qty is None or net is None:
                continue
            net = float(net)
            q = abs(float(qty))
            conv = net if str(aunit) == str(qunit) else (net / float(pkg) if pkg else net)
            if conv > q + 1e-6:
                over.append({"orderId": oid, "医嘱": (q, str(qunit)),
                             "有效摆药净量": (net, str(aunit)),
                             "换算回医嘱单位": round(conv, 4), "包装量": pkg})
            elif conv < q - 1e-6:
                partial.append({"orderId": oid, "医嘱": q, "换算发放": round(conv, 4)})
        ev["④不得超发"] = {"比对医嘱数": len(conv_rows), "超发条数": len(over),
                            "超发样例": over[:3],
                            "部分发放或已全退(正常业务，不判缺陷)": len(partial),
                            "部分发放样例": partial[:3]}
        if over:
            bad.append(f"④有 {len(over)} 条医嘱的摆药净量超过医嘱量，例：{over[0]}")

        # ---- ⑤ 长期医嘱确实参与摆药 ---------------------------------------
        ev["⑤摆药明细的源医嘱类型分布"] = {
            f"{k}({otype_dict.get(k, ('?', '?'))[0]})": v for k, v in sorted(types.items())}
        n_long = sum(v for k, v in types.items() if otype_dict.get(k, ("", ""))[1] == "L")
        ev["⑤长期医嘱派生明细条数"] = n_long
        if n_long == 0:
            bad.append("⑤没有任何摆药明细来自长期医嘱(CZ/ZC)，无法印证「长期医嘱自动摆药」")

        # ---- ⑥ 退药行成对 --------------------------------------------------
        by_order: Dict[Any, List[float]] = {}
        for (oid, aqty) in mirror_rows:
            by_order.setdefault(oid, []).append(float(aqty))
        unpaired = []
        for oid, qtys in by_order.items():
            negs = [q for q in qtys if q < 0]
            for q in negs:
                if not any(abs(p + q) < 0.001 for p in qtys if p > 0):
                    unpaired.append({"orderId": oid, "负数量": q, "同医嘱全部数量": qtys})
        ev["⑥退药成对"] = {"含退药行的医嘱数": sum(1 for v in by_order.values() if any(q < 0 for q in v)),
                            "找不到正数量镜像的条数": len(unpaired), "样例": unpaired[:3]}
        if unpaired:
            bad.append(f"⑥有 {len(unpaired)} 条退药行在同医嘱下找不到等量正数量镜像，例：{unpaired[0]}")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "长期医嘱摆药与关联校验不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        n_rows = sum(len(v) for v in db.values())
        res.status = "通过"
        res.note = (
            f"住院药房摆药：{len(bills)} 张摆药单 / {n_rows} 条有效明细 —— "
            f"医嘱汇总接口 {pairs_ok}/{pairs_checked} 组与库逐行一致，"
            f"药品汇总 {drug_ok}/{drug_checked} 组一致；"
            f"明细全部挂回源医嘱（住院走 MED_IP_ORDER、门诊走 MED_OP_ORDER，零悬挂），"
            f"其中长期医嘱(CZ/ZC)派生 {n_long} 条；"
            f"按医嘱汇总的摆药净量换算回医嘱单位后均未超发（另有 {len(partial)} 条为部分发放/已全退，属正常业务）；"
            f"退药行均有等量正数量镜像")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


def flow_L9_013(ctx: Ctx) -> LoopResult:
    """
    出院带药发药 —— **本环境没有可验的业务数据，如实标注「未执行」并附证据**。

    口径：出院带药是医嘱类型 `CD`（`MED_BD_ORDER_TYPE`：出院带药，CLASSIFY_TYPE='S'，
    `OUTSIDE_FLAG='1'` —— 院外带药，走门诊药房）。
    实测（2026-10-09）库里只有 6 条 CD 医嘱，且：
      · 其中 3 条根本不是药品（"内外踝骨折切开复位内固定术" / "紫外线治疗"，`ITEM_FEE_TYPE` 为诊疗类）
      · **6 条全部没有发药明细**（`PHA_DISPENSE_APPLY` 按 ORDER_ID 查 0 条）
      · 也**没有出库明细**（`PHA_OUTPUT_LIST` 按 ORDER_ID 查 0 条）
    也就是说，"出院带药发药"这条业务链在本环境从未被走过 —— 没有数据就无法核对
    "发出的药与出院带药医嘱一致"，硬写断言只会变成空跑判通过。
    """
    res = LoopResult(case_id="L9-013", title="住院药房·出院带药发药")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT o.order_id, o.register_id, o.item_name, o.qty, o.qty_unit,
                              o.order_state, o.item_fee_type,
                              (SELECT COUNT(*) FROM pha_dispense_apply d
                                WHERE d.order_id = o.order_id) AS n_disp,
                              (SELECT COUNT(*) FROM pha_output_list l
                                WHERE l.order_id = o.order_id) AS n_out
                         FROM med_ip_order o
                        WHERE o.order_type = 'CD'
                        ORDER BY o.order_id""")
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM pha_dispense_apply WHERE sys_business_type IN "
                    "('PHA_DIS_OUT01','PHA_DIS_OUT02')")
        n_op_disp_all = int(cur.fetchone()[0])
        conn.close()

        detail = [{"orderId": r[0], "就诊": r[1], "项目": r[2],
                   "数量": f"{r[3]}{r[4]}", "医嘱状态": r[5], "费用类型": r[6],
                   "发药明细条数": r[7], "出库明细条数": r[8]} for r in rows]
        ev = {"出院带药(CD)医嘱条数": len(rows), "明细": detail,
              "有发药明细的CD医嘱条数": sum(1 for r in rows if r[7]),
              "有出库明细的CD医嘱条数": sum(1 for r in rows if r[8]),
              "全库门诊发药明细条数(对照)": n_op_disp_all}

        if not rows:
            res.status = "未执行"
            res.note = "库里没有任何「出院带药(CD)」医嘱，无从核对出院带药发药"
            res.evidence = ev
            return res

        if not any(r[7] or r[8] for r in rows):
            res.status = "未执行"
            res.note = (f"库里只有 {len(rows)} 条出院带药(CD)医嘱，且**没有任何一条生成过发药或出库明细**"
                        f"（门诊发药明细有 {n_op_disp_all} 条作为对照，说明发药功能本身有数据）——"
                        f"出院带药这条业务链在本环境没有走过，无法核对「发出的药与医嘱一致」")
            res.evidence = ev
            return res

        # 有数据时才谈得上核对：断言「不得超发」（口径同 L9-012）
        over = []
        for r in rows:
            if not r[7]:
                continue
            c2 = _oracle_conn()
            cu = c2.cursor()
            cu.execute("""SELECT NVL(SUM(apply_qty),0), MAX(apply_unit) FROM pha_dispense_apply
                           WHERE order_id=:1 AND valid_flag='1'""", [r[0]])
            net, aunit = cu.fetchone()
            c2.close()
            net = float(net or 0)
            conv = net if str(aunit) == str(r[4]) else net
            if conv > abs(float(r[3])) + 1e-6:
                over.append({"orderId": r[0], "医嘱": f"{r[3]}{r[4]}",
                             "摆药净量": f"{net}{aunit}"})
        ev["超发"] = over
        if over:
            res.status = "失败"
            res.note = f"出院带药发药量超过医嘱量：{over[:3]}"
            res.evidence = ev
            return res
        res.status = "通过"
        res.note = (f"{len(rows)} 条出院带药(CD)医嘱：有发药明细的均能挂回医嘱且未超发；"
                    f"（另有 {sum(1 for r in rows if not r[7])} 条尚未发药）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


FLOWS = {
    "L9-012": flow_L9_012,
    "L9-013": flow_L9_013,
}
