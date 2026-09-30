import sys, time
sys.stdout.reconfigure(encoding='utf-8')

from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.suites import register_all_suites

engine = TestEngine(headless=False, login_mode="B")
register_all_suites(engine)

print(f"Total tests registered: {len(engine.registry)}")
invasive = [tid for tid, m in engine.registry.items() if m.get("mode") == "INVASIVE"]
non_invasive = [tid for tid, m in engine.registry.items() if m.get("mode") == "NON_INVASIVE"]

print(f"  👀 侵入式用例 (给我看): {len(invasive)} 项")
for tid in invasive:
    print(f"     - [{tid}] {engine.registry[tid]['name']}")

print(f"  🤖 非侵入式用例 (AI验证): {len(non_invasive)} 项")
for tid in non_invasive:
    print(f"     - [{tid}] {engine.registry[tid]['name']}")

print("\n" + "="*70)
print("  >>> 执行【🤖 非侵入式·AI静默验证套件】(零前端干扰，纯后端+Oracle+规则)...")
print("="*70)
t0 = time.time()
results = engine.run_tests(selected_ids=non_invasive, mode_filter="NON_INVASIVE")
elapsed = round(time.time() - t0, 2)

passed = [r for r in results if r.status == "PASSED"]
failed = [r for r in results if r.status == "FAILED"]

print(f"\n【AI静默验证结果汇总】: 总计 {len(results)} 项, 通过 {len(passed)} 项, 失败 {len(failed)} 项 (总耗时: {elapsed}s)")
for r in results:
    icon = "✓" if r.status == "PASSED" else "✗"
    print(f"  {icon} [{r.test_id}] {r.name} -> {r.status} ({r.duration_ms}ms)")
    if r.error_message:
        print(f"      [ERROR]: {r.error_message}")
