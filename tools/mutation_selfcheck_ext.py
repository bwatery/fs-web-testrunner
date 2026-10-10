# -*- coding: utf-8 -*-
"""
扩展版变异自检 —— 回答「通过率是不是虚高」。

原版（`mutation_selfcheck.py`）**只扰动数值列**，所以只能证明"金额/数量类的断言是承重的"；
对**字符串 / 标志位 / 日期**类断言（文书名、签名人、ARCHIVE_FLAG、时间戳…）它**测不到** ——
"没变红"并不意味着断言有效。

本脚本把扰动扩展到四类：
    数值   → +1
    日期   → +1 天
    字符串 → '0'/'1' 翻转；其余追加哨兵后缀
    布尔/None → 不动

判定口径（重要）：
    🔴 变红 = 断言**注意到了**被改动的库值 → 这条用例的断言是"承重的"
    🟢 仍绿 = 断言**没注意到** → 这条用例的绿可能是装饰性的

⚠️ 方法学局限，读结论时必须带上：
  ① 仍是**只在库侧**扰动，所以"同行两列自洽"型断言（如 `金额 == 单价×数量`）
     在常数偏移下差值不变，测不出来 —— 这类会被**误列为"仍绿"**；
  ② 字符串扰动可能让按名字查找的流程查空，从而**误红**（把承重的说成不承重）——
     所以 **"仍绿"是更可靠的信号**，"变红"的数字偏乐观。
  ③ 这是**自检手段，不是测试结果**：变红的用例**不得**当成真缺陷。

用法：python -I tools/mutation_selfcheck_ext.py
"""
import datetime
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oracledb
import requests
from verify import closed_loop as cl

GATEWAY = "http://192.168.1.198:8081"
_REAL_CONNECT = oracledb.connect
SENTINEL = "~MUT"


def _mutate_value(col_name: str, val):
    """按列名 + 值类型决定怎么扰动。列名含 ID 的一律不动（主外键，改了会全盘崩）。"""
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


def main() -> int:
    token = requests.post(f"{GATEWAY}/login",
                          json={"username": "admin", "password": "admin123"},
                          timeout=20).json()["data"]
    cases = cl.supported_cases()
    print(f"待测用例 {len(cases)} 条；扰动：非 ID 列的 数值+1 / 日期+1天 / 0-1翻转 / 字符串加后缀")
    print("=" * 74)

    oracledb.connect = lambda *a, **k: MutatingConnection(_REAL_CONNECT(*a, **k))
    mark = {"通过": "GREEN", "失败": "RED  ", "未执行": "SKIP "}
    try:
        results = cl.run(cases, GATEWAY, token,
                         progress=lambda i, n, r: print(f"  [{i:02d}/{n:02d}] "
                                                        f"{mark.get(r.status, '?')} {r.case_id} -> {r.status}"))
    finally:
        oracledb.connect = _REAL_CONNECT          # 坚决还原

    red = [r for r in results if r.status == "失败"]
    green = [r for r in results if r.status == "通过"]
    skip = [r for r in results if r.status == "未执行"]

    print("=" * 74)
    print(f"  🔴 变红（断言承重）    : {len(red)} 条")
    print(f"  🟢 仍绿（断言没注意到）: {len(green)} 条   ← 这才是问题的答案")
    print(f"  ⚪ 未执行              : {len(skip)} 条")
    print()
    print("  ⚠️ 仍绿清单（这些用例的绿，在本次扰动下没有表现出任何敏感性）：")
    for r in green:
        print(f"     {r.case_id:9} {(r.note or '')[:56]}")
    print()
    print("  🔴 变红清单：")
    for r in red:
        print(f"     {r.case_id:9} {(r.note or '')[:56]}")

    out = ROOT / "reports" / "verify" / "协作产出" / f"mutation_ext_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "库侧扰动：非ID列 数值+1 / 日期+1天 / '0'-'1'翻转 / 字符串加后缀",
        "total": len(cases),
        "red": [{"case_id": r.case_id, "note": (r.note or "")[:200]} for r in red],
        "green": [{"case_id": r.case_id, "note": (r.note or "")[:200]} for r in green],
        "skipped": [r.case_id for r in skip],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  JSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
