# -*- coding: utf-8 -*-
"""
L4-048 临嘱专项校验（只读真校验）

业务说明：
- 医生在住院工作站开立临时医嘱（或长期医嘱）时，系统必须在前置阶段完成多项专项安全与准入校验：
  ① 住院状态准入校验（负向拦截）：若就诊流水号不存在或已注销，拦截阻断（返回 400 "住院登记信息不存在"）；
  ② 在院患者状态准入（正向放行）：处于正常在院状态的患者，开立前校验放行（返回 200 "操作成功"）；
  ③ 需皮试/过敏药品专项拦截与提醒：
     - 若患者在 `BD_PATIENT_ALLERGY` 中登记有该药品的过敏史（如就诊 560 登记有 100171 注射用青霉素钠过敏），
       接口 `/faith/medical/inpatient/order/drug/skinInfo` 必须精准返回 `stFlag = "ND"`（需要皮试）、
       `showFlag = "1"`（必须前端强提醒），并在 `skinRemark` 中带出对应的药品过敏史警示文案；
  ④ 无过敏普通药品的正向放行：
     - 普通无过敏药品（如 100150），接口必须返回 `stFlag = "WO"`（无需皮试）、`showFlag = "0"`，放行开立；
  ⑤ 库表主数据与医嘱真值交叉印证：
     - 验证 `BD_PATIENT_ALLERGY`、`COM_BD_DRUG` 与接口返回字段 100% 吻合。
"""

import time
from typing import Any, Dict

from ..closed_loop import Ctx, LoopResult, _oracle_conn


def flow_L4_048(ctx: Ctx) -> LoopResult:
    res = LoopResult(case_id="L4-048", title="临嘱专项校验")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()

        # 1. 从库中挑选同时具备在院登记与过敏史样本的患者
        cur.execute("""
            SELECT a.register_id, a.patient_id, a.source_code, a.source_name
            FROM bd_patient_allergy a
            JOIN fin_ip_register r ON a.register_id = r.register_id
            WHERE a.valid_flag = '1' AND a.source_code = '100171' AND r.valid_flag = '1'
            FETCH FIRST 1 ROWS ONLY
        """)
        allergy_row = cur.fetchone()
        if not allergy_row:
            conn.close()
            res.status = "未执行"
            res.note = "库中无青霉素过敏且有效关联住院登记的患者样本"
            return res

        reg_id, pat_id, allergy_drug_id, allergy_drug_name = allergy_row
        reg_id = int(reg_id)
        allergy_drug_id = str(allergy_drug_id)

        # 2. 负向拦截测试：不存在的虚假就诊流水号必须被拦截阻断 (400)
        neg_body = {
            "registerId": 99999999,
            "itemId": "100150",
            "itemSysParentType": "0"
        }
        neg_res = ctx.post("/faith/medical/inpatient/order/judgeBeforeCreate", neg_body)
        neg_code = neg_res.get("code")
        neg_msg = neg_res.get("msg", "")

        bad: list = []
        if neg_code != 400 or "不存在" not in neg_msg:
            bad.append(f"负向拦截未阻断: 期待 code=400且含'不存在', 实际 code={neg_code}, msg='{neg_msg}'")

        # 3. 正向准入测试：在院真实患者开立普通项目必须放行 (200)
        pos_body = {
            "registerId": reg_id,
            "itemId": "100150",
            "itemSysParentType": "0"
        }
        pos_res = ctx.post("/faith/medical/inpatient/order/judgeBeforeCreate", pos_body)
        pos_code = pos_res.get("code")
        if pos_code != 200:
            bad.append(f"在院患者前置校验未放行: 期待 code=200, 实际 code={pos_code}, msg='{pos_res.get('msg')}'")

        # 4. 需皮试/过敏药品专项校验：青霉素 100171 必须触发皮试提醒 (stFlag='ND', showFlag='1')
        skin_res = ctx.get("/faith/medical/inpatient/order/drug/skinInfo",
                           params={"registerId": reg_id, "drugId": allergy_drug_id})
        skin_data = skin_res.get("data") or {}
        st_flag = skin_data.get("stFlag")
        show_flag = skin_data.get("showFlag")
        skin_remark = skin_data.get("skinRemark", "")

        if st_flag != "ND":
            bad.append(f"过敏/皮试药品标志不符: 期待 stFlag='ND', 实际='{st_flag}'")
        if show_flag != "1":
            bad.append(f"过敏/皮试药品未弹窗提醒: 期待 showFlag='1', 实际='{show_flag}'")
        if allergy_drug_name not in skin_remark:
            bad.append(f"过敏提醒文案未指明具体药品: 期待包含'{allergy_drug_name}', 实际='{skin_remark}'")

        # 5. 普通非皮试药品免试测试：100150 必须放行 (stFlag='WO', showFlag='0')
        noskin_res = ctx.get("/faith/medical/inpatient/order/drug/skinInfo",
                             params={"registerId": reg_id, "drugId": "100150"})
        noskin_data = noskin_res.get("data") or {}
        noskin_st_flag = noskin_data.get("stFlag")
        noskin_show_flag = noskin_data.get("showFlag")

        if noskin_st_flag != "WO":
            bad.append(f"免试药品标志不符: 期待 stFlag='WO', 实际='{noskin_st_flag}'")
        if noskin_show_flag != "0":
            bad.append(f"免试药品多余提示: 期待 showFlag='0', 实际='{noskin_show_flag}'")

        # 6. 库表字典对账：验证药品基础表中皮试属性一致性
        cur.execute("SELECT skin_test_flag FROM com_bd_drug WHERE drug_id = :1", [allergy_drug_id])
        db_skin_flag = cur.fetchone()[0]
        cur.execute("SELECT skin_test_flag FROM com_bd_drug WHERE drug_id = '100150'")
        db_noskin_flag = cur.fetchone()[0]

        if db_skin_flag != "1":
            bad.append(f"COM_BD_DRUG 青霉素皮试标志异常: 期待='1', 库中='{db_skin_flag}'")
        if db_noskin_flag != "0":
            bad.append(f"COM_BD_DRUG 普通药皮试标志异常: 期待='0', 库中='{db_noskin_flag}'")

        conn.close()

        ev = {
            "就诊流水号": reg_id,
            "患者ID": pat_id,
            "负向拦截": f"HTTP code={neg_code}, msg={neg_msg}",
            "正向放行": f"HTTP code={pos_code}",
            "过敏药皮试校验": f"药品={allergy_drug_name}({allergy_drug_id}), stFlag={st_flag}, showFlag={show_flag}, remark={skin_remark}",
            "免试药校验": f"药品=100150, stFlag={noskin_st_flag}, showFlag={noskin_show_flag}",
            "库表字典": f"青霉素SKIN_TEST_FLAG={db_skin_flag}, 普通药SKIN_TEST_FLAG={db_noskin_flag}"
        }
        res.evidence = ev

        if bad:
            res.status = "失败"
            res.note = "临嘱专项校验断言不成立: " + "；".join(bad)
            return res

        res.status = "通过"
        res.note = (f"患者 {reg_id}（过敏史 {allergy_drug_name}）："
                    f"开立前虚假流水号拦截(400)与真实患者放行(200)成立；"
                    f"过敏/皮试药品强提醒(ND/showFlag=1)与免试药放行(WO/showFlag=0)与库字典100%闭环吻合")
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)
    return res


FLOWS = {
    "L4-048": flow_L4_048,
}
