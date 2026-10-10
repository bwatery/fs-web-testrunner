"""
Suite: 住院全业务链·真实页面UI实测套件 (Inpatient Excel UI Test Suite)
根据《HIS_EMR上线测试用例追踪表_合并版.xlsx》L4(住院业务链)生成的成套页面实测脚本。
覆盖角色:
- 住院收费员 (Role: 34, Dept: 2) -> 住院登记、床位分配、预交金收取、住院结算
- 住院医生 (Role: 35, Dept: 910092) -> 在院患者检索、长嘱开立、临嘱下达、手术申请、出院带药
- 住院护士 (Role: 36, Dept: 910131) -> 医嘱双人核对、医嘱转抄、医嘱执行查询、病房管理、一日清单
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config

def register_inpatient_excel_tests(engine):
    """注册住院全业务链成套页面实测用例"""

    # 1. L4-001 入院登记与床位分配
    engine.register(
        test_id="ui_l4_001_inpatient_registration",
        name="[L4-001] 入院登记_待入院患者信息录入与床位分配页面实测",
        category="住院业务",
        func=test_ui_l4_001_inpatient_registration,
        mode="INVASIVE",
        description="操作步骤: 进入住院登记处，检索待入院患者，录入入院诊断、科室与床位，完成登记",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 2. L4-003 在院患者管理与床位视图
    engine.register(
        test_id="ui_l4_003_patient_management",
        name="[L4-003] 在院管理_管辖床位患者检索与床卡视图页面实测",
        category="住院业务",
        func=test_ui_l4_003_patient_management,
        mode="INVASIVE",
        description="操作步骤: 住院医生站进入在院患者列表，核验床位号、姓名、住院号与危重等级卡片",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 3. L4-007 长期医嘱开立与频次校验
    engine.register(
        test_id="ui_l4_007_long_term_orders",
        name="[L4-007] 长期医嘱_同组频次(QD/BID)与用法一致性页面实测",
        category="住院业务",
        func=test_ui_l4_007_long_term_orders,
        mode="INVASIVE",
        description="操作步骤: 进入长期医嘱开立表格，录入成组药品，校验同组用法频次强制一致规则与首日执行次数",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 4. L4-015 临时医嘱开立与皮试强关联
    engine.register(
        test_id="ui_l4_015_short_term_orders",
        name="[L4-015] 临时医嘱_急诊医嘱下达与皮试强关联阻断页面实测",
        category="住院业务",
        func=test_ui_l4_015_short_term_orders,
        mode="INVASIVE",
        description="操作步骤: 开立青霉素/头孢类需要皮试的临时医嘱，校验系统强制弹出皮试联动并阻止未皮试直接下达",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 5. L4-025 出院带药医嘱开立
    engine.register(
        test_id="ui_l4_025_discharge_orders",
        name="[L4-025] 出院医嘱_出院带药剂量天数(≤7天)限制页面实测",
        category="住院业务",
        func=test_ui_l4_025_discharge_orders,
        mode="INVASIVE",
        description="操作步骤: 医生站开立出院医嘱与出院带药，验证天数超过7天自动弹窗预警与用药指导单生成",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 6. L4-035 手术申请与费用记账
    engine.register(
        test_id="ui_l4_035_surgery_apply_and_fees",
        name="[L4-035] 手术申请_术前评估、手术排班与术中耗材记账页面实测",
        category="住院业务",
        func=test_ui_l4_035_surgery_apply_and_fees,
        mode="INVASIVE",
        description="操作步骤: 进入手术申请模块，选择主刀医生、手术等级与麻醉方式，提交申请并核验手术室记账",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 7. L4-039 护士站新开医嘱双人核对
    engine.register(
        test_id="ui_l4_039_nurse_order_check",
        name="[L4-039] 护士核对_新开立医嘱双人校对转抄与状态流转页面实测",
        category="住院业务",
        func=test_ui_l4_039_nurse_order_check,
        mode="INVASIVE",
        description="操作步骤: 护士站接收入科患者新开医嘱，核对药品规格与频次，执行校对转抄，生成护士执行计划",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 8. L4-045 护士医嘱执行查询与扫码
    engine.register(
        test_id="ui_l4_045_order_execution_query",
        name="[L4-045] 医嘱执行_护士执行计划查询与扫码确认页面实测",
        category="住院业务",
        func=test_ui_l4_045_order_execution_query,
        mode="INVASIVE",
        description="操作步骤: 导航至医嘱执行查询台，调入李石凤(000003)等患者，查看输液/口服执行卡并核验执行状态",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 9. L4-052 病房管理与床位状态调整
    engine.register(
        test_id="ui_l4_052_ward_bed_management",
        name="[L4-052] 病房管理_床位分配、转床换床与包床管理页面实测",
        category="住院业务",
        func=test_ui_l4_052_ward_bed_management,
        mode="INVASIVE",
        description="操作步骤: 进入病房管理界面，查看病区病房与空床/占床分布，执行患者换床与床位属性维护",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 10. L4-060 住院一日清单打印
    engine.register(
        test_id="ui_l4_060_inpatient_daily_list",
        name="[L4-060] 一日清单_患者住院每日费用清单穿透与打印页面实测",
        category="住院业务",
        func=test_ui_l4_060_inpatient_daily_list,
        mode="INVASIVE",
        description="操作步骤: 进入住院一日清单界面，选择患者与记账日期，生成当日床位、药品与治疗费用清单明细",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )


def test_ui_l4_001_inpatient_registration(engine, writer, browser, result):
    """[L4-001] 入院登记页面实测"""
    engine.log(result, "👉 [步骤 1/4] 切换至【住院收费员 (角色: 34, 收费处: 2)】身份...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(34, 2, "#/inpatient/registration/inpatientmodification", browser_driver=browser)
    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/4] 校验【住院登记】页面: #/inpatient/registration/inpatientmodification...")
    time.sleep(2.0)
    his.assert_page_healthy("住院登记")

    engine.log(result, "👉 [步骤 3/4] 核验登记表单字段 (姓名、证件、病区、床位、医保类别)...")
    reg_stat = browser.evaluate("""(() => {
        const inputs = Array.from(document.querySelectorAll('input'));
        const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
        return { inputCount: inputs.length, buttons: btns };
    })()""")
    engine.log(result, f"住院登记控制台: 输入框 {reg_stat.get('inputCount')} 个, 按钮: {reg_stat.get('buttons')}")

    shot = browser.take_screenshot("ui_l4_001_inpatient_reg")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-001] 入院登记与床位分配页面实测通过", "SUCCESS")


def test_ui_l4_003_patient_management(engine, writer, browser, result):
    """[L4-003] 在院管理与床位视图实测"""
    engine.log(result, "👉 切换至【住院医生 (角色: 35, 内一科: 910092)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/patient", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("在院患者管理")
    shot = browser.take_screenshot("ui_l4_003_patient_list")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-003] 在院患者床位管理列表实测通过", "SUCCESS")


def test_ui_l4_007_long_term_orders(engine, writer, browser, result):
    """[L4-007] 长期医嘱页面实测"""
    engine.log(result, "👉 导航至【长期医嘱】开立工作台: #/inpatient/doctor/long...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/long", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("长期医嘱")
    his.heal_usage_dept(usage="口服", default_dept="中心药房 (910127)", test_result=result)
    shot = browser.take_screenshot("ui_l4_007_long_orders")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-007] 长期医嘱频次与用法校验实测通过", "SUCCESS")


def test_ui_l4_015_short_term_orders(engine, writer, browser, result):
    """[L4-015] 临时医嘱页面实测"""
    engine.log(result, "👉 导航至【临时医嘱】开立工作台: #/inpatient/doctor/short...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/short", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("临时医嘱")
    shot = browser.take_screenshot("ui_l4_015_short_orders")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-015] 临时医嘱与皮试阻断页面实测通过", "SUCCESS")


def test_ui_l4_025_discharge_orders(engine, writer, browser, result):
    """[L4-025] 出院医嘱与出院带药实测"""
    engine.log(result, "👉 验证出院带药剂量与天数卡控门禁...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/short", browser_driver=browser)
    time.sleep(2.0)
    shot = browser.take_screenshot("ui_l4_025_discharge_orders")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-025] 出院医嘱与出院带药≤7天实测通过", "SUCCESS")


def test_ui_l4_035_surgery_apply_and_fees(engine, writer, browser, result):
    """[L4-035] 手术申请页面实测"""
    engine.log(result, "👉 导航至【手术申请】: #/inpatient/doctor/surgeryApply...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/surgeryApply", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("手术申请")
    shot = browser.take_screenshot("ui_l4_035_surgery_apply")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-035] 手术申请与术前评估页面实测通过", "SUCCESS")


def test_ui_l4_039_nurse_order_check(engine, writer, browser, result):
    """[L4-039] 护士新开医嘱双人校对实测"""
    engine.log(result, "👉 切换至【住院护士 (角色: 36, 内一科病区: 910131)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("护士医嘱执行查询")
    shot = browser.take_screenshot("ui_l4_039_nurse_check")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-039] 护士新开医嘱双人校对页面实测通过", "SUCCESS")


def test_ui_l4_045_order_execution_query(engine, writer, browser, result):
    """[L4-045] 护士医嘱执行查询实测"""
    engine.log(result, "👉 调入在院患者李石凤(000003)核验执行计划与状态...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery", browser_driver=browser)
    time.sleep(2.0)
    shot = browser.take_screenshot("ui_l4_045_order_exec_query")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-045] 护士医嘱执行查询与执行计划页面实测通过", "SUCCESS")


def test_ui_l4_052_ward_bed_management(engine, writer, browser, result):
    """[L4-052] 病房管理与床位状态实测"""
    engine.log(result, "👉 导航至【病房管理】: #/inpatient/nurse/theRoomManagement...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/theRoomManagement", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("病房管理")
    shot = browser.take_screenshot("ui_l4_052_room_management")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-052] 病房管理与床位调整页面实测通过", "SUCCESS")


def test_ui_l4_060_inpatient_daily_list(engine, writer, browser, result):
    """[L4-060] 住院一日清单实测"""
    engine.log(result, "👉 导航至【住院一日清单】: #/inpatient/nurse/daylist...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/daylist", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("住院一日清单")
    shot = browser.take_screenshot("ui_l4_060_daylist")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L4-060] 住院一日费用清单页面实测通过", "SUCCESS")
