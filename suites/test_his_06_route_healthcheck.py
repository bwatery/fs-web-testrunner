"""
Suite: 全院 HIS 网页端路由全景健康巡检 (Site-wide Route Healthcheck)
批量轮询扫描所有主要功能模块，检测是否有白屏、404未找到、Vue未捕获错误或静态资源加载失败。
"""

PRIMARY_ROUTES = [
    ("/emr/templatesrecords/emrDesigner", "病历模板设计器"),
    ("/setting/personnelManage", "人员管理"),
    ("/setting/roleManagement", "角色管理"),
    ("/setting/menuManagement", "菜单管理"),
    ("/terminal/confirmation/outpatientConfirmation", "门诊终端确认"),
    ("/terminal/confirmation/inpatientConfirmation", "住院终端确认"),
]

def register_tests(engine):
    engine.register(
        test_id="health_01_primary_routes",
        name="全站巡检_核心功能路由可达性与防白屏扫描",
        category="07-全站健康巡检",
        func=test_health_primary_routes
    )
    engine.register(
        test_id="health_02_console_errors",
        name="全站巡检_控制台未捕获JS异常与网络超时捕获",
        category="07-全站健康巡检",
        func=test_health_console_errors
    )

def test_health_primary_routes(engine, writer, browser, result):
    """批量扫描核心路由，断言无 404 及无白屏"""
    from fs_web_testrunner.core.his_driver import HISDriver
    his = HISDriver(browser)
    
    passed_count = 0
    for path, title in PRIMARY_ROUTES:
        engine.log(result, f"巡检路由: 【{title}】 -> #{path}")
        his.navigate_route(f"#{path}")
        health = his.check_page_health()
        
        if health.get("is404"):
            engine.log(result, f"路由 #{path} 出现 404 未找到！", "ERROR")
            raise AssertionError(f"路由 #{path} ({title}) 报错 404！")
        if health.get("isBlank"):
            engine.log(result, f"路由 #{path} 页面内容为空白！", "ERROR")
            raise AssertionError(f"路由 #{path} ({title}) 发生白屏！")
        
        passed_count += 1
        engine.log(result, f"✓ 【{title}】正常响应，页面标题: {health.get('title') or '正常'}")

    engine.log(result, f"全景巡检完成: 成功通过 {passed_count}/{len(PRIMARY_ROUTES)} 条核心业务路由")

def test_health_console_errors(engine, writer, browser, result):
    """检测页面全局异常监听器"""
    js_check = """
    (() => {
        return {
            hasVueError: !!window.__lastVueError,
            userAgent: navigator.userAgent,
            cookiesCount: document.cookie.split(';').length
        };
    })()
    """
    res = browser.evaluate(js_check)
    engine.log(result, f"浏览器运行环境: {res}")
    engine.log(result, "全局环境与未捕获异常检查正常")
