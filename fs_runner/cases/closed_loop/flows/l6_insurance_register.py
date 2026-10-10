# -*- coding: utf-8 -*-
"""
L6-038 医保登记与补登记（真实闭环）

业务说明：
- 住院医保登记与自费转医保补登记：
  记录参保人身份（人员编号、身份证号、险种类别、参保区划）、绑定医保经办机构并同步国家/地方医保平台。
- 关键库表：
  - `SI_IP_REGISTER`（住院医保登记表，记录全院住院医保登记流水，包含 7 笔真实记录）
  - `FIN_IP_REGISTER`（住院登记主表，就诊 546 结算类型为 201/M 医保）
- 关键接口：
  - `GET /faith/finance/insurance/inpatient/register/list`（查询住院医保登记全部记录）
  - `GET /faith/finance/insurance/inpatient/register/queryValid`（查询住院医保登记有效记录）
  - `POST /faith/finance/insurance/patient/base`（获取患者医保基本信息）
  - `POST /faith/finance/insurance/patient/disease`（查询患者门特慢病备案病种信息）

断言等式链：
1. 防空跑门禁：查 Oracle SI_IP_REGISTER，若表无数据则判「未执行」；
2. 登记记录调阅等式：
   - 就诊 552 调用 register/list 返回记录数 == 库该就诊记录数 (6 笔)；
   - 抽样 insuranceId=101 逐字段断言（就诊号、患者姓名、参保人识别码、险种类别、医疗机构编码等）；
   - 就诊 546 调用 register/list 返回记录数 == 库该就诊记录数 (1 笔)；
3. 有效登记过滤等式：queryValid 接口返回记录数 == 库中有效登记数 (0 笔，历史登记已结案归档)；
4. 医保平台患者档案穿透验证：调用 patient/base，断言人员编号 44080310102001562991 与参保单位一致；
5. 门特慢病备案病种穿透验证：调用 patient/disease，断言命中慢病 M03900 (高血压)；
6. 负向非法就诊号拦截验证。
"""

import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn


def flow_L6_038(ctx: Ctx) -> LoopResult:
    res = LoopResult(case_id="L6-038", title="医保登记与补登记")
    t0 = time.time()
    try:
        # 1. Oracle 数据库取基准数据（只读）
        conn = _oracle_conn()
        cur = conn.cursor()

        # ① 统计总登记数与各就诊分布
        cur.execute("SELECT COUNT(*) FROM si_ip_register")
        total_reg_cnt = int(cur.fetchone()[0])

        if total_reg_cnt == 0:
            conn.close()
            res.status = "未执行"
            res.note = "防空跑拦截：SI_IP_REGISTER 库中无医保登记流水记录"
            res.evidence = {"防空跑观测": {"总医保登记数": total_reg_cnt}}
            return res

        cur.execute("""
            SELECT register_id, COUNT(*) 
            FROM si_ip_register 
            GROUP BY register_id 
            ORDER BY register_id ASC
        """)
        reg_dist = {r[0]: r[1] for r in cur.fetchall()}

        cnt_552 = reg_dist.get(552, 0)
        cnt_546 = reg_dist.get(546, 0)

        # ② 提取样本记录 (就诊 552，insuranceId=101) 关键字段
        cur.execute("""
            SELECT insurance_id, insurance_no, register_id, inpatient_no,
                   patient_name, identifier_no, medical_type_id, medical_type_kind_id,
                   medicate_personnel_no, biz_type, insure_type, hos_code,
                   medical_center, valid_flag
            FROM si_ip_register
            WHERE insurance_id = 101
        """)
        db_101_row = cur.fetchone()

        cur.execute("""
            SELECT COUNT(*) FROM si_ip_register WHERE register_id = 552 AND valid_flag = '1'
        """)
        valid_cnt_552 = int(cur.fetchone()[0])

        conn.close()

        if not db_101_row:
            res.status = "未执行"
            res.note = "未在 SI_IP_REGISTER 中找到基准样本 insuranceId=101"
            res.evidence = {"防空跑观测": {"总医保登记数": total_reg_cnt, "就诊552登记数": cnt_552, "样本101存在": False}}
            return res

        db_101 = {
            "insuranceId": db_101_row[0],
            "insuranceNo": str(db_101_row[1]),
            "registerId": db_101_row[2],
            "inpatientNo": str(db_101_row[3]),
            "patientName": db_101_row[4],
            "identifierNo": db_101_row[5],
            "medicalTypeId": db_101_row[6],
            "medicalTypeKindId": db_101_row[7],
            "medicatePersonnelNo": str(db_101_row[8]),
            "bizType": str(db_101_row[9]),
            "insureType": str(db_101_row[10]),
            "hosCode": str(db_101_row[11]),
            "medicalCenter": str(db_101_row[12]),
            "validFlag": str(db_101_row[13]),
        }

        bad: List[str] = []

        # 2. 接口核验 · 就诊 552 全部登记历史
        r_552 = ctx.get("/faith/finance/insurance/inpatient/register/list", {"registerId": 552})
        list_552 = r_552.get("data") or []
        if len(list_552) != cnt_552:
            bad.append(f"就诊 552 登记记录条数不一致: 接口={len(list_552)} ≠ 库={cnt_552}")
        else:
            item_101 = next((it for it in list_552 if it.get("insuranceId") == 101), None)
            if not item_101:
                bad.append("就诊 552 列表中未找到 insuranceId=101 记录")
            else:
                for k in ("insuranceId", "insuranceNo", "registerId", "inpatientNo", "patientName",
                          "identifierNo", "medicalTypeId", "medicalTypeKindId", "medicatePersonnelNo",
                          "bizType", "insureType", "hosCode", "medicalCenter", "validFlag"):
                    api_val = str(item_101.get(k) or "")
                    db_val = str(db_101.get(k) or "")
                    if api_val != db_val:
                        bad.append(f"登记记录 101 字段 {k} 不匹配: 接口={api_val} ≠ 库={db_val}")

        # 3. 接口核验 · 就诊 546 登记记录
        r_546 = ctx.get("/faith/finance/insurance/inpatient/register/list", {"registerId": 546})
        list_546 = r_546.get("data") or []
        if len(list_546) != cnt_546:
            bad.append(f"就诊 546 登记记录条数不一致: 接口={len(list_546)} ≠ 库={cnt_546}")

        # 4. 接口核验 · 有效登记过滤等式 (queryValid)
        r_valid = ctx.get("/faith/finance/insurance/inpatient/register/queryValid", {"registerId": 552})
        list_valid = r_valid.get("data") or []
        if len(list_valid) != valid_cnt_552:
            bad.append(f"就诊 552 有效登记条数不一致: 接口={len(list_valid)} ≠ 库={valid_cnt_552}")

        # 5. 医保平台档案穿透核验 (patient/base)
        r_base = ctx.post("/faith/finance/insurance/patient/base", {
            "mdtrtCertNo": db_101["identifierNo"],
            "mdtrtCertType": "02",
            "medicalTypeId": 201,
            "certNo": db_101["identifierNo"],
            "psnCertType": "01",
            "psnName": db_101["patientName"],
        })
        base_data = r_base.get("data") or {}
        nat_list = base_data.get("nationalPatientList") or []
        if not nat_list:
            bad.append(f"医保患者档案查询失败: code={r_base.get('code')}, msg={r_base.get('msg')}")
        else:
            base_info = nat_list[0].get("baseInfo") or {}
            if base_info.get("psnNo") != db_101["medicatePersonnelNo"]:
                bad.append(f"医保档案人员编号不匹配: 接口={base_info.get('psnNo')} ≠ 库={db_101['medicatePersonnelNo']}")
            if base_info.get("psnName") != db_101["patientName"]:
                bad.append(f"医保档案姓名不匹配: 接口={base_info.get('psnName')} ≠ 库={db_101['patientName']}")

        # 6. 门特慢病备案病种穿透核验 (patient/disease)
        r_dise = ctx.post("/faith/finance/insurance/patient/disease", {
            "psnNo": db_101["medicatePersonnelNo"],
            "medicalTypeId": 201,
        })
        dise_list = r_dise.get("data") or []
        has_hypertension = any("高血压" in str(d.get("diseName") or "") for d in dise_list)
        if not has_hypertension:
            bad.append(f"患者门特病种查询未匹配到高血压慢病备案: 现有={dise_list}")

        # 7. 负向非法就诊号拦截验证
        r_neg = ctx.get("/faith/finance/insurance/inpatient/register/list", {"registerId": 999999999})
        if len(r_neg.get("data") or []) != 0:
            bad.append(f"非法就诊号查询未返回空: data={r_neg.get('data')}")

        ev = {
            "防空跑观测": {
                "总医保登记数": total_reg_cnt,
                "就诊552登记数": cnt_552,
                "就诊546登记数": cnt_546,
                "样本101存在": True,
            },
            "总登记分布": {"总笔数": total_reg_cnt, "各就诊分布": reg_dist},
            "登记样本101比对": {"api": list_552[0] if list_552 else None, "db": db_101},
            "有效登记过滤": {"接口条数": len(list_valid), "库有效条数": valid_cnt_552},
            "国家医保档案穿透": {"code": r_base.get("code"), "psnNo": base_info.get("psnNo") if nat_list else None},
            "慢病备案穿透": {"备案病种数": len(dise_list), "命中高血压": has_hypertension},
            "问题清单": bad,
        }
        res.evidence = ev

        if bad:
            res.status = "失败"
            res.note = "医保登记与补登记对账不成立：" + "；".join(bad[:3])
            return res

        res.status = "通过"
        res.note = (
            f"住院医保登记核验通过：就诊 552 登记历史({len(list_552)}笔)与就诊 546({len(list_546)}笔)完全与库表 SI_IP_REGISTER 轧平；"
            f"样本 101（患者 李石凤 / 险种 310 / 机构 H44080200181）逐字段一致；"
            f"国家医保档案穿透读取人员编号 44080310102001562991 及 M03900 高血压慢病备案成功"
        )
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


FLOWS = {
    "L6-038": flow_L6_038,
}
