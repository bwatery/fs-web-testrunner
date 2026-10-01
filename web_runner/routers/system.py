"""
System Diagnostic, Environment, REPL, and Local Logging Router.
Handles environment mode switching, Wasm REPL, XML inspection, modules radar, and local disk log retrieval.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel

from fs_web_testrunner.core.logger import get_logger, get_recent_logs, list_log_files, clear_logs
from fs_web_testrunner.web_runner.state import engine, ws_manager

from fs_web_testrunner.core.env_config import env_config

router = APIRouter(tags=["system"])
logger = get_logger("system")

class EnvSwitchRequest(BaseModel):
    mode: str  # "MOCK", "LIVE", "AUTO"

class EnvConfigRequest(BaseModel):
    frontend_base_url: Optional[str] = None
    api_gateway_url: Optional[str] = None
    emr_designer_url: Optional[str] = None
    active_preset: Optional[str] = None
    oracle: Optional[Dict[str, Any]] = None
    offline_adaptive_strategy: Optional[str] = None
    workstations: Optional[Dict[str, Any]] = None

class AdaptiveStrategyRequest(BaseModel):
    strategy: str  # "ADAPTIVE_MOCK", "SKIP_INVASIVE", "STRICT"

class ConnectivityTestRequest(BaseModel):
    target_type: str = "api_gateway"  # "frontend", "api_gateway", "oracle", "custom"
    target_url: Optional[str] = None

class EvalRequest(BaseModel):
    expression: str

@router.get("/api/environment")
async def get_env_endpoint():
    """Get offline mock sandbox vs live intranet status."""
    from fs_web_testrunner.core.offline_sandbox import get_environment_status
    return {"status": "ok", **get_environment_status()}

@router.get("/api/environment/config")
async def get_env_config_endpoint():
    """Get full editable target environment configuration and available presets."""
    return {"status": "ok", "config": env_config.get_config()}

@router.post("/api/environment/config")
async def update_env_config_endpoint(req: EnvConfigRequest):
    """Save manual target environment configurations and sync with runtime."""
    updates = req.dict(exclude_unset=True)
    updated = env_config.update_config(updates)
    ws_manager.broadcast_sync({"type": "env_config_change", "config": updated})
    return {"status": "ok", "config": updated}

@router.post("/api/environment/adaptive_strategy")
async def set_adaptive_strategy_endpoint(req: AdaptiveStrategyRequest):
    """Switch offline sandbox adaptive strategy: Option A (ADAPTIVE_MOCK) vs Option B (SKIP_INVASIVE) vs STRICT."""
    new_strategy = env_config.set_adaptive_strategy(req.strategy)
    ws_manager.broadcast_sync({"type": "adaptive_strategy_change", "strategy": new_strategy})
    return {"status": "ok", "strategy": new_strategy}

@router.post("/api/environment/test_connectivity")
async def test_connectivity_endpoint(req: ConnectivityTestRequest):
    """Live connectivity and latency diagnostic test for target environment."""
    res = env_config.test_connectivity(req.target_type, req.target_url)
    return {"status": "ok", "result": res}

@router.post("/api/environment/switch")
async def switch_env_endpoint(req: EnvSwitchRequest):
    """Switch environment between MOCK, LIVE, and AUTO mode."""
    from fs_web_testrunner.core.offline_sandbox import (
        activate_live_mode, activate_offline_mode, auto_configure_environment, get_environment_status
    )
    logger.info(f"Switching environment mode to {req.mode}")
    if req.mode == "MOCK":
        activate_offline_mode()
    elif req.mode == "LIVE":
        activate_live_mode()
    else:
        auto_configure_environment()
    status = get_environment_status()
    ws_manager.broadcast_sync({"type": "env_change", "status": status})
    return {"status": "ok", **status}

@router.get("/api/workstations")
async def get_workstations_endpoint():
    """Returns the 6 hospital workstations with metadata, test cases, and pass rates."""
    conf = env_config.get_config()
    ws_dict = conf.get("workstations", {})
    
    items = []
    ws_meta = [
        {"code": "INPATIENT_DOCTOR", "name": "住院工作站", "icon": "inpatient", "key": "inpatient_doctor", "tag": "医嘱·病历·诊断"},
        {"code": "OUTPATIENT_DOCTOR", "name": "门诊工作站", "icon": "outpatient", "key": "outpatient_doctor", "tag": "接诊·处方·病历"},
        {"code": "PHARMACY", "name": "药房系统", "icon": "pharmacy", "key": "pharmacy", "tag": "审方·发药·摆药"},
        {"code": "OUTPATIENT_BILLING", "name": "门诊收费", "icon": "charge", "key": "outpatient_billing", "tag": "挂号·划价·发票"},
        {"code": "INPATIENT_BILLING", "name": "住院收费", "icon": "settlement", "key": "inpatient_billing", "tag": "押金·清单·结算"},
        {"code": "INPATIENT_NURSE", "name": "住院护士", "icon": "nurse", "key": "inpatient_nurse", "tag": "床位·执行·三测单"},
    ]
    
    for wm in ws_meta:
        code = wm["code"]
        key = wm["key"]
        saved_info = ws_dict.get(key, {})
        
        matching_tests = [
            tid for tid, m in engine.registry.items()
            if m.get("workstation_code") == code or m.get("workstation") == wm["name"]
        ]
        
        recent_results = [
            r for r in engine.results
            if getattr(r, "workstation_code", None) == code or getattr(r, "workstation", None) == wm["name"]
        ]
        passed_count = len([r for r in recent_results if r.status == "PASSED"])
        failed_count = len([r for r in recent_results if r.status == "FAILED"])
        skipped_count = len([r for r in recent_results if r.status == "SKIPPED"])

        items.append({
            "code": code,
            "name": wm["name"],
            "icon": wm["icon"],
            "key": key,
            "tag": wm["tag"],
            "url": saved_info.get("url", env_config.get_workstation_url(code)),
            "route": saved_info.get("route", ""),
            "desc": saved_info.get("desc", ""),
            "tests_count": len(matching_tests),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "test_ids": matching_tests
        })
        
    return {"status": "ok", "workstations": items}

@router.get("/api/modules")
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

@router.get("/api/xml")
async def get_current_xml():
    """Fetch current live XML from the editor."""
    if not engine.writer:
        return {"status": "error", "message": "浏览器/编辑器实例未连接"}
    try:
        xml = engine.writer.get_document_xml()
        return {"status": "ok", "xml": xml}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/screenshot")
async def get_screenshot():
    """Fetch live screenshot."""
    if not engine.browser:
        return {"status": "error", "message": "浏览器未连接"}
    try:
        b64 = engine.browser.get_screenshot_base64()
        return {"status": "ok", "data": f"data:image/jpeg;base64,{b64}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/eval")
async def eval_sandbox(req: EvalRequest):
    """Interactive API SandBox: Execute JS in browser on the fly."""
    if not engine.browser:
        return {"status": "error", "message": "浏览器未启动，请先运行测试或连接"}
    try:
        val = engine.browser.evaluate(req.expression)
        return {"status": "ok", "result": val}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------------
# Local Logging Inspection API (本地日志系统端点)
# -------------------------------------------------------------
@router.get("/api/logs")
async def get_logs_endpoint(
    type: Optional[str] = Query(None),
    log_type: Optional[str] = Query(None),
    limit: int = Query(150, ge=1, le=1000)
):
    """Read recent N lines of logs from local rotating log files on disk."""
    selected_type = log_type or type or "app"
    if selected_type in ("test_engine", "engine"):
        selected_type = "test_engine"
    elif selected_type not in ("app", "rules"):
        selected_type = "app"

    lines = get_recent_logs(log_type=selected_type, limit=limit)
    return {
        "status": "ok",
        "type": selected_type,
        "count": len(lines),
        "limit": limit,
        "lines": lines
    }

@router.get("/api/logs/files")
async def get_log_files_endpoint():
    """List all rotating log files saved on disk in logs/ directory."""
    files = list_log_files()
    return {
        "status": "ok",
        "files": files,
        "count": len(files)
    }

@router.delete("/api/logs")
async def clear_logs_endpoint():
    """Clear all local log files in logs/ directory."""
    success = clear_logs()
    return {
        "status": "ok" if success else "error",
        "message": "本地日志已成功清理" if success else "清理日志失败"
    }
