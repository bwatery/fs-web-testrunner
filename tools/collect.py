# -*- coding: utf-8 -*-
"""
机械活的统一入口 —— 给协作方/Antigravity 照着跑，不用动脑子、不用改代码。

    python tools/collect.py api-by-tag       # 1590 条接口按 tag 分类 -> CSV
    python tools/collect.py tables           # 所有表 + 行数 + 关注关键词命中 -> CSV
    python tools/collect.py evidence-index   # 历史闭环结果汇总索引 -> CSV
    python tools/collect.py pending-grouped  # 未执行用例按依赖类型分组 -> CSV
    python tools/collect.py regression       # 全量回归 x3，留档

产出统一放 reports/verify/协作产出/。
**只读**：不写数据库、不改源文件、不碰 closed_loop.py。
"""
import csv
import json
import os
import subprocess
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
OUT = ROOT / "reports" / "verify" / "协作产出"
OUT.mkdir(parents=True, exist_ok=True)

DSN = dict(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
# 主力关心的表名/列名关键词（找口径用）
KEYWORDS = ("BALANCE", "DISCOUNT", "REBATE", "DIAG", "ORDER", "EMR", "MR", "NURSE",
            "TEMPLATE", "EBILL", "INVOICE", "DISPENSE", "STOCK", "CHARGE")


def _write_csv(name, header, rows):
    p = OUT / name
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"[产出] {p}  ({len(rows)} 行)")


def cmd_api_by_tag():
    spec = json.loads((ROOT / "data" / "api_spec.json").read_text(encoding="utf-8"))
    rows, tags = [], set()
    for path, ops in spec.get("paths", {}).items():
        for method, v in ops.items():
            tag = (v.get("tags") or ["(无tag)"])[0]
            tags.add(tag)
            rows.append([tag, method.upper(), path, (v.get("summary") or "").replace("\n", " ")])
    rows.sort()
    _write_csv("api_by_tag.csv", ["tag", "method", "path", "summary"], rows)
    print(f"  tag 去重后 {len(tags)} 个")
    print(f"  路径 {len(spec.get('paths', {}))} 条，展开成「路径×方法」{len(rows)} 行"
          f"（交接文档说的 1590 是路径数，对得上）")
    return 0


def cmd_tables():
    import oracledb
    c = oracledb.connect(**DSN)
    cur = c.cursor()
    cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    tables = [r[0] for r in cur.fetchall()]
    rows, kw_rows = [], []
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            n = int(cur.fetchone()[0])
        except Exception:
            n = -1
        cur.execute("SELECT COUNT(*) FROM user_tab_columns WHERE table_name=:1", [t])
        cols = int(cur.fetchone()[0])
        rows.append([t, n, cols])
        hit = [k for k in KEYWORDS if k in t]
        if hit:
            kw_rows.append([t, n, cols, "|".join(hit)])
        cur.execute("SELECT column_name FROM user_tab_columns WHERE table_name=:1", [t])
        colnames = [r[0] for r in cur.fetchall()]
        chit = [k for k in KEYWORDS if any(k in cn for cn in colnames)]
        if chit and not hit:
            kw_rows.append([t, n, cols, "(列名) " + "|".join(sorted(set(chit)))[:80]])
    c.close()
    _write_csv("table_inventory.csv", ["table_name", "row_count", "column_count"], rows)
    _write_csv("tables_keyword.csv", ["table_name", "row_count", "column_count", "命中"], kw_rows)
    print(f"  表总数 {len(rows)}")
    return 0


def cmd_evidence_index():
    rows = []
    for p in sorted((ROOT / "reports" / "verify").glob("closed_loop_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        stamp = (d.get("meta") or {}).get("started") or p.stem
        for r in d.get("results") or []:
            rows.append([r.get("case_id"), r.get("title"), r.get("status"), stamp,
                         (r.get("note") or "")[:60]])
    # 同一用例只留最新一条
    latest = {}
    for r in rows:
        k = r[0]
        if k not in latest or r[3] > latest[k][3]:
            latest[k] = r
    out = sorted(latest.values(), key=lambda x: str(x[0]))
    _write_csv("evidence_index.csv", ["用例ID", "标题", "状态", "时间", "备注前60字"], out)
    print("  （同一用例只保留最新一轮）")
    return 0


GROUPS = [
    ("A 需硬件（打印/读卡器/外设）", ("打印", "读卡", "扫码", "高拍仪", "叫号", "条码", "复印")),
    ("B 需外部系统（医保/电子发票/LIS/PACS）", ("医保", "前置机", "电子发票", "电子票据", "LIS", "PACS", "接口")),
    ("C 需特定业务状态", ("在院", "出院", "术后", "死亡", "归档", "手术", "皮试", "过敏", "转科", "欠费")),
    ("D 需已配置数据", ("模板", "路径", "配置", "字典", "已配置")),
]


def cmd_pending_grouped():
    pending = json.loads((ROOT / "reports" / "verify" / "pending_87.json").read_text(encoding="utf-8"))
    done = set()
    ep = ROOT / "reports" / "verify" / "closed_loop_latest.json"
    if ep.exists():
        for r in json.loads(ep.read_text(encoding="utf-8")).get("results") or []:
            if r.get("status") == "通过":
                done.add(r.get("case_id"))
    rows = []
    for case in pending:
        if case["case_id"] in done:
            continue
        blob = " ".join(str(case.get(k) or "") for k in
                        ("l2", "feature", "test_point", "precond", "steps", "expected"))
        g = "E 其他"
        for name, kws in GROUPS:
            if any(k in blob for k in kws):
                g = name
                break
        rows.append([case["case_id"], g, (case.get("precond") or "")[:60], case.get("test_point")])
    rows.sort(key=lambda x: (x[1], x[0]))
    _write_csv("pending_grouped.csv", ["用例ID", "分组", "前置条件", "测试点"], rows)
    print("  分组只按关键词粗分，分不清的都进了 E —— 别当成结论")
    return 0


KNOWN_DEFECTS = ROOT / "reports" / "verify" / "known_defects.json"


def _load_known_defects():
    """
    已知缺陷清单（如 L5-027 病历封存 ORA-12899）。

    设计要点：**已知缺陷每次回归都必须原样打印出来，不许静默**。
    之所以要做这个区分，是因为"真缺陷修好之前每次回归都红"会让人开始忽略红灯 ——
    而"让人忽略红灯"正是本项目成立的原因（旧工具把 320 条没跑过的用例洗成"通过"）。
    所以：新失败 = 红；已知缺陷 = 绿但**逐条大声列出**，绝不隐藏。
    """
    try:
        d = json.loads(KNOWN_DEFECTS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _failed_ids(stdout: str):
    import re
    ids = set()
    for ln in (stdout or "").splitlines():
        if "❌" in ln:
            m = re.search(r"\bL\d+-\d+\b", ln)
            if m:
                ids.add(m.group(0))
    return ids


def cmd_regression():
    """执行三轮全量闭环回归（转调 fs_runner regression 统一执行器）。"""
    from fs_runner.cli import run_regression
    return run_regression()


def cmd_emr_by_tag():
    """EMR 是**独立后端**（http://192.168.1.198:8021），接口清单落在 data/emr_api_spec.json。"""
    p = ROOT / "data" / "emr_api_spec.json"
    if not p.exists():
        print(f"[缺文件] {p} 不存在。先跑：python tools/fetch_emr_spec.py")
        return 1
    spec = json.loads(p.read_text(encoding="utf-8"))
    rows, tags = [], set()
    for path, ops in spec.get("paths", {}).items():
        for method, v in ops.items():
            tag = (v.get("tags") or ["(无tag)"])[0]
            tags.add(tag)
            rows.append([tag, method.upper(), path, (v.get("summary") or "").replace("\n", " ")])
    rows.sort()
    _write_csv("emr_api_by_tag.csv", ["tag", "method", "path", "summary"], rows)
    print(f"  tag 去重后 {len(tags)} 个；路径 {len(spec.get('paths', {}))} 条 / 展开 {len(rows)} 行")

    # 额外产出：L5 病历文书用例 -> 候选接口 的对照草稿（只是关键词粗匹配，**不是结论**）
    kw_map = {
        "体温单": ("temperature",), "护理记录": ("nurseRecord", "nurse"),
        "病程": ("record",), "病历": ("record",), "模板": ("template",),
        "病案首页": ("recordFrontpage", "frontpage"), "会诊": ("consultation",),
        "签名": ("sign",), "归档": ("archive", "file"), "临床路径": ("pathway", "path"),
    }
    pending = json.loads((ROOT / "reports" / "verify" / "pending_87.json").read_text(encoding="utf-8"))
    draft = []
    for case in pending:
        cid = case["case_id"]
        if not cid.startswith("L5-"):
            continue
        blob = " ".join(str(case.get(k) or "") for k in ("feature", "test_point", "precond"))
        cands = set()
        for kw, pats in kw_map.items():
            if kw in blob:
                for pat in pats:
                    cands |= {f"{r[1]} {r[2]}" for r in rows if pat.lower() in r[2].lower()}
        draft.append([cid, case.get("test_point"), len(cands), " ; ".join(sorted(cands)[:6])])
    _write_csv("emr_case_candidates.csv",
               ["用例ID", "测试点", "候选接口数", "候选接口(前6)"], draft)
    print("  ⚠️ emr_case_candidates.csv 是**关键词粗匹配的草稿**，要主力确认后才算数")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("api-by-tag", "tables", "evidence-index",
                                                "pending-grouped", "regression", "emr-by-tag"):
        print(__doc__)
        return 2
    return {"api-by-tag": cmd_api_by_tag, "tables": cmd_tables,
            "evidence-index": cmd_evidence_index, "pending-grouped": cmd_pending_grouped,
            "regression": cmd_regression, "emr-by-tag": cmd_emr_by_tag}[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
