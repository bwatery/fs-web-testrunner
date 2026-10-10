# -*- coding: utf-8 -*-
"""
fs_runner.selfcheck · 自检与扩展变异承重分析。

继承并固化 tools/mutation_selfcheck_ext.py 的四类扰动能力：
    1. 数值   → +1
    2. 日期   → +1 天
    3. 标志位 → '0'/'1' 翻转
    4. 字符串 → 追加 '~MUT' 哨兵后缀（主外键列含 'ID' 者跳过）
    5. 布尔/None → 保持原值

结果同时写入时间戳归档与固定路径产物：
    - reports/verify/mutation_latest.json
    - reports/verify/协作产出/mutation_latest.json
    - reports/verify/协作产出/mutation_ext_{ts}.json
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import oracledb
import requests

from .config import GATEWAY_URL, ROOT_DIR, VERIFY_DIR
from .cases.closed_loop import closed_loop as cl

_REAL_CONNECT = oracledb.connect
SENTINEL = "~MUT"


def _mutate_value(col_name: str, val: Any) -> Any:
    """按列名 + 值类型决定怎么扰动。列名含 ID 的一律不动（主外键改了会直接报 ORA 或关联中断）。"""
    if "ID" in col_name or val is None or isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val + 1
    if isinstance(val, datetime.datetime):
        return val + datetime.timedelta(days=1)
    if isinstance(val, datetime.date):
        return val + datetime.timedelta(days=1)
    if isinstance(val, str):
        s = val.strip()
        if s in ("0", "1"):              # 标志位翻转
            return "1" if s == "0" else "0"
        if not s:
            return val
        return val + SENTINEL
    return val


class MutatingCursor:
    """在游标取数时透明实施内存级扰动，绝不污染真实 Oracle 库。"""
    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _row(self, row):
        if row is None or not self._raw.description:
            return row
        out = list(row)
        for i, (desc, v) in enumerate(zip(self._raw.description, row)):
            out[i] = _mutate_value(str(desc[0]).upper(), v)
        return tuple(out)

    def fetchone(self):
        return self._row(self._raw.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._raw.fetchall()]

    def fetchmany(self, size=None):
        rows = self._raw.fetchmany(size) if size is not None else self._raw.fetchmany()
        return [self._row(r) for r in rows]

    def __iter__(self):
        for r in self._raw:
            yield self._row(r)


class MutatingConnection:
    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def cursor(self, *a, **k):
        return MutatingCursor(self._raw.cursor(*a, **k))


def run_mutation_selfcheck(gateway: Optional[str] = None) -> int:
    """执行扩展变异自检，回答「通过率是否虚高、断言是否真正承重」并落盘固定产物。"""
    gw = (gateway or GATEWAY_URL).rstrip("/")
    login_url = f"{gw}/login"
    try:
        lr = requests.post(login_url, json={"username": "admin", "password": "admin123"}, timeout=20)
        token = lr.json().get("data")
        if not token:
            print(f"[错误] 无法获取登录令牌: {lr.text[:120]}")
            return 2
    except Exception as e:
        print(f"[错误] 无法连接网关 {login_url}: {e}")
        return 2

    cases = cl.supported_cases()
    print("=" * 76)
    print("  FS.TestRunner · 扩展变异自检（断言承重与防空跑检验）")
    print("=" * 76)
    print(f"  网关      : {gw}")
    print(f"  用例范围  : 共 {len(cases)} 条闭环用例")
    print("  扰动策略  : 非 ID 列内存级扰动（数值+1 / 日期+1天 / '0'-'1'翻转 / 字符串加~MUT）")
    print("  测试目的  : 验证断言是否敏感（🔴变红=承重；🟢仍绿=不敏感/或同表两列自洽）")
    print("-" * 76)

    oracledb.connect = lambda *a, **k: MutatingConnection(_REAL_CONNECT(*a, **k))
    mark = {"通过": "GREEN", "失败": "RED  ", "未执行": "SKIP "}
    try:
        results = cl.run(
            cases, gw, token,
            progress=lambda i, n, r: print(f"  [{i:02d}/{n:02d}] {mark.get(r.status, '?')} {r.case_id} -> {r.status}"),
        )
    finally:
        oracledb.connect = _REAL_CONNECT          # 坚决还原原生连接

    red = [r for r in results if r.status == "失败"]
    green = [r for r in results if r.status == "通过"]
    skip = [r for r in results if r.status == "未执行"]

    print("=" * 76)
    print(f"  🔴 变红（断言承重，捕获到扰动）: {len(red)} 条")
    print(f"  🟢 仍绿（断言未红，需审计成因）  : {len(green)} 条")
    print(f"  ⚪ 未执行（无数据/门禁前置阻断）: {len(skip)} 条")
    print("-" * 76)

    print("  🔴 变红清单（样本断言承重）：")
    for r in red:
        print(f"     {r.case_id:9} {(r.note or '')[:60]}")

    print("\n  🟢 仍绿清单（在本次四类扰动下未变红）：")
    for r in green:
        print(f"     {r.case_id:9} {(r.note or '')[:60]}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir_collab = Path(VERIFY_DIR) / "协作产出"
    out_dir_collab.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gateway": gw,
        "method": "库侧扰动：非ID列 数值+1 / 日期+1天 / '0'-'1'翻转 / 字符串加后缀~MUT",
        "total": len(cases),
        "summary": {
            "red_weight_bearing": len(red),
            "green_insensitive": len(green),
            "skipped": len(skip),
        },
        "red": [{"case_id": r.case_id, "title": r.title, "note": (r.note or "")[:200],
                 "evidence_sample": {k: v for k, v in (r.evidence.items() if isinstance(r.evidence, dict) else {})} if isinstance(r.evidence, dict) else {}} for r in red],
        "green": [{"case_id": r.case_id, "title": r.title, "note": (r.note or "")[:200],
                   "evidence_sample": {k: v for k, v in (r.evidence.items() if isinstance(r.evidence, dict) else {})} if isinstance(r.evidence, dict) else {}} for r in green],
        "skipped": [{"case_id": r.case_id, "title": r.title, "note": (r.note or "")[:200],
                     "evidence": r.evidence} for r in skip],
    }

    raw_json = json.dumps(report_payload, ensure_ascii=False, indent=2)

    # 固定路径产物
    p_stamp = out_dir_collab / f"mutation_ext_{ts}.json"
    p_latest1 = Path(VERIFY_DIR) / "mutation_latest.json"
    p_latest2 = out_dir_collab / "mutation_latest.json"

    p_stamp.write_text(raw_json, encoding="utf-8")
    p_latest1.write_text(raw_json, encoding="utf-8")
    p_latest2.write_text(raw_json, encoding="utf-8")

    print(f"\n[产出] 变异自检报告已落盘：")
    print(f"  - 固定主入口: {p_latest1}")
    print(f"  - 协作固定产出: {p_latest2}")
    print(f"  - 历史归档: {p_stamp}")
    return 0


def run_selfcheck(args) -> int:
    """自检子命令入口。"""
    if getattr(args, "mutation", False):
        return run_mutation_selfcheck(getattr(args, "gateway", None))
    print("请指定自检模式，例如: python -m fs_runner selfcheck --mutation")
    return 1
