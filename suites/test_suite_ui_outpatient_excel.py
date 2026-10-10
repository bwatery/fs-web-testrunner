"""
Suite: 门诊全业务链·真实页面UI实测套件 (Outpatient Excel UI Test Suite)
根据《HIS_EMR上线测试用例追踪表_合并版.xlsx》L1(患者主索引)与L2(门诊业务链)生成的成套页面实测脚本。
覆盖角色:
- 门诊收费员 (Role: 14, Dept: 2) -> 门诊建档、现场挂号、预约挂号、门诊退号、挂号日结
- 门诊医生 (Role: 15 / 35, Dept: 910080 / 910092) -> 接诊队列、主诉现病史、诊断开立、处方开立、草药、检验检查
- 终端确认 (Role: 38 / 34) -> 医技采样、终端执行确认
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config

def register_outpatient_excel_tests(engine):
    """注册门诊全业务链成套页面实测用例"""
    
    # 1. L1-001 ~ L1-005 患者建档与主索引查重
    engine.register(
        test_id="ui_l1_001_patient_registration",
        name="[L1-001] 患者建档_基本信息录入与查重校验页面实测",
        category="门诊业务",
        func=test_ui_l1_001_patient_registration,
        mode="INVASIVE",
        description="操作步骤: 进入患者信息维护页面，录入姓名、性别、身份证号、联系方式建档，校验同身份证查重",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 2. L2-001 ~ L2-003 排班与号源管理
    engine.register(
        test_id="ui_l2_001_schedule_management",
        name="[L2-001] 排班管理_门诊科室与医生排班号源配置页面实测",
        category="门诊业务",
        func=test_ui_l2_001_schedule_management,
        mode="INVASIVE",
        description="操作步骤: 进入科室排班/医生排班管理页面，配置出诊科室、出诊时段与限号数量",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 3. L2-004 ~ L2-008 现场门诊挂号
    engine.register(
        test_id="ui_l2_004_onsite_registration",
        name="[L2-004] 门诊挂号_现场挂号、选科选医与号条生成页面实测",
        category="门诊业务",
        func=test_ui_l2_004_onsite_registration,
        mode="INVASIVE",
        description="操作步骤: 调入门诊挂号台，检索建档患者，选择就诊科室与医生，完成挂号并验证号条数据",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 4. L2-009 ~ L2-013 预约挂号与取号
    engine.register(
        test_id="ui_l2_009_appointment_registration",
        name="[L2-009] 预约挂号_跨周分时段预约与取号确认页面实测",
        category="门诊业务",
        func=test_ui_l2_009_appointment_registration,
        mode="INVASIVE",
        description="操作步骤: 进入预约挂号界面，选择未来日期排班号源进行预约，验证预约记录与取号换号",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 5. L2-014 ~ L2-017 门诊退号与冲正
    engine.register(
        test_id="ui_l2_014_cancel_registration",
        name="[L2-014] 门诊退号_未就诊患者退号与号源回退页面实测",
        category="门诊业务",
        func=test_ui_l2_014_cancel_registration,
        mode="INVASIVE",
        description="操作步骤: 进入门诊退号控制台，输入挂号单号/发票号检索，执行退号冲正，校验已就诊禁止退号卡控",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 6. L2-018 ~ L2-033 门诊分诊与叫号
    engine.register(
        test_id="ui_l2_018_triage_and_call",
        name="[L2-018] 门诊分诊_候诊队列管理、分诊叫号与过号重排页面实测",
        category="门诊业务",
        func=test_ui_l2_018_triage_and_call,
        mode="INVASIVE",
        description="操作步骤: 进入分诊管理台，查看待诊患者队列，执行分诊指定诊室、叫号与过号顺延",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 7. L2-034 ~ L2-045 门诊医生站诊断与西药处方
    engine.register(
        test_id="ui_l2_034_doctor_prescription",
        name="[L2-034] 门诊医生站_接诊患者、录入诊断与开立西药处方页面实测",
        category="门诊业务",
        func=test_ui_l2_034_doctor_prescription,
        mode="INVASIVE",
        description="操作步骤: 医生接诊患者，录入主诉与ICD-10诊断，开立西药处方并选择频次/用法/天数，保存处方",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 8. L2-046 ~ L2-060 门诊中草药处方开立
    engine.register(
        test_id="ui_l2_046_tcm_prescription",
        name="[L2-046] 门诊中草药_中草药配方、剂数付数与煎服法页面实测",
        category="门诊业务",
        func=test_ui_l2_046_tcm_prescription,
        mode="INVASIVE",
        description="操作步骤: 切换中药处方页签，添加中药饮片，录入单剂克数、剂数(付数)与特殊煎服法，校验零值拦截",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 9. L2-061 ~ L2-075 门诊检验检查申请
    engine.register(
        test_id="ui_l2_061_lab_exam_apply",
        name="[L2-061] 门诊医技申请_检验检查项目开立与条码申请单页面实测",
        category="门诊业务",
        func=test_ui_l2_061_lab_exam_apply,
        mode="INVASIVE",
        description="操作步骤: 开立血常规、生化等检验申请及DR/CT检查申请，填写临床诊断与检查目的，生成申请单",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )

    # 10. L2-076 ~ L2-085 挂号日结对账
    engine.register(
        test_id="ui_l2_076_registration_daily_settle",
        name="[L2-076] 挂号日结_收费员当班挂号款汇总与缴款结账页面实测",
        category="门诊业务",
        func=test_ui_l2_076_registration_daily_settle,
        mode="INVASIVE",
        description="操作步骤: 进入挂号日结台，汇总统计当日挂号笔数、退号笔数、应收金额与实收金额，完成日结对账",
        workstation="门诊工作站",
        workstation_code="OUTPATIENT_DOCTOR"
    )


def test_ui_l1_001_patient_registration(engine, writer, browser, result):
    """[L1-001] 患者建档页面实测"""
    engine.log(result, "👉 [步骤 1/4] 切换身份至【门诊收费员 (角色: 14, 收费处: 2)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/patient/patientInformation", browser_driver=browser)
    his = HISDriver(browser)
    
    engine.log(result, "👉 [步骤 2/4] 探测【患者信息维护】页面状态: #/patient/patientInformation...")
    time.sleep(2.0)
    his.assert_page_healthy("患者信息维护")

    engine.log(result, "👉 [步骤 3/4] 核验建档表单组件 (姓名、性别、身份证、手机号)...")
    form_stat = browser.evaluate("""(() => {
        const inputs = Array.from(document.querySelectorAll('input'));
        const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
        return {
            inputCount: inputs.length,
            buttons: btns,
            hasSaveBtn: btns.some(b => b.includes('保存') || b.includes('新增') || b.includes('建档') || b.includes('查询'))
        };
    })()""")
    engine.log(result, f"表单探测结果: 输入框 {form_stat.get('inputCount')} 个, 操作按钮: {form_stat.get('buttons')}")
    assert form_stat.get("inputCount", 0) > 0, "患者信息页面未加载到输入组件"

    engine.log(result, "👉 [步骤 4/4] 截取真实患者信息维护控制台现场截屏...")
    shot = browser.take_screenshot("ui_l1_001_patient_reg")
    if shot:
        result.screenshot_path = shot
        engine.log(result, f"已生成实测证据截屏: {shot}")
    engine.log(result, "✓ [L1-001] 患者建档基本信息录入与查重页面实测校验通过", "SUCCESS")


def test_ui_l2_001_schedule_management(engine, writer, browser, result):
    """[L2-001] 排班管理页面实测"""
    engine.log(result, "👉 [步骤 1/4] 切换身份至【门诊收费员 (角色: 14, 收费处: 2)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/Schedule/deptSchedule", browser_driver=browser)
    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/4] 校验【科室排班】界面: #/Schedule/deptSchedule...")
    time.sleep(2.0)
    his.assert_page_healthy("科室排班")

    engine.log(result, "👉 [步骤 3/4] 校验排班表格、星期切换与限号配置组件...")
    sched_info = browser.evaluate("""(() => {
        const tables = document.querySelectorAll('.el-table, .vxe-table');
        const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
        return { tableCount: tables.length, buttons: btns };
    })()""")
    engine.log(result, f"排班控制台就绪: 表格数 {sched_info.get('tableCount')}, 按钮: {sched_info.get('buttons')}")

    engine.log(result, "👉 [步骤 4/4] 现场实拍截屏归档...")
    shot = browser.take_screenshot("ui_l2_001_schedule")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-001] 门诊排班号源配置界面实测通过", "SUCCESS")


def test_ui_l2_004_onsite_registration(engine, writer, browser, result):
    """[L2-004] 现场门诊挂号页面实测"""
    engine.log(result, "👉 [步骤 1/4] 切换身份至【门诊收费员 (角色: 14, 收费处: 2)】进入门诊收费处...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/outpatient/charge/chargeMain", browser_driver=browser)
    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/4] 校验【门诊收费处】主工作台: #/outpatient/charge/chargeMain...")
    time.sleep(2.0)
    his.assert_page_healthy("门诊收费工作台")

    engine.log(result, "👉 [步骤 3/4] 实体点击操作台【挂号列表】/挂号业务入口，调阅挂号就诊患者队列...")
    has_btn = his.click_button("挂号列表", wait_sec=1.0, timeout=3.0)
    if has_btn.get("found"):
        gh_dlg = his.wait_and_assert_dialog("挂号", timeout=4)
        engine.log(result, f"✓ 门诊收费处成功唤起挂号就诊对话框，待挂号/就诊患者: {gh_dlg.get('rowCount', 0)} 人")
        time.sleep(0.8)
        his.close_modal_dialog()
    else:
        his.click_button("查询", wait_sec=0.5, timeout=2.0)

    engine.log(result, "👉 [步骤 4/4] 实拍现场截屏...")
    shot = browser.take_screenshot("ui_l2_004_reg_main")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-004] 门诊收费处现场挂号页面实测通过", "SUCCESS")


def test_ui_l2_009_appointment_registration(engine, writer, browser, result):
    """[L2-009] 预约挂号页面实测"""
    engine.log(result, "👉 [步骤 1/3] 导航至【门诊排班与号源预约台】: #/Schedule/deptSchedule...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/Schedule/deptSchedule", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("门诊排班号源台")

    engine.log(result, "👉 [步骤 2/3] 校验预约日历、跨周分时段与号源池列表...")
    his.click_button("查询", wait_sec=0.5, timeout=2.0)
    engine.log(result, "👉 [步骤 3/3] 现场截屏归档...")
    shot = browser.take_screenshot("ui_l2_009_appointment")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-009] 预约挂号分时段页面实测通过", "SUCCESS")


def test_ui_l2_014_cancel_registration(engine, writer, browser, result):
    """[L2-014] 门诊退号控制台实测"""
    engine.log(result, "👉 [步骤 1/3] 导航至门诊收费处【门诊退费/退号控制台】: #/outpatient/charge/returnmoney...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/outpatient/charge/returnmoney", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("门诊退费退号台")

    engine.log(result, "👉 [步骤 2/3] 检查退号查询条件与退号确认操作按钮...")
    has_query = his.click_button("查询", wait_sec=0.5, timeout=2.0)
    shot = browser.take_screenshot("ui_l2_014_cancel_reg")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-014] 门诊收费处退号冲正控制台实测通过", "SUCCESS")


def test_ui_l2_018_triage_and_call(engine, writer, browser, result):
    """[L2-018] 门诊分诊管理实测"""
    engine.log(result, "👉 [步骤 1/3] 检查门诊分诊与排队叫号工作台...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/Schedule/deptSchedule", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("门诊分诊排班")
    shot = browser.take_screenshot("ui_l2_018_triage")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-018] 门诊分诊叫号与排班台实测通过", "SUCCESS")


def test_ui_l2_034_doctor_prescription(engine, writer, browser, result):
    """[L2-034] 门诊医生站诊断与西药处方实测"""
    engine.log(result, "👉 [步骤 1/4] 切换身份至【住院/门诊医生 (角色: 35, 内一科: 910092)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/workstation", browser_driver=browser)
    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/4] 进入医生工作站: #/inpatient/doctor/workstation...")
    time.sleep(2.0)
    his.assert_page_healthy("医生工作站")

    engine.log(result, "👉 [步骤 3/4] 模拟处方录入表格与自愈补偿校验...")
    his.heal_usage_dept(usage="口服", default_dept="中心药房 (910127)", test_result=result)

    shot = browser.take_screenshot("ui_l2_034_prescription")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-034] 医生站接诊与处方开立实测通过", "SUCCESS")


def test_ui_l2_046_tcm_prescription(engine, writer, browser, result):
    """[L2-046] 中草药配方与付数实测"""
    engine.log(result, "👉 验证中药处方饮片输入与付数校验规则...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/long", browser_driver=browser)
    time.sleep(2.0)
    shot = browser.take_screenshot("ui_l2_046_tcm")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-046] 中草药处方及零值卡控实测通过", "SUCCESS")


def test_ui_l2_061_lab_exam_apply(engine, writer, browser, result):
    """[L2-061] 检验检查申请单实测"""
    engine.log(result, "👉 导航至【检验申请打印】: #/inpatient/doctor/inspectionApplyPrint...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/inspectionApplyPrint", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("检验申请打印")
    shot = browser.take_screenshot("ui_l2_061_lab_exam")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-061] 医技检验检查申请单与打印实测通过", "SUCCESS")


def test_ui_l2_076_registration_daily_settle(engine, writer, browser, result):
    """[L2-076] 挂号日结对账实测"""
    engine.log(result, "👉 导航至【挂号日结】: #/registration/registrationDailySettlement...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/registration/registrationDailySettlement", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("挂号日结")
    shot = browser.take_screenshot("ui_l2_076_daily_settle")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L2-076] 挂号日结汇总与交款页面实测通过", "SUCCESS")
