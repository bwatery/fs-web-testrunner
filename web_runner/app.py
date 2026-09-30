"""
FastAPI Backend for Google-style HIS & EMR Web TestRunner Dashboard.
Supports multi-module HIS testing, real-time WebSocket logging,
route health scans, XML inspection, and live screenshots.
"""

import asyncio
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from fs_web_testrunner.config import (
    EMR_DESIGNER_URL,
    EMR_BASE_URL,
    WEB_RUNNER_HOST,
    WEB_RUNNER_PORT
)
from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.business_rules_manager import BusinessRulesManager
from fs_web_testrunner.suites import register_all_suites

app = FastAPI(title="HIS WebRunner - 医院信息系统全栈自动化测试平台")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared Engine, Rules Manager & State
engine = TestEngine(headless=False)
register_all_suites(engine)
rules_mgr = BusinessRulesManager()
active_websockets: List[WebSocket] = []
current_loop = None

def broadcast_sync(msg: Dict[str, Any]):
    """Thread-safe event broadcast to all connected WebSocket clients."""
    global current_loop
    if not current_loop:
        return
    text = json.dumps(msg, ensure_ascii=False)
    for ws in list(active_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(text), current_loop)
        except Exception:
            pass

engine.subscribe(broadcast_sync)

class RunRequest(BaseModel):
    selected_ids: Optional[List[str]] = None
    headless: bool = False
    url: Optional[str] = None
    login_mode: str = "B"  # "A" (Auto) or "B" (Manual)
    username: Optional[str] = None
    password: Optional[str] = None
    mode: Optional[str] = "ALL"  # "ALL", "INVASIVE", or "NON_INVASIVE"

class EvalRequest(BaseModel):
    expression: str

class OrderSearchRequest(BaseModel):
    keyword: Optional[str] = ""
    classifyType: Optional[str] = "W"
    pageNum: Optional[int] = 1
    pageSize: Optional[int] = 10

class SwitchIdentityRequest(BaseModel):
    roleId: int
    deptId: int
    targetRoute: Optional[str] = ""


@app.on_event("startup")
async def on_startup():
    global current_loop
    current_loop = asyncio.get_running_loop()

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

def normalize_category(cat: str, test_id: str) -> str:
    """Map any technical/raw category into canonical 6 hospital business domains."""
    c = cat.lower()
    t = test_id.lower()
    if 'cpoe' in t or '医嘱' in cat or 'order' in t:
        return '📋 医嘱闭环'
    if '药房' in cat or '药库' in cat or 'pharmacy' in t or 'stock' in t or 'dispense' in t:
        return '💊 药房药库'
    if '门诊' in cat or 'outpatient' in t:
        return '🏥 门诊业务'
    if '住院' in cat or '护理' in cat or 'inpatient' in t or 'settle' in t or 'fee' in t or 'prepay' in t:
        return '🛏️ 住院业务'
    if '病历' in cat or '文本' in cat or '数值' in cat or '单选' in cat or '专用控件' in cat or '表达式' in cat or 'xml' in cat or 'emr' in t or 'text_' in t or 'num_' in t or 'choice_' in t or 'med_' in t or 'expr_' in t or 'xml_' in t:
        return '📝 电子病历'
    if 'oracle' in c or '接口' in c or '底座' in c or 'api_' in t or 'db_' in t or 'rule_' in t:
        return '🛡️ 系统底座'
    return '🛡️ 系统底座'

@app.get("/api/tests")
async def get_tests():
    """List all registered test cases with categorization and execution mode."""
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
            "mode": mode,
            "description": meta.get("description", "")
        })
    return {
        "status": "ok",
        "tests": res,
        "total": len(res),
        "invasive_count": inv_count,
        "non_invasive_count": non_inv_count
    }

@app.get("/api/status")
async def get_status():
    """Get current test runner status."""
    return {
        "is_running": engine._is_running,
        "results": [
            {
                "test_id": r.test_id,
                "name": r.name,
                "category": normalize_category(r.category, r.test_id),
                "mode": r.mode,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "error": r.error_message,
                "screenshot_path": r.screenshot_path,
                "screenshot_b64": r.screenshot_b64,
                "logs": r.logs
            }
            for r in engine.results
        ]
    }

@app.post("/api/run")
async def run_tests_endpoint(req: RunRequest):
    """Start running tests in background thread with mode filtering."""
    if engine._is_running:
        return JSONResponse(status_code=400, content={"error": "测试任务已在运行中"})
    
    engine.headless = req.headless
    engine.login_mode = req.login_mode
    engine.username = req.username or ""
    engine.password = req.password or ""
    target_ids = req.selected_ids or list(engine.registry.keys())
    target_url = req.url
    mode_filter = req.mode or "ALL"

    def _worker():
        engine.run_tests(target_ids, target_url=target_url, mode_filter=mode_filter)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {
        "status": "ok",
        "message": f"已启动测试执行",
        "mode": mode_filter,
        "target_count": len(target_ids),
        "headless": req.headless
    }

@app.post("/api/ai/verify")
async def ai_verify_endpoint():
    """
    Dedicated AI code verification endpoint.
    Executes all non-invasive tests silently without touching the browser.
    Returns structured pass/fail results.
    """
    if engine._is_running:
        return JSONResponse(status_code=400, content={"error": "测试任务已在运行中"})

    non_inv_ids = [tid for tid, meta in engine.registry.items() if meta.get("mode") == "NON_INVASIVE"]
    results = engine.run_tests(selected_ids=non_inv_ids, mode_filter="NON_INVASIVE")
    passed = [r for r in results if r.status == "PASSED"]
    failed = [r for r in results if r.status == "FAILED"]
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

@app.post("/api/stop")
async def stop_tests():
    """Stop currently running tests."""
    engine.stop()
    return {"status": "ok", "message": "已发送停止请求"}

@app.post("/api/open_browser")
async def open_browser_endpoint():
    """Launch or bring to front a visible Chrome window directly without disrupting current page."""
    def _open():
        if not engine.browser or not engine.browser.is_alive():
            from fs_web_testrunner.core.browser_driver import BrowserDriver
            engine.browser = BrowserDriver(headless=False)
            engine.browser.start("http://192.168.1.198:8088/#/login")
        else:
            engine.browser.bring_to_front()
    threading.Thread(target=_open, daemon=True).start()
    return {"status": "ok", "message": "已在桌面置顶 Chrome 浏览器窗口"}

@app.get("/api/validator/status")
async def validator_status_endpoint():
    """Run full session and backend diagnosis without touching frontend pages."""
    validator = LoginValidator()
    return validator.run_full_diagnosis()

@app.post("/api/validator/search_order")
async def validator_search_order_endpoint(req: OrderSearchRequest):
    """Search order items from Oracle DB via HIS backend."""
    validator = LoginValidator()
    return validator.search_order_items(
        keyword=req.keyword or "",
        classify_type=req.classifyType or "W",
        page_num=req.pageNum or 1,
        page_size=req.pageSize or 10
    )

@app.get("/api/validator/role_presets")
async def get_role_presets_endpoint():
    validator = LoginValidator()
    return {"status": "ok", "presets": validator.get_role_presets()}

@app.get("/api/validator/roles")
async def get_roles_endpoint():
    validator = LoginValidator()
    return {"status": "ok", "roles": validator.get_roles_list()}

@app.get("/api/validator/depts")
async def get_depts_endpoint(roleId: int):
    validator = LoginValidator()
    return {"status": "ok", "depts": validator.get_depts_by_role(roleId)}

@app.post("/api/validator/switch_identity")
async def switch_identity_endpoint(req: SwitchIdentityRequest):
    validator = LoginValidator()
    return validator.switch_identity_in_browser(req.roleId, req.deptId, req.targetRoute or "")

@app.post("/api/validator/preset_identity")
async def preset_identity_endpoint(req: SwitchIdentityRequest):
    validator = LoginValidator()
    return validator.preset_login_identity(req.roleId, req.deptId, req.targetRoute or "")

@app.get("/api/xml")

async def get_current_xml():
    """Fetch current live XML from the editor."""
    if not engine.writer:
        return {"status": "error", "message": "浏览器/编辑器实例未连接"}
    try:
        xml = engine.writer.get_document_xml()
        return {"status": "ok", "xml": xml}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/screenshot")
async def get_screenshot():
    """Fetch live screenshot."""
    if not engine.browser:
        return {"status": "error", "message": "浏览器未连接"}
    try:
        b64 = engine.browser.get_screenshot_base64()
        return {"status": "ok", "data": f"data:image/jpeg;base64,{b64}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/eval")
async def eval_sandbox(req: EvalRequest):
    """
    Interactive API SandBox: Execute JS in browser on the fly.
    """
    if not engine.browser:
        return {"status": "error", "message": "浏览器未启动，请先运行测试或连接"}
    try:
        val = engine.browser.evaluate(req.expression)
        return {"status": "ok", "result": val}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/modules")
async def get_his_modules():
    """Returns the full catalog of HIS business modules for site-wide testing."""
    return {
        "status": "ok",
        "modules": [
            {
                "group": "电子病历系统 (EMR)",
                "icon": "emr",
                "items": [
                    {"name": "病历模板制作", "path": "/emr/templatesrecords/emrDesigner", "desc": "FSWriter Wasm 编辑器与病历元素设计"},
                    {"name": "元素管理", "path": "/emr/elementManage", "desc": "卫生健康委标准数据元与输入域管理"},
                    {"name": "门诊病历书写", "path": "/emr/outpatientMedical", "desc": "门诊医生病历实时录入与校验"},
                    {"name": "体温单测试", "path": "/emr/temperatureTest", "desc": "生命体征三测单曲线渲染"},
                    {"name": "片段模板库", "path": "/emr/fragmentTemplate", "desc": "科室病历常用文本宏片段"}
                ]
            },
            {
                "group": "门诊业务系统 (Outpatient)",
                "icon": "outpatient",
                "items": [
                    {"name": "门诊挂号", "path": "/outpatient/registration", "desc": "排班号源选择与现场挂号"},
                    {"name": "门诊收费", "path": "/outpatient/charge", "desc": "处方划价收费与结算发票打印"},
                    {"name": "门诊医生工作站", "path": "/outpatient/doctor", "desc": "门诊诊断ICD-10、西药/中草药处方开立"},
                    {"name": "挂号日结", "path": "/outpatient/dailySettlement", "desc": "收费员交班与对账汇总"}
                ]
            },
            {
                "group": "住院业务系统 (Inpatient)",
                "icon": "inpatient",
                "items": [
                    {"name": "住院登记", "path": "/inpatient/registration", "desc": "入院登记、病案号分配与押金缴纳"},
                    {"name": "住院护士站", "path": "/inpatient/nurse", "desc": "床位分配、长期/临时医嘱执行、费用补录"},
                    {"name": "住院医生站", "path": "/inpatient/doctor", "desc": "病程记录、入院记录书写、会诊开立"},
                    {"name": "出院结算", "path": "/inpatient/settlement", "desc": "住院费用清算与医保结算"}
                ]
            },
            {
                "group": "药房药库系统 (Pharmacy)",
                "icon": "pharmacy",
                "items": [
                    {"name": "门诊药房", "path": "/pharmacy/outpatient", "desc": "门诊处方自动配药、窗口扫码发药"},
                    {"name": "住院摆药", "path": "/pharmacy/inpatient", "desc": "病区医嘱批量自动摆药与发药核对"},
                    {"name": "药库管理", "path": "/pharmacy/stock", "desc": "入库验收、出库领发、库存盘点"}
                ]
            },
            {
                "group": "系统与字典维护 (Settings)",
                "icon": "settings",
                "items": [
                    {"name": "人员管理", "path": "/setting/personnelManage", "desc": "全院职工信息、医务权限与科室绑定"},
                    {"name": "角色权限", "path": "/setting/roleManagement", "desc": "RBAC 角色权限与功能菜单权限控制"},
                    {"name": "频次维护", "path": "/dictionary/frequentMaintenance", "desc": "医嘱用药频次字典 (QD/BID/TID)"},
                    {"name": "用法维护", "path": "/dictionary/usageMaintenance", "desc": "给药途径字典 (口服/静脉滴注)"}
                ]
            }
        ]
    }

class EnvSwitchRequest(BaseModel):
    mode: str  # "MOCK", "LIVE", "AUTO"

class RuleCreateRequest(BaseModel):
    id: Optional[str] = None
    domain: str = "inpatient"
    domain_name: Optional[str] = None
    name: str
    severity: str = "BLOCK"
    severity_name: Optional[str] = None
    trigger_phase: Optional[str] = ""
    target_api_table: Optional[str] = ""
    summary: str
    detail: Optional[str] = ""
    parameters: Optional[Dict[str, Any]] = None
    enabled: bool = True

class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    severity: Optional[str] = None
    trigger_phase: Optional[str] = None
    target_api_table: Optional[str] = None
    summary: Optional[str] = None
    detail: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None

@app.get("/api/environment")
async def get_env_endpoint():
    from fs_web_testrunner.core.offline_sandbox import get_environment_status
    return {"status": "ok", **get_environment_status()}

@app.post("/api/environment/switch")
async def switch_env_endpoint(req: EnvSwitchRequest):
    from fs_web_testrunner.core.offline_sandbox import (
        activate_live_mode, activate_offline_mode, auto_configure_environment, get_environment_status
    )
    if req.mode == "MOCK":
        activate_offline_mode()
    elif req.mode == "LIVE":
        activate_live_mode()
    else:
        auto_configure_environment()
    status = get_environment_status()
    broadcast_sync({"type": "env_change", "status": status})
    return {"status": "ok", **status}

@app.get("/api/rules")
async def get_rules_endpoint(domain: Optional[str] = None):
    return {
        "status": "ok",
        "stats": rules_mgr.get_summary_stats(),
        "rules": rules_mgr.get_all_rules(domain)
    }

@app.post("/api/rules")
async def create_rule_endpoint(req: RuleCreateRequest):
    try:
        new_rule = rules_mgr.add_rule(req.dict())
        broadcast_sync({"type": "rule_create", "rule": new_rule})
        return {"status": "ok", "rule": new_rule}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/api/rules/{rule_id}")
async def get_single_rule_endpoint(rule_id: str):
    r = rules_mgr.get_rule_by_id(rule_id)
    if not r:
        return JSONResponse(status_code=404, content={"error": f"Rule {rule_id} not found"})
    return {"status": "ok", "rule": r}

@app.put("/api/rules/{rule_id}")
async def update_rule_endpoint(rule_id: str, req: RuleUpdateRequest):
    try:
        updated = rules_mgr.update_rule(rule_id, req.dict(exclude_unset=True))
        broadcast_sync({"type": "rule_update", "rule_id": rule_id, "rule": updated})
        return {"status": "ok", "rule": updated}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.delete("/api/rules/{rule_id}")
async def delete_rule_endpoint(rule_id: str):
    success = rules_mgr.delete_rule(rule_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": f"Rule {rule_id} not found"})
    broadcast_sync({"type": "rule_delete", "rule_id": rule_id})
    return {"status": "ok", "message": f"Rule {rule_id} deleted"}

@app.post("/api/rules/{rule_id}/verify")
async def verify_single_rule_endpoint(rule_id: str):
    try:
        res = rules_mgr.verify_rule(rule_id, broadcast_sync)
        broadcast_sync({"type": "rule_verify_done", "result": res})
        return {"status": "ok", "result": res}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/api/rules/verify_all")
async def verify_all_rules_endpoint():
    rules = [r for r in rules_mgr.get_all_rules() if r.get("enabled", True)]
    results = []
    for r in rules:
        res = rules_mgr.verify_rule(r["id"], broadcast_sync)
        results.append(res)
    stats = rules_mgr.get_summary_stats()
    return {
        "status": "ok",
        "total": len(results),
        "passed": sum(1 for res in results if res["status"] == "PASSED"),
        "failed": sum(1 for res in results if res["status"] == "FAILED"),
        "stats": stats,
        "results": results
    }

@app.post("/api/rules/reset")
async def reset_rules_endpoint():
    rules = rules_mgr.reset_to_defaults()
    return {"status": "ok", "message": "已恢复官方默认16条业务规则", "rules": rules}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
