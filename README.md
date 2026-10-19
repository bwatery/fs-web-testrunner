# FS.TestRunner · 医院信息系统自动化测试与业务规则校验平台

一套专为医疗信息系统（Vue 3 + Element Plus + VXE-Table + Oracle 微服务架构）打造的自动化测试套件与业务规则校验引擎。

---

## 唯一执行入口 (`fsrun.py`)

系统统一通过隔离模式命令执行（避免隐式依赖干扰）：

```bash
python -I fsrun.py <command> [options]
```

### 常用子命令速查表

| 子命令 | 说明 | 典型示例 |
|---|---|---|
| `run` | 运行测试套件（支持闭环套件、冒烟套件等） | `python -I fsrun.py run --suite closed-loop` |
| `regression` | 运行三轮回归测试，含跑前跑后库中测试数据零残留比对 | `python -I fsrun.py regression` |
| `ui-verify` | 真实浏览器 (CDP) 驱动界面验证与 Oracle 持久层对账 | `python -I fsrun.py ui-verify --headless --screenshot` |
| `rules` | 业务规则库治理（AST 断言静态扫描、Schema 校验、双向反查） | `python -I fsrun.py rules --check` |
| `selfcheck` | 变异自检（内存扰动库值/接口响应，验证断言变红敏感度） | `python -I fsrun.py selfcheck --mutation` |
| `cleanup-testdata` | 测试患者与关联流水安全清理（默认 dry-run 预览，`--yes` 物理回滚） | `python -I fsrun.py cleanup-testdata` |
| `serve` | 启动只读 Web 控制台（查看用例、历史红绿、缺陷单列） | `python -I fsrun.py serve --port 8989` |

---

## 项目工程结构

```text
fs_web_testrunner/
├── fs_runner/             # 核心测试执行器框架 (CDP浏览器驱动、契约测试、断言引擎、Web控制台)
├── verify/                # 业务闭环与验证套件 (closed_loop, api_surface, workstation_check, ui_walk)
├── tools/                 # 数据造数、报表导出、台账同步工具
├── rules/                 # 业务规则库定义 (YAML) 与 AST 绑定
├── data/                  # 基础配置与脱敏参考数据 (包含 db_config.json 模板)
├── docs/                  # 核心架构与业务工作流文档
│   ├── assets/images/     # 核心文档截图证据
│   └── archive/           # 历史多轮迭代回执与产出归档
├── reports/               # 运行时测试报告与输出目录 (Git 忽略临时生成物，仅保留基线与定义)
├── baseline_66.json       # 66 条业务闭环基线测试集
├── fsrun.py               # 统一命令行执行入口
├── run_verify.py          # 兼容历史调用的测试入口
├── config.py              # 全局配置入口
├── requirements.txt       # Python 依赖清单
└── *.bat                  # Windows 快速启动脚本
```

---

## 真实环境 vs 离线沙盒防伪保证

平台严格贯彻「**真实必留痕、沙盒绝不判通过**」的防伪准则：

1. **真实环境 (`--env real`, 默认)**：
   - 直连真实 SpringCloud 微服务与现场 Oracle 物理数据库；
   - 验证真实业务状态机流转、财务账目守恒与持久层事务一致性；
   - **造数护栏**：所有写库操作接入审计（`_created_*.json`），设置单次造数安全阈值熔断（默认 50 条），回归前后执行库表零残留强校验。
2. **离线沙盒 (`--env sandbox`)**：
   - 纯本地离线参数形状校验，物理拦截所有网络出口与数据库连接；
   - **硬约束：沙盒模式绝不产出「通过」**，只判为「未执行（沙盒模式）」或「参数校验异常」，彻底杜绝离线环境伪造通过假象。

---

## 现状能力与已知限制

### 现状能力
- **闭环业务套件**：覆盖 66 条端到端业务与财务闭环流程（基线分布：通过 59 / 失败 1 / 阻塞 1 / 跳过 2 / 未执行 3）。
- **界面业务断言**：通过真实表单登录提取 Token，CDP 读取前端页面渲染文本与 VXE-Table 表格，与 Oracle 持久层执行 1:1 双向对账。
- **规则 ↔ 代码绑定**：56 条业务规则（`rules/*.yaml`）通过 AST 静态扫描与 `ids.py` 常量库与代码断言建立双向溯源；`rules --rule <ID>` 精确定位代码断言行号。

### 已知限制与保护
- **已知系统缺陷**：`L5-027`（出院结算退款明细缺失）为被测系统客观缺陷，测试套件保持真实断言失败，不予放行。
- **造数闸门保护**：`L6-001`、`L6-009`、`L6-012` 默认阻断新建测试患者，避免持续污染生产或测试库。
- **界面权限隔离**：当前测试账号 (`admin`) 仅挂载住院/病历类菜单，门诊退号与药房窗口按路由守卫策略进行安全拦截，界面断言严守住院业务（宁缺毋滥，绝不伪造）。
