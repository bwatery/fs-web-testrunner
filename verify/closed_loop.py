# -*- coding: utf-8 -*-
"""
verify.closed_loop 兼容转发薄壳
===============================
所有闭环真校验逻辑已重构搬迁至 fs_runner.cases.closed_loop.closed_loop
保留本文件以兼容旧入口（run_verify.py --closed-loop、tools/collect.py 等）。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import fs_runner.cases.closed_loop.closed_loop as _target
    from fs_runner.cases.closed_loop.closed_loop import *  # noqa: F401, F403
    from fs_runner.cases.closed_loop.closed_loop import (  # noqa: F401
        Ctx,
        LoopResult,
        _oracle_conn,
        _FLOWS,
        supported_cases,
        run,
    )
except ImportError:
    import fs_web_testrunner.fs_runner.cases.closed_loop.closed_loop as _target
    from fs_web_testrunner.fs_runner.cases.closed_loop.closed_loop import *  # noqa: F401, F403
    from fs_web_testrunner.fs_runner.cases.closed_loop.closed_loop import (  # noqa: F401
        Ctx,
        LoopResult,
        _oracle_conn,
        _FLOWS,
        supported_cases,
        run,
    )

sys.modules[__name__] = _target
