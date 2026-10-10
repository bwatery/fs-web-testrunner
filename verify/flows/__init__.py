# -*- coding: utf-8 -*-
"""
并行协作口子：每个模块/每个 AI 把自己的用例放成 `verify/flows/<模块名>.py`，
在文件里导出：

    FLOWS = {"L5-001": flow_L5_001, "L5-002": flow_L5_002}

`closed_loop.py` 会自动把这些注册进来，**不用改公共文件**，所以多人/多 AI 并行不会互相冲突。

约定：
- 每个 flow 的签名是 `(ctx: Ctx) -> LoopResult`，和 `closed_loop.py` 里现有的完全一样
- 需要 Oracle 就用 `from ..closed_loop import _oracle_conn`；需要 camelCase 转换用 `_order_camel`
- 只读的用例优先；写入类必须自己收尾（净零），收尾失败要如实判失败
- 项目没有测试库回滚，**别用"猜"的断言**——断言必须能失败，否则就是假通过
"""

import importlib
import os
import pkgutil
from typing import Any, Dict


def collect() -> Dict[str, Any]:
    """扫描本包下所有模块，合并它们的 FLOWS 字典。"""
    merged: Dict[str, Any] = {}
    pkg_dir = os.path.dirname(__file__)
    for m in pkgutil.iter_modules([pkg_dir]):
        if m.name.startswith("_") or m.name == "collect":
            continue
        try:
            mod = importlib.import_module(f"{__package__}.{m.name}")
        except Exception as e:                      # 某个模块写坏了，不能拖垮整条流水线
            print(f"[flows] 跳过 {m.name}: {type(e).__name__}: {e}")
            continue
        flows = getattr(mod, "FLOWS", None)
        if not isinstance(flows, dict):
            continue
        for cid, fn in flows.items():
            if cid in merged:
                print(f"[flows] 用例 {cid} 被 {m.name} 重复注册，已忽略后者")
                continue
            merged[cid] = fn
    return merged
