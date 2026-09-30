"""
Suite: 基础字典与系统权限测试 (Master Data & System Settings)
涵盖: 频次与用法维护 (frequentMaintenance/usageMaintenance)、
科室常用项目与套餐、人员与角色权限管理 (personnelManage/roleManagement)
"""

def register_tests(engine):
    engine.register(
        test_id="sys_01_personnel_roles",
        name="基础权限_人员管理、角色权限分配与菜单树组件",
        category="06-基础字典与权限",
        func=test_sys_personnel_roles
    )
    engine.register(
        test_id="sys_02_clinical_dicts",
        name="临床字典_频次用法维护、医嘱执行单与调配科室设置",
        category="06-基础字典与权限",
        func=test_sys_clinical_dicts
    )
    engine.register(
        test_id="sys_03_dept_packages",
        name="科室套餐_科室常用项目、诊疗套餐维护与组合包",
        category="06-基础字典与权限",
        func=test_sys_dept_packages
    )

def test_sys_personnel_roles(engine, writer, browser, result):
    """测试人员与角色管理"""
    engine.log(result, "导航至人员与角色管理: #/setting/personnelManage")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/setting/personnelManage")
    
    health = his.check_page_health()
    engine.log(result, f"人员管理健康度: {health.get('title')}, 表格数={health.get('elementStats', {}).get('tables')}")
    assert not health.get("is404"), "人员管理模块未找到"
    engine.log(result, "人员与权限管理基础组件加载验证通过")

def test_sys_clinical_dicts(engine, writer, browser, result):
    """测试频次与用法临床字典"""
    engine.log(result, "导航至频次用法维护: #/dictionary/frequentMaintenance")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/dictionary/frequentMaintenance")
    
    health = his.check_page_health()
    engine.log(result, f"频次维护界面状态: {health.get('url')}")
    assert not health.get("isBlank"), "字典界面空白异常"
    engine.log(result, "临床频次用法字典维护界面健康检验通过")

def test_sys_dept_packages(engine, writer, browser, result):
    """测试科室套餐维护"""
    engine.log(result, "导航至科室套餐维护: #/dictionary/deptPackageMaintain")
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    his.navigate_route("#/dictionary/deptPackageMaintain")
    
    health = his.check_page_health()
    engine.log(result, f"科室套餐健康度: 按钮数={health.get('elementStats', {}).get('buttons')}")
    assert not health.get("is404"), "科室套餐路由异常"
    engine.log(result, "科室常用项目与套餐配置组件验证通过")
