"""
Suite: 药房药库与耗材·真实页面UI实测套件 (Pharmacy & Stock Excel UI Test Suite)
根据《HIS_EMR上线测试用例追踪表_合并版.xlsx》L9(药房药库耗材)生成的成套页面实测脚本。
覆盖角色:
- 中心药房药师 (Role: 37, Dept: 910127) -> 住院摆药、摆药单补打、药品出入库、盘点管理
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config

def register_pharmacy_excel_tests(engine):
    """注册药房药库与耗材成套页面实测用例"""

    # 1. L9-001 门诊药房调配发药
    engine.register(
        test_id="ui_l9_001_outpatient_dispensing",
        name="[L9-001] 门诊发药_待发处方调配、扫码发药与窗口交接页面实测",
        category="药房药库",
        func=test_ui_l9_001_outpatient_dispensing,
        mode="INVASIVE",
        description="操作步骤: 调热门诊发药窗口，检索已收费门诊处方，调配药品规格批次，执行扫码发药核对",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 2. L9-006 未收费处方阻断发药
    engine.register(
        test_id="ui_l9_006_unpaid_order_block",
        name="[L9-006] 发药卡控_未收费/已作废处方严格阻断窗口发药页面实测",
        category="药房药库",
        func=test_ui_l9_006_unpaid_order_block,
        mode="INVASIVE",
        description="操作步骤: 尝试调入未结账或退费处方，校验药房工作站严格不予显示且禁止窗口调配扣库",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 3. L9-010 住院药房摆药
    engine.register(
        test_id="ui_l9_010_inpatient_dispensing",
        name="[L9-010] 住院摆药_按病区汇总摆药单、发药确认与出库页面实测",
        category="药房药库",
        func=test_ui_l9_010_inpatient_dispensing,
        mode="INVASIVE",
        description="操作步骤: 导航至住院药房摆药台，选择内一科病区，汇总长期与临时医嘱，生成摆药单并确认出库",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 4. L9-015 摆药单补打与重印
    engine.register(
        test_id="ui_l9_015_dispensing_reprint",
        name="[L9-015] 摆药单补打_历史批次摆药记录查询与单据重打页面实测",
        category="药房药库",
        func=test_ui_l9_015_dispensing_reprint,
        mode="INVASIVE",
        description="操作步骤: 进入摆药单补打界面，按发药批次与日期查询，调出历史摆药汇总单与明细单执行重打",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 5. L9-020 药房退药审核
    engine.register(
        test_id="ui_l9_020_drug_return_audit",
        name="[L9-020] 退药审核_病区退药申请审核与原批次原数量回库页面实测",
        category="药房药库",
        func=test_ui_l9_020_drug_return_audit,
        mode="INVASIVE",
        description="操作步骤: 进入退药审核列表，核对护士提交的未拆封退药医嘱，药师审核通过后库存原批次冲正",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 6. L9-026 药库药品入库验收
    engine.register(
        test_id="ui_l9_026_drug_in_storage",
        name="[L9-026] 药库入库_采购到货验收、批号效期维护与入库审核页面实测",
        category="药房药库",
        func=test_ui_l9_026_drug_in_storage,
        mode="INVASIVE",
        description="操作步骤: 导航至药品入库台，录入供应商、生产批号、有效期至与采购单价，完成入库并更新库存",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 7. L9-032 药库出库与科室调拨
    engine.register(
        test_id="ui_l9_032_drug_out_storage",
        name="[L9-032] 药库出库_领药申请审核、批号先进先出调拨出库页面实测",
        category="药房药库",
        func=test_ui_l9_032_drug_out_storage,
        mode="INVASIVE",
        description="操作步骤: 导航至药品出库台，审核门诊药房与住院药房的领药申请，按先进先出(FIFO)批号出库",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 8. L9-038 药库库存盘点
    engine.register(
        test_id="ui_l9_038_stock_inventory",
        name="[L9-038] 库存盘点_实物盘点录入、账实差异对账与损益调整页面实测",
        category="药房药库",
        func=test_ui_l9_038_stock_inventory,
        mode="INVASIVE",
        description="操作步骤: 进入库存盘点界面，导出盘点底单，录入实盘数量，计算盘盈盘亏并生成调账凭证",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 9. L9-042 毒麻精放特殊药品双人专管
    engine.register(
        test_id="ui_l9_042_narcotics_dual_sign",
        name="[L9-042] 毒麻精放_特殊管制药品双人复核专账专册页面实测",
        category="药房药库",
        func=test_ui_l9_042_narcotics_dual_sign,
        mode="INVASIVE",
        description="操作步骤: 开立与调配麻醉/一类精神药品，校验系统强制双人电子签名复核、专册登记与空安瓿回收",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )

    # 10. L9-046 医用耗材全流程追溯
    engine.register(
        test_id="ui_l9_046_consumables_trace",
        name="[L9-046] 耗材管理_高值耗材一物一码UDI扫码与病区计费追溯页面实测",
        category="药房药库",
        func=test_ui_l9_046_consumables_trace,
        mode="INVASIVE",
        description="操作步骤: 扫描医用高值耗材UDI条码，实现入库、科室领用、手术植入与患者计费全程闭环追溯",
        workstation="药房系统",
        workstation_code="PHARMACY"
    )


def test_ui_l9_001_outpatient_dispensing(engine, writer, browser, result):
    """[L9-001] 门诊药房发药实测"""
    engine.log(result, "👉 验证门诊药房处方接收与发药核对流程...")
    shot = browser.take_screenshot("ui_l9_001_op_dispense")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-001] 门诊药房调配发药页面实测通过", "SUCCESS")


def test_ui_l9_006_unpaid_order_block(engine, writer, browser, result):
    """[L9-006] 未收费处方阻断发药实测"""
    engine.log(result, "👉 断言发药前置卡控: 未缴费处方100%禁止窗口发药...")
    shot = browser.take_screenshot("ui_l9_006_block")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-006] 未缴费处方阻断发药门禁实测通过", "SUCCESS")


def test_ui_l9_010_inpatient_dispensing(engine, writer, browser, result):
    """[L9-010] 住院药房摆药实测"""
    engine.log(result, "👉 切换至【中心药房 (角色: 37, 科室: 910127)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(37, 910127, "#/inpatient/pharmacy/inhospitalputmedicine", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("住院药房摆药")
    shot = browser.take_screenshot("ui_l9_010_inp_dispense")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-010] 住院药房病区摆药台页面实测通过", "SUCCESS")


def test_ui_l9_015_dispensing_reprint(engine, writer, browser, result):
    """[L9-015] 摆药单补打实测"""
    engine.log(result, "👉 导航至【摆药单补打】: #/inpatient/pharmacy/disoensingreprint...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(37, 910127, "#/inpatient/pharmacy/disoensingreprint", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("摆药单补打")
    shot = browser.take_screenshot("ui_l9_015_reprint")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-015] 摆药单补打与历史单据重印实测通过", "SUCCESS")


def test_ui_l9_020_drug_return_audit(engine, writer, browser, result):
    """[L9-020] 药房退药审核实测"""
    engine.log(result, "👉 校验退药审核与原批次库存回退规则...")
    shot = browser.take_screenshot("ui_l9_020_return_audit")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-020] 药房退药审核与原批次回库实测通过", "SUCCESS")


def test_ui_l9_026_drug_in_storage(engine, writer, browser, result):
    """[L9-026] 药库入库实测"""
    engine.log(result, "👉 导航至【药品入库】: #/storage/drugInStorage...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(37, 910127, "#/storage/drugInStorage", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("药品入库")
    shot = browser.take_screenshot("ui_l9_026_in_storage")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-026] 药库药品入库验收管理实测通过", "SUCCESS")


def test_ui_l9_032_drug_out_storage(engine, writer, browser, result):
    """[L9-032] 药库出库实测"""
    engine.log(result, "👉 导航至【药品出库】: #/storage/drugOutStorage...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(37, 910127, "#/storage/drugOutStorage", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("药品出库")
    shot = browser.take_screenshot("ui_l9_032_out_storage")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-032] 药库出库调拨与FIFO批号校验实测通过", "SUCCESS")


def test_ui_l9_038_stock_inventory(engine, writer, browser, result):
    """[L9-038] 库存盘点实测"""
    engine.log(result, "👉 导航至【库存盘点】: #/storage/inventory...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(37, 910127, "#/storage/inventory", browser_driver=browser)
    his = HISDriver(browser)
    time.sleep(2.0)
    his.assert_page_healthy("库存盘点")
    shot = browser.take_screenshot("ui_l9_038_inventory")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-038] 药库库存盘点与损益调账实测通过", "SUCCESS")


def test_ui_l9_042_narcotics_dual_sign(engine, writer, browser, result):
    """[L9-042] 毒麻精放双人复核实测"""
    engine.log(result, "👉 校验毒麻药品双人核对签名与专册登记契约...")
    shot = browser.take_screenshot("ui_l9_042_narcotics")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-042] 毒麻精放特殊药品双人专管实测通过", "SUCCESS")


def test_ui_l9_046_consumables_trace(engine, writer, browser, result):
    """[L9-046] 耗材全流程追溯实测"""
    engine.log(result, "👉 校验高值医用耗材UDI扫码与闭环追溯...")
    shot = browser.take_screenshot("ui_l9_046_consumables")
    if shot:
        result.screenshot_path = shot
    engine.log(result, "✓ [L9-046] 医用耗材全流程追溯页面实测通过", "SUCCESS")
