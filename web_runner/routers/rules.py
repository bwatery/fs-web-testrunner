"""
Business Rules & Gates Governance Router.
Handles business rule inspection, CRUD operations, single/batch assertion verification, and defaults reset.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.web_runner.state import rules_mgr, ws_manager

router = APIRouter(tags=["rules"])
logger = get_logger("rules")

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

@router.get("/api/rules")
async def get_rules_endpoint(domain: Optional[str] = None):
    """Retrieve all business rules and summary statistics, optionally filtered by domain."""
    return {
        "status": "ok",
        "stats": rules_mgr.get_summary_stats(),
        "rules": rules_mgr.get_all_rules(domain)
    }

@router.post("/api/rules")
async def create_rule_endpoint(req: RuleCreateRequest):
    """Register a new custom business rule."""
    try:
        new_rule = rules_mgr.add_rule(req.dict())
        ws_manager.broadcast_sync({"type": "rule_create", "rule": new_rule})
        logger.info(f"Created rule [{new_rule.get('id')}]: {new_rule.get('name')}")
        return {"status": "ok", "rule": new_rule}
    except Exception as e:
        logger.error(f"Failed to create rule: {e}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.get("/api/rules/{rule_id}")
async def get_single_rule_endpoint(rule_id: str):
    """Retrieve full details of a single rule."""
    r = rules_mgr.get_rule_by_id(rule_id)
    if not r:
        return JSONResponse(status_code=404, content={"error": f"Rule {rule_id} not found"})
    return {"status": "ok", "rule": r}

@router.put("/api/rules/{rule_id}")
async def update_rule_endpoint(rule_id: str, req: RuleUpdateRequest):
    """Update rule parameters and configuration."""
    try:
        updated = rules_mgr.update_rule(rule_id, req.dict(exclude_unset=True))
        ws_manager.broadcast_sync({"type": "rule_update", "rule_id": rule_id, "rule": updated})
        logger.info(f"Updated rule [{rule_id}]")
        return {"status": "ok", "rule": updated}
    except Exception as e:
        logger.error(f"Failed to update rule [{rule_id}]: {e}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.delete("/api/rules/{rule_id}")
async def delete_rule_endpoint(rule_id: str):
    """Delete a custom business rule."""
    success = rules_mgr.delete_rule(rule_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": f"Rule {rule_id} not found"})
    ws_manager.broadcast_sync({"type": "rule_delete", "rule_id": rule_id})
    logger.info(f"Deleted rule [{rule_id}]")
    return {"status": "ok", "message": f"Rule {rule_id} deleted"}

@router.post("/api/rules/{rule_id}/verify")
async def verify_single_rule_endpoint(rule_id: str):
    """Execute live assertion verification for a single rule."""
    try:
        logger.info(f"Verifying single rule [{rule_id}]")
        res = rules_mgr.verify_rule(rule_id, ws_manager.broadcast_sync)
        ws_manager.broadcast_sync({"type": "rule_verify_done", "result": res})
        logger.info(f"Rule [{rule_id}] result: {res.get('status')}")
        return {"status": "ok", "result": res}
    except Exception as e:
        logger.error(f"Error verifying rule [{rule_id}]: {e}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.post("/api/rules/verify_all")
async def verify_all_rules_endpoint():
    """Execute full automated acceptance verification across all active rules."""
    rules = [r for r in rules_mgr.get_all_rules() if r.get("enabled", True)]
    logger.info(f"Starting verify_all for {len(rules)} rules")
    results = []
    for r in rules:
        res = rules_mgr.verify_rule(r["id"], ws_manager.broadcast_sync)
        results.append(res)
    stats = rules_mgr.get_summary_stats()
    passed_count = sum(1 for res in results if res["status"] == "PASSED")
    failed_count = sum(1 for res in results if res["status"] == "FAILED")
    logger.info(f"Verify all finished: {passed_count}/{len(results)} passed, {failed_count} failed")
    return {
        "status": "ok",
        "total": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "stats": stats,
        "results": results
    }

@router.post("/api/rules/reset")
async def reset_rules_endpoint():
    """Reset rules database back to standard factory 16 hospital rules."""
    logger.info("Resetting rules to defaults")
    rules = rules_mgr.reset_to_defaults()
    return {"status": "ok", "message": "已恢复官方默认16条业务规则", "rules": rules}
