"""
HIS WebRunner - Python AI Agent SDK
Provides native OpenAI, LangChain, and AutoGen Function Calling bindings for the HIS automated testing platform.
"""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any, Union

class HISAgentSDK:
    """Python Client & Function Calling Toolkit for AI Agents."""

    def __init__(self, base_url: str = "http://127.0.0.1:8989"):
        self.base_url = base_url.rstrip("/")

    def _request(self, endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {"status": "ok"}
        except urllib.error.URLError as e:
            return {"status": "error", "message": f"连接 HIS WebRunner 失败 ({url}): {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # High-level Python Automation Methods
    # =========================================================================

    def run_all(self, headless: bool = True) -> Dict[str, Any]:
        """执行全院全量 86 项自动化测试用例。"""
        return self._request("/api/run", method="POST", payload={"mode": "ALL", "headless": headless})

    def run_workstation(self, workstation_code: str, headless: bool = True) -> Dict[str, Any]:
        """执行指定业务工作站全套模块测试。
        可用代码: 'INPATIENT_DOCTOR', 'OUTPATIENT_DOCTOR', 'PHARMACY', 'OUTPATIENT_BILLING', 'INPATIENT_BILLING', 'INPATIENT_NURSE'
        """
        return self._request("/api/run", method="POST", payload={
            "mode": "ALL",
            "workstation": workstation_code,
            "headless": headless
        })

    def get_status(self) -> Dict[str, Any]:
        """获取当前测试任务进度、通过率与失败用例明细。"""
        return self._request("/api/status")

    def stop(self) -> Dict[str, Any]:
        """强制终止测试任务并释放资源。"""
        return self._request("/api/stop", method="POST")

    def get_workstations(self) -> Dict[str, Any]:
        """获取六大工作站测试矩阵与通过率。"""
        return self._request("/api/workstations")

    def verify_rules(self, rule_id: Optional[str] = None) -> Dict[str, Any]:
        """校验全院 16 条业务规则或指定规则。"""
        if rule_id:
            return self._request(f"/api/rules/{rule_id}/verify", method="POST")
        return self._request("/api/rules/verify_all", method="POST")

    def switch_identity(self, role_code: str, dept_code: Optional[str] = None) -> Dict[str, Any]:
        """置换当前浏览器测试身份（如 'INPATIENT_DOCTOR', 'PHARMACIST'）。"""
        payload = {"role_code": role_code}
        if dept_code:
            payload["dept_code"] = dept_code
        return self._request("/api/validator/switch_identity", method="POST", payload=payload)

    def get_logs(self, source: str = "app", limit: int = 50) -> Dict[str, Any]:
        """读取系统持久化日志用于报错诊断。"""
        return self._request(f"/api/logs?source={source}&limit={limit}")

    def diagnose_environment(self) -> Dict[str, Any]:
        """诊断目标系统前端地址、后端 API 及 Oracle 连通性。"""
        return self._request("/api/environment/test_connectivity", method="POST")

    # =========================================================================
    # OpenAI & LangChain Function Calling Schemas
    # =========================================================================

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """返回符合 OpenAI Function Calling / Tools 规范的标准工具定义列表。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "his_run_tests",
                    "description": "触发全院或指定模块的自动化测试。支持全量测试、按工作站筛选或指定用例ID列表。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["ALL", "INVASIVE", "NON_INVASIVE"],
                                "description": "测试模式：ALL(全量), INVASIVE(页面实测), NON_INVASIVE(接口直测)"
                            },
                            "workstation": {
                                "type": "string",
                                "enum": ["INPATIENT_DOCTOR", "OUTPATIENT_DOCTOR", "PHARMACY", "OUTPATIENT_BILLING", "INPATIENT_BILLING", "INPATIENT_NURSE"],
                                "description": "指定测试六大工作站之一"
                            },
                            "headless": {
                                "type": "boolean",
                                "description": "是否后台静默运行（无窗口）。AI自动化建议为true"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "his_get_status",
                    "description": "获取当前测试任务的执行进度、通过率、失败项及异常错误堆栈。",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "his_verify_rules",
                    "description": "校验全院16条核心临床业务规则（如抗菌药物分级、出院带药限额、同组频次等）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rule_id": {
                                "type": "string",
                                "description": "可选。指定规则ID，不传则校验全量16条规则"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "his_switch_identity",
                    "description": "切换当前测试浏览器的会话角色身份（如医生、护士、药剂师、收费员），无需人工登出。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role_code": {
                                "type": "string",
                                "enum": ["INPATIENT_DOCTOR", "OUTPATIENT_DOCTOR", "PHARMACIST", "NURSE", "CHARGER"],
                                "description": "目标角色代码"
                            },
                            "dept_code": {
                                "type": "string",
                                "description": "目标科室代码（可选）"
                            }
                        },
                        "required": ["role_code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "his_get_logs",
                    "description": "获取测试系统底层的磁盘日志，用于分析测试失败原因。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "enum": ["app", "test_engine", "rules"],
                                "description": "日志源"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "读取最新行数，默认50行"
                            }
                        }
                    }
                }
            }
        ]

    def handle_tool_call(self, tool_name: str, arguments: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """分发执行来自大模型的 Function Calling 工具调用。"""
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except Exception:
                args = {}
        else:
            args = arguments or {}

        if tool_name == "his_run_tests":
            return self._request("/api/run", method="POST", payload=args)
        elif tool_name == "his_get_status":
            return self.get_status()
        elif tool_name == "his_verify_rules":
            return self.verify_rules(args.get("rule_id"))
        elif tool_name == "his_switch_identity":
            return self.switch_identity(args.get("role_code", ""), args.get("dept_code"))
        elif tool_name == "his_get_logs":
            return self.get_logs(args.get("source", "app"), args.get("limit", 50))
        else:
            return {"status": "error", "message": f"未知的工具名称: {tool_name}"}

# Global singleton instance for quick imports
sdk = HISAgentSDK()
