# -*- coding: utf-8 -*-
"""
verify
======
验证层兼容转发薄壳。
闭环真校验核心逻辑已搬迁至 fs_runner.cases.closed_loop。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fs_runner.cases.closed_loop import closed_loop  # noqa: F401
except ImportError:
    from fs_web_testrunner.fs_runner.cases.closed_loop import closed_loop  # noqa: F401
