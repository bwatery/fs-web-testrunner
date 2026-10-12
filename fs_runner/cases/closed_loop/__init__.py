# -*- coding: utf-8 -*-
"""
fs_runner.cases.closed_loop
===========================
闭环真实验证用例集。
"""
from .closed_loop import (
    Ctx,
    LoopResult,
    run,
    supported_cases,
    _oracle_conn,
    _FLOWS,
    UI_SUPPORTED_CASES,
)

__all__ = [
    "Ctx",
    "LoopResult",
    "run",
    "supported_cases",
    "_oracle_conn",
    "_FLOWS",
    "UI_SUPPORTED_CASES",
]
