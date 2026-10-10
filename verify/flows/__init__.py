# -*- coding: utf-8 -*-
"""
verify.flows 兼容转发薄壳
=========================
所有 flows 逻辑已重构搬迁至 fs_runner.cases.closed_loop.flows
"""
import sys
import fs_runner.cases.closed_loop.flows as _target
from fs_runner.cases.closed_loop.flows import collect  # noqa: F401

sys.modules[__name__] = _target
