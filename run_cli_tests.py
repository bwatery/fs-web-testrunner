"""
FS.TestRunner Web - CLI Runner
Runs test suites directly from the terminal with clean formatting.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.suites import register_all_suites

def main():
    parser = argparse.ArgumentParser(description="FS Web TestRunner CLI")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--login-mode", type=str, default="B", choices=["A", "B"], help="Login mode: 'A' (Auto) or 'B' (Manual)")
    parser.add_argument("--username", type=str, default="", help="Username for auto login")
    parser.add_argument("--password", type=str, default="", help="Password for auto login")
    parser.add_argument("--category", type=str, default=None, help="Filter tests by category")
    parser.add_argument("--test-id", type=str, default=None, help="Run specific test ID")
    args = parser.parse_args()

    engine = TestEngine(
        headless=args.headless,
        login_mode=args.login_mode,
        username=args.username,
        password=args.password
    )
    register_all_suites(engine)

    # Filter tests
    target_ids = []
    for tid, meta in engine.registry.items():
        if args.test_id and tid != args.test_id:
            continue
        if args.category and args.category not in meta["category"]:
            continue
        target_ids.append(tid)

    if not target_ids:
        print("未找到匹配的测试用例！")
        return

    print(f"\n=======================================================")
    print(f"  FS.TestRunner CLI - 执行开始 (共 {len(target_ids)} 项)")
    print(f"=======================================================\n")

    results = engine.run_tests(target_ids)

    passed = sum(1 for r in results if r.status == "PASSED")
    failed = sum(1 for r in results if r.status == "FAILED")

    print(f"\n=======================================================")
    print(f"  测试汇总: 总计 {len(results)} | 通过 {passed} | 失败 {failed}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    main()
