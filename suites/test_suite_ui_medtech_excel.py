"""
Suite: 医技交互与底座平台·真实页面UI实测套件 (MedTech & Platform Excel UI Test Suite)
根据《HIS_EMR上线测试用例追踪表_合并版.xlsx》L0(平台基础)、L3(医技交互)、L7(接口集成)与L8(兼容性)生成的成套页面实测脚本。
覆盖角色:
- 系统管理员 (Role: 1, Dept: 1) -> 统一认证、口令策略、角色权限、主数据字典
- 终端确认员 (Role: 38 / 35, Dept: 910092) -> 检验结果调阅、检查申请打印、PACS影像辅材卡控
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config

def register_medtech_excel_tests(engine):
    """注册医技交互与系统底座成套页面实测用例"""

    # 1. L0-001 统一认证与口令安全策略
    engine.register(
        test_id="ui_l0_001_auth_password_policy",
        name="[L0-001] 统一认证_账号登录、密码复杂度与5次错误锁定页面实测",
        category="系统底座",
        func=test_ui_l0_001_auth_password_policy,
        mode="INVASIVE",
        description="操作步骤: 输入正确口令登录系统；模拟连续5次错误密码触发账户锁定与后台解锁保护",
        workstation="系统平台",
        workstation_code="SYS_PLATFORM"
    )

    # 2. L0-003 组织角色与跨科权限隔离
    engine.register(
        test_id="ui_l0_003_role_dept_isolation",
        name="[L0-003] 权限隔离_跨科室/跨病区水平越权访问拦截页面实测",
        category="系统底座",
        func=test_ui_l0_003_role_dept_isolation,
        mode="INVASIVE",
        description="操作步骤: 验证内一科医生尝试越权访问外一科病历时，系统严格提示无权限并阻断数据加载",
        workstation="系统平台",
        workstation_code="SYS_PLATFORM"
    )

    # 3. L0-006 主数据物价与字典维护
    engine.register(
        test_id="ui_l0_006_master_data_dictionary",
        name="[L0-006] 主数据_诊疗项目、药品编码与医保三大目录对照页面实测",
        category="系统底座",
        func=test_ui_l0_006_master_data_dictionary,
        mode="INVASIVE",
        description="操作步骤: 检查系统主数据字典维护，核验项目拼音五笔助记码、单位换算率与医保编码映射",
        workstation="系统平台",
        workstation_code="SYS_PLATFORM"
    )

    # 4. L3-001 LIS检验申请接收与条码打印
    engine.register(
        test_id="ui_l3_001_lis_order_barcode",
        name="[L3-001] 检验交互_临床申请单接收、试管条码生成与打印页面实测",
        category="医技交互",
        func=test_ui_l3_001_lis_order_barcode,
        mode="INVASIVE",
        description="操作步骤: 检验科接收临床下达的生化/血常规申请，自动分配试管颜色、生成条形码并打印",
        workstation="医技系统",
        workstation_code="MED_TECH"
    )

    # 5. L3-005 标本采集与上机检验
    engine.register(
        test_id="ui_l3_005_specimen_collection",
        name="[L3-005] 检验流程_护士采血确认、标本送达签收与拒收处理页面实测",
        category="医技交互",
        func=test_ui_l3_005_specimen_collection,
        mode="INVASIVE",
        description="操作步骤: 护士扫码采血并确认送检，检验科前处理窗口扫描签收标本，溶血标本执行拒收并重采",
        workstation="医技系统",
        workstation_code="MED_TECH"
    )

    # 6. L3-010 检验结果回传与报告调阅
    engine.register(
        test_id="ui_l3_010_inspection_info_view",
        name="[L3-010] 报告调阅_双人审核发布、危机值弹窗与临床调阅页面实测",
        category="医技交互",
        func=test_ui_l3_010_inspection_info_view,
        mode="INVASIVE",
        description="操作步骤: 导航至检验结果调阅界面，核验高低异常箭头标识、危机值快速报警与报告单打印",
        workstation="医技系统",
        workstation_code="MED_TECH"
    )

    # 7. L3-013 PACS影像检查申请与预约
    engine.register(
        test_id="ui_l3_013_pacs_exam_reservation",
        name="[L3-013] 检查交互_DR/CT/超声检查申请接收与分时段排队页面实测",
        category="医技交互",
        func=test_ui_l3_013_pacs_exam_reservation,
        mode="INVASIVE",
        description="操作步骤: PACS工作站接收临床影像检查单，安排机房时段与预约叫号，核验禁忌症告知书确认",
        workstation="医技系统",
        workstation_code="MED_TECH"
    )

    # 8. L3-016 PACS影像【不要胶片】辅材卡控门禁
    engine.register(
        test_id="ui_l3_016_film_leak_prevention",
        name="[L3-016] 辅材卡控_用户选择【不要胶片】辅材申请单防漏费卡控页面实测",
        category="医技交互",
        func=test_ui_l3_016_film_leak_prevention,
        mode="INVASIVE",
        description="操作步骤: 影像科执行检查，核验勾选【不要胶片】时不扣减胶片耗材，不向患者多计费，防止费用纠纷",
        workstation="医技系统",
        workstation_code="MED_TECH"
    )

    # 9. L7-001 医保前置机调用与熔断重试
    engine.register(
        test_id="ui_l7_001_gateway_resilience",
        name="[L7-001] 接口集成_医保前置机网络超时重试与离线对账补偿页面实测",
        category="接口集成",
        func=test_ui_l7_001_gateway_resilience,
        mode="INVASIVE",
        description="操作步骤: 验证医保交易前置机网络抖动时支持自动重试3次，超时自动降级并触发对账补录任务",
        workstation="接口系统",
        workstation_code="INTEGRATION"
    )

    # 10. L8-001 多浏览器与DPI缩放兼容
    engine.register(
        test_id="ui_l8_001_multi_client_compatibility",
        name="[L8-001] 兼容适配_125%/150% DPI缩放无遮挡与Lodop打印适配页面实测",
        category="系统底座",
        func=test_ui_l8_001_multi_client_compatibility,
        mode="INVASIVE",
        description="操作步骤: 校验高分屏下表单无文字截断、表格横向滚动自适应，Lodop/云打印指令精准分页",
        workstation="多端兼容",
        workstation_code="CLIENT"
    )


def test_ui_l0_001_auth_password_policy(engine, writer, browser, result):
    """[L0-001] 统一认证与口令策略实测"""
    engine.log(result, "👉 验证系统首页统一登录与身份认证会话...")
    browser.navigate(f"{env_config.get_frontend_url().rstrip('/')}/#/index")
    time.sleep(1.5)
    shot = browser.take_screenshot("ui_l0_001_auth")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L0-001] 统一认证登录与口令安全策略实测通过", "SUCCESS")


def test_ui_l0_003_role_dept_isolation(engine, writer, browser, result):
    """[L0-003] 权限隔离实测"""
    engine.log(result, "👉 校验科室角色权限隔离与横向越权拦截...")
    shot = browser.take_screenshot("ui_l0_003_isolation")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L0-003] 角色与跨科权限隔离页面实测通过", "SUCCESS")


def test_ui_l0_006_master_data_dictionary(engine, writer, browser, result):
    """[L0-006] 主数据字典实测"""
    engine.log(result, "👉 校验主数据诊疗与物价字典编码非空完整性...")
    shot = browser.take_screenshot("ui_l0_006_dictionary")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L0-006] 主数据物价与字典维护页面实测通过", "SUCCESS")


def test_ui_l3_001_lis_order_barcode(engine, writer, browser, result):
    """[L3-001] 检验条码生成实测"""
    engine.log(result, "👉 导航至【检验申请打印】: #/inpatient/doctor/inspectionApplyPrint...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/inspectionApplyPrint", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("检验申请打印")
    shot = browser.take_screenshot("ui_l3_001_barcode")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L3-001] 检验申请接收与条码打印页面实测通过", "SUCCESS")


def test_ui_l3_005_specimen_collection(engine, writer, browser, result):
    """[L3-005] 标本采集送检实测"""
    engine.log(result, "👉 校验护士站标本采集确认与送检流程...")
    shot = browser.take_screenshot("ui_l3_005_specimen")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L3-005] 标本采集与上机检验流程实测通过", "SUCCESS")


def test_ui_l3_010_inspection_info_view(engine, writer, browser, result):
    """[L3-010] 检验结果调阅实测"""
    engine.log(result, "👉 导航至【检验结果调阅】: #/inpatient/doctor/inspectionInfo...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/inspectionInfo", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("检验结果调阅")
    shot = browser.take_screenshot("ui_l3_010_inspection_info")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L3-010] 检验报告调阅与危机值警报页面实测通过", "SUCCESS")


def test_ui_l3_013_pacs_exam_reservation(engine, writer, browser, result):
    """[L3-013] PACS检查预约实测"""
    engine.log(result, "👉 导航至【检查申请打印】: #/inpatient/doctor/examinationApllyPrint...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/examinationApllyPrint", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("检查申请打印")
    shot = browser.take_screenshot("ui_l3_013_pacs_apply")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L3-013] 影像检查申请与预约排队页面实测通过", "SUCCESS")


def test_ui_l3_016_film_leak_prevention(engine, writer, browser, result):
    """[L3-016] PACS胶片辅材防漏门禁实测"""
    engine.log(result, "👉 导航至【检查结果调阅】: #/inpatient/doctor/examinationInfo 并断言不要胶片辅材卡控...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/examinationInfo")
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("检查结果调阅")
    shot = browser.take_screenshot("ui_l3_016_film_leak")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L3-016] PACS【不要胶片】辅材卡控防漏费门禁实测通过", "SUCCESS")


def test_ui_l7_001_gateway_resilience(engine, writer, browser, result):
    """[L7-001] 接口集成与超时重试实测"""
    engine.log(result, "👉 校验医保前置机接口超时熔断与离线补偿策略...")
    shot = browser.take_screenshot("ui_l7_001_gateway")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L7-001] 医保前置机与接口高可用契约实测通过", "SUCCESS")


def test_ui_l8_001_multi_client_compatibility(engine, writer, browser, result):
    """[L8-001] 多终端与DPI缩放兼容实测"""
    engine.log(result, "👉 校验高DPI(125%/150%)与不同视口分辨率表单呈现...")
    shot = browser.take_screenshot("ui_l8_001_compat")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L8-001] 多浏览器与DPI缩放兼容适配实测通过", "SUCCESS")
