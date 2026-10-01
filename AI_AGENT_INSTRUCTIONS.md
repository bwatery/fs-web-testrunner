# HIS WebRunner - AI 智能体直接协同与外骨骼指令卡

> **适用对象**：ChatGPT、Claude、DeepSeek、Kimi、Cursor、Antigravity、本地部署大模型（Ollama/vLLM）以及任意支持 Tool-Use / Function Calling / 终端命令行执行的 AI Agent。

---

## 1. 智能体系统提示词 (System Prompt - 直接复制给 Agent)

```text
你是一个医疗 HIS（医院信息系统）高级自动化测试与质量保障专家 Agent。
你拥有自主操控 HIS 自动化测试平台的能力，可以对全院六大工作站（住院医生站、门诊医生站、药房系统、门诊收费、住院收费、住院护士）进行全流程自动化测试、临床业务规则校验、浏览器身份置换以及日志排查。

你的工作原则：
1. 目标导向：当用户要求测试某个模块或排查问题时，主动调用工具执行，并在拿到结果后进行深度分析，向用户汇报核心指标（通过率、失败项、可能原因）。
2. 异常诊断：若测试用例失败，主动拉取对应失败日志（his_get_logs 或 cli_agent.py logs），给出根因分析及修复建议。
3. 规范操作：在进行跨科室业务前，确保浏览器身份已切换为对应岗位的角色（如开医嘱切换为医生，发药切换为药剂师）。
```

---

## 2. 外部智能体 4 种快速接入方式对比

| 接入方式 | 适用场景 | 接入成本 | 特点 |
| :--- | :--- | :--- | :--- |
| **① Dify / 扣子 Coze** | 零代码可视化智能体编排 | ⭐ 极低（1分钟导入） | 导入 `docs/openapi_dify.json` 即可生成一整套智能体插件工具 |
| **② MCP 协议** | Claude Desktop / Cursor / Antigravity | ⭐ 极低（配置即用） | 将 `mcp_config.json` 挂入客户端，AI 自动感知 8 大质检函数 |
| **③ Python SDK** | LangChain / AutoGen / 自研 Python Agent | ⭐⭐ 低（3行代码） | `from his_agent_sdk import sdk`，原生导出 OpenAI Tools Schema |
| **④ CLI / 终端命令行** | 具有终端执行权限的 Agent / CI流水线 | ⭐ 极低（直接运行） | 直接在 Bash / PowerShell 运行 `python cli_agent.py <subcommand>` |

---

## 3. 终端命令行快速调用速查表 (CLI Reference)

如果你的智能体具备命令行执行能力（如 Antigravity、Cursor Agent、Claude Code），可以直接下发以下终端命令：

```bash
# 1. 触发全院全量 86 项自动化测试
python cli_agent.py run

# 2. 触发指定工作站测试并实时监视进度 (--watch 直到完成)
python cli_agent.py run -w PHARMACY --watch
# 可选工作站代码: INPATIENT_DOCTOR | OUTPATIENT_DOCTOR | PHARMACY | OUTPATIENT_BILLING | INPATIENT_BILLING | INPATIENT_NURSE

# 3. 有头模式（弹出真实浏览器看操作画面）
python cli_agent.py run -w INPATIENT_DOCTOR --head

# 4. 获取当前测试执行进度、通过率与失败清单 (文本模式)
python cli_agent.py status

# 5. 获取 JSON 结构化数据 (非常适合 Agent 解析提取字段)
python cli_agent.py --json status

# 6. 一键校验全院 16 条核心临床业务规则
python cli_agent.py rules

# 7. 切换测试浏览器身份为药房药剂师 (无需手工登出)
python cli_agent.py switch-role -r PHARMACIST

# 8. 查看系统底层最新 50 行排错日志
python cli_agent.py logs -s test_engine -n 50

# 9. 诊断 HIS 前端、后端 API 及 Oracle 数据库网络连通性
python cli_agent.py diagnose
```

---

## 4. 原生 REST API / cURL 接口速查表 (HTTP Calling)

若智能体运行在独立网络环境中，可直接通过 HTTP 发起调用（服务端默认运行在 `http://127.0.0.1:8989`）：

### 4.1 触发测试执行
* **URL**: `POST /api/run`
* **Payload**:
  ```json
  {
    "mode": "ALL",
    "workstation": "PHARMACY",
    "headless": true
  }
  ```
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8989/api/run \
       -H "Content-Type: application/json" \
       -d "{\"mode\": \"ALL\", \"workstation\": \"PHARMACY\", \"headless\": true}"
  ```

### 4.2 查询执行状态
* **URL**: `GET /api/status`
* **cURL**:
  ```bash
  curl -s http://127.0.0.1:8989/api/status
  ```

### 4.3 强制终止任务
* **URL**: `POST /api/stop`
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8989/api/stop
  ```

### 4.4 校验全院业务规则
* **URL**: `POST /api/rules/verify_all`
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8989/api/rules/verify_all
  ```

### 4.5 切换浏览器角色身份
* **URL**: `POST /api/validator/switch_identity`
* **Payload**: `{"role_code": "INPATIENT_DOCTOR", "dept_code": "1001"}`
* **cURL**:
  ```bash
  curl -X POST http://127.0.0.1:8989/api/validator/switch_identity \
       -H "Content-Type: application/json" \
       -d "{\"role_code\": \"INPATIENT_DOCTOR\"}"
  ```

### 4.6 读取排错日志
* **URL**: `GET /api/logs?source=test_engine&limit=50`
* **cURL**:
  ```bash
  curl -s "http://127.0.0.1:8989/api/logs?source=test_engine&limit=50"
  ```

---

## 5. 常见质检场景与 AI 决策链 (Decision Playbook)

### 场景 A：日常发版全量回归
1. AI 发起 `python cli_agent.py run --watch`；
2. 监视测试进度直至 100%；
3. 调用 `python cli_agent.py rules` 校验临床规则是否被破坏；
4. 汇总生成发布质量验收报告（用例总数、通过率、耗时）。

### 场景 B：排查药房审方失败原因
1. 用户告知：“药房审方测试怎么报错了？”
2. AI 调用 `python cli_agent.py logs -s test_engine -n 30`；
3. 定位日志中的 `[ERROR] [FAIL]` 行与堆栈追踪；
4. 向用户解释：“经排查，系统在模拟药师审方时，测试用例中的头孢曲松与禁忌症规则发生冲突，触发了阻断拦截，属于正常业务拦截逻辑而非系统崩溃”。
