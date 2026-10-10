# -*- coding: utf-8 -*-
"""
fs_runner.rules.scanner
=======================
静态 AST 代码扫描与断言-规则关联分析引擎：
1. 扫描全部 Flow 代码中的 assert_rule 调用，提取 (case_id, rule_id, desc, file, lineno)。
2. 校验断言引用的规则 ID 是否存在于 YAML 规则库（不存在时带文件+行号精确定位报错）。
3. 统计规则引用覆盖率（规则总数、被引用数、未被引用数清单）。
4. 统计暴露未归规则断言数（裸断言计数，按用例列出）。
5. 提供反向点名能力：输入规则 ID，列出引用它的所有断言（用例编号、人话描述、文件+行号）。
"""
import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import ROOT_DIR
from .registry import registry


CASES_DIRS = [
    ROOT_DIR / "fs_runner" / "cases",
]


class AssertionInfo:
    def __init__(self, case_id: str, rule_id: str, desc: str, file_path: Path, lineno: int):
        self.case_id = case_id
        self.rule_id = rule_id
        self.desc = desc
        self.file_path = file_path
        self.lineno = lineno
        self.location = f"{self.file_path.name}:{self.lineno}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "rule_id": self.rule_id,
            "desc": self.desc,
            "file": str(self.file_path.relative_to(ROOT_DIR)).replace("\\", "/"),
            "lineno": self.lineno,
            "location": f"{self.file_path.name}:{self.lineno}",
        }


def _extract_string_value(node: Optional[ast.AST]) -> Optional[str]:
    """提取 AST 节点的常量字符串值或变量名标识。"""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def scan_all_assertions() -> List[AssertionInfo]:
    """遍历扫描所有 Flow 代码中调用的 assert_rule。"""
    assertions: List[AssertionInfo] = []

    for cdir in CASES_DIRS:
        if not cdir.exists():
            continue
        for py_path in cdir.glob("**/*.py"):
            try:
                content = py_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_path))
            except Exception:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                func_name = node.name
                case_id = ""
                if func_name.startswith("flow_"):
                    case_id = func_name[5:].replace("_", "-")

                for subnode in ast.walk(node):
                    if not isinstance(subnode, ast.Call):
                        continue
                    # 匹配 res.assert_rule(...) 或 self.assert_rule(...)
                    is_assert_call = False
                    if isinstance(subnode.func, ast.Attribute) and subnode.func.attr == "assert_rule":
                        is_assert_call = True

                    if not is_assert_call:
                        continue

                    # 提取 rule_id (第1个参数)
                    rule_id = ""
                    if subnode.args:
                        rule_id = _extract_string_value(subnode.args[0]) or ""
                    else:
                        for kw in subnode.keywords:
                            if kw.arg == "rule_id":
                                rule_id = _extract_string_value(kw.value) or ""

                    # 提取 desc
                    desc = ""
                    for kw in subnode.keywords:
                        if kw.arg == "desc":
                            desc = _extract_string_value(kw.value) or ""
                    if not desc and len(subnode.args) >= 6:
                        desc = _extract_string_value(subnode.args[5]) or ""

                    if rule_id:
                        assertions.append(AssertionInfo(
                            case_id=case_id or "UNKNOWN",
                            rule_id=rule_id,
                            desc=desc,
                            file_path=py_path,
                            lineno=subnode.lineno,
                        ))

    return assertions


def check_assertions_and_rules() -> Dict[str, Any]:
    """执行三条硬校验并生成审计报告。"""
    registry.ensure_loaded()
    all_yaml_rules = registry.rules
    scanned = scan_all_assertions()

    # 1. 校验引用的 rule_id 必须存在于 YAML
    invalid_citations: List[Dict[str, Any]] = []
    for a in scanned:
        if a.rule_id not in all_yaml_rules:
            invalid_citations.append({
                "rule_id": a.rule_id,
                "case_id": a.case_id,
                "file": str(a.file_path.relative_to(ROOT_DIR)).replace("\\", "/"),
                "lineno": a.lineno,
                "location": f"{a.file_path.name}:{a.lineno}",
                "desc": a.desc,
            })

    # 2. 统计引用覆盖
    cited_rules = {a.rule_id for a in scanned if a.rule_id in all_yaml_rules}
    uncited_rules = sorted(list(set(all_yaml_rules.keys()) - cited_rules))

    # 3. 统计裸断言（未归规则断言）
    # 获取全部支持的闭环用例
    try:
        from ..cases.closed_loop import _FLOWS
        all_cases = sorted(list(_FLOWS.keys()))
    except Exception:
        all_cases = []

    cases_with_assertions = {a.case_id for a in scanned}
    unmapped_cases: Dict[str, int] = {}
    for cid in all_cases:
        if cid not in cases_with_assertions:
            # 尚未接入 assert_rule 的老用例，算作含 1 处裸断言
            unmapped_cases[cid] = 1

    return {
        "total_rules": len(all_yaml_rules),
        "total_assertions": len(scanned),
        "cited_rules_count": len(cited_rules),
        "uncited_rules_count": len(uncited_rules),
        "uncited_rules": uncited_rules,
        "invalid_citations": invalid_citations,
        "unmapped_cases": unmapped_cases,
        "assertions": scanned,
    }


def find_assertions_for_rule(rule_id: str) -> List[Dict[str, Any]]:
    """反向点名：给定规则 ID，查出所有引用它的具体断言信息。"""
    scanned = scan_all_assertions()
    out = []
    for a in scanned:
        if a.rule_id == rule_id:
            out.append(a.to_dict())
    return out


def generate_ids_file(out_path: Optional[Path] = None) -> Path:
    """根据 YAML 规则库自动生成 fs_runner/rules/ids.py 常量文件。"""
    registry.ensure_loaded()
    target = out_path or (ROOT_DIR / "fs_runner" / "rules" / "ids.py")
    rules = sorted(list(registry.rules.keys()))
    convs = [r for r in rules if r.startswith("CONV_")]
    b_rules = [r for r in rules if not r.startswith("CONV_")]

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "fs_runner.rules.ids",
        "===================",
        "规则与测试口径 ID 常量定义。",
        "由 `python -I fsrun.py rules --gen-ids` 自动生成与同步。",
        "硬约束：所有 flow 代码必须直接引用此处常量，严禁手写字面量字符串，",
        "拼错当场报 ImportError，杜绝静默失效。",
        '"""',
        "",
        "# ===========================================================================",
        "# 测试口径（Conventions）",
        "# ===========================================================================",
    ]
    for c in convs:
        lines.append(f'{c} = "{c}"')
    lines.extend([
        "",
        "# ===========================================================================",
        "# 业务规则（Business Rules）",
        "# ===========================================================================",
    ])
    for b in b_rules:
        lines.append(f'{b} = "{b}"')
    lines.extend([
        "",
        "ALL_RULE_IDS = {",
    ])
    for r in rules:
        lines.append(f"    {r},")
    lines.append("}\n")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target

