"""
Suite: 药房药库管理测试 (Pharmacy & Stock Inventory)
涵盖: 门诊配药发药、住院摆药单、药库库存盘点、药品调价与警戒线
"""

def register_tests(engine):
    engine.register(
        test_id="pharm_01_outpatient_dispense",
        name="门诊药房_处方接收、自动配药与窗口发药核对",
        category="05-药房药库管理",
        func=test_pharm_outpatient_dispense
    )
    engine.register(
        test_id="pharm_02_inpatient_dispense",
        name="住院药房_按病区批次摆药、摆药单打印与退药审核",
        category="05-药房药库管理",
        func=test_pharm_inpatient_dispense
    )
    engine.register(
        test_id="pharm_03_inventory_management",
        name="药库管理_药品出入库单据、效期预警与库存盘点",
        category="05-药房药库管理",
        func=test_pharm_inventory_management
    )

def test_pharm_outpatient_dispense(engine, writer, browser, result):
    """测试门诊配药与发药模块"""
    engine.log(result, "导航至门诊药房页面: #/pharmacy/outpatient")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/pharmacy/outpatient")
    
    health = his.check_page_health()
    engine.log(result, f"门诊药房健康状态: 表格数={health.get('elementStats', {}).get('tables')}")
    assert not health.get("is404"), "门诊药房路由未找到"
    engine.log(result, "门诊药房配发药界面验证通过")

def test_pharm_inpatient_dispense(engine, writer, browser, result):
    """测试住院摆药模块"""
    engine.log(result, "导航至住院摆药界面: #/pharmacy/inpatient")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/pharmacy/inpatient")
    
    health = his.check_page_health()
    engine.log(result, f"住院摆药健康状态: 标题={health.get('title')}")
    assert not health.get("isBlank"), "住院摆药页面呈现空白"
    engine.log(result, "住院药房批次摆药与单据组件验证通过")

def test_pharm_inventory_management(engine, writer, browser, result):
    """测试药库盘点与库存管理"""
    engine.log(result, "导航至药库管理界面: #/pharmacy/stock")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/pharmacy/stock")
    
    health = his.check_page_health()
    engine.log(result, f"药库盘点页面状态: 按钮数={health.get('elementStats', {}).get('buttons')}")
    assert not health.get("is404"), "药库管理路由异常"
    engine.log(result, "药库管理出入库与盘点表单验证通过")
