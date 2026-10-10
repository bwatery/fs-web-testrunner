# -*- coding: utf-8 -*-
"""
fs_runner.browser.trace
=======================
UI 失败现场追踪与回放包生成器（Playwright trace / replay 等价自研物）：
当界面断言失败或变异断言触发时，自动打包：
1. DOM 实时快照 (dom.html: document.documentElement.outerHTML)
2. 浏览器控制台日志 (console.json: Runtime.consoleAPICalled + Log.entryAdded)
3. 网络请求与响应日志 (network.json: Network.* 请求流与状态码)
4. 路由与视口状态 (route.json: location.href / location.hash / document.title)
5. 现场视口截图 (screenshot.png)
6. 诊断元信息 (meta.json)
落盘目录：reports/verify/ui_traces/<case_id>_<timestamp>/
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import ROOT_DIR
from .cdp import BrowserSession


TRACES_DIR = ROOT_DIR / "reports" / "verify" / "ui_traces"


def save_ui_trace_package(
    session: BrowserSession,
    case_id: str,
    note: str = "",
    evidence: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    抓取当前浏览器的完整执行现场包并落盘，返回生成目录路径。
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    clean_cid = case_id.replace(" ", "_").replace("/", "_")
    trace_dir = TRACES_DIR / f"{clean_cid}_{ts}"
    trace_dir.mkdir(parents=True, exist_ok=True)

    # 1. 抓取 DOM 快照
    dom_html = ""
    try:
        dom_html = session.eval("document.documentElement ? document.documentElement.outerHTML : ''") or ""
    except Exception as e:
        dom_html = f"<!-- 抓取 DOM 异常: {e} -->"
    dom_file = trace_dir / "dom.html"
    dom_file.write_text(dom_html, encoding="utf-8")

    # 2. 抓取路由与页面信息
    route_info = {}
    try:
        route_info = session.eval("""(() => ({
            href: window.location.href,
            origin: window.location.origin,
            pathname: window.location.pathname,
            hash: window.location.hash,
            title: document.title,
            readyState: document.readyState
        }))()""") or {}
    except Exception as e:
        route_info = {"error": str(e)}
    route_file = trace_dir / "route.json"
    route_file.write_text(json.dumps(route_info, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. 抓取与格式化控制台日志
    console_logs: List[Dict[str, Any]] = []
    try:
        for ev in getattr(session, "history_events", []):
            method = ev.get("method", "")
            params = ev.get("params", {})
            if method == "Runtime.consoleAPICalled":
                c_type = params.get("type", "log")
                args = params.get("args", [])
                text_parts = []
                for a in args:
                    if "value" in a:
                        text_parts.append(str(a["value"]))
                    elif "description" in a:
                        text_parts.append(str(a["description"]))
                console_logs.append({
                    "source": "console",
                    "type": c_type,
                    "text": " ".join(text_parts),
                    "timestamp": params.get("timestamp", time.time()),
                    "stackTrace": params.get("stackTrace"),
                })
            elif method == "Log.entryAdded":
                entry = params.get("entry", {})
                console_logs.append({
                    "source": entry.get("source", "browser"),
                    "type": entry.get("level", "info"),
                    "text": entry.get("text", ""),
                    "url": entry.get("url", ""),
                    "timestamp": entry.get("timestamp", time.time()),
                })
    except Exception as e:
        console_logs.append({"type": "error", "text": f"解析控制台日志异常: {e}"})

    if not console_logs:
        console_logs.append({"type": "info", "text": "会话期间未捕获到 console 异常或报错", "timestamp": time.time()})

    console_file = trace_dir / "console.json"
    console_file.write_text(json.dumps(console_logs, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. 抓取与聚合网络请求日志
    network_map: Dict[str, Dict[str, Any]] = {}
    try:
        for ev in getattr(session, "history_events", []):
            method = ev.get("method", "")
            params = ev.get("params", {})
            req_id = params.get("requestId")
            if not req_id:
                continue

            item = network_map.setdefault(req_id, {
                "requestId": req_id,
                "url": "",
                "method": "",
                "status": None,
                "type": "",
                "duration_ms": 0,
                "failed": False,
                "failureReason": "",
            })

            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                item["url"] = req.get("url", "")
                item["method"] = req.get("method", "")
                item["type"] = params.get("type", "")
                item["wallTime"] = params.get("wallTime", time.time())
            elif method == "Network.responseReceived":
                resp = params.get("response", {})
                item["status"] = resp.get("status")
                item["mimeType"] = resp.get("mimeType", "")
                if not item["url"]:
                    item["url"] = resp.get("url", "")
            elif method == "Network.loadingFailed":
                item["failed"] = True
                item["failureReason"] = params.get("errorText", "")
    except Exception as e:
        pass

    network_list = list(network_map.values())
    network_file = trace_dir / "network.json"
    network_file.write_text(json.dumps(network_list, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. 抓取现场视口截图
    shot_file = trace_dir / "screenshot.png"
    shot_saved = False
    try:
        session.screenshot(shot_file)
        shot_saved = True
    except Exception as e:
        shot_file.write_text(f"screenshot error: {e}", encoding="utf-8")

    # 6. 生成诊断元信息 meta.json
    meta = {
        "case_id": case_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
        "route": route_info,
        "screenshot_saved": shot_saved,
        "dom_bytes": len(dom_html.encode("utf-8")),
        "console_entries_count": len(console_logs),
        "network_requests_count": len(network_list),
        "evidence": evidence or {},
        "files": [
            "meta.json",
            "dom.html",
            "route.json",
            "console.json",
            "network.json",
            "screenshot.png" if shot_saved else None,
        ],
    }
    meta["files"] = [f for f in meta["files"] if f]
    meta_file = trace_dir / "meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return trace_dir
