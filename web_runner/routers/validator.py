"""
Session Validator & Identity Switching Router.
Handles live browser session token extraction, backend service diagnosis, and role/dept matrix switching.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter
from pydantic import BaseModel

from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.logger import get_logger

router = APIRouter(tags=["validator"])
logger = get_logger("validator")

class OrderSearchRequest(BaseModel):
    keyword: Optional[str] = ""
    classifyType: Optional[str] = "W"
    pageNum: Optional[int] = 1
    pageSize: Optional[int] = 10

class SwitchIdentityRequest(BaseModel):
    roleId: int
    deptId: int
    targetRoute: Optional[str] = ""

@router.get("/api/validator/status")
async def validator_status_endpoint():
    """Run full session and backend diagnosis without touching frontend pages."""
    validator = LoginValidator()
    return validator.run_full_diagnosis()

@router.post("/api/validator/search_order")
async def validator_search_order_endpoint(req: OrderSearchRequest):
    """Search order items from Oracle DB via HIS backend."""
    validator = LoginValidator()
    return validator.search_order_items(
        keyword=req.keyword or "",
        classify_type=req.classifyType or "W",
        page_num=req.pageNum or 1,
        page_size=req.pageSize or 10
    )

@router.get("/api/validator/role_presets")
async def get_role_presets_endpoint():
    """Retrieve commonly used role & department workstation presets."""
    validator = LoginValidator()
    return {"status": "ok", "presets": validator.get_role_presets()}

@router.get("/api/validator/roles")
async def get_roles_endpoint():
    """List all available roles in the hospital HIS matrix."""
    validator = LoginValidator()
    return {"status": "ok", "roles": validator.get_roles_list()}

@router.get("/api/validator/depts")
async def get_depts_endpoint(roleId: int):
    """List applicable departments for a specific role."""
    validator = LoginValidator()
    return {"status": "ok", "depts": validator.get_depts_by_role(roleId)}

@router.post("/api/validator/switch_identity")
async def switch_identity_endpoint(req: SwitchIdentityRequest):
    """Switch role and department identity in the live browser."""
    logger.info(f"Switching identity to role={req.roleId}, dept={req.deptId}, route={req.targetRoute}")
    validator = LoginValidator()
    return validator.switch_identity_in_browser(req.roleId, req.deptId, req.targetRoute or "")

@router.post("/api/validator/preset_identity")
async def preset_identity_endpoint(req: SwitchIdentityRequest):
    """Pre-set role and department cache before login."""
    logger.info(f"Presetting identity to role={req.roleId}, dept={req.deptId}")
    validator = LoginValidator()
    return validator.preset_login_identity(req.roleId, req.deptId, req.targetRoute or "")
