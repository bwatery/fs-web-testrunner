# -*- coding: utf-8 -*-
"""
fs_runner.report.json_writer
============================
测试报告 JSON 写入器。
"""
import json
from pathlib import Path
from typing import Any, Dict, List
from ..core.result import LoopResult


def write_json_report(results: List[LoopResult], out_path: Path, meta: Dict[str, Any]) -> None:
    """写入标准闭环报告 JSON。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r.status == "通过"),
            "fail": sum(1 for r in results if r.status == "失败"),
            "unexecuted": sum(1 for r in results if r.status == "未执行"),
        },
        "results": [
            {
                "case_id": r.case_id,
                "title": r.title,
                "status": r.status,
                "note": r.note,
                "evidence": r.evidence,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
