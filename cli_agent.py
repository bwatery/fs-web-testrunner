#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIS WebRunner - CLI Agent & 终端快速调用工具
专为开发者、DevOps/CI流水线以及外部 AI 智能体设计的终端快速调用外骨骼。
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

# 保证 Windows 控制台正常支持 UTF-8 中文与 Emoji
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_BASE_URL = os.environ.get("HIS_RUNNER_URL", "http://127.0.0.1:8989")


def http_req(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, base_url: str = DEFAULT_BASE_URL) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {"status": "ok"}
    except urllib.error.URLError as e:
        return {"status": "error", "message": f"连接服务失败 ({url}): {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# =========================================================================
# 命令实现
# =========================================================================

def cmd_run(args):
    payload = {
        "mode": args.mode,
        "headless": not args.head,
    }
    if args.workstation:
        payload["workstation"] = args.workstation

    res = http_req("/api/run", method="POST", payload=payload, base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("status") == "error":
        print(f"❌ 启动失败: {res.get('message')}")
        sys.exit(1)

    print(f"🚀 已触发自动化测试任务！")
    print(f"   • 测试模式: {payload['mode']}")
    print(f"   • 指定工作站: {payload.get('workstation', '全院所有工作站')}")
    print(f"   • 无头静默: {payload['headless']}")
    print(f"   • 本次任务计划用例: {res.get('target_count', '全部')} 项")

    if args.watch:
        print("\n⏳ 正在实时监视测试进度 (按 Ctrl+C 可退出监视)...")
        time.sleep(1)
        while True:
            st = http_req("/api/status", base_url=args.url)
            is_running = st.get("is_running", False)
            total = st.get("total_count", 0)
            passed = st.get("passed_count", 0)
            failed = st.get("failed_count", 0)
            done = passed + failed
            pct = (done / total * 100) if total > 0 else 0

            print(f"\r📊 进度: [{done}/{total}] {pct:.1f}% | ✅ 通过: {passed} | ❌ 失败: {failed} ", end="", flush=True)

            if not is_running and done >= total and total > 0:
                print("\n\n🎉 测试执行已顺利完成！")
                failed_cases = [r for r in st.get("results", []) if r.get("status") == "FAILED"]
                if failed_cases:
                    print(f"⚠️ 发现 {len(failed_cases)} 项失败用例:")
                    for fc in failed_cases:
                        print(f"   - [{fc.get('test_id')}] {fc.get('name')}: {fc.get('error')}")
                else:
                    print("✅ 全量用例 100% 验收通过！")
                break

            if not is_running and done == 0:
                print("\n⚠️ 引擎已处于空闲状态。")
                break

            time.sleep(1.5)


def cmd_status(args):
    res = http_req("/api/status", base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("status") == "error":
        print(f"❌ 查询失败: {res.get('message')}")
        sys.exit(1)

    is_running = res.get("is_running", False)
    total = res.get("total_count", 0)
    passed = res.get("passed_count", 0)
    failed = res.get("failed_count", 0)

    print("==================================================")
    print(f"🏥 HIS 自动化测试平台运行状态: {'[🟢 正在运行中]' if is_running else '[⚪ 空闲/已完成]'}")
    print("==================================================")
    print(f"• 总测试项: {total}")
    print(f"• 成功通过: {passed}")
    print(f"• 异常失败: {failed}")
    if total > 0:
        pass_rate = (passed / total) * 100
        print(f"• 综合通过率: {pass_rate:.1f}%")

    results = res.get("results", [])
    failed_cases = [r for r in results if r.get("status") == "FAILED"]
    if failed_cases:
        print("\n⚠️ 失败用例清单:")
        for fc in failed_cases:
            print(f"  ❌ [{fc.get('test_id')}] {fc.get('name')}")
            if fc.get("error"):
                print(f"     原因: {fc.get('error')}")
    elif total > 0:
        print("\n✅ 所有已运行测试用例全部通过！")


def cmd_stop(args):
    res = http_req("/api/stop", method="POST", base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"🛑 已下发终止指令: {res.get('message', 'ok')}")


def cmd_workstations(args):
    res = http_req("/api/workstations", base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    wss = res.get("workstations", [])
    print("🏥 六大业务工作站质检矩阵:")
    print("----------------------------------------------------------------------")
    print(f"{'代码':<22} | {'工作站名称':<14} | {'总用例':<6} | {'通过':<6} | {'失败':<6} | {'状态'}")
    print("----------------------------------------------------------------------")
    for ws in wss:
        code = ws.get("code", "")
        name = ws.get("name", "")
        tot = ws.get("tests_count", 0)
        p = ws.get("passed_count", 0)
        f = ws.get("failed_count", 0)
        st = "✅ 正常" if f == 0 and p > 0 else ("⚠️ 存在异常" if f > 0 else "⚪ 未执行")
        print(f"{code:<22} | {name:<14} | {tot:<8} | {p:<8} | {f:<8} | {st}")
    print("----------------------------------------------------------------------")


def cmd_rules(args):
    if args.id:
        endpoint = f"/api/rules/{args.id}/verify"
    else:
        endpoint = "/api/rules/verify_all"

    res = http_req(endpoint, method="POST", base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("status") == "error":
        print(f"❌ 规则校验失败: {res.get('message')}")
        sys.exit(1)

    print("🛡️ 全院核心临床与业务规则校验报告:")
    print("==================================================")
    stats = res.get("stats", {})
    if stats:
        print(f"• 规则总数: {stats.get('total', 16)} 条")
        print(f"• 住院域规则: {stats.get('inpatient_count', 0)} 条 | 门诊域规则: {stats.get('outpatient_count', 0)} 条")
        print(f"• 强阻断规则: {stats.get('block_count', 0)} 条 | 弱预警规则: {stats.get('warn_count', 0)} 条")
        print(f"• 校验结果: ✅ 通过 {stats.get('passed_count', 0)} / ❌ 失败 {stats.get('failed_count', 0)}")
    print("--------------------------------------------------")

    results = res.get("results", [])
    for r in results:
        rid = r.get("rule_id", "")
        name = r.get("name", "")
        st = r.get("status", "")
        icon = "✅" if st == "PASSED" else "❌"
        print(f"{icon} [{rid}] {name} ➔ {st}")


def cmd_switch_role(args):
    payload = {"role_code": args.role}
    if args.dept:
        payload["dept_code"] = args.dept

    res = http_req("/api/validator/switch_identity", method="POST", payload=payload, base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("status") == "error":
        print(f"❌ 身份切换失败: {res.get('message')}")
        sys.exit(1)

    print(f"🎭 浏览器测试身份已成功切换至: 【{args.role}】 (科室: {args.dept or '默认'})")


def cmd_logs(args):
    endpoint = f"/api/logs?source={args.source}&limit={args.limit}"
    res = http_req(endpoint, base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    lines = res.get("lines", [])
    print(f"📜 系统底层日志 [{args.source}.log] 最近 {len(lines)} 行:")
    print("--------------------------------------------------")
    for line in lines:
        print(line)


def cmd_diagnose(args):
    res = http_req("/api/environment/test_connectivity", method="POST", base_url=args.url)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    print("🩺 目标系统网络与数据库连通性诊断:")
    print("--------------------------------------------------")
    print(f"状态: {res.get('status')}")
    details = res.get("details", res.get("message", "无"))
    print(f"详情: {details}")


# =========================================================================
# 主入口与参数解析
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="HIS WebRunner CLI - 自动化测试平台终端命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python cli_agent.py run                           # 触发全院全量测试
  python cli_agent.py run -w PHARMACY --watch       # 运行药房工作站测试并实时监视进度
  python cli_agent.py status                        # 查看当前测试执行进度与通过率
  python cli_agent.py rules                         # 校验全院 16 条业务规则
  python cli_agent.py switch-role -r PHARMACIST     # 切换浏览器会话身份为药剂师
  python cli_agent.py logs -n 30                    # 查看最近 30 行测试系统日志
  python cli_agent.py --json status                 # 输出结构化 JSON 格式数据供 AI 解析
        """
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help=f"HIS WebRunner API 基地址 (默认: {DEFAULT_BASE_URL})")
    parser.add_argument("--json", action="store_true", help="以标准 JSON 格式输出结果 (供 Agent 或 CI 工具链解析)")

    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # 1. run
    p_run = subparsers.add_parser("run", help="启动自动化测试")
    p_run.add_argument("-m", "--mode", choices=["ALL", "INVASIVE", "NON_INVASIVE"], default="ALL", help="测试模式 (默认: ALL)")
    p_run.add_argument("-w", "--workstation", choices=["INPATIENT_DOCTOR", "OUTPATIENT_DOCTOR", "PHARMACY", "OUTPATIENT_BILLING", "INPATIENT_BILLING", "INPATIENT_NURSE"], help="指定六大工作站之一")
    p_run.add_argument("--head", action="store_true", help="有头模式启动（弹出真实浏览器窗口，默认无头静默）")
    p_run.add_argument("--watch", action="store_true", help="实时轮询监视直到测试任务执行完毕")
    p_run.set_defaults(func=cmd_run)

    # 2. status
    p_status = subparsers.add_parser("status", help="获取测试运行状态与通过率统计")
    p_status.set_defaults(func=cmd_status)

    # 3. stop
    p_stop = subparsers.add_parser("stop", help="终止当前测试任务")
    p_stop.set_defaults(func=cmd_stop)

    # 4. workstations
    p_ws = subparsers.add_parser("workstations", help="查看六大工作站测试矩阵")
    p_ws.set_defaults(func=cmd_workstations)

    # 5. rules
    p_rules = subparsers.add_parser("rules", help="校验全院业务规则")
    p_rules.add_argument("--id", help="指定规则ID (如 rule_01_antibiotics)，默认校验全部 16 条")
    p_rules.set_defaults(func=cmd_rules)

    # 6. switch-role
    p_role = subparsers.add_parser("switch-role", help="置换测试浏览器身份角色")
    p_role.add_argument("-r", "--role", required=True, choices=["INPATIENT_DOCTOR", "OUTPATIENT_DOCTOR", "PHARMACIST", "NURSE", "CHARGER"], help="目标角色")
    p_role.add_argument("-d", "--dept", help="目标科室代码 (可选)")
    p_role.set_defaults(func=cmd_switch_role)

    # 7. logs
    p_logs = subparsers.add_parser("logs", help="查看持久化日志")
    p_logs.add_argument("-s", "--source", choices=["app", "test_engine", "rules"], default="app", help="日志源 (默认: app)")
    p_logs.add_argument("-n", "--limit", type=int, default=50, help="行数 (默认: 50)")
    p_logs.set_defaults(func=cmd_logs)

    # 8. diagnose
    p_diag = subparsers.add_parser("diagnose", help="诊断系统网络与服务连通性")
    p_diag.set_defaults(func=cmd_diagnose)

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
