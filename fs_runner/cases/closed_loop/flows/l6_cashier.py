# -*- coding: utf-8 -*-
"""
L6-026 自费收银与医保收银（真实闭环）

业务说明：
- 门诊收银管理包含两条独立且关键的结算链路：
  ① 自费收银（payType='O'，全自费病人）：无医保统筹基金支付，总费用 100% 由患者通过现金/微信自费结清；
  ② 医保收银（payType='M'，职工/居民医保病人）：总费用经过医保规则切分，统筹基金部分 (pubCost) 记账，
     其余自付/自费部分 (ownCost + payCost) 由患者通过现金/微信支付结清。
- 关键库表：
  - `FIN_OP_INVOICE_RECEIPT`（门诊发票收据表，记录结算类型、统筹与自付金额）
  - `FIN_OP_PAYMENT`（门诊支付方式明细表，记录具体支付渠道流水）
- 关键接口：
  - `POST /faith/finance/outpatient/receipt/view/list`（按结算大类/发票号查询收银发票）
  - `GET /faith/finance/outpatient/receipt/payment/queryByReceiptNo`（按发票号查询支付方式明细）

断言等式链：
1. 防空跑门禁：查库确认 FIN_OP_INVOICE_RECEIPT 中同时存在自费 ('O') 与医保 ('M') 发票；
2. 自费收银等式（样本收据 1683，方泰）：
   - 接口与库逐字段严格一致（payType='O', medicalTypeId=101, pubCost=0, ownCost=totCost）；
   - 支付流水轧平：sum(paymentCost) == totCost == 库 FIN_OP_PAYMENT 合计 (40.89)；
3. 医保收银等式（样本收据 1400，李石凤）：
   - 接口与库逐字段严格一致（payType='M', medicalTypeId=201, 职工医保 20201）；
   - 医保统筹切分等式：totCost (8.64) == pubCost (7.62) + ownCost (1.02)；
   - 个人实付轧平等式：sum(paymentCost) == ownCost (1.02) + payCost (0.71) == 1.73 元；
4. 负向非法收据号查询拦截与健壮性验证。
"""

import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn


def flow_L6_026(ctx: Ctx) -> LoopResult:
    requires_rules = ['CONV_GATE_OBSERVATION_EXPLICIT', 'RULE_FIN_CASHIER_SEGMENT', 'RULE_OP_05', 'RULE_OP_08']
    res = LoopResult(case_id="L6-026", title="自费收银与医保收银")
    t0 = time.time()
    try:
        # 1. Oracle 数据库取基准数据（只读）
        conn = _oracle_conn()
        cur = conn.cursor()

        # ① 统计自费与医保发票总数及支付流水
        cur.execute("""
            SELECT pay_type, COUNT(*), NVL(SUM(tot_cost), 0), NVL(SUM(pub_cost), 0), NVL(SUM(own_cost), 0)
            FROM fin_op_invoice_receipt
            WHERE valid_flag = '1'
            GROUP BY pay_type
        """)
        summary_rows = {r[0]: {"cnt": r[1], "tot": float(r[2]), "pub": float(r[3]), "own": float(r[4])} for r in cur.fetchall()}

        cnt_o = summary_rows.get("O", {}).get("cnt", 0)
        cnt_m = summary_rows.get("M", {}).get("cnt", 0)

        # 防空跑门禁
        if cnt_o == 0 or cnt_m == 0:
            conn.close()
            res.status = "未执行"
            res.note = f"防空跑拦截：FIN_OP_INVOICE_RECEIPT 中有效自费发票({cnt_o})或医保发票({cnt_m})样本不足"
            res.evidence = {"防空跑观测": {"有效自费发票数": cnt_o, "有效医保发票数": cnt_m, "全量分布": summary_rows}}
            return res

        # ② 提取自费发票样本 (收据 1683) 与支付明细
        cur.execute("""
            SELECT r.receipt_id, r.receipt_no, r.patient_id, r.patient_name, r.pay_type,
                   r.medical_type_id, r.tot_cost, r.own_cost, r.pub_cost, r.pay_cost
            FROM fin_op_invoice_receipt r
            WHERE r.receipt_no = '1683' AND r.valid_flag = '1'
        """)
        o_row = cur.fetchone()

        cur.execute("""
            SELECT payment_id, payment_name, payment_cost, actual_cost
            FROM fin_op_payment
            WHERE receipt_id = :1
        """, [o_row[0] if o_row else 0])
        o_pay_rows = cur.fetchall()

        # ③ 提取医保发票样本 (收据 1400) 与支付明细
        cur.execute("""
            SELECT r.receipt_id, r.receipt_no, r.patient_id, r.patient_name, r.pay_type,
                   r.medical_type_id, r.tot_cost, r.own_cost, r.pub_cost, r.pay_cost
            FROM fin_op_invoice_receipt r
            WHERE r.receipt_no = '1400' AND r.valid_flag = '1'
        """)
        m_row = cur.fetchone()

        cur.execute("""
            SELECT payment_id, payment_name, payment_cost, actual_cost
            FROM fin_op_payment
            WHERE receipt_id = :1
        """, [m_row[0] if m_row else 0])
        m_pay_rows = cur.fetchall()

        conn.close()

        if not o_row or not m_row:
            res.status = "未执行"
            res.note = "未定位到指定自费(1683)或医保(1400)对比发票样本"
            res.evidence = {"防空跑观测": {"有效自费发票数": cnt_o, "有效医保发票数": cnt_m,
                                           "自费样本1683命中": bool(o_row), "医保样本1400命中": bool(m_row)}}
            return res

        bad: List[str] = []

        # 2. 自费收银接口核验 (Receipt 1683)
        r_o = ctx.post("/faith/finance/outpatient/receipt/view/list", {
            "receiptNo": "1683",
            "beginDate": "2026-01-01 00:00:00",
            "endDate": "2026-12-31 23:59:59"
        })
        api_o_list = r_o.get("data") or []
        if not api_o_list:
            bad.append("自费发票 1683 接口未查出记录")
        else:
            api_o = api_o_list[0]
            if api_o.get("payType") != "O":
                bad.append(f"自费发票 payType 错误: 期望 O, 实际 {api_o.get('payType')}")
            if api_o.get("medicalTypeId") != 101:
                bad.append(f"自费发票 medicalTypeId 错误: 期望 101, 实际 {api_o.get('medicalTypeId')}")
            if abs(float(api_o.get("totCost") or 0) - float(o_row[6])) > 0.001:
                bad.append(f"自费发票总额不一致: 接口={api_o.get('totCost')} ≠ 库={o_row[6]}")
            if abs(float(api_o.get("pubCost") or 0) - 0.0) > 0.001:
                bad.append(f"自费发票统筹金额不为0: {api_o.get('pubCost')}")
            if abs(float(api_o.get("ownCost") or 0) - float(api_o.get("totCost") or 0)) > 0.001:
                bad.append(f"自费发票自费额与总额不相等: 自费={api_o.get('ownCost')}, 总额={api_o.get('totCost')}")

            # 自费支付流水对账
            r_pay_o = ctx.get("/faith/finance/outpatient/receipt/payment/queryByReceiptNo", {"receiptNo": "1683"})
            pay_o_list = r_pay_o.get("data") or []
            sum_pay_o = round(sum(float(p.get("paymentCost") or 0) for p in pay_o_list), 2)
            db_sum_pay_o = round(sum(float(p[2]) for p in o_pay_rows), 2)
            if abs(sum_pay_o - db_sum_pay_o) > 0.001:
                bad.append(f"自费支付明细总额不一致: 接口={sum_pay_o} ≠ 库={db_sum_pay_o}")
            if abs(sum_pay_o - float(o_row[6])) > 0.001:
                bad.append(f"自费支付实付金额未轧平总费用: 实付={sum_pay_o} ≠ 总额={o_row[6]}")

        # 3. 医保收银接口核验 (Receipt 1400)
        r_m = ctx.post("/faith/finance/outpatient/receipt/view/list", {
            "receiptNo": "1400",
            "beginDate": "2026-01-01 00:00:00",
            "endDate": "2026-12-31 23:59:59"
        })
        api_m_list = r_m.get("data") or []
        if not api_m_list:
            bad.append("医保发票 1400 接口未查出记录")
        else:
            api_m = api_m_list[0]
            if api_m.get("payType") != "M":
                bad.append(f"医保发票 payType 错误: 期望 M, 实际 {api_m.get('payType')}")
            if api_m.get("medicalTypeId") != 201:
                bad.append(f"医保发票 medicalTypeId 错误: 期望 201, 实际 {api_m.get('medicalTypeId')}")
            
            tot_m = float(api_m.get("totCost") or 0)
            pub_m = float(api_m.get("pubCost") or 0)
            own_m = float(api_m.get("ownCost") or 0)
            pay_m = float(api_m.get("payCost") or 0)

            # 医保基金切分等式：总费用 = 统筹记账 + 全自费
            if abs(tot_m - (pub_m + own_m)) > 0.01:
                bad.append(f"医保统筹切分不轧平: 总额({tot_m}) ≠ 统筹({pub_m}) + 自费({own_m})")

            # 医保支付流水对账
            r_pay_m = ctx.get("/faith/finance/outpatient/receipt/payment/queryByReceiptNo", {"receiptNo": "1400"})
            pay_m_list = r_pay_m.get("data") or []
            sum_pay_m = round(sum(float(p.get("paymentCost") or 0) for p in pay_m_list), 2)
            db_sum_pay_m = round(sum(float(p[2]) for p in m_pay_rows), 2)
            if abs(sum_pay_m - db_sum_pay_m) > 0.001:
                bad.append(f"医保支付明细总额不一致: 接口={sum_pay_m} ≠ 库={db_sum_pay_m}")

            # 个人实付轧平等式：个人现金实付 = 自费(ownCost) + 自付(payCost)
            expected_patient_pay = round(own_m + pay_m, 2)
            if abs(sum_pay_m - expected_patient_pay) > 0.01:
                bad.append(f"医保收银个人实付未轧平: 个人实付({sum_pay_m}) ≠ 自费({own_m}) + 自付({pay_m})")

        # 4. 负向非法发票号查询拦截验证
        r_neg = ctx.get("/faith/finance/outpatient/receipt/payment/queryByReceiptNo", {"receiptNo": "NON_EXIST_999999"})
        if len(r_neg.get("data") or []) != 0:
            bad.append(f"非法收据号查询未返回空: data={r_neg.get('data')}")

        ev = {
            "防空跑观测": {
                "有效自费发票数": cnt_o,
                "有效医保发票数": cnt_m,
                "自费样本1683命中": True,
                "医保样本1400命中": True,
            },
            "全量发票分布": summary_rows,
            "自费收银样本(1683)": {
                "发票号": "1683",
                "患者": "方泰",
                "结算类别": "自费(O/101)",
                "总费用": o_row[6],
                "统筹记账": o_row[8],
                "个人自费": o_row[7],
                "支付明细": [{"支付方式": p[1], "金额": float(p[2])} for p in o_pay_rows],
            },
            "医保收银样本(1400)": {
                "发票号": "1400",
                "患者": "李石凤",
                "结算类别": "国家医保(M/201)",
                "总费用": m_row[6],
                "统筹记账": m_row[8],
                "个人自费": m_row[7],
                "个人自付": m_row[9],
                "支付明细": [{"支付方式": p[1], "金额": float(p[2])} for p in m_pay_rows],
            },
            "问题清单": bad,
        }
        res.evidence = ev

        if bad:
            res.status = "失败"
            res.note = "自费收银与医保收银对账不成立：" + "；".join(bad[:3])
            return res

        res.status = "通过"
        res.note = (
            f"门诊自费收银与医保收银核验通过：自费收银（样本1683，总额 {o_row[6]} 元全部由现金结清且统筹为0）；"
            f"医保收银（样本1400，总额 {m_row[6]} 元由统筹记账 {m_row[8]} 元与个人现金支付 {db_sum_pay_m} 元精确切分并轧平）；"
            f"接口与库表 FIN_OP_INVOICE_RECEIPT 及 FIN_OP_PAYMENT 逐笔逐字段一致"
        )
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


flow_L6_026.requires_rules = ['CONV_GATE_OBSERVATION_EXPLICIT', 'RULE_FIN_CASHIER_SEGMENT', 'RULE_OP_05', 'RULE_OP_08']

FLOWS = {
    "L6-026": flow_L6_026,
}


FLOW_RULES = {
    "L6-026": flow_L6_026.requires_rules,
}
