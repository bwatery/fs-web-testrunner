# -*- coding: utf-8 -*-
"""
fs_runner.core.case
===================
用例模型与断言原语。
"""
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from .result import LoopResult


@dataclass
class TestCase:
    """用例定义。"""
    case_id: str
    title: str
    func: Optional[Callable] = None
    requires: List[str] = field(default_factory=list)
