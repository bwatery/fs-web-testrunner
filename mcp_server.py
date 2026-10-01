"""
HIS WebRunner - MCP (Model Context Protocol) Server
Exposes all hospital automated testing capabilities to Claude Desktop, Cursor, Antigravity, and other MCP-enabled AI Agents.
"""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP

BASE_URL = "http://127.0.0.1:8989"

mcp = FastMCP(
    "HIS-TestRunner",
    instructions="HIS WebRunner 医院信息系统全栈自动化测试平台 MCP 工具集。支持调度全院六大工作站测试、临床业务规则校验、跨角色身份置换、底层日志诊断与页面调试。"
)

def _http_request(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{endpoint}"
    data = None
    headers = {"Content-Type": "application/json"}
    
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {"status": "ok"}
    except urllib.error.URLError as e:
        return {
            "error": True,
            "message": f"无法连接到 HIS WebRunner 执行服务 ({url})，请确认后台已启动 (start_webrunner.bat)。原因: {e}"
        }
    except Exception as e:
        return {"error": True, "message": str(e)}

@mcp.tool()
def his_run_tests(
    mode: str = "ALL",
    workstation: Optional[str] = None,
    selected_ids: Optional[List[str]] = None,
    headless: bool = True
) -> str:
    """启动 HIS 自动化测试任务。
    参数:
    - mode: 测试模式，'ALL'(全量) / 'INVASIVE'(仅页面实测) / 'NON_INVASIVE'(仅接口直测)
    - workstation: 可选，指定测试六大工作站之一：'INPATIENT_DOCTOR'(住院工作站), 'OUTPATIENT_DOCTOR'(门诊工作站), 'PHARMACY'(药房系统), 'OUTPATIENT_BILLING'(门诊收费), 'INPATIENT_BILLING'(住院收费), 'INPATIENT_NURSE'(住院护士)
    - selected_ids: 可选，指定特定测试用例 ID 列表
    - headless: 是否后台静默执行 (默认 True)
    """
    payload = {
        "mode": mode,
        "headless": headless,
        "selected_ids": selected_ids
    }
    if workstation:
        payload["workstation"] = workstation
        
    res = _http_request("/api/run", method="POST", payload=payload)
    if res.get("error"):
        return f"启动测试失败: {res['message']}"
    return f"测试已成功触发启动！当前任务用例数: {res.get('total', '未知')}。可调用 his_get_status 查看执行进度。"

@mcp.tool()
def his_get_status() -> str:
    """获取当前或最近一次自动化测试任务的执行进度、通过率、失败用例及耗时。"""
    res = _http_request("/api/status")
    if res.get("error"):
        return f"获取状态失败: {res['message']}"
    
    is_running = res.get("is_running", False)
    total = res.get("total_count", 0)
    passed = res.get("passed_count", 0)
    failed = res.get("failed_count", 0)
    results = res.get("results", [])
    
    status_str = "【正在运行中...】" if is_running else "【执行已完成/就绪】"
    summary = [
        f"HIS 测试引擎状态: {status_str}",
        f"总用例数: {total} | 通过: {passed} | 失败: {failed}",
        "------------------------------------"
    ]
    
    failed_cases = [r for r in results if r.get("status") == "FAILED"]
    if failed_cases:
        summary.append("⚠️ 异常失败用例列表:")
        for fc in failed_cases:
            summary.append(f"  • [{fc.get('test_id')}] {fc.get('name')} - 报错: {fc.get('error')}")
    else:
        summary.append("✅ 暂无失败用例或已全部顺利通过。")
        
    return "\n".join(summary)

@mcp.tool()
def his_stop_tests() -> str:
    """强制终止当前正在运行的测试任务并释放资源。"""
    res = _http_request("/api/stop", method="POST")
    if res.get("error"):
        return f"停止测试失败: {res['message']}"
    return "已成功发送终止指令，测试引擎正在安全释放浏览器与连接句柄。"

@mcp.tool()
def his_get_workstations() -> str:
    """查询医院六大核心业务工作站（住院、门诊、药房、门诊收费、住院收费、住院护士）的模块测试矩阵与通过率。"""
    res = _http_request("/api/workstations")
    if res.get("error"):
        return f"获取工作站信息失败: {res['message']}"
    
    wss = res.get("workstations", [])
    lines = ["全院六大核心业务工作站模块测试矩阵:", "===================================="]
    for ws in wss:
        lines.append(
            f"• 【{ws.get('name')} ({ws.get('code')})】: "
            f"总计 {ws.get('tests_count')} 项功能 | 通过 {ws.get('passed_count')} | 失败 {ws.get('failed_count')}"
        )
    return "\n".join(lines)

@mcp.tool()
def his_verify_business_rules(rule_id: Optional[str] = None) -> str:
    """校验全院 16 条核心临床与业务规则（或校验某一条指定规则）。
    参数:
    - rule_id: 可选，如 'rule_01_antibiotics'。不传则校验全量 16 条规则。
    """
    if rule_id:
        res = _http_request(f"/api/rules/{rule_id}/verify", method="POST")
        if res.get("error"):
            return f"校验规则 {rule_id} 失败: {res['message']}"
        return f"规则 [{rule_id}] 校验完成: 状态={res.get('status')} | 诊断信息={res.get('message', '正常')}"
    else:
        res = _http_request("/api/rules/verify_all", method="POST")
        if res.get("error"):
            return f"全量规则校验失败: {res['message']}"
        results = res.get("results", [])
        passed = sum(1 for r in results if r.get("status") == "PASSED")
        return f"全院 16 条核心业务规则校验完成！通过: {passed}/{len(results)} 项。"

@mcp.tool()
def his_switch_identity(role_code: str, dept_code: Optional[str] = None) -> str:
    """平滑置换当前测试浏览器的角色身份与科室上下文（无需人工登出）。
    常用角色:
    - 'INPATIENT_DOCTOR': 住院管床医生
    - 'OUTPATIENT_DOCTOR': 门诊接诊医生
    - 'PHARMACIST': 药房药剂师
    - 'NURSE': 病区护士
    - 'CHARGER': 门诊/住院收费员
    """
    payload = {"role_code": role_code}
    if dept_code:
        payload["dept_code"] = dept_code
    res = _http_request("/api/validator/switch_identity", method="POST", payload=payload)
    if res.get("error"):
        return f"身份置换失败: {res['message']}"
    return f"浏览器身份已成功切换为 【{role_code}】 (科室: {dept_code or '默认科室'})！"

@mcp.tool()
def his_get_logs(source: str = "app", limit: int = 50) -> str:
    """读取测试系统持久化磁盘日志，供 AI 进行错误定位与根因诊断。
    参数:
    - source: 'app'(系统日志), 'test_engine'(测试执行引擎日志), 'rules'(规则校验日志)
    - limit: 读取最近的日志行数 (默认 50 行)
    """
    res = _http_request(f"/api/logs?source={source}&limit={limit}")
    if res.get("error"):
        return f"获取日志失败: {res['message']}"
    lines = res.get("lines", [])
    if not lines:
        return f"[{source}.log] 暂无日志记录。"
    return "\n".join(lines)

@mcp.tool()
def his_diagnose_environment() -> str:
    """诊断目标 HIS 系统环境的前端地址、后端接口与数据库连通性。"""
    res = _http_request("/api/environment/test_connectivity", method="POST")
    if res.get("error"):
        return f"诊断失败: {res['message']}"
    return f"环境连通性诊断完成: 状态={res.get('status')} | 诊断详情={res.get('details', res.get('message', '正常'))}"

if __name__ == "__main__":
    mcp.run()
