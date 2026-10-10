# -*- coding: utf-8 -*-
"""
fs_runner.rules.registry
========================
规则库装载器、双向反查表生成器与依赖分析器。
"""
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from ..config import ROOT_DIR
from .models import Rule, validate_rule_dict


RULES_DIR = ROOT_DIR / "rules"
BUSINESS_RULES_FILE = RULES_DIR / "business_rules.yaml"
CONVENTIONS_FILE = RULES_DIR / "conventions.yaml"


class RuleRegistry:
    """规则库集中管理器，提供 Schema 校验与双向反查能力。"""

    def __init__(self, rules_dir: Optional[Path] = None):
        self.rules_dir = rules_dir or RULES_DIR
        self.rules: Dict[str, Rule] = {}
        self.rules_by_case: Dict[str, List[Rule]] = {}
        self.cases_by_rule: Dict[str, List[str]] = {}
        self.code_declared_by_case: Dict[str, Set[str]] = {}
        self.load_errors: List[str] = []
        self._loaded = False

    def load(self, reload: bool = False) -> "RuleRegistry":
        if self._loaded and not reload:
            return self

        self.rules.clear()
        self.rules_by_case.clear()
        self.cases_by_rule.clear()
        self.code_declared_by_case.clear()
        self.load_errors.clear()

        # 1. 载入并严格校验 rules/business_rules.yaml
        b_file = self.rules_dir / "business_rules.yaml"
        if b_file.exists():
            self._load_yaml_file(b_file)
        else:
            self.load_errors.append(f"业务规则文件不存在: {b_file}")

        # 2. 载入并严格校验 rules/conventions.yaml
        c_file = self.rules_dir / "conventions.yaml"
        if c_file.exists():
            self._load_yaml_file(c_file)
        else:
            self.load_errors.append(f"测试口径文件不存在: {c_file}")

        # 3. 收集 Flow 与套件代码中显式声明的 requires_rules
        self._collect_flow_declared_rules()

        # 4. 构建双向索引
        self._build_indices()
        self._loaded = True
        return self

    def _load_yaml_file(self, file_path: Path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or []
            if not isinstance(content, list):
                self.load_errors.append(f"[{file_path.name}] 根结构必须是 YAML 列表")
                return

            for item in content:
                rule = validate_rule_dict(item, source_file=file_path.name)
                if rule.id in self.rules:
                    self.load_errors.append(f"规则 ID 重复: {rule.id} (出现在 {file_path.name})")
                self.rules[rule.id] = rule
        except Exception as e:
            self.load_errors.append(f"解析规则文件 {file_path.name} 失败: {e}")

    def _collect_flow_declared_rules(self):
        """扫描 closed_loop 模块及 suite_rules 下所有用例声明的 requires_rules。"""
        self.code_declared_by_case.clear()
        try:
            from ..cases.closed_loop import _FLOWS
            for case_id, fn in _FLOWS.items():
                declared = getattr(fn, "requires_rules", None)
                if declared is not None:
                    self.code_declared_by_case[case_id] = set(declared)
        except Exception as e:
            self.load_errors.append(f"收集闭环用例 requires_rules 异常: {e}")

        try:
            from ..cases.suite_rules import SUITE_RULES
            for case_id, r_list in SUITE_RULES.items():
                self.code_declared_by_case.setdefault(case_id, set()).update(r_list)
        except Exception:
            pass

    def validate_bidirectional_consistency(self) -> List[str]:
        """双向一致性硬校验：

        YAML 中规则的 affected_cases ↔ 代码 Flow / 套件中的 requires_rules 必须 100% 对齐。
        任何一边有多出或遗漏，立即返回错误列表阻断流水线。
        """
        self.ensure_loaded()
        errors: List[str] = []

        # 1. 检查代码引用的规则是否存在于 YAML 规则库中
        for cid, r_set in self.code_declared_by_case.items():
            for rid in r_set:
                if rid not in self.rules:
                    errors.append(f"代码用例 [{cid}] 声明了未在 YAML 规则库中登记的规则 ID: '{rid}'")

        # 2. 收集 YAML 侧反向映射：case -> set of rule_ids
        yaml_case_rules: Dict[str, Set[str]] = {}
        for rid, rule in self.rules.items():
            for cid in rule.affected_cases:
                yaml_case_rules.setdefault(cid, set()).add(rid)

        # 3. 双向严格对称比对
        all_cases = set(self.code_declared_by_case.keys()) | set(yaml_case_rules.keys())
        for cid in sorted(all_cases):
            code_rules = self.code_declared_by_case.get(cid, set())
            yaml_rules = yaml_case_rules.get(cid, set())
            if code_rules != yaml_rules:
                diffs = []
                in_yaml_not_code = yaml_rules - code_rules
                in_code_not_yaml = code_rules - yaml_rules
                if in_yaml_not_code:
                    diffs.append(f"YAML 声明了该规则影响此用例，但代码 Flow 未声明依赖（YAML 多 / 代码少）: {sorted(in_yaml_not_code)}")
                if in_code_not_yaml:
                    diffs.append(f"代码 Flow 声明依赖该规则，但 YAML 未将其列入 affected_cases（代码多 / YAML 漏）: {sorted(in_code_not_yaml)}")
                errors.append(f"用例 [{cid}] 规则依赖双向不一致：{'；'.join(diffs)}")

        return errors

    def _build_indices(self):
        """建立两套反查索引：用例 -> 规则列表，规则 -> 用例列表。"""
        self.rules_by_case.clear()
        self.cases_by_rule.clear()

        for rid, rule in self.rules.items():
            self.cases_by_rule[rid] = sorted(list(set(rule.affected_cases)))
            for cid in rule.affected_cases:
                self.rules_by_case.setdefault(cid, []).append(rule)

        # 排序保持确定性
        for cid in self.rules_by_case:
            self.rules_by_case[cid].sort(key=lambda r: r.id)
            self.rules_by_case[cid].sort(key=lambda r: r.id)

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        self.ensure_loaded()
        return self.rules.get(rule_id)

    def get_rules_for_case(self, case_id: str) -> List[Rule]:
        self.ensure_loaded()
        return self.rules_by_case.get(case_id, [])

    def get_cases_for_rule(self, rule_id: str) -> List[str]:
        self.ensure_loaded()
        return self.cases_by_rule.get(rule_id, [])

    def all_rules(self) -> List[Rule]:
        self.ensure_loaded()
        return sorted(self.rules.values(), key=lambda r: (r.domain, r.id))

    def ensure_loaded(self):
        if not self._loaded:
            self.load()

    def cross_reference_summary(self) -> Dict[str, Any]:
        """导出全量反查表。"""
        self.ensure_loaded()
        return {
            "total_rules": len(self.rules),
            "confirmed_rules": sum(1 for r in self.rules.values() if r.status == "confirmed"),
            "suspected_rules": sum(1 for r in self.rules.values() if r.status == "suspected"),
            "total_associated_cases": len(self.rules_by_case),
            "case_to_rules": {
                cid: [r.to_dict() for r in rlist]
                for cid, rlist in self.rules_by_case.items()
            },
            "rule_to_cases": dict(self.cases_by_rule),
        }


# 全局单例注册表
registry = RuleRegistry()
