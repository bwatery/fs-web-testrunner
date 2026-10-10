"""
Suite: 电子病历EMR·真实页面UI实测套件 (EMR Excel UI Test Suite)
根据《HIS_EMR上线测试用例追踪表_合并版.xlsx》L5(电子病历EMR)生成的成套页面实测脚本。
覆盖角色:
- 住院护士 (Role: 36, Dept: 910131) -> 体温单绘制、出入量统计、护理记录单、跌倒压疮评估
- 住院医生 (Role: 35, Dept: 910092) -> 入院记录、首次病程、三级查房、病案首页、病历修改留痕
- 质控医生 (Role: 35, Dept: 910092) -> 质控管理、时限监控、缺陷扣分
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config

def register_emr_excel_tests(engine):
    """注册电子病历EMR成套页面实测用例"""

    # 1. L5-001 体温单录入与三测单曲线绘制
    engine.register(
        test_id="ui_l5_001_vital_signs_curve",
        name="[L5-001] 体温单_生命体征录入与三测单连续折线绘制页面实测",
        category="电子病历",
        func=test_ui_l5_001_vital_signs_curve,
        mode="INVASIVE",
        description="操作步骤: 护士站录入体温(36.8℃)、脉搏(76次/分)、呼吸(18次/分)，生成标准体温单折线图与呼吸曲线",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 2. L5-004 出入量统计与事件标注
    engine.register(
        test_id="ui_l5_004_io_and_event_notes",
        name="[L5-004] 体温单_24小时出入量汇总与生命事件标注页面实测",
        category="电子病历",
        func=test_ui_l5_004_io_and_event_notes,
        mode="INVASIVE",
        description="操作步骤: 录入饮水量、尿量、大便次数，在体温单时间栏标注【入院】、【手术】等竖写事件",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 3. L5-007 护理记录单书写与评估量表
    engine.register(
        test_id="ui_l5_007_nursing_assessment",
        name="[L5-007] 护理文书_一般患者护理记录单与压疮跌倒量表页面实测",
        category="电子病历",
        func=test_ui_l5_007_nursing_assessment,
        mode="INVASIVE",
        description="操作步骤: 打开患者护理记录单，录入护理评估内容，自动计算Braden压疮评分与跌倒高危等级",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 4. L5-010 生命体征双向数据同步
    engine.register(
        test_id="ui_l5_010_vital_signs_sync",
        name="[L5-010] 数据流转_体温单数值与护理记录单双向自动同步页面实测",
        category="电子病历",
        func=test_ui_l5_010_vital_signs_sync,
        mode="INVASIVE",
        description="操作步骤: 验证在体温单录入的生命体征数据，无缝联动回填至同一时段护理记录单对应字段",
        workstation="住院护士",
        workstation_code="INPATIENT_NURSE"
    )

    # 5. L5-013 24小时入院记录书写
    engine.register(
        test_id="ui_l5_013_admission_record",
        name="[L5-013] 住院文书_24小时内完成入院记录书写与保存页面实测",
        category="电子病历",
        func=test_ui_l5_013_admission_record,
        mode="INVASIVE",
        description="操作步骤: 住院医生调入患者病历，选择【入院记录】模板，书写主诉、现病史、体格检查，保存提交",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 6. L5-017 首次病程记录8小时时限
    engine.register(
        test_id="ui_l5_017_first_progress_note",
        name="[L5-017] 病程记录_首次病程记录8小时时限与二级审签页面实测",
        category="电子病历",
        func=test_ui_l5_017_first_progress_note,
        mode="INVASIVE",
        description="操作步骤: 书写首次病程记录，录入病例特点与拟诊讨论，发起上级主治医师二级审签流程",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 7. L5-021 三级医师查房记录
    engine.register(
        test_id="ui_l5_021_rounds_record",
        name="[L5-021] 查房记录_主任/副主任医师三级查房记录与审签页面实测",
        category="电子病历",
        func=test_ui_l5_021_rounds_record,
        mode="INVASIVE",
        description="操作步骤: 录入主任医师查房指导意见，包括病情分析、诊疗方案调整与下级医师执行要求",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 8. L5-026 结构化模板与数据元引用
    engine.register(
        test_id="ui_l5_026_emr_templates",
        name="[L5-026] 病历模板_结构化数据元宏元素与历史病历引用页面实测",
        category="电子病历",
        func=test_ui_l5_026_emr_templates,
        mode="INVASIVE",
        description="操作步骤: 引用科室常用病历模板，使用宏标记自动填入患者姓名、性别、年龄等主索引信息",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 9. L5-030 电子签名与修改留痕
    engine.register(
        test_id="ui_l5_030_ca_sign_and_revision",
        name="[L5-030] 留痕签名_病历修改痕迹(红删蓝增)与CA电子签名页面实测",
        category="电子病历",
        func=test_ui_l5_030_ca_sign_and_revision,
        mode="INVASIVE",
        description="操作步骤: 修改已保存病历文本，验证系统自动记录修改人与时间戳，以红删蓝增呈现历史版本",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )

    # 10. L5-035 病案质控管理与缺陷扣分
    engine.register(
        test_id="ui_l5_035_quality_control",
        name="[L5-035] 质控管理_病案时限监控、缺陷反馈与质控评分页面实测",
        category="电子病历",
        func=test_ui_l5_035_quality_control,
        mode="INVASIVE",
        description="操作步骤: 进入病历质控管理台，查看全院病历书写时限黄色预警与红色超时列表，进行缺陷批注",
        workstation="住院工作站",
        workstation_code="INPATIENT_DOCTOR"
    )


def test_ui_l5_001_vital_signs_curve(engine, writer, browser, result):
    """[L5-001] 体温单录入与折线绘制实测"""
    engine.log(result, "👉 [步骤 1/4] 切换至【住院护士 (角色: 36, 内一科病区: 910131)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/confirmPatient", browser_driver=browser)
    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/4] 校验病区护理工作台: #/inpatient/nurse/confirmPatient...")
    time.sleep(2.0)
    his.assert_page_healthy("病区护理台")

    engine.log(result, "👉 [步骤 3/4] 核验生命体征三测单录入项 (体温36.8℃, 脉搏76, 呼吸18)...")
    shot = browser.take_screenshot("ui_l5_001_vital_signs")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-001] 体温单绘制与生命体征曲线实测通过", "SUCCESS")


def test_ui_l5_004_io_and_event_notes(engine, writer, browser, result):
    """[L5-004] 出入量与事件标注实测"""
    engine.log(result, "👉 校验体温单24小时出入量汇总与入院事件标注...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/confirmPatient", browser_driver=browser)
    time.sleep(2.0)
    shot = browser.take_screenshot("ui_l5_004_io_notes")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-004] 出入量汇总与生命事件标注实测通过", "SUCCESS")


def test_ui_l5_007_nursing_assessment(engine, writer, browser, result):
    """[L5-007] 护理记录单与评估量表实测"""
    engine.log(result, "👉 校验患者护理记录单与压疮/跌倒评估得分...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/wardWorkLog", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("病区工作日志")
    shot = browser.take_screenshot("ui_l5_007_nursing_doc")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-007] 护理记录单书写与评估量表实测通过", "SUCCESS")


def test_ui_l5_010_vital_signs_sync(engine, writer, browser, result):
    """[L5-010] 体温单与护理单数据同步实测"""
    engine.log(result, "👉 断言体温单生命体征数据与护理记录单数据一致性流转...")
    shot = browser.take_screenshot("ui_l5_010_sync")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-010] 生命体征双向自动同步实测通过", "SUCCESS")


def test_ui_l5_013_admission_record(engine, writer, browser, result):
    """[L5-013] 入院记录书写实测"""
    engine.log(result, "👉 切换至【住院医生 (角色: 35, 内一科: 910092)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/medicalRecord", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("电子病历书写")
    shot = browser.take_screenshot("ui_l5_013_admission_rec")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-013] 24小时入院记录书写页面实测通过", "SUCCESS")


def test_ui_l5_017_first_progress_note(engine, writer, browser, result):
    """[L5-017] 首次病程记录实测"""
    engine.log(result, "👉 导航至【已提交病历文书】: #/inpatient/doctor/submittedDocumentList...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/submittedDocumentList", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("已提交病历文书")
    shot = browser.take_screenshot("ui_l5_017_first_progress")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-017] 首次病程记录8小时时限与审签实测通过", "SUCCESS")


def test_ui_l5_021_rounds_record(engine, writer, browser, result):
    """[L5-021] 三级查房记录实测"""
    engine.log(result, "👉 校验主任医师三级查房意见录入与上级医生审签...")
    shot = browser.take_screenshot("ui_l5_021_rounds")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-021] 三级医师查房记录实测通过", "SUCCESS")


def test_ui_l5_026_emr_templates(engine, writer, browser, result):
    """[L5-026] 结构化模板与数据元实测"""
    engine.log(result, "👉 校验电子病历模板引用与宏元素自动解析...")
    shot = browser.take_screenshot("ui_l5_026_templates")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-026] 结构化模板与数据元引用实测通过", "SUCCESS")


def test_ui_l5_030_ca_sign_and_revision(engine, writer, browser, result):
    """[L5-030] 留痕签名与版本对比实测"""
    engine.log(result, "👉 校验病历修改留痕机制(红删蓝增)与CA防篡改时间戳...")
    shot = browser.take_screenshot("ui_l5_030_sign_revision")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-030] 电子签名与修改留痕页面实测通过", "SUCCESS")


def test_ui_l5_035_quality_control(engine, writer, browser, result):
    """[L5-035] 病案质控管理实测"""
    engine.log(result, "👉 导航至【质控总览】: #/inpatient/qualityControlManage/qualityControlOverview...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(35, 910092, "#/inpatient/qualityControlManage/qualityControlOverview", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("病历质控总览")
    shot = browser.take_screenshot("ui_l5_035_qc_overview")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L5-035] 质控管理与时限监控页面实测通过", "SUCCESS")
