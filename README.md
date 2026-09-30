# 🏥 HIS WebRunner - 医院信息系统全栈自动化测试与业务规则校验平台

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-Vue%203-409EFF.svg)](https://element-plus.org/)
[![Oracle Database](https://img.shields.io/badge/Oracle-Database-F80000.svg)](https://www.oracle.com/database/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **HIS WebRunner** 是一套专为现代医疗信息系统（**Vue 3 + Element Plus + VXE-Table + Oracle 微服务架构**）打造的企业级全栈自动化测试平台与临床业务规则校验引擎。  
> 平台深度覆盖 **住院全生命周期大闭环**、**医生长临医嘱时间继承**、**成组输液强一致性**、**门诊挂号收费**、**药房中心摆药**、**退药退费分离流转**、**出院结算五前置拦截** 等 47+ 项核心业务测试场景。

---

## 🌟 核心特性与设计亮点

### 1. 🛏️ 住院全生命周期大闭环 (Inpatient Full-Lifecycle E2E)
具备从患者自造数据录入到最终结算的全流程演练能力：
1. **入院登记与数据生成**：自造全新合规患者（支持选择“其他无证件人员”），全字段校验通过并生成住院号；
2. **预交金充值与额度核验**：押金缴纳、财务账本联动与可用额度计算；
3. **床位分配与入科流转**：病房管理中自动接收入科并分配至实际床位（如 401-2 床）；
4. **住院医生工作站开嘱**：双击载入患者完整上下文，下达长期医嘱与临时医嘱；
5. **住院护士工作站核对**：树形目录定位患者，核对医嘱并生成每日执行档；
6. **中心药房摆药发药**：住院摆药单自动生成，实物调配出库与库存实时扣减；
7. **退药退费闭环冲正**：护士站发起退药申请 ➔ 药房实物清点入库 ➔ 收费处负数红字记账冲正；
8. **出院登记与最终结算**：检索患者并穿透核算总费用、自付额、预交金返还与票据打印。

---

### 2. 📋 8 大核心临床与财务业务规则引擎 (Clinical & Financial Rules Engine)
在 `docs/INPATIENT_BUSINESS_RULES.md` 中全面规范并完成了代码化断言：
* **【医嘱开始时间自动继承】**：医生开立长/临医嘱新增行时，开始时间自动跟随上一条处于“暂存 (SV)”状态医嘱的开始时间，无需重复选择；
* **【成组输液时间联动】**：修改主药开始时间时，同组所有子医嘱（同 `groupNo`）开始时间自动联动更新；
* **【成组输液强一致性】**：同一组输液的给药途径（静脉输液）与执行频次（QD/BID）必须完全一致，严禁静滴与口服混搭；
* **【中西药物理隔离】**：中药饮片处方与西药严格隔离，强制录入剂数（付数）与煎服法；
* **【抗菌药物皮试闭环】**：皮试未出阴性结果前，护士站强行阻断核对，药房禁止发药；
* **【医嘱单向状态机】**：遵循 `暂存(SV) ➔ 提交(SB) ➔ 核对(VF) ➔ 执行(ET) ➔ 停止(ST)` 单向防篡改流转；
* **【先退药后退费分离】**：实物未入库，财务不退钱。药房未确认实物前阻断收费处红字退款；
* **【出院结算五前置拦截】**：未停长期医嘱、未执行临时医嘱、未确认退药单时强行阻断结算。

---

### 3. 🎭 双模驱动测试内核 (Dual Testing Modes)
* **【👀 侵入式·视觉演示套件】**：
  - 基于 Chrome Remote Debugging (CDP) WebSocket 协议，直连真实浏览器；
  - 模拟真实人类操作：真实表单键入、下拉 Popper 点击、表格行双击、树节点激活；
  - 自动分步捕获并归档高保真截图存证（保存在 `reports/screenshots/`）。
* **【🤖 非侵入式·AI静默验证套件】**：
  - 直连微服务 REST API 与 Oracle 数据库（`oracledb` 驱动）；
  - 毫秒级多角色 Token 交换（住院医生/住院护士/中心药房/住院收费处）；
  - 财务账目守恒断言、库存实物扣减与回退断言、数据库锁与事务一致性。

---

### 4. 🎨 Google Material Design 3 风格控制台
* **可视化 Web Dashboard**：运行于 `http://127.0.0.1:8989`；
* **实时 KPI 卡片**：用例总数、执行进度、通过率、异常阻断实时刷新；
* **Google Cloud Shell 抽屉终端**：底部抽屉式实时 WebSocket 执行日志，支持一键展开/折叠与清屏；
* **多角色身份中枢**：支持在门诊医生、门诊收费、住院医生、住院护士、中心药房等 10+ 角色间一键平滑置换。

---

## 🚀 快速上手与使用指南

### 一、运行环境准备

1. **操作系统**：Windows 10 / 11 或 Linux / macOS
2. **Python 版本**：Python 3.10 或更高版本
3. **依赖安装**：
   ```bash
   pip install -r requirements.txt
   ```

### 二、浏览器远程调试模式配置 (CDP 9222)
确保本地 Google Chrome 以远程调试模式启动：
```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:/chrome-dev-profile"
```

---

### 三、启动测试平台

#### 方式 1：启动可视化 Web 控制台（推荐体验）
在 Windows 资源管理器中直接双击：
👉 **`start_webrunner.bat`**  
*(或在终端中执行：`python run_runner.py`)*

启动成功后，浏览器访问控制台：
👉 **`http://127.0.0.1:8989`**

在界面中可以：
* 查看 47 个全量测试用例的分类大纲；
* 勾选特定用例或点击【一键执行全量测试】；
* 实时查看执行日志与错误分析。

---

#### 方式 2：命令行执行核心业务规则校验 (毫秒级)
验证医嘱时间跟随、成组一致性、先退药后退费等规则：
👉 **双击 `run_business_rules.bat`**  
*(或在终端中执行：`python run_rules_tests.py`)*

控制台将输出详细规则断言结果：
```text
============================================================
  住院系统业务规则与流程流转自动化测试引擎 (共 5 项规则)
============================================================
[PASS] ✓ 断言通过: 第二条医嘱开始时间成功跟随上一条暂存医嘱 (10:00:00)
[PASS] ✓ 断言通过: 组内时间联动强一致性通过
[PASS] ✓ 成功拦截违规同组医嘱: 静脉输液与口服禁止混搭
[PASS] ✓ 状态机防篡改单向流转校验通过 (ET 无法逆退至 SV)
[PASS] ✓ 财务安全门禁生效: 药房尚未确认实物入库，收费处阻断退款
[PASS] ✓ 出院结算硬性拦截门禁验证通过：成功阻断带有未停医嘱出院
============================================================
总计: 5 项规则全部校验完成！结果: 全部通过 🎉
```

---

#### 方式 3：全量命令行快速回归测试 (47 项用例)
👉 **双击 `run_cli_tests.bat`**  
*(或在终端中执行：`python run_cli_tests.py`)*

---

## 📂 项目工程结构目录

```text
fs_web_testrunner/
├── docs/                                # 业务规则与系统规范文档
│   └── INPATIENT_BUSINESS_RULES.md      # 🏥 住院核心业务规则全景规范 (8大规则体系)
├── core/                                # 自动化底层核心驱动
│   ├── test_engine.py                   # 测试调度主执行引擎与生命周期管理
│   ├── his_driver.py                    # CDP 浏览器低代码交互驱动器 (点击/双击/输入)
│   ├── login_validator.py               # 多角色 Token 置换与身份快速切换中枢
│   ├── emr_xml_validator.py             # 电子病历 WebAssembly XML 语法树校验器
│   └── oracle_db.py                     # Oracle 数据库直连与持久层校验
├── suites/                              # 业务测试套件集 (47 项测试用例)
│   ├── __init__.py                      # 套件总线统一注册中心
│   ├── test_suite_inpatient_business_rules.py # 📋 住院核心业务规则断言套件 (时间跟随/成组等)
│   ├── test_suite_inpatient_full_lifecycle.py  # 🏥 住院全生命周期大闭环端到端实测套件
│   ├── test_suite_invasive.py           # 👀 侵入式全流程视觉演示套件
│   ├── test_suite_non_invasive.py       # 🤖 非侵入式微服务与数据库静默套件
│   ├── test_suite_cpoe_closed_loop.py   # 💊 医嘱闭环全流程实测套件
│   └── test_his_03_inpatient.py         # 🛏️ 住院业务经典兼容套件
├── web_runner/                          # Material 3 风格前端控制台
│   ├── static/index.html                # Google 风格 Web 控制台主界面
│   └── app.py                           # FastAPI 后端服务与 WebSocket 日志管道
├── reports/                             # 自动化报告与截图存证
│   └── screenshots/                     # 全生命周期六幕高清凭证截图
├── config.py                            # 数据库与网络环境全局配置文件
├── requirements.txt                     # Python 运行依赖清单
├── start_webrunner.bat                  # 一键启动 WebRunner 控制台批处理
├── run_business_rules.bat               # 一键运行业务规则测试批处理
└── run_cli_tests.bat                    # 一键运行全量 CLI 快速测试批处理
```

---

## ⚙️ 环境与系统配置 (`config.py`)

如需适配您的医院内网测试环境，请编辑 `config.py`：

```python
# 医院系统前端 Web 地址
HIS_WEB_BASE = "http://192.168.1.198:8088"

# 医院微服务后端 API 端口
HIS_API_BASE = "http://192.168.1.198:8081"

# Oracle 数据库配置
ORACLE_DSN = "192.168.1.199:1521/orcl"
ORACLE_USER = "xchis"
ORACLE_PASS = "xchis"

# Chrome 远程调试端口
CDP_PORT = 9222
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。欢迎医院信息化同仁、医疗软件测试工程师共同交流与完善！
