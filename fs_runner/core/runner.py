# -*- coding: utf-8 -*-
"""
fs_runner.core.runner
=====================
统一测试执行器骨架。
"""
from typing import Callable, List, Optional
from .result import LoopResult


class TestRunner:
    """用例执行器。"""

    def __init__(self, env: str = "real"):
        self.env = env

    def run_suite(self, suite_name: str, selected: Optional[List[str]] = None) -> List[LoopResult]:
        """按套件执行。"""
        if suite_name == "closed-loop":
            from ..cases.closed_loop import run, supported_cases
            from ..config import GATEWAY_URL
            cases = selected or supported_cases()
            return run(cases, gateway=GATEWAY_URL, admin_token="")
        return []
