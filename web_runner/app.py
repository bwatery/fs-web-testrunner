"""
FastAPI Backend Application Entry Point.
Modular application architecture adhering to clean enterprise and big-tech patterns.
Mounts feature routers, static assets, and manages application lifecycles.
"""

import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.web_runner.state import ws_manager
from fs_web_testrunner.web_runner.routers import (
    tests_router,
    rules_router,
    validator_router,
    system_router,
    ws_router,
)

logger = get_logger("app")

def create_app() -> FastAPI:
    """Application factory for HIS WebRunner Dashboard."""
    application = FastAPI(
        title="HIS WebRunner - 医院信息系统全栈自动化测试平台",
        description="基于 Chrome CDP、REST API 与 Oracle 数据库的多模态自动化验收与规则治理平台",
        version="2.0.0",
        servers=[{"url": "http://127.0.0.1:8989", "description": "HIS WebRunner 本地执行引擎"}]
    )

    static_dir = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include modular feature routers
    application.include_router(tests_router)
    application.include_router(rules_router)
    application.include_router(validator_router)
    application.include_router(system_router)
    application.include_router(ws_router)

    @application.on_event("startup")
    async def on_startup():
        loop = asyncio.get_running_loop()
        ws_manager.set_loop(loop)
        logger.info("HIS WebRunner backend initialized successfully")

    @application.get("/", response_class=HTMLResponse)
    async def get_index():
        index_path = static_dir / "index.html"
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

    return application

app = create_app()
