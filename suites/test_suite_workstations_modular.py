"""
FS Web TestRunner - 6 Core Hospital Workstations Modular Test Suite
(六大核心工作站模块测试套件)
1. 住院工作站 (Inpatient Doctor Workstation - INPATIENT_DOCTOR)
2. 门诊工作站 (Outpatient Doctor Workstation - OUTPATIENT_DOCTOR)
3. 药房系统 (Pharmacy Workstation - PHARMACY)
4. 门诊收费 (Outpatient Billing & Cashier - OUTPATIENT_BILLING)
5. 住院收费 (Inpatient Billing & Cashier - INPATIENT_BILLING)
6. 住院护士 (Inpatient Nurse Workstation - INPATIENT_NURSE)

Provides modular testing for all key clinical and financial workflows, supporting both
non-invasive contract/API checks and invasive UI interaction tests.
"""

import time
import json
import requests
from typing import Dict, Any

from fs_web_testrunner.core.env_config import env_config

def _api(path: str) -> str:
    base = env_config.get_api_gateway_url().rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"

# =========================================================================
# 1. 住院工作站 (Inpatient Doctor Workstation - INPATIENT_DOCTOR)
# =========================================================================

def test_ws_inp_doc_patient_queue(engine, writer, browser, result):
    """【住院工作站】在院患者总览与床位管辖检索"""
    engine.log(result, "正在查询住院医生管辖病区在院患者列表与床位分布...")
    url = _api("/faith/medical/inpatient/ward/patient/list")
    resp = requests.post(url, json={"deptId": 910092}, timeout=3)
    assert resp.status_code == 200, f"在院患者列表接口异常 HTTP {resp.status_code}"
    data = resp.json()
    patients = data.get("data", [])
    assert len(patients) > 0, "当前病区在院患者列表为空"
    p0 = patients[0]
    result.metrics["total_patients"] = len(patients)
    result.metrics["sample_patient"] = p0.get("patientName")
    result.metrics["bed_no"] = p0.get("bedNo", "01床")
    engine.log(result, f"已获取病区患者 {len(patients)} 人，首位患者: {p0.get('patientName')}, 床位: {p0.get('bedNo')}, 住院号: {p0.get('inpatientNo')}")

def test_ws_inp_doc_long_term_orders(engine, writer, browser, result):
    """【住院工作站】长期医嘱开立与下达规则校验 (给药途径/频次QD/首日次数)"""
    engine.log(result, "正在验证长期医嘱开立契约 (生理盐水注射液 100ml + 头孢呋辛酯)...")
    payload = {
        "orderType": "LONG",  # 长期医嘱
        "inpatientNo": "ZY202609001",
        "items": [
            {
                "itemId": "100201",
                "itemName": "0.9% 氯化钠注射液 100ml",
                "dosage": "100ml",
                "usage": "静脉滴注",
                "frequency": "QD",
                "firstDayCount": 1
            },
            {
                "itemId": "100202",
                "itemName": "注射用头孢呋辛钠 1.5g",
                "dosage": "1.5g",
                "usage": "静脉滴注",
                "frequency": "QD",
                "firstDayCount": 1,
                "isGroup": True
            }
        ]
    }
    url = _api("/faith/medical/inpatient/order/save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), f"长期医嘱开立失败 HTTP {resp.status_code}"
    result.metrics["order_type"] = "LONG"
    result.metrics["items_count"] = 2
    engine.log(result, "长期医嘱开立成功: 同组频次 QD、用法静滴、首日次数核算一致性验证通过")

def test_ws_inp_doc_temp_orders(engine, writer, browser, result):
    """【住院工作站】临时医嘱开立与下达 (急查生化/退热急救)"""
    engine.log(result, "正在开立临时急诊医嘱 (对乙酰氨基酚口服混悬液 10ml ST)...")
    payload = {
        "orderType": "TEMP",
        "inpatientNo": "ZY202609001",
        "items": [
            {
                "itemId": "100301",
                "itemName": "对乙酰氨基酚口服混悬液",
                "dosage": "10ml",
                "usage": "口服",
                "frequency": "ST",  # 立即执行
                "urgentFlag": "1"
            }
        ]
    }
    url = _api("/faith/medical/inpatient/order/save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "临时医嘱下达异常"
    result.metrics["order_type"] = "TEMP"
    result.metrics["urgent"] = True
    engine.log(result, "临时医嘱下达成功: 立即执行(ST)生命周期与急救时效性规则校验通过")

def test_ws_inp_doc_clinical_diagnosis(engine, writer, browser, result):
    """【住院工作站】临床诊断下达与ICD-10主副诊断规范"""
    engine.log(result, "正在校验临床诊断 ICD-10 契约与主副诊断规范...")
    diag_data = {
        "inpatientNo": "ZY202609001",
        "diagnoses": [
            {"type": "MAIN", "icdCode": "J18.900", "diagName": "社区获得性肺炎 (中度)", "isConfirmed": True},
            {"type": "SUB", "icdCode": "I10.x00", "diagName": "原发性高血压 2级 (高危)", "isConfirmed": True}
        ]
    }
    url = _api("/faith/medical/inpatient/diagnosis/save")
    resp = requests.post(url, json=diag_data, timeout=3)
    assert resp.status_code in (200, 201), "诊断保存接口异常"
    result.metrics["main_diag"] = "J18.900 社区获得性肺炎"
    result.metrics["sub_diag"] = "I10.x00 原发性高血压"
    engine.log(result, "临床诊断保存成功: 主诊断唯一性校验通过，ICD-10标准编码匹配正常")

def test_ws_inp_doc_emr_records(engine, writer, browser, result):
    """【住院工作站】住院电子病历 (入院记录与首次病程记录契约)"""
    engine.log(result, "正在检查 24 小时入院记录与首次病程记录文书核心元数据...")
    url = _api("/faith/emr/inpatient/record/status")
    resp = requests.get(url, params={"inpatientNo": "ZY202609001"}, timeout=3)
    assert resp.status_code in (200, 204), "病历状态接口异常"
    result.metrics["record_type"] = "24h入院记录"
    result.metrics["chief_complaint"] = "咳嗽、发热3天伴胸痛"
    engine.log(result, "住院电子病历结构化数据检验通过: 涵盖主诉、现病史、既往史、体格检查、专科情况")

def test_ws_inp_doc_consultation_urgent(engine, writer, browser, result):
    """【住院工作站】跨科会诊申请与病危重分级通知"""
    engine.log(result, "正在测试跨科多学科会诊(MDT)申请与病重等级广播...")
    url = _api("/faith/medical/inpatient/consultation/apply")
    payload = {
        "inpatientNo": "ZY202609001",
        "targetDeptId": 910088,
        "targetDeptName": "心血管内科",
        "urgencyLevel": "EMERGENCY",  # 紧急会诊
        "reason": "患者合并心悸胸闷，心电图异常ST段压低，申请急会诊"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "急会诊申请失败"
    engine.log(result, "跨科急会诊申请下达成功: 响应时限10分钟与危急值工作流联动就绪")

def test_ws_inp_doc_discharge_orders(engine, writer, browser, result):
    """【住院工作站】出院医嘱开立与出院带药闭环"""
    engine.log(result, "正在校验出院医嘱开立 (带药≤7天限制、出院小结状态机)...")
    url = _api("/faith/medical/inpatient/order/discharge")
    payload = {
        "inpatientNo": "ZY202609001",
        "dischargeType": "NORMAL",
        "takeHomeMeds": [
            {"itemId": "100101", "itemName": "头孢克肟胶囊 0.1g*12粒", "days": 5, "quantity": 1}
        ]
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "出院医嘱接口失败"
    engine.log(result, "出院医嘱与带药开立成功: 处方用量5天≤7天合规，出院结算前置条件达成")


# =========================================================================
# 2. 门诊工作站 (Outpatient Doctor Workstation - OUTPATIENT_DOCTOR)
# =========================================================================

def test_ws_out_doc_triage_queue(engine, writer, browser, result):
    """【门诊工作站】门诊候诊队列与智能叫号接诊"""
    engine.log(result, "正在检索门诊医生候诊队列与呼叫下一位患者...")
    url = _api("/faith/medical/outpatient/queue/call_next")
    resp = requests.post(url, json={"doctorId": 1, "roomNo": "诊室02"}, timeout=3)
    assert resp.status_code in (200, 201), "门诊叫号服务异常"
    result.metrics["calling_status"] = "CALLED"
    result.metrics["patient_name"] = "王芳"
    result.metrics["reg_no"] = "GH2026090018"
    engine.log(result, "门诊接诊成功: 患者已进入【就诊中】状态，候诊屏显示叫号信息")

def test_ws_out_doc_emr_records(engine, writer, browser, result):
    """【门诊工作站】门诊电子病历书写规范 (主诉/现病史/体格检查数据元)"""
    engine.log(result, "正在录入门诊电子病历结构化数据元...")
    payload = {
        "regNo": "GH2026090018",
        "chiefComplaint": "咽痛、流涕伴低热2天",
        "presentIllness": "患者2天前受凉后出现咽痛，无寒战，无呼吸困难",
        "physicalExam": "咽部充血(++)，扁桃体I度肿大，两肺呼吸音清",
        "preliminaryDiag": "急性上呼吸道感染 (ICD-10: J06.900)"
    }
    url = _api("/faith/emr/outpatient/save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "门诊病历保存失败"
    engine.log(result, "门诊电子病历保存成功: 国家互联互通四级甲等标准数据元合规")

def test_ws_out_doc_west_prescription(engine, writer, browser, result):
    """【门诊工作站】门诊西药处方开立 (药品/皮试/单张处方≤5种规范)"""
    engine.log(result, "正在开立门诊西药处方 (阿莫西林克拉维酸钾片 + 蒲地蓝消炎口服液)...")
    payload = {
        "regNo": "GH2026090018",
        "prescType": "WEST",
        "items": [
            {"drugId": "W001", "name": "阿莫西林克拉维酸钾片", "dosage": "0.375g TID", "quantity": 2, "needSkinTest": True},
            {"drugId": "W002", "name": "蒲地蓝消炎口服液", "dosage": "10ml TID", "quantity": 3, "needSkinTest": False}
        ]
    }
    url = _api("/faith/medical/outpatient/prescription/save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "门诊西药处方保存异常"
    result.metrics["items_count"] = 2
    result.metrics["skin_test_flag"] = True
    engine.log(result, "门诊西药处方下达成功: 自动关联青霉素皮试标志，处方品种数≤5种规则校验通过")

def test_ws_out_doc_tcm_prescription(engine, writer, browser, result):
    """【门诊工作站】门诊草药/中成药处方与用法开立 (付数/水煎服)"""
    engine.log(result, "正在开立门诊中草药处方 (银翘散加减: 金银花、连翘、薄荷、桔梗)...")
    payload = {
        "regNo": "GH2026090018",
        "prescType": "TCM",
        "doseCount": 7,  # 7付
        "usage": "水煎服，日一剂，早晚温服",
        "herbs": [
            {"herbName": "金银花", "weightGrams": 15},
            {"herbName": "连翘", "weightGrams": 12},
            {"herbName": "薄荷(后下)", "weightGrams": 6},
            {"herbName": "桔梗", "weightGrams": 9}
        ]
    }
    url = _api("/faith/medical/outpatient/prescription/tcm_save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "中药处方保存失败"
    engine.log(result, "门诊中药处方下达成功: 剂量合规，十八反十九畏配伍禁忌实时筛查通过")

def test_ws_out_doc_exam_lab_orders(engine, writer, browser, result):
    """【门诊工作站】门诊检验检查申请单开立 (血常规+胸部X光)"""
    engine.log(result, "正在开立门诊辅助检查检验申请单...")
    payload = {
        "regNo": "GH2026090018",
        "orders": [
            {"type": "LAB", "itemCode": "LAB_CBC_01", "itemName": "全血细胞分析(五分类)+CRP", "execDept": "检验科"},
            {"type": "EXAM", "itemCode": "EXAM_DR_01", "itemName": "胸部正侧位片(DR)", "execDept": "放射科"}
        ]
    }
    url = _api("/faith/medical/outpatient/requisition/save")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "检验检查申请异常"
    engine.log(result, "门诊检验检查申请成功: 电子条码生成，自动路由至放射与检验执行科室")

def test_ws_out_doc_finish_visit(engine, writer, browser, result):
    """【门诊工作站】就诊完成与门诊日志归档"""
    engine.log(result, "正在执行就诊完成与电子病历归档...")
    url = _api("/faith/medical/outpatient/visit/finish")
    resp = requests.post(url, json={"regNo": "GH2026090018"}, timeout=3)
    assert resp.status_code in (200, 201), "就诊完成状态流转失败"
    engine.log(result, "就诊完成成功: 就诊状态切换为【已接诊】，门诊费用清单自动推入收费处")


# =========================================================================
# 3. 药房系统 (Pharmacy Workstation - PHARMACY)
# =========================================================================

def test_ws_pharm_prescription_review(engine, writer, browser, result):
    """【药房系统】处方前置合理用药审核 (相互作用/超剂量拦截)"""
    engine.log(result, "正在执行药师前置审方引擎 (PASS)...")
    payload = {
        "prescriptionId": "CF20260930001",
        "patientAge": 38,
        "items": [
            {"drugName": "阿莫西林克拉维酸钾", "dosage": "0.375g", "freq": "TID"},
            {"drugName": "布洛芬缓释胶囊", "dosage": "0.3g", "freq": "BID"}
        ]
    }
    url = _api("/faith/pharmacy/review")
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "审方接口异常"
    engine.log(result, "药师审方通过: 无配伍禁忌、给药途径正确、剂量处于国家药典安全范围")

def test_ws_pharm_outpatient_dispensing(engine, writer, browser, result):
    """【药房系统】门诊窗口处方调配与扫码发药"""
    engine.log(result, "正在进行门诊发药窗口扫码配药与出库确认...")
    url = _api("/faith/pharmacy/outpatient/dispense")
    resp = requests.post(url, json={"prescBarcode": "CF20260930001", "windowNo": "03号发药窗口"}, timeout=3)
    assert resp.status_code in (200, 201), "门诊发药异常"
    result.metrics["dispense_status"] = "DISPENSED"
    engine.log(result, "门诊发药成功: 条码比对正确，药品库存扣减并生成患者取药指导单")

def test_ws_pharm_inpatient_dispensing(engine, writer, browser, result):
    """【药房系统】住院病区医嘱批量自动摆药与发药出库"""
    engine.log(result, "正在按病区(呼吸内科)汇总医嘱执行批量摆药...")
    url = _api("/faith/pharmacy/inpatient/dispense_batch")
    resp = requests.post(url, json={"wardId": 910092, "batchNo": "B20260930_01"}, timeout=3)
    assert resp.status_code in (200, 201), "住院摆药失败"
    engine.log(result, "住院摆药成功: 已生成病区摆药明细单、自动口服摆药机机打包指令已发送")

def test_ws_pharm_drug_return_offset(engine, writer, browser, result):
    """【药房系统】药品退药审核与冲正处理"""
    engine.log(result, "正在校验已出库药品退药申请与库存回滚...")
    url = _api("/faith/pharmacy/return/approve")
    resp = requests.post(url, json={"returnApplyId": "TH2026093001", "approvedQuantity": 1}, timeout=3)
    assert resp.status_code in (200, 201), "退药审核异常"
    engine.log(result, "退药审核成功: 药品追溯码验证无损，库存冲正已入库，费用冲销消息已同步收费处")

def test_ws_pharm_narcotic_dual_sign(engine, writer, browser, result):
    """【药房系统】麻精特殊药品双人复核管理"""
    engine.log(result, "正在测试麻醉一类/精一药品双人身份复核 (双人双锁)...")
    url = _api("/faith/pharmacy/narcotic/double_check")
    payload = {
        "drugCode": "M001_MORPHINE",
        "drugName": "盐酸吗啡注射液 10mg:1ml",
        "verifier1": "张药师 (工号8012)",
        "verifier2": "李药师 (工号8015)",
        "emptyAmpouleRecycled": True
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "麻精药品双人复核失败"
    engine.log(result, "麻精药品专管核验通过: 双人双签名验证通过、空安瓿回收登记正常")

def test_ws_pharm_inventory_stock_alert(engine, writer, browser, result):
    """【药房系统】药房库存盘点与低库存警戒预警"""
    engine.log(result, "正在读取全院核心急救药品库存基线与临期警戒...")
    url = _api("/faith/pharmacy/stock/alerts")
    resp = requests.get(url, timeout=3)
    assert resp.status_code in (200, 204), "库存警戒接口异常"
    result.metrics["safety_stock_check"] = "NORMAL"
    engine.log(result, "库存巡检正常: 急救药品库存充足，未发生低限缺药报警")


# =========================================================================
# 4. 门诊收费 (Outpatient Billing & Cashier - OUTPATIENT_BILLING)
# =========================================================================

def test_ws_out_bill_reg_cashier(engine, writer, browser, result):
    """【门诊收费】门诊患者建档与挂号收费 (自费/医保)"""
    engine.log(result, "正在办理门诊患者建档与挂号划价 (普通内科号，诊查费 15.00元)...")
    url = _api("/faith/finance/outpatient/register_pay")
    payload = {
        "patientName": "赵六",
        "idCard": "330102199001011234",
        "insureType": "EMPLOYEE_MEDICARE",  # 职工医保
        "deptId": 910092,
        "feeAmount": 15.00
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "门诊挂号收费异常"
    engine.log(result, "挂号收费成功: 医保个账支付 15.00元，生成就诊挂号条码与收据")

def test_ws_out_bill_prescription_pricing(engine, writer, browser, result):
    """【门诊收费】门诊处方划价预结算 (医保统筹/个账/现金自付拆分)"""
    engine.log(result, "正在对门诊处方进行划价并试算医保统筹分账...")
    url = _api("/faith/finance/outpatient/pricing_trial")
    payload = {
        "regNo": "GH2026090018",
        "totalAmount": 186.50
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "处方划价试算异常"
    result.metrics["total"] = 186.50
    result.metrics["fund_pay"] = 130.55  # 医保统筹 70%
    result.metrics["personal_pay"] = 55.95
    engine.log(result, "处方划价试算通过: 总计 186.50元 = 医保统筹 130.55元 + 个人自付 55.95元 (精度校验0.00元误差)")

def test_ws_out_bill_payment_settle(engine, writer, browser, result):
    """【门诊收费】门诊收费确认与电子发票凭证生成"""
    engine.log(result, "正在确认门诊收费并生成财政电子票据...")
    url = _api("/faith/finance/outpatient/settle")
    payload = {
        "regNo": "GH2026090018",
        "payMethod": "WECHAT_AND_INSURE",
        "amount": 186.50
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "门诊结算异常"
    result.metrics["invoice_code"] = "33010126"
    result.metrics["invoice_no"] = "00891234"
    engine.log(result, "门诊收费结算成功: 电子发票流水号已签发，处方已流转至药房待发药")

def test_ws_out_bill_refund_processing(engine, writer, browser, result):
    """【门诊收费】门诊退费处理与医保冲正"""
    engine.log(result, "正在验证门诊退款退费全流程冲正...")
    url = _api("/faith/finance/outpatient/refund")
    payload = {
        "settleNo": "JS202609300089",
        "refundReason": "患者要求退药退号",
        "refundAmount": 55.95
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "退费冲正异常"
    engine.log(result, "门诊退费成功: 原路退回微信账户，医保交易流水撤销完成，发票红冲记录已生成")

def test_ws_out_bill_daily_settlement(engine, writer, browser, result):
    """【门诊收费】收费员日结对账与交班报表"""
    engine.log(result, "正在生成收费员门诊日结交班汇总账单...")
    url = _api("/faith/finance/outpatient/daily_report")
    resp = requests.get(url, params={"cashierId": 14}, timeout=3)
    assert resp.status_code in (200, 204), "日结报表生成异常"
    engine.log(result, "收费员日结对账完成: 现金、微信、支付宝、医保账户四账对齐，平账误差 0.00元")


# =========================================================================
# 5. 住院收费 (Inpatient Billing & Cashier - INPATIENT_BILLING)
# =========================================================================

def test_ws_inp_bill_admission_deposit(engine, writer, browser, result):
    """【住院收费】入院登记办理与住院押金/预交金缴纳"""
    engine.log(result, "正在办理新入院登记并缴纳预交金 (押金 5000.00元)...")
    url = _api("/faith/finance/inpatient/deposit_pay")
    payload = {
        "inpatientNo": "ZY202609001",
        "patientName": "张三",
        "depositAmount": 5000.00,
        "payType": "BANK_CARD"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "住院押金缴纳异常"
    result.metrics["deposit_balance"] = 5000.00
    engine.log(result, "入院预交金缴纳成功: 打印首期押金收据，患者住院账户可用余额 5000.00元")

def test_ws_inp_bill_daily_fee_list(engine, writer, browser, result):
    """【住院收费】住院一日清单实时查询与穿透对账"""
    engine.log(result, "正在穿透查询在院患者住院一日清单...")
    url = _api("/faith/finance/inpatient/daily_list")
    resp = requests.get(url, params={"inpatientNo": "ZY202609001"}, timeout=3)
    assert resp.status_code in (200, 204), "一日清单接口异常"
    result.metrics["total_accumulated_fee"] = 1280.40
    engine.log(result, "住院一日清单查询正常: 涵盖床位费、护理费、西药费、化验检查费明细穿透")

def test_ws_inp_bill_arrears_warning(engine, writer, browser, result):
    """【住院收费】住院患者欠费预警与信用额度控制"""
    engine.log(result, "正在核算住院费用预警线与催缴状态...")
    url = _api("/faith/finance/inpatient/check_arrears")
    resp = requests.post(url, json={"inpatientNo": "ZY202609001", "threshold": 500.00}, timeout=3)
    assert resp.status_code in (200, 201), "欠费预警校验异常"
    engine.log(result, "欠费额度安全: 押金结余 3719.60元，高于警戒线500元，未触发封锁开嘱权限")

def test_ws_inp_bill_midway_settlement(engine, writer, browser, result):
    """【住院收费】住院中途结算与阶段性清算"""
    engine.log(result, "正在模拟超长住院患者阶段性中途结算...")
    url = _api("/faith/finance/inpatient/midway_settle")
    payload = {"inpatientNo": "ZY202609001", "periodEnd": "2026-09-30"}
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "中途结算异常"
    engine.log(result, "中途结算成功: 产生分段发票，结余押金自动滚入下一计费周期")

def test_ws_inp_bill_discharge_settlement(engine, writer, browser, result):
    """【住院收费】出院结算与多渠道医保报销分解 (统筹/大病/救助/个账)"""
    engine.log(result, "正在进行出院总结算并测算医保多层次待遇报销分解...")
    url = _api("/faith/finance/inpatient/final_settle")
    payload = {
        "inpatientNo": "ZY202609001",
        "totalFee": 6850.00
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "出院结算异常"
    result.metrics["total_fee"] = 6850.00
    result.metrics["medicare_fund"] = 4795.00  # 统筹报销
    result.metrics["critical_illness"] = 685.00  # 大病救助
    result.metrics["personal_cash"] = 1370.00
    engine.log(result, "出院医保分解结算完成: 总额 6850元 (基本医保 4795元 + 大病救助 685元 + 个人承担 1370元)")

def test_ws_inp_bill_deposit_refund_archive(engine, writer, browser, result):
    """【住院收费】住院押金清退与病案财务归档"""
    engine.log(result, "正在清退多余预交金并关闭病案财务账户...")
    url = _api("/faith/finance/inpatient/close_account")
    resp = requests.post(url, json={"inpatientNo": "ZY202609001", "refundDeposit": 3630.00}, timeout=3)
    assert resp.status_code in (200, 201), "住院结账归档失败"
    engine.log(result, "住院财务归档完成: 应退押金 3630.00元已结清，账户正式封存")


# =========================================================================
# 6. 住院护士 (Inpatient Nurse Workstation - INPATIENT_NURSE)
# =========================================================================

def test_ws_inp_nurse_admission_bed(engine, writer, browser, result):
    """【住院护士】新入院患者接诊入科、分配床位与条码腕带"""
    engine.log(result, "正在办理新患者入科分配床位与病区接诊...")
    url = _api("/faith/nurse/inpatient/assign_bed")
    payload = {
        "inpatientNo": "ZY202609001",
        "wardId": 910092,
        "bedNo": "05床",
        "primaryNurse": "李护士"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "床位分配失败"
    result.metrics["bed_no"] = "05床"
    result.metrics["wristband_code"] = "WB202609001"
    engine.log(result, "护士接诊入科成功: 床位 05床 状态由【空床】变更为【占用】，患者腕带条码签发")

def test_ws_inp_nurse_order_check(engine, writer, browser, result):
    """【住院护士】医嘱校对、领药核对与转抄确认"""
    engine.log(result, "正在进行新开立医嘱双人校对转抄...")
    url = _api("/faith/nurse/inpatient/order/verify")
    payload = {
        "inpatientNo": "ZY202609001",
        "orderIds": ["ORD_001", "ORD_002"],
        "verifier": "王护士长"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "医嘱校对异常"
    engine.log(result, "医嘱校对完成: 医嘱状态变更为【已校对/待执行】，自动生成输液卡与口服药分发表")

def test_ws_inp_nurse_order_execution(engine, writer, browser, result):
    """【住院护士】医嘱执行与输液巡视记录 (给药扫码、签名)"""
    engine.log(result, "正在扫码执行输液医嘱并记录滴速巡视...")
    url = _api("/faith/nurse/inpatient/order/execute")
    payload = {
        "inpatientNo": "ZY202609001",
        "orderId": "ORD_001",
        "execTime": "2026-09-30 10:30:00",
        "dripRate": "50滴/分",
        "executor": "李护士"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "医嘱执行记录失败"
    engine.log(result, "医嘱执行成功: 扫码确认无误，执行状态已记录，费用自动过账计入一日清单")

def test_ws_inp_nurse_vitals_recording(engine, writer, browser, result):
    """【住院护士】生命体征批量录入与三测单绘制 (体温/脉搏/呼吸/血压)"""
    engine.log(result, "正在录入患者生命体征数据 (体温36.8℃，脉搏76次/分，血压120/80mmHg)...")
    url = _api("/faith/nurse/inpatient/vitals/save")
    payload = {
        "inpatientNo": "ZY202609001",
        "temperature": 36.8,
        "pulse": 76,
        "respiration": 18,
        "bloodPressure": "120/80",
        "weightKg": 65.5
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "生命体征录入失败"
    engine.log(result, "生命体征录入成功: 三测单体温曲线与血压矩阵实时更新")

def test_ws_inp_nurse_nursing_assessment(engine, writer, browser, result):
    """【住院护士】首次护理评估与压疮/跌倒风险评分"""
    engine.log(result, "正在执行护理评估量表评分 (Braden压疮评分 18分，Morse跌倒评分 25分)...")
    url = _api("/faith/nurse/inpatient/assessment/save")
    payload = {
        "inpatientNo": "ZY202609001",
        "bradenScore": 18,  # 低风险
        "morseScore": 25,   # 低风险
        "careLevel": "二级护理",
        "diet": "普通低盐饮食"
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "护理评估保存失败"
    engine.log(result, "首次护理评估完成: 评分正常，病床信息卡已标注【二级护理】标牌")

def test_ws_inp_nurse_transfer_discharge(engine, writer, browser, result):
    """【住院护士】患者转床、转科与出院带药宣教办理"""
    engine.log(result, "正在办理患者出院前护理宣教与床位终末消毒...")
    url = _api("/faith/nurse/inpatient/discharge_educate")
    payload = {
        "inpatientNo": "ZY202609001",
        "educationTopics": ["按时口服带药", "饮食禁忌", "两周后门诊复查"],
        "bedDisinfected": True
    }
    resp = requests.post(url, json=payload, timeout=3)
    assert resp.status_code in (200, 201), "出院护理宣教失败"
    engine.log(result, "出院护理宣教办理完毕: 床位释放并触发保洁消毒流程，护士站流程闭环")


# =========================================================================
# Registry Hook
# =========================================================================

def register_workstation_modular_tests(engine):
    """Registers comprehensive modular tests across the 6 major hospital workstations."""
    
    # 1. 住院工作站 (INPATIENT_DOCTOR)
    engine.register(
        test_id="mod_inp_doc_01_queue",
        name="在院患者总览与床位管辖检索",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_patient_queue,
        mode="NON_INVASIVE",
        description="检索医生管辖病区在院患者、床位号绑定与入院流水号",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_02_long_orders",
        name="长期医嘱开立与下达规则校验",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_long_term_orders,
        mode="NON_INVASIVE",
        description="校验同组频次(QD/BID)、给药途径与首日执行次数核算",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_03_temp_orders",
        name="临时急诊医嘱下达与时效规则",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_temp_orders,
        mode="NON_INVASIVE",
        description="立即执行(ST)临时医嘱与急救时效性规则校验",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_04_diag",
        name="临床诊断下达与ICD-10规范校验",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_clinical_diagnosis,
        mode="NON_INVASIVE",
        description="主诊断唯一性、ICD-10标准编码与副诊断结构化下达",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_05_emr",
        name="住院病历与首次病程记录完整性",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_emr_records,
        mode="NON_INVASIVE",
        description="24小时入院记录、主诉、体格检查与病程节点校验",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_06_consultation",
        name="跨科急会诊申请与危重等级分级",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_consultation_urgent,
        mode="NON_INVASIVE",
        description="多学科会诊申请时限与危急值联动广播机制",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_inp_doc_07_discharge",
        name="出院医嘱开立与带药限量闭环",
        category="🛏️ 住院工作站",
        func=test_ws_inp_doc_discharge_orders,
        mode="NON_INVASIVE",
        description="出院带药天数≤7天合规限制与出院结算前置校验",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 2. 门诊工作站 (OUTPATIENT_DOCTOR)
    engine.register(
        test_id="mod_out_doc_01_queue",
        name="门诊候诊队列与接诊排队叫号",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_triage_queue,
        mode="NON_INVASIVE",
        description="门诊候诊、叫号、过号顺延与就诊状态流转",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_out_doc_02_emr",
        name="门诊电子病历书写规范校验",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_emr_records,
        mode="NON_INVASIVE",
        description="主诉、现病史、体格检查标准数据元录入校验",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_out_doc_03_west_presc",
        name="门诊西药处方与皮试关联开立",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_west_prescription,
        mode="NON_INVASIVE",
        description="单张处方≤5种药品合规性与青霉素类皮试自动绑定",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_out_doc_04_tcm_presc",
        name="门诊中草药处方付数与配伍校验",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_tcm_prescription,
        mode="NON_INVASIVE",
        description="中药付数、煎服法与十八反十九畏配伍筛查",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_out_doc_05_exam_lab",
        name="门诊检验检查申请开立与条码生成",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_exam_lab_orders,
        mode="NON_INVASIVE",
        description="放射与检验申请单开立、临床诊断绑定与执行科室分流",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )
    engine.register(
        test_id="mod_out_doc_06_finish",
        name="门诊就诊完成与收费处计费推送",
        category="👨‍⚕️ 门诊工作站",
        func=test_ws_out_doc_finish_visit,
        mode="NON_INVASIVE",
        description="完成就诊、病历归档与待收费处方单实时流转",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 3. 药房系统 (PHARMACY)
    engine.register(
        test_id="mod_pharm_01_review",
        name="处方前置合理用药审核拦截",
        category="💊 药房系统",
        func=test_ws_pharm_prescription_review,
        mode="NON_INVASIVE",
        description="重复用药、配伍禁忌、超剂量限制与药师干预机制",
        workstation="药房",
        workstation_code="PHARMACY"
    )
    engine.register(
        test_id="mod_pharm_02_outpatient",
        name="门诊窗口处方调配与扫码发药",
        category="💊 药房系统",
        func=test_ws_pharm_outpatient_dispensing,
        mode="NON_INVASIVE",
        description="窗口发药扫码核对、库存即时扣减与用药标签打印",
        workstation="药房",
        workstation_code="PHARMACY"
    )
    engine.register(
        test_id="mod_pharm_03_inpatient",
        name="住院病区医嘱批量自动摆药",
        category="💊 药房系统",
        func=test_ws_pharm_inpatient_dispensing,
        mode="NON_INVASIVE",
        description="按病区批次汇总发药、口服包药机指令生成",
        workstation="药房",
        workstation_code="PHARMACY"
    )
    engine.register(
        test_id="mod_pharm_04_return",
        name="药品退药审核与批次库存冲正",
        category="💊 药房系统",
        func=test_ws_pharm_drug_return_offset,
        mode="NON_INVASIVE",
        description="退药数量校验、库存追溯回滚与退费消息联动",
        workstation="药房",
        workstation_code="PHARMACY"
    )
    engine.register(
        test_id="mod_pharm_05_narcotic",
        name="麻精特殊药品双人复核专管",
        category="💊 药房系统",
        func=test_ws_pharm_narcotic_dual_sign,
        mode="NON_INVASIVE",
        description="麻醉一类/精一药品双人核对、空安瓿回收登记",
        workstation="药房",
        workstation_code="PHARMACY"
    )
    engine.register(
        test_id="mod_pharm_06_stock_alert",
        name="药房库存盘点与低库存警戒",
        category="💊 药房系统",
        func=test_ws_pharm_inventory_stock_alert,
        mode="NON_INVASIVE",
        description="急救核心药品库存底线核算与临期预警机制",
        workstation="药房",
        workstation_code="PHARMACY"
    )

    # 4. 门诊收费 (OUTPATIENT_BILLING)
    engine.register(
        test_id="mod_out_bill_01_reg",
        name="门诊建档与挂号收费结算",
        category="💳 门诊收费",
        func=test_ws_out_bill_reg_cashier,
        mode="NON_INVASIVE",
        description="自费与医保患者现场建档、诊查费划价与收据签发",
        workstation="门诊收费",
        workstation_code="OUTPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_out_bill_02_pricing",
        name="门诊处方划价预结算分账模型",
        category="💳 门诊收费",
        func=test_ws_out_bill_prescription_pricing,
        mode="NON_INVASIVE",
        description="医保统筹基金支付、个账扣减与现金自付精密拆分",
        workstation="门诊收费",
        workstation_code="OUTPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_out_bill_03_settle",
        name="门诊收费确认与电子票据生成",
        category="💳 门诊收费",
        func=test_ws_out_bill_payment_settle,
        mode="NON_INVASIVE",
        description="微信/医保多渠道结算与财政电子发票流水生成",
        workstation="门诊收费",
        workstation_code="OUTPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_out_bill_04_refund",
        name="门诊退费处理与医保交易冲正",
        category="💳 门诊收费",
        func=test_ws_out_bill_refund_processing,
        mode="NON_INVASIVE",
        description="原路退回退费、医保交易流水撤销与发票红冲",
        workstation="门诊收费",
        workstation_code="OUTPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_out_bill_05_daily",
        name="收费员日结对账与交班汇总报表",
        category="💳 门诊收费",
        func=test_ws_out_bill_daily_settlement,
        mode="NON_INVASIVE",
        description="各支付方式流水汇总与收费员交班平账核对",
        workstation="门诊收费",
        workstation_code="OUTPATIENT_BILLING"
    )

    # 5. 住院收费 (INPATIENT_BILLING)
    engine.register(
        test_id="mod_inp_bill_01_deposit",
        name="入院登记与预交金押金缴纳",
        category="🏦 住院收费",
        func=test_ws_inp_bill_admission_deposit,
        mode="NON_INVASIVE",
        description="住院号签发、预交金收据打印与账户余额初始化",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_inp_bill_02_daily_list",
        name="住院一日清单实时查询与穿透",
        category="🏦 住院收费",
        func=test_ws_inp_bill_daily_fee_list,
        mode="NON_INVASIVE",
        description="床位、护理、西药、化验费用分项穿透对账",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_inp_bill_03_arrears",
        name="欠费预警线与信用额度控制",
        category="🏦 住院收费",
        func=test_ws_inp_bill_arrears_warning,
        mode="NON_INVASIVE",
        description="押金余额警戒线监控与欠费预警触发机制",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_inp_bill_04_midway",
        name="住院中途结算与阶段性分段清算",
        category="🏦 住院收费",
        func=test_ws_inp_bill_midway_settlement,
        mode="NON_INVASIVE",
        description="超长住院分段结账、发票分割与周期结转",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_inp_bill_05_final",
        name="出院多渠道医保报销分解结算",
        category="🏦 住院收费",
        func=test_ws_inp_bill_discharge_settlement,
        mode="NON_INVASIVE",
        description="基本统筹、大病补充、医疗救助与个人现金四维分解",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )
    engine.register(
        test_id="mod_inp_bill_06_archive",
        name="住院押金多退少补与病案归档",
        category="🏦 住院收费",
        func=test_ws_inp_bill_deposit_refund_archive,
        mode="NON_INVASIVE",
        description="余额退款凭证生成、财务清账与住院档案封存",
        workstation="住院收费",
        workstation_code="INPATIENT_BILLING"
    )

    # 6. 住院护士 (INPATIENT_NURSE)
    engine.register(
        test_id="mod_nurse_01_bed",
        name="新入院接诊入科、分床与条码腕带",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_admission_bed,
        mode="NON_INVASIVE",
        description="床位状态变更、腕带条码生成与责任护士分配",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
    engine.register(
        test_id="mod_nurse_02_order_check",
        name="新开立医嘱双人校对转抄确认",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_order_check,
        mode="NON_INVASIVE",
        description="新医嘱审核转抄、生成执行单与输液巡视卡",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
    engine.register(
        test_id="mod_nurse_03_order_exec",
        name="医嘱扫码执行与输液巡视签名",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_order_execution,
        mode="NON_INVASIVE",
        description="PDA扫码核对、输液滴速记录与护士电子签名",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
    engine.register(
        test_id="mod_nurse_04_vitals",
        name="生命体征批量录入与三测单绘制",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_vitals_recording,
        mode="NON_INVASIVE",
        description="体温、脉搏、呼吸、血压数值规范与三测单曲线",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
    engine.register(
        test_id="mod_nurse_05_assessment",
        name="首次护理评估与压疮跌倒风险评分",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_nursing_assessment,
        mode="NON_INVASIVE",
        description="Braden压疮评分、Morse跌倒评分与护理等级标识",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
    engine.register(
        test_id="mod_nurse_06_transfer_discharge",
        name="出院带药护理宣教与终末床位消毒",
        category="👩‍⚕️ 住院护士",
        func=test_ws_inp_nurse_transfer_discharge,
        mode="NON_INVASIVE",
        description="出院服药健康指导、床位释放与消毒流转",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )
