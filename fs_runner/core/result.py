# -*- coding: utf-8 -*-
"""
fs_runner.core.result
=====================
测试结果模型。
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LoopResult:
    """闭环验证单项结果。"""
    case_id: str
    title: str
    status: str = "PENDING"        # 通过 / 失败 / 未执行 / 阻塞 / 跳过
    note: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
