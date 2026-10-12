# -*- coding: utf-8 -*-
"""
fs_runner.ui.data_provider
==========================
控制台数据提供层：
1. 闭环 66 条用例及最新运行结果（closed_loop_latest.json）
2. 353 行生产台账（HIS_EMR上线测试用例追踪表_合并版.xlsx）
3. 57 条规则与反查数据（rules/*.yaml）
4. 运行日志与造数审计清单（reports/verify/）
5. 界面巡检最新等式对账（ui_verify_latest.json）
"""
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
_VERIFY_DIR = _ROOT / "reports" / "verify"
_RULES_DIR = _ROOT / "rules"
_SCREENSHOTS_DIR = _VERIFY_DIR / "screenshots"
_EXCEL_PATH = Path(r"D:\workapp\ZJCK\HIS_EMR上线测试用例追踪表_合并版.xlsx")


def get_closed_loop_cases() -> Dict[str, Any]:
    """
    获取 66 条闭环用例定义及最新运行结果。
    """
    from ..cases.closed_loop.closed_loop import supported_cases, _CASE_TITLES

    all_ids = supported_cases()
    latest_file = _VERIFY_DIR / "closed_loop_latest.json"

    latest_data = {}
    if latest_file.exists():
        try:
            latest_data = json.loads(latest_file.read_text(encoding="utf-8"))
        except Exception:
            latest_data = {}

    # 读取界面巡检最新落盘数据，判定哪些用例具备真实界面断言
    ui_latest_file = _VERIFY_DIR / "ui_verify_latest.json"
    ui_covered_cases = set()
    if ui_latest_file.exists():
        try:
            ui_data = json.loads(ui_latest_file.read_text(encoding="utf-8"))
            for ur in ui_data.get("results", []):
                # 只有真实执行且具备有效断言的用例才算覆盖（排除未执行/虚构用例）
                if ur.get("status") == "未执行":
                    continue
                ucid = ur.get("case_id", "")
                m = re.match(r"^UI-(L\d+-\d+)", ucid)
                if m:
                    ui_covered_cases.add(m.group(1))
                elif ucid and not ucid.startswith("UI-INDEX"):
                    ui_covered_cases.add(ucid)
        except Exception:
            pass

    results_map = {}
    for r in latest_data.get("results", []):
        results_map[r.get("case_id")] = r

    cases_list = []
    for cid in all_ids:
        r = results_map.get(cid, {})
        title = r.get("title") or _CASE_TITLES.get(cid, "")
        status = r.get("status", "未执行")
        note = r.get("note", "")
        evidence = r.get("evidence", {})
        duration_ms = r.get("duration_ms", 0.0)

        # 区分是否命制造数闸门
        is_create_patient = cid in ("L6-001", "L6-009", "L6-012")

        # 严格按判定依据打标：命中界面巡检则为「接口+界面」，否则为「接口」
        has_ui = cid in ui_covered_cases
        verify_mode = "接口+界面" if has_ui else "接口"

        cases_list.append({
            "case_id": cid,
            "title": title,
            "status": status,
            "note": note,
            "evidence": evidence,
            "duration_ms": duration_ms,
            "is_create_patient": is_create_patient,
            "verify_mode": verify_mode,
        })

    ui_covered_count = sum(1 for c in cases_list if c["verify_mode"] == "接口+界面")

    summary = latest_data.get("summary", {
        "通过": sum(1 for c in cases_list if c["status"] == "通过"),
        "失败": sum(1 for c in cases_list if c["status"] == "失败"),
        "阻塞": sum(1 for c in cases_list if c["status"] == "阻塞"),
        "跳过": sum(1 for c in cases_list if c["status"] == "跳过"),
        "未执行": sum(1 for c in cases_list if c["status"] == "未执行"),
        "总计": len(cases_list),
    })
    summary["ui_covered_count"] = ui_covered_count

    return {
        "cases": cases_list,
        "summary": summary,
        "meta": latest_data.get("meta", {}),
    }


def get_excel_cases() -> List[Dict[str, Any]]:
    """
    读取 353 行生产台账 Excel。
    """
    if not _EXCEL_PATH.exists():
        return []

    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(_EXCEL_PATH), read_only=True, data_only=True)
        if "用例清单" not in wb.sheetnames:
            return []

        ws = wb["用例清单"]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h or "").strip() for h in rows[0]]
        items = []
        for r in rows[1:]:
            if not r or not any(r):
                continue
            item = {}
            for h, v in zip(headers, r):
                item[h] = "" if v is None else str(v).strip()
            if item.get("用例ID"):
                items.append(item)
        return items
    except Exception as e:
        print(f"[data_provider] 读取台账 Excel 失败: {e}")
        return []


def get_rules_catalog() -> Dict[str, Any]:
    """
    读取业务规则库 (business_rules.yaml + conventions.yaml) 57 条。
    """
    import yaml

    biz_path = _RULES_DIR / "business_rules.yaml"
    conv_path = _RULES_DIR / "conventions.yaml"

    rules = []
    stats = {"confirmed": 0, "suspected": 0, "total": 0}

    for path, kind in [(biz_path, "业务规则"), (conv_path, "测试口径")]:
        if not path.exists():
            continue
        try:
            docs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            if isinstance(docs, list):
                items = docs
            elif isinstance(docs, dict):
                items = docs.get("rules") or docs.get("conventions") or []
            else:
                items = []

            for item in items:
                status = item.get("status", "confirmed")
                if status == "confirmed":
                    stats["confirmed"] += 1
                else:
                    stats["suspected"] += 1
                stats["total"] += 1

                title = item.get("title") or item.get("statement", "").split("：")[0][:40]

                rules.append({
                    "id": item.get("id"),
                    "title": title,
                    "kind": kind,
                    "domain": item.get("domain", ""),
                    "status": status,
                    "statement": item.get("statement", ""),
                    "evidence": item.get("evidence", ""),
                    "affected_cases": item.get("affected_cases", []),
                })
        except Exception as e:
            print(f"[data_provider] 读取规则文件 {path.name} 失败: {e}")

    return {
        "rules": rules,
        "stats": stats,
    }


def get_log_files() -> List[Dict[str, Any]]:
    """
    列出 reports/verify 下的运行报告、审计文件和日志文件。
    """
    files = []
    for p in sorted(_VERIFY_DIR.glob("*.*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_dir() or p.name.startswith("ui_verify_"):
            continue
        if p.suffix in (".json", ".log", ".txt", ".md"):
            files.append({
                "name": p.name,
                "path": str(p.relative_to(_ROOT)).replace("\\", "/"),
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified": p.stat().st_mtime,
                "type": "audit" if "_created_" in p.name else ("report" if "closed_loop_" in p.name else "log"),
            })
    return files


def read_file_content(rel_path: str) -> Optional[str]:
    """
    安全读取文件内容。
    """
    target = _ROOT / rel_path
    if not target.exists() or not target.is_file():
        return None
    # 限制必须在 reports/verify 目录下
    try:
        target.relative_to(_VERIFY_DIR)
    except ValueError:
        return None

    return target.read_text(encoding="utf-8", errors="replace")


def get_ui_verify_latest() -> Dict[str, Any]:
    """
    获取最新界面巡检等式对账数据。
    """
    p = _VERIFY_DIR / "ui_verify_latest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_health_overview() -> Dict[str, Any]:
    """
    体检总览大盘数据。
    """
    closed = get_closed_loop_cases()
    rules = get_rules_catalog()
    ui = get_ui_verify_latest()

    # 提取已知真实缺陷 L5-027
    defect_l5_027 = next((c for c in closed["cases"] if c["case_id"] == "L5-027"), None)

    return {
        "closed_loop_summary": closed.get("summary", {}),
        "rule_stats": rules.get("stats", {}),
        "ui_summary": ui.get("summary", {}),
        "real_defect": defect_l5_027,
        "created_text": closed.get("meta", {}).get("created_text", "本次造数：净增 0 条"),
    }
