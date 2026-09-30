import sys
from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.suites import test_his_03_inpatient

sys.stdout.reconfigure(encoding='utf-8')

engine = TestEngine(headless=False, login_mode="B")
test_his_03_inpatient.register_tests(engine)

# Subscribe to logs
def on_event(evt):
    if evt.get("type") == "LOG":
        data = evt.get("data", {})
        print(f"[{data.get('level', 'INFO')}] {data.get('message')}")

engine.subscribe(on_event)

print("Starting single test: inpatient_03_settlement...")
results = engine.run_tests(selected_ids=["inpatient_03_settlement"])
print("\nExecution Completed!")
for r in results:
    print(f"Test: {r.name}")
    print(f"Status: {r.status} (Duration: {r.duration_ms}ms)")
    if r.error_message:
        print(f"Error: {r.error_message}")
    if r.screenshot_path:
        print(f"Screenshot: {r.screenshot_path}")
