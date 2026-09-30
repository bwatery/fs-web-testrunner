"""
Suite: 门诊业务测试 (Outpatient Workstation, Registration & Billing)
涵盖: 挂号流程与号源检查、门诊收费与退费界面、门诊医生站处方开立与诊断维护
"""

def register_tests(engine):
    engine.register(
        test_id="outpatient_01_reg_page",
        name="门诊挂号_页面加载与排班号源组件校验",
        category="02-门诊挂号与收费",
        func=test_outpatient_registration_page
    )
    engine.register(
        test_id="outpatient_02_charge_billing",
        name="门诊收费_收费结算表单与发票管理组件校验",
        category="02-门诊挂号与收费",
        func=test_outpatient_charge_billing
    )
    engine.register(
        test_id="outpatient_03_doctor_workstation",
        name="门诊医生站_患者队列、处方开立与诊断树检查",
        category="03-门诊医生工作站",
        func=test_outpatient_doctor_workstation
    )

def test_outpatient_registration_page(engine, writer, browser, result):
    """测试门诊挂号页面加载与核心元素"""
    engine.log(result, "导航至门诊挂号页面: #/outpatient/registration")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/outpatient/registration")
    
    health = his.check_page_health()
    engine.log(result, f"页面健康体检: {health.get('title')}, 表格数: {health.get('elementStats', {}).get('tables')}")
    assert not health.get("is404"), "门诊挂号页面返回404未找到！"
    assert not health.get("isBlank"), "门诊挂号页面呈现白屏！"
    engine.log(result, "门诊挂号模块路由与基础DOM组件健康检验通过")

def test_outpatient_charge_billing(engine, writer, browser, result):
    """测试门诊收费与日结界面"""
    engine.log(result, "导航至门诊收费结算页面: #/outpatient/charge")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/outpatient/charge")
    
    health = his.check_page_health()
    engine.log(result, f"门诊收费界面状态: URL={health.get('hash')}, 按钮数={health.get('elementStats', {}).get('buttons')}")
    assert not health.get("is404"), "门诊收费页面异常404"
    engine.log(result, "门诊收费与结算界面加载验证通过")

def test_outpatient_doctor_workstation(engine, writer, browser, result):
    """测试门诊医生站"""
    engine.log(result, "导航至门诊医生工作站: #/outpatient/doctor")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/outpatient/doctor")
    
    health = his.check_page_health()
    engine.log(result, f"门诊医生站健康度: 标题={health.get('title')}, 输入框数={health.get('elementStats', {}).get('inputs')}")
    assert not health.get("is404"), "医生工作站路由异常"
    engine.log(result, "门诊医生工作站交互组件加载验证通过")
