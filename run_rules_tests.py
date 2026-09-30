import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'D:\CSsoft\AI\googleAntiGravity\cliProject')
from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.suites import test_suite_inpatient_business_rules

engine = TestEngine(headless=True, login_mode="B")
test_suite_inpatient_business_rules.register_tests(engine)

def on_event(evt):
    if evt.get("type") == "LOG":
        data = evt.get("data", {})
        print(f"[{data.get('level', 'INFO')}] {data.get('message')}")

engine.subscribe(on_event)

rule_ids = [
    "rule_01_order_start_time_inheritance",
    "rule_02_grouped_order_consistency",
    "rule_03_order_state_machine_transition",
    "rule_04_drug_return_before_fee_refund",
    "rule_05_discharge_settlement_prerequisites"
]

print(f"============================================================")
print(f"  住院系统业务规则与流程流转自动化测试引擎启动 (共 {len(rule_ids)} 项规则)")
print(f"============================================================")

results = engine.run_tests(selected_ids=rule_ids)

print("\n" + "=" * 60)
print("  规则测试运行总结报告")
print("=" * 60)
all_passed = True
for r in results:
    icon = "✅" if r.status == "PASSED" else "❌"
    if r.status != "PASSED":
        all_passed = False
    print(f"{icon} [{r.status}] {r.name} ({r.duration_ms}ms)")
    if r.error_message:
        print(f"   报错: {r.error_message}")

print("=" * 60)
print(f"总计: {len(results)} 项规则全部校验完成！结果: {'全部通过 🎉' if all_passed else '存在失败 ⚠️'}")
