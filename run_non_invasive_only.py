import sys
sys.stdout.reconfigure(encoding='utf-8')

from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.suites.test_suite_non_invasive import register_tests

engine = TestEngine(headless=True)
register_tests(engine)
results = engine.run_tests(mode_filter='NON_INVASIVE')
passed = [r for r in results if r.status == 'PASSED']

print(f"\n==========================================")
print(f"Total: {len(results)}, Passed: {len(passed)}, Failed: {len(results) - len(passed)}")
print(f"==========================================")
for r in results:
    icon = "✓" if r.status == "PASSED" else "✗"
    print(f" {icon} [{r.test_id}] {r.name}: {r.status} ({r.duration_ms}ms)")
    if r.error_message:
        print(f"     ERROR: {r.error_message}")
