# -*- coding: utf-8 -*-
"""
fs_runner.rules.cli
===================
规则库 CLI 子命令实现：Schema 校验、双向反查、死配置扫描。
"""
import json
import sys
from typing import Any

from .lint import scan_dead_configs, scan_sampling_violations
from .registry import registry


def run_rules_command(args: Any) -> int:
    """执行 rules 子命令分发。"""
    # 1. 装载并严格校验
    registry.load(reload=True)

    if registry.load_errors:
        print("❌ 规则库加载或 Schema 校验失败：")
        for err in registry.load_errors:
            print(f"  - {err}")
        return 1

    consistency_errors = registry.validate_bidirectional_consistency()
    if consistency_errors:
        print(f"❌ 规则库与用例双向一致性校验失败（发现 {len(consistency_errors)} 处漂移）：")
        for err in consistency_errors:
            print(f"  - {err}")
        return 1

    # 反查指定用例：用例 -> 规则
    if getattr(args, "case", None):
        cid = str(args.case).strip()
        rules = registry.get_rules_for_case(cid)
        print("─" * 66)
        print(f"  【用例 ➔ 规则反查】用例: {cid}（共依赖 {len(rules)} 条规则/口径）")
        print("─" * 66)
        if not rules:
            print(f"  未查到用例 {cid} 显式关联的业务规则或测试口径。")
        else:
            for r in rules:
                status_mark = "🟢 [confirmed 已证实]" if r.status == "confirmed" else "🟡 [suspected 存疑/推测]"
                print(f"\n  📌 [{r.id}] ({r.domain}) {status_mark}")
                print(f"     规则断言 : {r.statement}")
                print(f"     实测证据 : {r.evidence}")
                print(f"     发现日期 : {r.discovered} | 来源: {r.source_file}")
                print(f"     受影响用例: {', '.join(r.affected_cases)}")
        return 0

    # 反查指定规则：规则 -> 用例
    if getattr(args, "rule", None):
        rid = str(args.rule).strip()
        rule = registry.get_rule(rid)
        print("─" * 66)
        print(f"  【规则 ➔ 用例反查】规则 ID: {rid}")
        print("─" * 66)
        if not rule:
            print(f"  未找到规则 ID: {rid}")
            return 1
        status_mark = "🟢 [confirmed 已证实]" if rule.status == "confirmed" else "🟡 [suspected 存疑/推测]"
        print(f"  领域分类 : {rule.domain}")
        print(f"  确证状态 : {status_mark}")
        print(f"  规则声明 : {rule.statement}")
        print(f"  实测证据 : {rule.evidence}")
        print(f"  发现日期 : {rule.discovered} | 来源文件: {rule.source_file}")
        print(f"\n  受影响用例清单 ({len(rule.affected_cases)} 条)：")
        for cid in sorted(rule.affected_cases):
            print(f"    - {cid}")
        return 0

    # 死配置扫描与采样抽查
    if getattr(args, "lint", False) or getattr(args, "dead_config", False):
        source = getattr(args, "source", None) or getattr(args, "snapshot", None) or "db"
        src_label = "历史快照" if str(source).lower() == "snapshot" or str(source).endswith(".json") else "当前真实数据库"
        print("─" * 66)
        print(f"  【规则库与配置自动化审计】死配置扫描 ({src_label}) + 采样规范抽查")
        print("─" * 66)
        dead = scan_dead_configs(source=source)
        if dead:
            print(f"\n❌ [死配置扫描] 发现 {len(dead)} 处死配置违规：")
            for d in dead:
                print(f"   • {d['message']}")
        else:
            print(f"\n✅ [死配置扫描] 未发现无条件兜底前置死配置（数据源: {src_label}）。")

        sampling = scan_sampling_violations()
        if sampling:
            print(f"\n⚠️  [采样规范抽查] 发现 {len(sampling)} 处潜在采样风险：")
            for s in sampling:
                print(f"   • {s['message']}")
        else:
            print("\n✅ [采样规范抽查] 闭环用例未发现盲目采样。")
        return 1 if dead else 0

    # JSON 导出
    if getattr(args, "json", False):
        data = registry.cross_reference_summary()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    # 列表展示
    if getattr(args, "list", False):
        rules = registry.all_rules()
        print("─" * 78)
        print(f"  FS.TestRunner 全量规则库清单（共 {len(rules)} 条）")
        print("─" * 78)
        print(f"  {'ID':<30} {'领域':<8} {'状态':<11} {'用例数':<6} 声明")
        print("  " + "-" * 74)
        for r in rules:
            st = "confirmed" if r.status == "confirmed" else "suspected"
            print(f"  {r.id:<30} {r.domain:<8} {st:<11} {len(r.affected_cases):<6} {r.statement[:35]}")
        return 0

    # 默认执行 Schema 校验
    summary = registry.cross_reference_summary()
    print("─" * 66)
    print("  FS.TestRunner 业务规则库与测试口径 Schema 校验")
    print("─" * 66)
    print(f"  ✅ Schema 校验全部通过！")
    print(f"  - 规则总数     : {summary['total_rules']} 条")
    print(f"  - 已证实规则   : {summary['confirmed_rules']} 条 (confirmed)")
    print(f"  - 存疑/推测规则: {summary['suspected_rules']} 条 (suspected)")
    print(f"  - 关联用例数   : {summary['total_associated_cases']} 条")
    print("\n  用法提示：")
    print("    python -I fsrun.py rules --case L9-011       # 反查用例依赖的规则")
    print("    python -I fsrun.py rules --rule RULE_PHA_DISPENSE_PRIORITY  # 反查规则约束的用例")
    print("    python -I fsrun.py rules --dead-config      # 运行死配置扫描")
    print("    python -I fsrun.py rules --list             # 列出全部规则")
    return 0
