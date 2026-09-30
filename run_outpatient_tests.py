import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.dirname(os.path.abspath(".")))

from core.test_engine import TestEngine
from suites.test_suite_outpatient_full_lifecycle import (
    test_outpatient_lifecycle_02_silent_contract_e2e,
    test_outpatient_lifecycle_03_business_rules
)

class DummyResult:
    def __init__(self, name):
        self.name = name
        self.logs = []
        self.status = "PENDING"
        self.error = None

class DummyEngine:
    def log(self, result, msg, level="INFO"):
        print(f"[{level}] {msg}")
        result.logs.append(msg)

engine = DummyEngine()

print("=" * 65)
print("  🚀 执行门诊全流程微服务契约与核心状态机自动化测试套件")
print("=" * 65)

res2 = DummyResult("outpatient_contract")
try:
    test_outpatient_lifecycle_02_silent_contract_e2e(engine, None, None, res2)
    print("\n[SUCCESS] ✓ 门诊八大阶段微服务契约与状态机跃迁全部通过！\n")
except Exception as e:
    print(f"\n[FAIL] ❌ 测试未通过: {e}\n")
    import traceback
    traceback.print_exc()

print("=" * 65)
print("  🛡️ 执行门诊业务规则门禁校验套件")
print("=" * 65)

res3 = DummyResult("outpatient_rules")
try:
    test_outpatient_lifecycle_03_business_rules(engine, None, None, res3)
    print("\n[SUCCESS] ✓ 门诊核心业务规则门禁校验全部通过！\n")
except Exception as e:
    print(f"\n[FAIL] ❌ 规则校验未通过: {e}\n")
    import traceback
    traceback.print_exc()
