"""
示例：如何使用 OpenAI 或任意大模型驱动 HIS 自动化测试平台
只需运行本脚本，大模型即可根据用户的自然语言自主选择调用测试、查看状态或分析日志！
"""

import os
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from his_agent_sdk import sdk

# 模拟大模型端到端 Function Calling 调度流程
def run_agent_turn(user_prompt: str):
    print(f"\n=======================================================")
    print(f"👤 用户需求: \"{user_prompt}\"")
    print(f"=======================================================")

    # 1. 获取 HIS 平台暴露的标准工具定义
    tools = sdk.get_openai_tools()
    print(f"[AI Agent] 已挂载 {len(tools)} 个原生 HIS 质检工具")

    # 2. 模拟 LLM 决策过程 (示例中使用业务分发逻辑)
    if "药房" in user_prompt:
        selected_tool = "his_run_tests"
        tool_args = {"workstation": "PHARMACY", "headless": True}
    elif "规则" in user_prompt:
        selected_tool = "his_verify_rules"
        tool_args = {}
    elif "日志" in user_prompt or "排查" in user_prompt:
        selected_tool = "his_get_logs"
        tool_args = {"source": "test_engine", "limit": 20}
    else:
        selected_tool = "his_get_status"
        tool_args = {}

    print(f"[AI Agent 决策] 触发工具: {selected_tool} | 参数: {tool_args}")

    # 3. 真正执行工具调用
    tool_result = sdk.handle_tool_call(selected_tool, tool_args)
    print(f"[工具返回结果]: {json.dumps(tool_result, ensure_ascii=False, indent=2)[:300]}...")

    # 4. 模拟 AI 总结汇报
    print(f"\n🤖 [AI 回复]: 已为您执行对应指令。工具返回状态正常，平台已平稳处理测试任务。")

if __name__ == "__main__":
    run_agent_turn("帮我测试一下药房系统的审方发药流程")
    run_agent_turn("检查一下全院业务规则")
