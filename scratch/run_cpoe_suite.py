import os, sys, time
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.test_engine import TestEngine, TestCaseResult
from fs_web_testrunner.core.browser_driver import BrowserDriver
from fs_web_testrunner.suites.test_suite_cpoe_closed_loop import test_cpoe_01_closed_loop_e2e_invasive

engine = TestEngine(headless=False)
browser = BrowserDriver(headless=False)
browser.start("http://192.168.1.198:8088/#/inpatient/doctor/workstation")
time.sleep(2.0)

result = TestCaseResult(
    test_id="cpoe_01_closed_loop_e2e_invasive",
    name="医嘱闭环_住院选患者、开立医嘱、护士校对、药房发药与账单穿透全流程实测",
    category="📋 医嘱闭环",
    mode="INVASIVE"
)

print("\n🚀 开始执行【医嘱闭环侵入式全流程实测】...")
try:
    test_cpoe_01_closed_loop_e2e_invasive(engine, None, browser, result)
    result.status = "PASSED"
    print("\n✅ 测试用例全部顺利通过 (PASSED)!")
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
