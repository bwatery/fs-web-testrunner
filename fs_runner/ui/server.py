# -*- coding: utf-8 -*-
"""
fs_runner.ui.server
===================
自动化控制台 FastAPI 服务端：
1. 挂载 /static 与单页前端 index.html
2. 提供用例执行调度接口 (POST /api/run, POST /api/stop)
3. 提供 WebSocket /ws/run 实时推送日志流
4. 提供规则库、台账、审计产物只读接口
"""
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .data_provider import (
    get_closed_loop_cases,
    get_excel_cases,
    get_health_overview,
    get_log_files,
    get_rules_catalog,
    get_ui_verify_latest,
    read_file_content,
)
from .runner_bridge import runner_bridge

_ROOT = Path(__file__).resolve().parent.parent.parent
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_VERIFY_DIR = _ROOT / "reports" / "verify"

app = FastAPI(title="FS.TestRunner Web Console", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态资源
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
def index():
    """主控制台单页入口。"""
    index_file = _STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(index_file))


@app.get("/api/status")
def get_status():
    """获取当前执行快照与进度。"""
    return runner_bridge.get_status()


@app.get("/api/recent-logs")
def get_recent_logs():
    """获取最近日志流。"""
    return {"logs": runner_bridge.get_recent_logs(limit=100)}


@app.get("/api/cases")
def get_cases():
    """获取 66 条闭环用例及最新落盘结果。"""
    return get_closed_loop_cases()


@app.get("/api/excel-cases")
def get_excel():
    """获取 353 行生产台账。"""
    return get_excel_cases()


@app.get("/api/rules")
def get_rules():
    """获取 57 条只读业务规则与反查信息。"""
    return get_rules_catalog()


@app.get("/api/health")
def get_health():
    """获取体检总览大盘数据。"""
    return get_health_overview()


@app.get("/api/log-files")
def list_logs():
    """列出报告与审计文件。"""
    return get_log_files()


@app.get("/api/log-files/content")
def get_log_content(path: str = Query(...), download: int = Query(0)):
    """读取指定日志/审计文件内容。"""
    target = _ROOT / path
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # 路径安全防护：限制在 reports/verify
    try:
        target.relative_to(_VERIFY_DIR)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if download == 1:
        return FileResponse(str(target), filename=target.name)

    content = read_file_content(path)
    return {"path": path, "content": content}


@app.get("/api/ui-verify/latest")
def get_ui_latest():
    """获取最新界面巡检等式对账数据。"""
    return get_ui_verify_latest()


@app.post("/api/run")
async def trigger_run(payload: Dict[str, Any]):
    """
    触发测试执行：
    支持单条、多条、全部；支持环境模式选择；支持显示浏览器和慢放。
    """
    cases = payload.get("cases")
    env = payload.get("env", "real")
    show_browser = bool(payload.get("show_browser", False))
    slowmo = int(payload.get("slowmo", 0))
    is_ui_verify = bool(payload.get("is_ui_verify", False))

    ok, msg = runner_bridge.start_run(
        cases=cases,
        env=env,
        show_browser=show_browser,
        slowmo=slowmo,
        is_ui_verify=is_ui_verify,
    )
    return {"ok": ok, "msg": msg}


@app.post("/api/stop")
def trigger_stop():
    """真正杀死正在运行的测试进程树。"""
    ok, msg = runner_bridge.stop_run()
    return {"ok": ok, "msg": msg}


@app.websocket("/ws/run")
async def websocket_run_endpoint(ws: WebSocket):
    """
    实时流式日志与步骤事件推送通道。
    """
    await ws.accept()
    q = runner_bridge.register_listener()
    try:
        # 先补发最近 30 行历史日志
        for line in runner_bridge.get_recent_logs(limit=30):
            await ws.send_text(json.dumps({"type": "log", "data": line}))

        while True:
            item = await q.get()
            await ws.send_text(json.dumps(item))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        runner_bridge.unregister_listener(q)


def run_ui_server(host: str = "0.0.0.0", port: int = 8989):
    """启动控制台服务器。"""
    import uvicorn
    print("=" * 66)
    print(f"  FS.TestRunner · 自动化测试交互控制台")
    print(f"  服务地址  : http://127.0.0.1:{port}")
    print(f"  网络监听  : http://{host}:{port}")
    print(f"  只读报告站: http://127.0.0.1:8990 (若已启动)")
    print("=" * 66)
    uvicorn.run(app, host=host, port=port, log_level="info")
