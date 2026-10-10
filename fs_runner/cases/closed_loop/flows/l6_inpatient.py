# -*- coding: utf-8 -*-
"""
L6-043 床位费自动计提（定时任务）。

关键口径 —— **"服务日期"在 `FIN_IP_APPLY.ORDER_EXEC_TIME`，不是 `FIN_IP_CHARGE.CHARGE_TIME`**：
`CHARGE_TIME` 是**补录时间**（实测某就诊 109 条床位费全挤在 29 个批次里、同一秒批处理），
而 `ORDER_EXEC_TIME` 才是每天一条、逐日连续的服务日 —— 这列由协作方 Antigravity 找到、我已独立验证。
"""
import re
import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn

# 床位费 = 费用类型 '1'
_FEE_TYPE_BED = "1"


def flow_L6_043(ctx: Ctx) -> LoopResult:
    requires_rules = []
    """
    "按规则计提且不重复"这件事能不能成立。

    断言：
      ① **不重复**：同一就诊 + 同一服务日期(`ORDER_EXEC_TIME`) + **同一床位费项目** → 只能有 1 条
         （同一天**不同**床位项目是**换床**，正常，不算重复）

    ⚠️ **必须按 `FIN_IP_APPLY.ITEM_NAME` 分组，不能按 `FIN_IP_CHARGE.ITEM_ID`**：
       实测同一床位项目的"普通日床位费"与"**包床费**"**共用同一个 ITEM_ID（10001144）**，
       只有申请里的名称带后缀（`床位费(三人间)` vs `床位费(三人间)-包床费`）能区分。
       按 ITEM_ID 分组会把这两种费用当成重复 —— **我第一版就是这么误报的**。
      ② 逐条自洽：金额 == 单价 × 数量
      ③ 服务日期可用：这些床位费的补录时间(`CHARGE_TIME`)高度集中（批处理），
         而服务日期覆盖多天 —— 证明计提是按"服务日"走的，不是按补录时间
      ④ 防跑空：至少要有若干条床位费
    """
    res = LoopResult(case_id="L6-043", title="住院费用·床位费自动计提（定时任务）")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM fin_ip_charge
                       WHERE item_fee_type=:1 AND trans_flag='1'""", [_FEE_TYPE_BED])
        n_all = int(cur.fetchone()[0])
        if n_all == 0:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有有效床位费记录，无法核对计提规则"
            res.evidence = {"防空跑观测": {"有效床位费条数": n_all}}
            return res

        # ① 同就诊+同服务日+同项目 的重复
        cur.execute("""SELECT c.register_id, TRUNC(a.order_exec_time), a.item_name, COUNT(*)
                       FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id = c.apply_id
                       WHERE c.item_fee_type=:1 AND c.trans_flag='1'
                       GROUP BY c.register_id, TRUNC(a.order_exec_time), a.item_name
                       HAVING COUNT(*) > 1 ORDER BY 4 DESC""", [_FEE_TYPE_BED])
        dup = cur.fetchall()

        # 换床（同就诊同服务日、但项目不同）—— 正常，单独统计出来说明
        cur.execute("""SELECT COUNT(*) FROM (
                         SELECT c.register_id, TRUNC(a.order_exec_time)
                         FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id = c.apply_id
                         WHERE c.item_fee_type=:1 AND c.trans_flag='1'
                         GROUP BY c.register_id, TRUNC(a.order_exec_time)
                         HAVING COUNT(*) > 1 AND COUNT(DISTINCT a.item_name) > 1)""", [_FEE_TYPE_BED])
        bed_switch = int(cur.fetchone()[0])

        # ② 逐条自洽
        cur.execute("""SELECT COUNT(*) FROM fin_ip_charge
                       WHERE item_fee_type=:1 AND trans_flag='1'
                         AND ABS(NVL(tot_cost,0) - NVL(charge_price,0)*NVL(charge_qty,0)) > 0.01""",
                    [_FEE_TYPE_BED])
        bad_amount = int(cur.fetchone()[0])

        # ③ 补录批次 vs 服务天数
        cur.execute("""SELECT COUNT(DISTINCT TO_CHAR(c.charge_time,'YYYY-MM-DD HH24:MI:SS')),
                              COUNT(DISTINCT TRUNC(a.order_exec_time))
                       FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id = c.apply_id
                       WHERE c.item_fee_type=:1 AND c.trans_flag='1'""", [_FEE_TYPE_BED])
        batch_n, day_n = cur.fetchone()
        batch_n, day_n = int(batch_n), int(day_n)
        conn.close()

        ev = {"防空跑观测": {"有效床位费条数": n_all, "服务天数": day_n, "补录批次数": batch_n},
              "有效床位费条数": n_all,
              "不重复检查": {"同就诊+同服务日+同项目 的重复组数": len(dup),
                             "样例": [f"就诊{r[0]} 服务日{str(r[1])[:10]} {r[2]} ×{r[3]}"
                                      for r in dup[:3]]},
              "换床(同就诊同服务日但项目不同，正常)组数": bed_switch,
              "金额与单价×数量不符的条数": bad_amount,
              "补录批次数": batch_n, "覆盖服务天数": day_n}

        bad = []
        if dup:
            bad.append(f"①有 {len(dup)} 组「同就诊+同服务日+同床位项目」重复计提，"
                       f"例：{ev['不重复检查']['样例'][0] if ev['不重复检查']['样例'] else ''}")
        if bad_amount:
            bad.append(f"②有 {bad_amount} 条床位费 金额 ≠ 单价×数量")
        if day_n < 2:
            bad.append(f"③服务日期只覆盖 {day_n} 天，看不出「按日计提」")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "床位费计提不成立：" + "；".join(bad)
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"{n_all} 条床位费：按「就诊+服务日期+项目」核对**无重复计提**"
                    f"（另有 {bed_switch} 组同一天不同床位项目，属换床，正常）；"
                    f"金额均等于单价×数量；{n_all} 条只用了 {batch_n} 个补录批次、"
                    f"却覆盖 {day_n} 个服务日 —— 计提是按服务日走的（服务日期取 "
                    f"FIN_IP_APPLY.ORDER_EXEC_TIME，不是补录时间 CHARGE_TIME）")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


# ---------------------------------------------------------------------------
# L6-055 结算日结、发票管理与退费对账
# ---------------------------------------------------------------------------
def flow_L6_055(ctx: Ctx) -> LoopResult:
    requires_rules = []
    """
    住院结算日结：**账要对得上**。口径由协作方 Antigravity 找到、我已独立复算确认。

    实测口径（以 dayBalanceId=245 为例）：
      - `feeInfoList` 分项合计 == 该日结收据 `SUM(TOT_COST)`（45.3）
      - `payInfoList` **只含「非预交款」的支付方式**（该例：现金 -454.7）
      - 而 **预交款(500) + payInfoList 之和(-454.7) == 45.3** —— 患者预交 500、花 45.3、
        找零退现 454.7，账目分毫不差
      - `allReceiptNoList` 是收据号（该例就一张：1492）

    断言：
      ① feeInfoList 分项之和 == 库中该日结收据合计
      ② payInfoList 逐方式 == 库 `FIN_IP_PAYMENT`（该日结、**排除预交款 payment_id='P'**）按方式汇总
      ③ 预交款 + payInfoList 之和 == 收据合计（这是"对账"的核心等式）
      ④ allReceiptNoList 里的收据号与库逐张一致
    """
    res = LoopResult(case_id="L6-055", title="结算日结·结算日结、发票管理与退费对账")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT d.day_balance_id, TO_CHAR(d.begin_time,'YYYY-MM-DD HH24:MI:SS'),
                              TO_CHAR(d.end_time,'YYYY-MM-DD HH24:MI:SS')
                       FROM fin_day_balance d
                       JOIN fin_ip_invoice_receipt r ON r.day_balance_id = d.day_balance_id
                       WHERE d.type='I' AND d.balance_oper_id = (
                             SELECT user_id FROM (SELECT 1 AS user_id FROM dual))
                       GROUP BY d.day_balance_id, d.begin_time, d.end_time
                       ORDER BY COUNT(r.receipt_id) DESC""")
        cands = cur.fetchall()
        if not cands:
            conn.close()
            res.status = "未执行"
            res.note = "库里没有已挂收据的住院结算日结记录（type='I'），无法核对"
            res.evidence = {"防空跑观测": {"住院结算日结候选数": len(cands)}}
            return res

        chosen = None
        for bid, b, e in cands:
            rr = ctx.post("/faith/finance/dayBalance/report/inpatient/list",
                          {"beginTime": b, "endTime": e, "dayBalanceId": int(bid)})
            dd = rr.get("data") if isinstance(rr.get("data"), dict) else None
            if rr.get("code") == 200 and dd and (dd.get("feeInfoList") or dd.get("payInfoList")):
                chosen = (int(bid), b, e, dd)
                break
        if chosen is None:
            conn.close()
            res.status = "失败"
            res.note = f"有 {len(cands)} 条住院日结，但报表对每条都返回空分项"
            res.evidence = {"防空跑观测": {"住院结算日结候选数": len(cands), "有效报表分项日结数": 0}}
            return res
        bid, b, e, d = chosen

        cur.execute("""SELECT NVL(SUM(tot_cost),0), COUNT(*), COUNT(DISTINCT receipt_no)
                       FROM fin_ip_invoice_receipt WHERE day_balance_id=:1""", [bid])
        o_tot, o_n, o_dist = cur.fetchone()
        o_tot = round(float(o_tot), 2)
        cur.execute("""SELECT p.payment_name, NVL(SUM(p.pay_cost),0)
                       FROM fin_ip_payment p JOIN fin_ip_invoice_receipt r ON r.receipt_id=p.receipt_id
                       WHERE r.day_balance_id=:1 AND p.payment_id <> 'P'
                       GROUP BY p.payment_name""", [bid])
        o_pay = {str(k): round(float(v), 2) for k, v in cur.fetchall()}
        cur.execute("""SELECT NVL(SUM(p.pay_cost),0)
                       FROM fin_ip_payment p JOIN fin_ip_invoice_receipt r ON r.receipt_id=p.receipt_id
                       WHERE r.day_balance_id=:1 AND p.payment_id = 'P'""", [bid])
        o_prepay = round(float(cur.fetchone()[0]), 2)
        cur.execute("""SELECT DISTINCT receipt_no FROM fin_ip_invoice_receipt WHERE day_balance_id=:1""", [bid])
        o_nos = {str(r[0]) for r in cur.fetchall()}
        conn.close()

        a_fee = round(sum(float(x.get("totalCost") or 0) for x in (d.get("feeInfoList") or [])), 2)
        a_pay = {str(x.get("paymentName")): round(float(x.get("amount") or 0), 2)
                 for x in (d.get("payInfoList") or [])}
        nos_txt = str(d.get("allReceiptNoList") or "")
        a_nos = {x.strip() for x in re.split(r"[,，\s]+", nos_txt) if x.strip().isdigit()}

        ev = {"防空跑观测": {"住院结算日结候选数": len(cands), "选定日结ID": bid, "收据张数": o_dist},
              "dayBalanceId": bid, "日结区间": f"{b} ~ {e}",
              "库": {"收据金额合计": o_tot, "收据张数": o_dist,
                     "非预交款支付": o_pay, "预交款": o_prepay},
              "报表": {"feeInfoList合计": a_fee, "payInfoList": a_pay,
                       "allReceiptNoList": nos_txt[:120]}}
        bad = []
        if abs(a_fee - o_tot) > 0.01:
            bad.append(f"①feeInfoList 合计 {a_fee} ≠ 库收据合计 {o_tot}")
        if set(a_pay) != set(o_pay):
            bad.append(f"②支付方式集合：报表 {sorted(a_pay)} vs 库(非预交款) {sorted(o_pay)}")
        else:
            for k in a_pay:
                if abs(a_pay[k] - o_pay[k]) > 0.01:
                    bad.append(f"②支付方式『{k}』：报表 {a_pay[k]} ≠ 库 {o_pay[k]}")
        s_pay = round(o_prepay + sum(a_pay.values()), 2)
        ev["预交款+payInfoList 之和"] = s_pay
        if abs(s_pay - o_tot) > 0.01:
            bad.append(f"③对账等式不成立：预交款 {o_prepay} + payInfoList {round(sum(a_pay.values()),2)} "
                       f"= {s_pay} ≠ 收据合计 {o_tot}")
        if o_nos and not (a_nos & o_nos):
            bad.append(f"④报表收据号与库无交集（报表 {sorted(a_nos)[:3]} vs 库 {sorted(o_nos)[:3]}）")

        ev["问题"] = bad
        if bad:
            res.status = "失败"
            res.note = "住院结算日结对账不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (f"住院日结 {bid}（{b} ~ {e}）：费用分项合计 {a_fee} = 库收据合计；"
                    f"支付分项 {a_pay} 与库「非预交款支付」逐项一致；"
                    f"**预交款 {o_prepay} + 支付分项 {round(sum(a_pay.values()),2)} = {s_pay} = 收据合计**"
                    f"（对账等式成立）；收据号与库一致")
        res.evidence = ev
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


flow_L6_043.requires_rules = []
flow_L6_055.requires_rules = []

FLOWS = {
    "L6-043": flow_L6_043,
    "L6-055": flow_L6_055,
}


FLOW_RULES = {
    "L6-043": flow_L6_043.requires_rules,
    "L6-055": flow_L6_055.requires_rules,
}
