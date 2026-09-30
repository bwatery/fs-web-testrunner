import os, sys, time
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.test_engine import TestEngine, TestCaseResult
from fs_web_testrunner.core.browser_driver import BrowserDriver
from fs_web_testrunner.suites.test_suite_inpatient_full_lifecycle import test_lifecycle_01_invasive_full_e2e

engine = TestEngine(headless=False)
browser = BrowserDriver(headless=False)
browser.start("http://192.168.1.198:8088/#/index")
time.sleep(2.0)

result = TestCaseResult(
    test_id="lifecycle_01_invasive_full_e2e",
    name="住院全生命周期_入院登记、预交金、开嘱核对、药房发药、退药退费与出院结算大闭环实测",
    category="🛏️ 住院业务",
    mode="INVASIVE"
)

print("\n🚀 开始执行【住院全生命周期大闭环侵入式实测】...")
try:
    test_lifecycle_01_invasive_full_e2e(engine, None, browser, result)
    result.status = "PASSED"
    print("\n✅ 全生命周期大闭环测试用例全部顺利通过 (PASSED)!")
except Exception as e:
    result.status = "FAILED"
    result.error_message = str(e)
    print(f"\n❌ 测试用例执行失败: {e}")
    import traceback
    traceback.print_exc()

print(f"\n最终状态: {result.status}")
print(f"最终截图: {result.screenshot_path}")
print("执行日志条数:", len(result.logs))
for l in result.logs:
    print("  ", l)
