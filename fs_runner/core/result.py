# -*- coding: utf-8 -*-
"""
fs_runner.core.result
=====================
测试结果模型。
扩充支持结构化规则断言、遵循规则聚合与未归规则断言计数。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LoopResult:
    """闭环验证单项结果。"""
    case_id: str
    title: str
    status: str = "PENDING"        # 通过 / 失败 / 未执行 / 阻塞 / 跳过
    note: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    unmapped_assertions_count: int = 0

    def assert_rule(
        self,
        rule_id: str,
        lhs: Any,
        op: str,
        rhs: Any,
        sides: Dict[str, Any],
        desc: str = "",
        tolerance: float = 1e-6,
    ) -> bool:
        """执行结构化规则断言并自动归档至 assertions 列表。"""
        from .assertions import execute_assert_rule
        return execute_assert_rule(
            result_obj=self,
            rule_id=rule_id,
            lhs=lhs,
            op=op,
            rhs=rhs,
            sides=sides,
            desc=desc,
            tolerance=tolerance,
        )

    @property
    def rules_followed(self) -> List[str]:
        """从已执行的断言中动态聚合遵循规则列表（保持确定性排序）。"""
        if not self.assertions:
            return []
        return sorted(list({a["rule"] for a in self.assertions if "rule" in a}))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为对外暴露的结构化结果字典。"""
        # 如果未通过 assert_rule 绑定任何规则，且存在非空判定（老裸断言阶段），未归规则数默认为 1
        unmapped = self.unmapped_assertions_count
        if not self.assertions and self.status in ("通过", "失败", "阻塞"):
            unmapped = max(unmapped, 1)

        d = {
            "case_id": self.case_id,
            "title": self.title,
            "status": self.status,
            "note": self.note,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
            "断言": self.assertions,
            "遵循规则": self.rules_followed,
            "未归规则断言数": unmapped,
        }
        # 同时将聚合的遵循规则回写进 evidence（满足 Hook A2 要求）
        if self.rules_followed and "遵循规则" not in self.evidence:
            self.evidence["遵循规则"] = self.rules_followed
        return d
