# HIS WebRunner 自动化测试系统 - 完整部署与终端调用指南

本文档详细介绍 HIS WebRunner 自动化测试平台的部署架构、服务器上线步骤、后台守护运行方法以及在终端进行调用的多种方式。

---

## 目录
1. [系统环境要求](#1-系统环境要求)
2. [本地 / Windows 测试机部署](#2-本地--windows-测试机部署)
3. [医院内网 / 独立服务器生产部署](#3-医院内网--独立服务器生产部署)
4. [Windows 后台服务与开机自启 (守护进程)](#4-windows-后台服务与开机自启-守护进程)
5. [Docker 容器化部署方案 (可选)](#5-docker-容器化部署方案-可选)
6. [终端命令行调用完整指南](#6-终端命令行调用完整指南)
7. [常见运维问题排查 (FAQ)](#7-常见运维问题排查-faq)

---

## 1. 系统环境要求

* **操作系统**：Windows 10/11、Windows Server 2016/2019/2022、或者主流 Linux 发行版（Ubuntu 20.04+, CentOS 7+）
* **Python**：Python 3.10 或更高版本
* **浏览器驱动**：Playwright Chromium 内核
* **网络端口**：默认占用 `8989` 端口（可在配置中修改）

---

## 2. 本地 / Windows 测试机部署

### 步骤 1：克隆或拷贝项目文件
确保项目解压或克隆到目标机器工作目录，例如 `D:\fs_web_testrunner`。

### 步骤 2：安装 Python 依赖
打开 Windows 终端（PowerShell 或 CMD），进入项目根目录：
```powershell
pip install -r requirements.txt
```

### 步骤 3：安装 Playwright 浏览器内核
本平台支持对前端界面进行真实侵入式点击测试，依赖 Playwright Chromium 内核：
```powershell
playwright install chromium
```
*(注：如果服务器处于离线内网，可在有网环境下载好 Chromium 驱动包放入 `%USERPROFILE%\AppData\Local\ms-playwright` 目录下。)*

### 步骤 4：启动服务
* **方式 A (推荐·双击运行)**：直接双击项目根目录下的 `start_webrunner.bat`。
* **方式 B (终端启动)**：
  ```powershell
  python run_web.py
  ```
启动成功后，控制台会输出：
```text
INFO:     Uvicorn running on http://127.0.0.1:8989 (Press CTRL+C to quit)
```
打开浏览器访问 `http://127.0.0.1:8989` 即可看到完整的可视化测试控制台！

---

## 3. 医院内网 / 独立服务器生产部署

如果需要将测试平台部署在内网服务器，供全院开发团队、测试团队以及外部 AI 统一调用：

### 1. 修改监听地址为 `0.0.0.0`
编辑 `run_web.py`，将 host 调整为 `0.0.0.0`：
```python
uvicorn.run("web_runner.app:app", host="0.0.0.0", port=8989, reload=False)
```

### 2. 开放防火墙 8989 端口
在 Windows Server 上的 PowerShell 管理员终端执行：
```powershell
New-NetFirewallRule -DisplayName "HIS-TestRunner" -Direction Inbound -LocalPort 8989 -Protocol TCP -Action Allow
```

### 3. 配置医院真实 HIS 目标地址
编辑 `config/hospital.json`，配置被测系统的实际 URL、API 地址及数据库连接串：
```json
{
  "target_system": {
    "web_url": "http://192.168.10.88:8080/his-web",
    "api_base_url": "http://192.168.10.88:8080/his-api"
  }
}
```
此时，内网同网段机器均可通过 `http://<服务器IP>:8989` 访问控制台与 API。

---

## 4. Windows 后台服务与开机自启 (守护进程)

为了确保服务器重启后测试服务不中断，推荐以下两种后台守护方案：

### 方案 A：使用 NSSM 将其注册为 Windows 系统服务（最稳健）
1. 下载 [NSSM (Non-Sucking Service Manager)](https://nssm.cc/download)；
2. 管理员权限打开 CMD 执行：
   ```cmd
   nssm install HISTestRunner "C:\Python311\python.exe" "run_web.py"
   nssm set HISTestRunner AppDirectory "D:\fs_web_testrunner"
   nssm start HISTestRunner
   ```
3. 此时该程序成为后台静默系统服务，随系统开机自动拉起，崩溃自动重启。

### 方案 B：使用 Windows 任务计划程序
1. 打开 `taskschd.msc`（任务计划程序）；
2. 创建基本任务 ➔ 触发器选择「计算机启动时」；
3. 操作选择「启动程序」➔ 脚本选择 `start_webrunner.bat` ➔ 起始于填入项目根目录绝对路径。

---

## 5. Docker 容器化部署方案 (可选)

如需在 Linux / K8s 集群中部署，可使用如下 Dockerfile：

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8989
CMD ["python", "-m", "uvicorn", "web_runner.app:app", "--host", "0.0.0.0", "--port", "8989"]
```

运行命令：
```bash
docker build -t his-webrunner:latest .
docker run -d --name his-runner -p 8989:8989 his-webrunner:latest
```

---

## 6. 终端命令行调用完整指南

平台提供了丰富的终端调用渠道，无论是人类工程师调试，还是智能体/CI流水线自动化调用，都能极速完成。

### 方式 1：使用内置外骨骼命令行工具 `cli_agent.py`（推荐）
我们在根目录提供了专门的 `cli_agent.py` 终端脚本，支持丰富的指令和格式化控制：

```powershell
# 1. 查看帮助与所有可用指令
python cli_agent.py --help

# 2. 触发全院全量 86 项自动化测试
python cli_agent.py run

# 3. 运行特定工作站测试（支持: INPATIENT_DOCTOR, OUTPATIENT_DOCTOR, PHARMACY, OUTPATIENT_BILLING, INPATIENT_BILLING, INPATIENT_NURSE）
python cli_agent.py run -w PHARMACY

# 4. 运行测试并挂起控制台，实时打印进度条直至任务结束 (--watch)
python cli_agent.py run -w INPATIENT_BILLING --watch

# 5. 查看当前系统测试状态、通过率及失败用例
python cli_agent.py status

# 6. 一键校验全院 16 条核心临床业务规则（抗菌药、限额、频次等）
python cli_agent.py rules

# 7. 动态切换测试浏览器身份为药房药剂师 (无需手工登出重新登录)
python cli_agent.py switch-role -r PHARMACIST

# 8. 读取最近 50 行持久化测试日志进行排障
python cli_agent.py logs -s test_engine -n 50

# 9. 远程连接调用 (如果服务跑在另一台服务器)
python cli_agent.py --url http://192.168.1.100:8989 status

# 10. 输出机器友好的纯 JSON (非常适合 CI/CD 脚本或 AI 提取字段)
python cli_agent.py --json status
```

---

### 方式 2：使用标准 cURL / PowerShell 进行 HTTP 直调
在任意无 Python 环境的终端中，直接利用系统自带的 `curl` 即可操控：

```powershell
# 启动测试任务
curl -X POST http://127.0.0.1:8989/api/run -H "Content-Type: application/json" -d "{\"mode\": \"ALL\", \"workstation\": \"PHARMACY\", \"headless\": true}"

# 查询进度
curl -s http://127.0.0.1:8989/api/status

# 终止测试
curl -X POST http://127.0.0.1:8989/api/stop

# 校验规则
curl -X POST http://127.0.0.1:8989/api/rules/verify_all

# 查看日志
curl -s "http://127.0.0.1:8989/api/logs?source=test_engine&limit=30"
```

---

### 方式 3：CI/CD 自动化流水线集成 (Jenkins / GitLab CI)
可在构建脚本中加入如下步骤，实现发版前自动回归质检：

```bash
# 执行自动化回归，失败则中断流水线
python cli_agent.py run -w ALL --watch
if [ $? -ne 0 ]; then
  echo "HIS 自动化测试未完全通过，中断部署流程！"
  exit 1
fi
```

---

## 7. 常见运维问题排查 (FAQ)

### Q1: 运行 `python cli_agent.py` 提示连接拒绝 (Connection Refused)？
**答**：请确保 WebRunner 服务已启动（默认端口为 `8989`）。若服务部署在远端，请带上 `--url http://<目标IP>:8989` 参数。

### Q2: 侵入式页面测试报错 `Executable doesn't exist at ...`？
**答**：说明 Playwright 尚未下载 Chromium 内核，请在终端执行 `playwright install chromium`。

### Q3: 端口 8989 被占用如何处理？
**答**：修改 `run_web.py` 中的 `port=8989` 为其他可用端口（如 `8990`），客户端和 CLI 调用时指定对应端口即可。

### Q4: 终端输出中文乱码？
**答**：`cli_agent.py` 已内置 Windows 控制台 UTF-8 自动重配逻辑。若在原生 CMD 下乱码，可先输入 `chcp 65001` 切换代码页为 UTF-8。
