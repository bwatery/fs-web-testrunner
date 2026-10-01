"""
Test Suites & Execution Router.
Handles test catalog discovery, batch test triggers, AI silent verification, and runner control.
"""

import threading
from typing import Dict, List, Optional, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.web_runner.state import engine, normalize_category

router = APIRouter(tags=["tests"])
logger = get_logger("tests")

class RunRequest(BaseModel):
    selected_ids: Optional[List[str]] = None
    headless: bool = False
    url: Optional[str] = None
    login_mode: str = "B"  # "A" (Auto) or "B" (Manual)
    username: Optional[str] = None
    password: Optional[str] = None
    mode: Optional[str] = "ALL"  # "ALL", "INVASIVE", or "NON_INVASIVE"
    workstation: Optional[str] = None  # Workstation code or name

@router.get("/api/tests")
async def get_tests():
    """List all registered test cases with categorization, workstation, and execution mode."""
    res = []
    inv_count = 0
    non_inv_count = 0
    for test_id, meta in engine.registry.items():
        mode = meta.get("mode", "NON_INVASIVE")
        if mode == "INVASIVE":
            inv_count += 1
        else:
            non_inv_count += 1
        
        clean_cat = normalize_category(meta.get("category", ""), test_id)
        res.append({
            "id": test_id,
            "name": meta["name"],
            "category": clean_cat,
            "raw_category": meta.get("category", ""),
            "mode": mode,
            "workstation": meta.get("workstation"),
            "workstation_code": meta.get("workstation_code"),
            "description": meta.get("description", "")
        })
    return {
        "status": "ok",
        "tests": res,
        "total": len(res),
        "invasive_count": inv_count,
        "non_invasive_count": non_inv_count
    }

@router.get("/api/status")
async def get_status():
    """Get current test runner status and latest execution results."""
    return {
        "is_running": engine._is_running,
        "results": [
            {
                "test_id": r.test_id,
                "name": r.name,
                "category": normalize_category(r.category, r.test_id),
                "raw_category": r.category,
                "mode": r.mode,
                "status": r.status,
                "workstation": getattr(r, "workstation", None),
                "workstation_code": getattr(r, "workstation_code", None),
                "duration_ms": r.duration_ms,
                "error": r.error_message,
                "screenshot_path": r.screenshot_path,
                "screenshot_b64": r.screenshot_b64,
                "logs": r.logs
            }
            for r in engine.results
        ]
    }

@router.post("/api/run")
async def run_tests_endpoint(req: RunRequest):
    """Start running tests in background worker thread with mode & workstation filtering."""
    if engine._is_running:
        logger.warning("Rejected run request: tests already running")
        return JSONResponse(status_code=400, content={"error": "测试任务已在运行中"})
    
    engine.headless = req.headless
    engine.login_mode = req.login_mode
    engine.username = req.username or ""
    engine.password = req.password or ""
    raw_ids = req.selected_ids or list(engine.registry.keys())
    target_url = req.url
    mode_filter = req.mode or "ALL"
    workstation_filter = req.workstation

    # Calculate filtered target_ids
    filtered_ids = list(raw_ids)
    if workstation_filter and workstation_filter.upper() != "ALL":
        wf = workstation_filter.upper()
        filtered_ids = [
            tid for tid in filtered_ids
            if (
                str(engine.registry.get(tid, {}).get("workstation_code") or "").upper() == wf
                or str(engine.registry.get(tid, {}).get("workstation") or "") == workstation_filter
                or workstation_filter in engine.registry.get(tid, {}).get("category", "")
            )
        ]
    if mode_filter and mode_filter.upper() in ["INVASIVE", "NON_INVASIVE"]:
        filtered_ids = [
            tid for tid in filtered_ids
            if engine.registry.get(tid, {}).get("mode", "NON_INVASIVE") == mode_filter.upper()
        ]

    logger.info(f"Triggering execution: {len(filtered_ids)} cases, mode={mode_filter}, workstation={workstation_filter}, headless={req.headless}")

    def _worker():
        try:
            engine.run_tests(
                filtered_ids,
                target_url=target_url,
                mode_filter=mode_filter,
                workstation_filter=workstation_filter
            )
        except Exception as e:
            logger.error(f"Error during background test execution: {e}", exc_info=True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {
        "status": "ok",
        "message": "已启动测试执行",
        "mode": mode_filter,
        "workstation": workstation_filter,
        "target_count": len(filtered_ids),
        "headless": req.headless
    }

@router.post("/api/ai/verify")
async def ai_verify_endpoint():
    """
    Dedicated AI code verification endpoint.
    Executes all non-invasive tests silently without touching the browser.
    Returns structured pass/fail results.
    """
    if engine._is_running:
        return JSONResponse(status_code=400, content={"error": "测试任务已在运行中"})

    non_inv_ids = [tid for tid, meta in engine.registry.items() if meta.get("mode") == "NON_INVASIVE"]
    logger.info(f"AI Silent Verification requested for {len(non_inv_ids)} non-invasive cases")
    results = engine.run_tests(selected_ids=non_inv_ids, mode_filter="NON_INVASIVE")
    passed = [r for r in results if r.status == "PASSED"]
    failed = [r for r in results if r.status == "FAILED"]
    logger.info(f"AI Verification finished: {len(passed)} passed, {len(failed)} failed")
    return {
        "status": "SUCCESS" if len(failed) == 0 else "FAIL",
        "total": len(results),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "failures": [
            {"test_id": f.test_id, "name": f.name, "error": f.error_message}
            for f in failed
        ],
        "summary": f"AI静默验证完成: {len(passed)}/{len(results)} 通过"
    }

@router.post("/api/stop")
async def stop_tests():
    """Stop currently running tests."""
    logger.info("Stop tests requested by user")
    engine.stop()
    return {"status": "ok", "message": "已发送停止请求"}

@router.post("/api/open_browser")
async def open_browser_endpoint():
    """Launch or bring to front a visible Chrome window directly without disrupting current page."""
    def _open():
        try:
            if not engine.browser or not engine.browser.is_alive():
                from fs_web_testrunner.core.browser_driver import BrowserDriver
                engine.browser = BrowserDriver(headless=False)
                engine.browser.start("http://192.168.1.198:8088/#/login")
            else:
                engine.browser.bring_to_front()
        except Exception as e:
            logger.error(f"Failed to launch Chrome browser: {e}", exc_info=True)

    threading.Thread(target=_open, daemon=True).start()
    return {"status": "ok", "message": "已在桌面置顶 Chrome 浏览器窗口"}
