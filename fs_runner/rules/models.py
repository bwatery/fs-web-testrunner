# -*- coding: utf-8 -*-
"""
fs_runner.rules.models
======================
规则库 Schema 模型与严格校验器。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List


VALID_STATUSES = {"confirmed", "suspected"}
REQUIRED_FIELDS = ["id", "domain", "statement", "evidence", "discovered", "status", "affected_cases"]


class RuleValidationError(ValueError):
    """规则 Schema 校验不通过错误。"""
    pass


@dataclass
class Rule:
    """系统业务规则 / 测试口径模型。"""
    id: str
    domain: str
    statement: str
    evidence: str
    discovered: str
    status: str
    affected_cases: List[str] = field(default_factory=list)
    source_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "statement": self.statement,
            "evidence": self.evidence,
            "discovered": self.discovered,
            "status": self.status,
            "affected_cases": self.affected_cases,
            "source_file": self.source_file,
        }


def validate_rule_dict(raw: Dict[str, Any], source_file: str = "") -> Rule:
    """严格校验规则字典结构，缺字段、缺 evidence、status 非法立即抛出异常。"""
    if not isinstance(raw, dict):
        raise RuleValidationError(f"[{source_file}] 规则条目必须是字典对象，实际获得: {type(raw)}")

    rule_id = str(raw.get("id") or "").strip()
    if not rule_id:
        raise RuleValidationError(f"[{source_file}] 缺失必填字段 'id' 或为空")

    for f in REQUIRED_FIELDS:
        if f not in raw:
            raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 缺失必填字段 '{f}'")

    domain = str(raw.get("domain") or "").strip()
    if not domain:
        raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 的 'domain' 字段不能为空")

    statement = str(raw.get("statement") or "").strip()
    if not statement:
        raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 的 'statement' 字段不能为空")

    # 硬约束：每条必须有 evidence，不许只有结论
    evidence = str(raw.get("evidence") or "").strip()
    if not evidence:
        raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 缺失实测证据 'evidence'（硬约束：不许只有结论）")

    discovered = str(raw.get("discovered") or "").strip()
    if not discovered:
        raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 的 'discovered' 字段不能为空")

    # 硬约束：status 必须区分 confirmed / suspected
    status = str(raw.get("status") or "").strip().lower()
    if status not in VALID_STATUSES:
        raise RuleValidationError(
            f"[{source_file}] 规则 {rule_id} 的 'status'='{status}' 无效！"
            f"必须严格为 {VALID_STATUSES} 之一（硬约束：推断规则不得当事实）"
        )

    affected_cases = raw.get("affected_cases")
    if not isinstance(affected_cases, list):
        raise RuleValidationError(f"[{source_file}] 规则 {rule_id} 的 'affected_cases' 必须为列表")

    cases_clean = [str(c).strip() for c in affected_cases if str(c).strip()]

    return Rule(
        id=rule_id,
        domain=domain,
        statement=statement,
        evidence=evidence,
        discovered=discovered,
        status=status,
        affected_cases=cases_clean,
        source_file=source_file,
    )
