# -*- coding: utf-8 -*-
"""
tools/mutation_selfcheck.py
===========================
任务 U · 反向验证（变异自检）独立脚本

目标：
在不碰生产/测试数据库、不修改任何业务代码与断言的前提下，
通过动态包装 Oracle DB-API 驱动（oracledb.connect），对游标返回的所有
非 ID 数值列注入 +1 扰动，实测闭环用例集的敏感度：
- 变红（失败） -> 证明断言对数据库数值差异高度敏感，非恒真摆设 ✓
- 仍然绿（通过） -> 证明该用例的断言未受数据库数值扰动影响，列为重点关注清单

原则与禁令：
- 不修改 verify/ 下的任何文件；
- 必须基于 cursor.description 的列名过滤，跳过含 "ID" 的主外键列，防止查不到数据导致的假崩溃；
- 运行完毕后自动解除 Monkey Patch，恢复真实环境。
"""

import json
import os
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oracledb
import requests
from verify import closed_loop as cl

GATEWAY = "http://192.168.1.198:8081"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

_REAL_CONNECT = oracledb.connect


class MutatingCursor:
    """包装游标：拦截 fetchone/fetchall/fetchmany/__iter__，对非 ID 数值列统一 +1 变异。"""

    def __init__(self, raw_cursor):
        self._raw = raw_cursor

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _mutate_row(self, row):
        if row is None or not self._raw.description:
            return row
        mutated = list(row)
        for idx, (col_desc, val) in enumerate(zip(self._raw.description, row)):
            col_name = str(col_desc[0]).upper()
            # 规则：跳过列名含 "ID" 的列（主键、外键、字典代码等）
            if "ID" in col_name:
                continue
            # 其余数值列一律加 1（包含 int 与 float，兼容金额、数量、统计计数值）
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                mutated[idx] = val + 1
        return tuple(mutated)

    def fetchone(self):
        row = self._raw.fetchone()
        return self._mutate_row(row)

    def fetchall(self):
        rows = self._raw.fetchall()
        return [self._mutate_row(r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._raw.fetchmany(size) if size is not None else self._raw.fetchmany()
        return [self._mutate_row(r) for r in rows]

    def __iter__(self):
        for row in self._raw:
            yield self._mutate_row(row)


class MutatingConnection:
    """包装连接：接管 cursor() 方法，返回 MutatingCursor。"""

    def __init__(self, raw_conn):
        self._raw = raw_conn

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def cursor(self, *args, **kwargs):
        c = self._raw.cursor(*args, **kwargs)
        return MutatingCursor(c)


def patch_oracle():
    """挂载变异驱动。"""
    def _patched_connect(*args, **kwargs):
        real_conn = _REAL_CONNECT(*args, **kwargs)
        return MutatingConnection(real_conn)

    oracledb.connect = _patched_connect
    print("[变异驱动] 已成功挂载：所有非 ID 数值列将被自动注入 +1 扰动")


def unpatch_oracle():
    """卸载变异驱动，恢复真实数据库交互。"""
    oracledb.connect = _REAL_CONNECT
    print("[变异驱动] 已成功卸载：恢复原生数据库连接")


def login_admin():
    r = requests.post(f"{GATEWAY}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=15)
    data = r.json()
    if data.get("code") != 200 or not data.get("data"):
        raise RuntimeError(f"网关登录失败: {data}")
    return data["data"]


def run_mutation_check():
    print("=" * 70)
    print("  任务 U · 闭环用例变异自检（Mutation Testing）")
    print("=" * 70)

    token = login_admin()
    cases = cl.supported_cases()
    print(f"  本次待测闭环用例共 {len(cases)} 条")

    # 1. 挂载变异驱动
    patch_oracle()

    mutated_results = []
    red_cases = []      # 变红（变异检测成功，断言敏感）
    green_cases = []    # 仍然绿（未受扰动影响，需重点分析）
    skipped_cases = []  # 未执行

    def _progress(i, total, r):
        mark = {"通过": "🟢", "失败": "🔴", "未执行": "⚪"}.get(r.status, "?")
        print(f"  [{i:02d}/{total:02d}] {mark} {r.case_id} {r.title} -> {r.status}")
        if r.status == "失败":
            print(f"        ↳ 触发断言捕获: {r.note[:140]}")

    try:
        results = cl.run(cases, GATEWAY, token, progress=_progress)
        for r in results:
            item = {
                "case_id": r.case_id,
                "title": r.title,
                "status": r.status,
                "note": r.note,
                "duration_ms": r.duration_ms,
            }
            mutated_results.append(item)
            if r.status == "失败":
                red_cases.append(item)
            elif r.status == "通过":
                green_cases.append(item)
            else:
                skipped_cases.append(item)
    finally:
        # 2. 无论发生何种异常，务必坚决卸载 Patch，防止测试污染！
        unpatch_oracle()

    # 3. 输出汇总统计
    print("\n" + "─" * 70)
    print("  变异自检完成汇总：")
    print(f"  🔴 变红（断言敏锐捕获数值异常）: {len(red_cases)} 条")
    print(f"  🟢 仍绿（未受数值扰动影响）    : {len(green_cases)} 条")
    print(f"  ⚪ 未执行                      : {len(skipped_cases)} 条")
    print("─" * 70)

    # 4. 生成报告数据
    out_dir = ROOT / "reports" / "verify" / "协作产出"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = out_dir / f"mutation_check_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(cases),
            "red_count": len(red_cases),
            "green_count": len(green_cases),
            "skipped_count": len(skipped_cases),
            "red_cases": red_cases,
            "green_cases": green_cases,
            "skipped_cases": skipped_cases,
        }, f, ensure_ascii=False, indent=2)
    print(f"  JSON 原始日志已保存至: {report_json}")

    return {
        "total": len(cases),
        "red": red_cases,
        "green": green_cases,
        "skipped": skipped_cases,
        "report_json": str(report_json),
    }


if __name__ == "__main__":
    run_mutation_check()
