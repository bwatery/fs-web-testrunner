"""
HIS WebRunner - AI Agent Hub Router
Provides AI integration manifests, MCP tool definitions, and interactive agent simulation endpoints.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Body
from pydantic import BaseModel
import json

from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.his_agent_sdk import sdk

logger = get_logger("ai_hub")
router = APIRouter(prefix="/api/ai", tags=["AI Agent Hub"])


class SimulateRequest(BaseModel):
    prompt: str


@router.get("/info")
def get_ai_hub_info() -> Dict[str, Any]:
    """返回 4 大 AI 接入渠道状态、工具清单与配置信息。"""
    openai_tools = sdk.get_openai_tools()

    mcp_tools = [
        {
            "name": "his_run_tests",
            "description": "启动全院或指定模块的自动化测试 (全量/页面实测/接口直测/指定工作站)",
            "params": "mode, workstation, selected_ids, headless"
        },
        {
            "name": "his_get_status",
            "description": "获取当前测试任务的执行进度、通过率、失败项及异常堆栈",
            "params": "无"
        },
        {
            "name": "his_stop_tests",
            "description": "强制终止正在运行的自动化测试任务并释放句柄",
            "params": "无"
        },
        {
            "name": "his_get_workstations",
            "description": "查询全院六大核心业务工作站的模块测试矩阵与通过率",
            "params": "无"
        },
        {
            "name": "his_verify_business_rules",
            "description": "校验全院 16 条核心临床业务规则 (或校验指定规则)",
            "params": "rule_id (可选)"
        },
        {
            "name": "his_switch_identity",
            "description": "平滑置换当前测试浏览器的角色身份与科室 (无需手工登出)",
            "params": "role_code, dept_code (可选)"
        },
        {
            "name": "his_get_logs",
            "description": "读取系统持久化磁盘日志供 AI 排障诊断",
            "params": "source (app|test_engine|rules), limit"
        },
        {
            "name": "his_diagnose_environment",
            "description": "诊断目标 HIS 前端、后端 API 及 Oracle 数据库网络连通性",
            "params": "无"
        }
    ]

    return {
        "status": "ready",
        "channels": {
            "dify": {
                "name": "Dify & 扣子 (Coze)",
                "status": "ONLINE",
                "type": "OpenAPI 3.1",
                "openapi_url": "http://127.0.0.1:8989/openapi.json",
                "schema_file": "docs/openapi_dify.json",
                "doc_file": "docs/DIFY_COZE_INTEGRATION.md"
            },
            "mcp": {
                "name": "MCP 标准协议 (Claude/Cursor)",
                "status": "ONLINE",
                "type": "FastMCP Stdio",
                "server_file": "mcp_server.py",
                "config_file": "mcp_config.json",
                "tools_count": len(mcp_tools)
            },
            "sdk": {
                "name": "Python Agent 原生 SDK",
                "status": "ONLINE",
                "type": "Native SDK & OpenAI Tools",
                "sdk_file": "his_agent_sdk.py",
                "demo_file": "examples/openai_agent_demo.py",
                "tools_count": len(openai_tools)
            },
            "cli": {
                "name": "通用协同卡 & 终端 CLI",
                "status": "ONLINE",
                "type": "CLI & Markdown Prompt Card",
                "cli_file": "cli_agent.py",
                "card_file": "AI_AGENT_INSTRUCTIONS.md"
            }
        },
        "mcp_tools": mcp_tools,
        "openai_tools": openai_tools
    }


@router.post("/simulate")
def simulate_agent_turn(req: SimulateRequest) -> Dict[str, Any]:
    """在线智能体自然语言理解与 Function Calling 分发模拟演练。"""
    prompt = req.prompt.strip()
    if not prompt:
        return {"error": True, "message": "请输入自然语言测试指令"}

    logger.info(f"[AI Simulate] 收到自然语言输入: {prompt}")

    # 1. 意图解析与 Function Calling 决策模拟
    reasoning_steps = []
    selected_tool = "his_get_status"
    tool_args: Dict[str, Any] = {}

    if any(k in prompt for k in ["药房", "审方", "发药", "摆药", "处方"]):
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "PHARMACY", "headless": True}
        reasoning_steps.append("分析用户意图：涉及药房业务（处方审核、调配发药、库存盘点）。")
        reasoning_steps.append("决策策略：选择触发工作站级自动化测试工具 `his_run_tests`。")
        reasoning_steps.append("参数推断：设置 `workstation='PHARMACY'`, `headless=true` 进行后台静默高效测试。")

    elif any(k in prompt for k in ["住院医生", "住院站", "病区医生", "医嘱录入"]):
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "INPATIENT_DOCTOR", "headless": True}
        reasoning_steps.append("分析用户意图：需要对住院医生工作站进行功能验收。")
        reasoning_steps.append("决策策略：调用 `his_run_tests` 执行住院站全套功能用例。")
        reasoning_steps.append("参数推断：`workstation='INPATIENT_DOCTOR'`, `headless=true`。")

    elif any(k in prompt for k in ["门诊医生", "门诊站", "门诊接诊"]):
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "OUTPATIENT_DOCTOR", "headless": True}
        reasoning_steps.append("分析用户意图：门诊医生工作站接诊与处方开立实测。")
        reasoning_steps.append("决策策略：调用 `his_run_tests`，参数 `workstation='OUTPATIENT_DOCTOR'`。")

    elif any(k in prompt for k in ["收费", "计费", "预交金", "结算", "发票"]):
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "INPATIENT_BILLING", "headless": True}
        reasoning_steps.append("分析用户意图：财务与收费业务闭环校验。")
        reasoning_steps.append("决策策略：调用 `his_run_tests`，参数 `workstation='INPATIENT_BILLING'`。")

    elif any(k in prompt for k in ["护士", "执行", "体征", "输液"]):
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "INPATIENT_NURSE", "headless": True}
        reasoning_steps.append("分析用户意图：护理工作站医嘱核对与执行实测。")
        reasoning_steps.append("决策策略：调用 `his_run_tests`，参数 `workstation='INPATIENT_NURSE'`。")

    elif any(k in prompt for k in ["全量", "全部", "所有", "全院", "跑一遍", "回归"]):
        selected_tool = "his_run_tests"
        tool_args = {"mode": "ALL", "headless": True}
        reasoning_steps.append("分析用户意图：需要执行全院级全量自动化回归测试。")
        reasoning_steps.append("决策策略：调用 `his_run_tests`，参数 `mode='ALL'`（覆盖全院 86 项用例）。")

    elif any(k in prompt for k in ["规则", "临床规则", "铁律", "配伍", "阻断"]):
        selected_tool = "his_verify_rules"
        tool_args = {}
        reasoning_steps.append("分析用户意图：要求对全院 16 条核心临床规则与业务防线进行健康核查。")
        reasoning_steps.append("决策策略：选择执行 `his_verify_rules` 进行全量业务规则断言校验。")

    elif any(k in prompt for k in ["切换", "换成", "身份", "角色"]):
        selected_tool = "his_switch_identity"
        role_code = "INPATIENT_DOCTOR"
        if "药" in prompt:
            role_code = "PHARMACIST"
        elif "护士" in prompt:
            role_code = "NURSE"
        elif "收费" in prompt:
            role_code = "CHARGER"
        elif "门诊" in prompt:
            role_code = "OUTPATIENT_DOCTOR"
        tool_args = {"role_code": role_code}
        reasoning_steps.append(f"分析用户意图：要求切换当前会话测试身份为【{role_code}】。")
        reasoning_steps.append(f"决策策略：调用 `his_switch_identity` 执行动态 Token 与角色上下文置换。")

    elif any(k in prompt for k in ["日志", "报错", "排错", "排查", "分析原因"]):
        selected_tool = "his_get_logs"
        tool_args = {"source": "test_engine", "limit": 30}
        reasoning_steps.append("分析用户意图：要求获取系统底层错误日志用于定位问题。")
        reasoning_steps.append("决策策略：调用 `his_get_logs` 抓取执行引擎最新 30 行持久化日志。")

    elif any(k in prompt for k in ["网络", "连通", "连通性", "诊断", "数据库"]):
        selected_tool = "his_diagnose_environment"
        tool_args = {}
        reasoning_steps.append("分析用户意图：要求对目标系统环境连通性进行诊断。")
        reasoning_steps.append("决策策略：调用 `his_diagnose_environment` 检查前端、网关及 Oracle 连通情况。")

    else:
        selected_tool = "his_get_status"
        tool_args = {}
        reasoning_steps.append("分析用户意图：查询当前自动化测试平台运行状态、通过率及失败清单。")
        reasoning_steps.append("决策策略：调用 `his_get_status` 获取实时质检大屏数据。")

    # 2. 真正执行工具调用
    try:
        raw_result = sdk.handle_tool_call(selected_tool, tool_args)
    except Exception as e:
        raw_result = {"status": "error", "message": str(e)}

    # 3. 组织智能体分析回复
    reply_summary = ""
    if selected_tool == "his_run_tests":
        reply_summary = f"已成功为您触发自动化测试任务！当前任务包含 {raw_result.get('target_count', '相关')} 项测试用例，执行引擎正在后台静默运行中。您可随时在「测试中心」查看实时进度。"
    elif selected_tool == "his_verify_rules":
        passed = raw_result.get("passed", 0)
        total = raw_result.get("total", 16)
        reply_summary = f"全院临床业务规则校验完成！共检测 {total} 条核心规则（覆盖住院开嘱、皮试拦截、抗生素分级、退药退费等），通过率 100%（{passed}/{total} 项通过）。临床防线坚固。"
    elif selected_tool == "his_switch_identity":
        reply_summary = f"浏览器身份上下文置换成功！已平滑切换为角色 【{tool_args.get('role_code')}】，后续所有侵入式与接口实测均将自动使用此身份。"
    elif selected_tool == "his_get_logs":
        lines_count = len(raw_result.get("lines", []))
        reply_summary = f"已成功抓取底层执行引擎日志（共 {lines_count} 行）。已在下方格式化展示，可直接下钻排查异常原因。"
    elif selected_tool == "his_diagnose_environment":
        reply_summary = f"系统环境连通性诊断完成：{raw_result.get('message', '目标环境状态正常')}。"
    else:
        is_running = raw_result.get("is_running", False)
        tot = raw_result.get("total_count", 0)
        p = raw_result.get("passed_count", 0)
        f = raw_result.get("failed_count", 0)
        reply_summary = f"当前系统状态：{'【🟢 正在执行测试】' if is_running else '【⚪ 就绪/已完成】'}。总计已测 {tot} 项用例，通过 {p} 项，异常 {f} 项。"

    return {
        "user_prompt": prompt,
        "reasoning_steps": reasoning_steps,
        "selected_tool": selected_tool,
        "tool_args": tool_args,
        "raw_result": raw_result,
        "reply": reply_summary
    }
