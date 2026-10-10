# 测试框架重构方案（交给 Antigravity 执行）

> 作者：zjck-21（Claude Code）　日期：2026-10-09
> 背景：用户指出"自动化测试代码太乱，启动方式既有新写的也有旧的；希望能在网页上展示；
> 原本的沙盒模式测试不准；需要**无头模式**与**网页显示**两种，且**都要求真实**"。
> 本文件是**执行方案**，不是讨论稿。执行时如遇与本文冲突的事实，先停下来报告，不要自行改方案。

---

## 一、先说结论：这次要做的是「换掉」，不是「包装」

**旧自动化测试模式（`core/`）的结论不可信，必须整体废弃，不能用新界面去包装它。**
它之所以不可信，是设计使然，不是实现质量问题：

| 旧模块 | 行数 | 问题 |
|---|---|---|
| `core/self_healing.py` | 287 | **自愈**：用例失败时自动尝试"补救"路径，把不该通过的判成通过 |
| `core/offline_sandbox.py` | 562 | **离线路由兜底**：不连真实后端也能"走完流程"，产出与真实环境无关的结论 |
| `core/test_engine.py` | 395 | 断言多为"存在性检查"，**无法失败** |
| `core/business_rules_manager.py` | 979 | 规则与断言耦合，改一处影响一片 |

已核实的历史事实：旧工具曾产出 **320 条从未执行过的"通过"**。这就是"测试不准"的根源。

### 最致命的一处：**导入即接管**（这条单独拎出来）

```
core/__init__.py          →  from . import offline_sandbox
core/offline_sandbox.py   →  最后一行：auto_configure_environment()      ← 导入时执行！
```

`auto_configure_environment()` 会探测内网网关，**探测不到就把 `requests.get/post` 与 `oracledb.connect`
整个替换成模拟实现**（`_patched_requests_*` / `_patched_oracledb_connect`）。

而 `run_verify.py:28` 是这么写的：

```python
from fs_web_testrunner.core.env_config import env_config
```

**也就是说：导入一个"配置模块"，就顺带触发了"整个后端可能被换成模拟"。**
用 `run_verify.py` 跑任何东西（包括 `--closed-loop`），都建立在"这次探测恰好通"的前提上。
这正是"沙盒会失真却看不出来"的机制 —— **不是它测错了，是你不知道它已经换了一套后端。**

（注：`AGENT_TASKS.md` 里给协作者的自动检查命令 `run_verify.py --closed-loop --cases L6-036`
正好走这条路。当前环境可达所以没有被接管，但这个前提不该存在。）

### 旧的网页界面是在**推荐**假通过，不是被动存在缺陷

`web_runner/static/index.html` 里明写着：

- `🟢 选项 A: 离线沙盒自适应通过 (推荐·全绿灯·行为仿真)`
- `🛡️ 智能自愈模式` 开关
- 执行结果里渲染 `🛡️ 自愈通过` 标签

一个把"全绿灯"当卖点的界面，**不能靠改文案救回来** —— 必须删掉重建。

**新框架的唯一真理来源**：`verify/` —— 独立闭环验证层。已核实它**对外零耦合**
（只 import `requests` / `oracledb` / `websocket` / 标准库，**没有一行引用 `core/`、`web_runner/`、`suites/` 或任何根模块**），
因此可以整体搬迁，风险极低。当前它已有 **66 条用例 = 通过 61 / 失败 1 / 未执行 4**，
且经变异自检（数值+日期+标志位+字符串全扰动）证明 **62 条里 52 条"库值一改就红"**（不是恒真摆设）。

**唯一的胶水**是根脚本 `run_verify.py` —— 全仓库只有它同时 import 两边：

```python
run_verify.py:27   from fs_web_testrunner.config import EMR_API_URL, REPORTS_DIR
run_verify.py:28   from fs_web_testrunner.core.env_config import env_config     # ← 触发上面那条接管
run_verify.py:110  from fs_web_testrunner.core.browser_driver import BrowserDriver
run_verify.py:111  from fs_web_testrunner.verify.ui_walk import UIWalker
```

搬迁时必须**切断这两条对 `core` 的依赖**（L2 页面巡检现在借用旧浏览器驱动；L1 借用旧配置）。

---

## 二、现状盘点（实测事实）

```
fs_web_testrunner/
├── core/              24 文件 522K   ← 旧引擎（自愈/沙盒/导入即接管）**待删**
│   ├── self_healing.py           自愈：失败时自动"补救"后仍判 PASSED
│   ├── offline_sandbox.py        沙盒：import 时 auto_configure_environment() 会替换 requests/oracledb
│   ├── test_engine.py            旧引擎主体（ADAPTIVE_MOCK 分支已在注释里标为"已废止"）
│   ├── browser_driver.py         旧 CDP 浏览器驱动（**run_verify.py 的 L2 还在借用它**）
│   └── env_config.py 等          配置/登录/业务规则等
├── suites/            27 文件 430K   ← 旧引擎的用例集（紧密耦合 core）**待删**
├── web_runner/        38 文件 646K   ← 旧网页 UI（FastAPI，默认 8989）**待删**
│   └── 界面里明写「🟢 选项 A: 离线沙盒自适应通过 (推荐·全绿灯)」「🛡️ 智能自愈模式」
├── verify/            28 文件 1.2M   ← 新闭环验证层 **保留，是未来核心**
│   └── closed_loop.py 196KB（含 55 条用例）+ flows/ + api_surface/smoke_api/ui_walk/workstation_check/report
├── tools/              3 文件  24K   ← collect.py / fetch_emr_spec.py / mutation_selfcheck.py
├── scratch/          616 文件  23M   ← 一次性脚本垃圾（已 gitignore，无代码引用）**待删**
├── reports/          993 文件  95M   ← 产物（716 张截图 + ~190 个验证产物）**保留，是网页数据源**
├── logs/               4.5M          ← 旧引擎的滚动日志（app.log/test_engine.log）**待删**
├── data/               5 文件 4.2M   ← 配置与 Swagger 规格缓存 **保留**
├── docs/               5 文件  44K   ← 其中 DEPLOYMENT_AND_CLI.md **已过期**
│                                        （引用了 run_web.py / config/hospital.json / Playwright，三者都不存在）
└── 顶层 *.py         74 个，其中 **~56 个是一次性脚本**（inspect_ 17 / check_ 11 / test_ 12 /
                      find_ 6 / click_ 3 / get_ 3 / nav_ 等）—— 没有任何文件 import 它们 **待删**
```

**文档本身也是割裂的**：`README.md`（18KB）整篇描述的是**旧产品**（WebRunner/TestEngine、
「离线沙盒自适应通过」的两模式架构），而 `AGENT_TASKS.md` 与 `reports/verify/*.md` 描述的是**新流程**，
两者从未互相校正。重构后 README 必须重写成一页，讲清新流程。

### 入口混乱的根源（用户抱怨的"启动方式两套"）

同一个闭环用例，**现在有两套互不相干的入口**，各写各的结果文件：

| 入口 | 用途 | 结果落到 |
|---|---|---|
| `python tools/collect.py regression` | 三轮回归 | `reports/verify/regression_*.log` |
| `python run_verify.py --closed-loop` | 体检入口的闭环分支 | 自己的报告 |
| `python run_verify.py --api` | 纯接口体检（**`--no-oracle` 就是那个"不连库"的模式**） | 自己的报告 |
| `python run_verify.py --ui` / `--workstations` | 页面巡检 | 自己的报告 |

`run_verify.py --no-oracle` 的原话是"不连数据库，仅按 Swagger 声明传参"——
**这正是用户说的"沙盒可能失真"**：它只能验接口参数形状，验不了任何业务。
**它当前被混在同一个入口里、用同一套状态词输出，这是最危险的地方。**

---

## 三、目标架构

**唯一入口、唯一包、环境可选、网页只读。**

```
fs_web_testrunner/
├── README.md                  # 一页说清：怎么装、怎么跑、结果是真是假
├── requirements.txt
├── fs_runner/                 # ← 唯一包
│   ├── __main__.py            #   python -m fs_runner <子命令>
│   ├── cli.py                 #   唯一的命令行解析
│   ├── config.py              #   环境/凭据/模式
│   ├── env/
│   │   ├── base.py            #   Env 接口：能否连库、能否连网关
│   │   ├── real.py            #   内网直连：网关 + Oracle（**唯一能产出"通过"的环境**）
│   │   └── sandbox.py         #   无库：只验参数形状，**永不产出"通过"**（见第四节）
│   ├── core/
│   │   ├── case.py            #   用例模型 + 断言原语（相等 / 不等式 / 防空跑）
│   │   ├── preconditions.py   #   ← 前置条件层（见第四节第 0 条）：声明式、走接口补齐、补不上即阻塞
│   │   ├── result.py          #   结果模型：status / note / evidence / env / source
│   │   └── runner.py          #   执行器：串行&并发、超时、失败隔离
│   ├── cases/
│   │   ├── closed_loop/       #   ← verify/flows/*.py 与 closed_loop.py 原样搬入
│   │   ├── api_probe.py       #   ← run_verify.py --api
│   │   └── ui_probe.py        #   ← run_verify.py --ui / --workstations
│   ├── report/
│   │   ├── json_writer.py     #   落 reports/*.json（沿用现有结构）
│   │   └── site.py            #   生成静态网页（数据源＝现有 JSON，不改测试逻辑）
│   └── web/
│       ├── app.py             #   只读展示服务（FastAPI）
│       └── static/
├── data/                      # 配置与规格缓存（保留）
├── reports/                   # 产物（保留）
└── tools/                     # 仅留真正需要的运维脚本
```

### CLI 设计（唯一入口）

```bash
# 无头模式 · 真实环境（默认，也是唯一能判"通过"的模式）
python -m fs_runner run --suite closed-loop
python -m fs_runner run --suite api
python -m fs_runner regression                 # 三轮回归

# 无头模式 · 沙盒（无数据库）—— 结果只能标"未验证"
python -m fs_runner run --suite api --env sandbox

# 网页显示（只读渲染 reports/，不跑测试）
python -m fs_runner serve --port 8990
```

**关键约束**：`--env` 决定真实性，且**必须写进每一条结果的 `evidence.env`**。

---

## 四、真实性保障（这是整件事的核心，不能打折）

用户要"无头模式 + 网页显示两种，**要求真实**"。这两件事的真实性靠下面五条保证：

### 0. 前置条件层：把「准备数据」和「判定结果」彻底分开

这条对应旧引擎的 `self_healing`。**先说清楚：它的本意不坏。**
"测试需要患者、但这里没有 → 自己建一个"是**任何自动化测试都必须做的事**，不是歪门邪道。
问题出在"自愈"把两件性质相反的事捆在一个名字下：

| | 例子 | 性质 |
|---|---|---|
| **A. 补齐前置** | 没患者就建一个 | **正当**，该做 |
| **B. 失败后绕过去继续** | 弹层挡住就点掉、用法被清空就替它填上，然后继续判 PASSED | **有害** |

而实测旧实现的真实行为是（比"强行判通过"更隐蔽）：

```python
core/self_healing.py:91   test_result.self_healed = True     # 只打标记，状态照旧 PASSED
core/test_engine.py:49    self_heal_enabled: bool = True     # 默认开着
```

界面再把它渲染成 `🛡️ 自愈通过` 的**褒义徽章** —— 把"替你擦了屁股"展示成勋章。
而且**全仓库没有任何显式的前置条件机制**（`ensure_*` 只有 `ensure_authenticated` 和 `_ensure_profile_prefs`，
都不是给测试数据用的）。

**它为什么有害（以"自建患者"为例）**：

1. **让用例自证**：测试自己造患者 → 再验证患者存在 → 恒真。
   而"这里没有患者时页面该怎样"这个**真实空态被永久漏测** —— 自愈把测试点吃掉了。
2. **归因丢失**：只记"补过"，不记"补了什么、补完对不对"。事后无人能判断这条"通过"里
   有多少是系统自己做到的、多少是工具替它做到的。
3. **掩盖的恰好是它该发现的**：`heal_usage_dept_wipeout` 是"用法/科室被清空时补上"——
   如果"切页面丢掉已填内容"**本身就是系统的 bug**，自愈去补，这个 bug 永远暴露不出来。
   **自愈和被测对象在打架。**
4. **假稳定**：自愈依赖当时的 DOM 状态，这次补上、下次没补上，结论就翻。
   真偶发红灯（如 L6-012）是**信号**，自愈制造的是**让红灯变绿的假稳定**，两者看着像、性质相反。

**新框架的前置条件层要求**：

- **声明式**：每条用例声明 `requires: [患者, 挂号, 在院登记]`，**不在测试步骤里边跑边补**
- **用被测系统自己的接口补齐**（走真实链路建患者），**不是绕过它** —— 顺带验了"建患者"这条链路
- **补完必须回读确认**（"我建的患者真的存在吗？"）—— 这一步本身就是一条断言
- **补不上 → `阻塞` / `未执行`，绝不允许是「通过」** ← 与自愈最本质的区别
- **evidence 必须写明**：本次用了哪些自建数据、ID 是什么
- **要有统计并暴露**：多少条用例是"靠自建数据才跑起来的"。
  **比例高 = 本环境不具备测试条件** —— 这个结论必须给到决策者，不许被抹平

**造数据的三种方式，可信度不同，必须分开对待**：

| 方式 | 可信度 | 适用 |
|---|---|---|
| 用被测系统接口造 + 回读 | **高**（顺带验了链路） | 推荐 |
| 直接写数据库造 | 中（绕过业务规则） | 仅用于纯读类用例的前置 |
| 使用已有历史数据 | 高（最真实） | 优先，但常常不够用 |

**UI 层"卡住了"那类**（关遮挡弹层、等元素出现）单独归为**驱动层稳健性**，不属于自愈：
可以做，但 ① 必须记一笔（"本次等待了 3 次"）② **不许代替系统完成业务动作** ——
帮用户点"保存"就越界了，那是替被测系统干活。

### 1. 状态词不得混用

沿用总表既有的五个词（通过 / 失败 / 阻塞 / 跳过 / 未执行），但**加一条硬约束**：

> **沙盒（无库）环境永远不能产出「通过」。** 它只能产出「未执行」，
> 备注写明"沙盒模式：仅校验接口参数形状，未验证业务"。

理由：沙盒验的是"参数能不能传进去"，不是"业务对不对"。判"通过"就是把没验的东西说成验了 ——
这正是旧工具干过的事。

### 2. 每条结果必须自带出处

`evidence` 里必须能回答："这条绿是拿什么等式换来的？等式两边分别从哪来？"
现有结构已支持（`evidence` 里有库值、接口值、等式），重构后**保持并强制**。

### 3. 网页上分开呈现

- **真实环境结果**：实心、可写进总表
- **沙盒结果**：灰底 + 虚线边框 + 显著标记，**且不提供"写入总表"的入口**
- **历史红绿**：保留。像 L6-012 那次偶发红灯要能看见 —— 这是可信度的证据，不是污点

### 4. 防空跑判断要加固

变异自检（2026-10-09）发现一个真实弱点：
**"没数据就跳过"的判断如果依据的是算出来的值（`COUNT(*)` / `SUM()`），那个值一旦被污染，
用例会从「未执行」静默翻成「通过」**（实测 L9-013：变异环境下变"通过"，正常环境下是"未执行"）。

加固要求：防空跑判断必须把**它当时观测到的值写进 `evidence`**，
使得任何一次"通过"都能被事后审计："它当时看到几条数据？"

---

## 五、分步迁移（每步都要能验收，不许一把梭）

> 原则：**每一步结束后，`python -m fs_runner regression` 必须三轮全绿，
> 且用例数与通过数与本步之前完全一致。** 数量对不上就是搬错了。

### 第 0 步 · 冻结基线
- `git tag baseline-20261009`，记录当前 `closed_loop_latest.json` 的用例数与通过数
- 把 `verify/` 当前 55 条用例的结果作为**唯一对照基准**

### 第 1 步 · 建骨架、原样搬迁（**不改一行逻辑**）
- 建 `fs_runner/`，把 `closed_loop.py` + `flows/` 原样搬进 `fs_runner/cases/closed_loop/`
- 只改 import 路径，不改断言
- **验收**：跑 `regression`，66 条结果与基线**逐条一致**（含 evidence）

### 第 2 步 · 合并入口，并切断对 `core` 的两条依赖
- 把 `run_verify.py` 的 `--api` / `--ui` / `--workstations` / `--closed-loop` 收进 `fs_runner/cli.py`
- **必须切断这两行**（这是新层与旧引擎唯一的胶水）：
  ```python
  run_verify.py:28   from fs_web_testrunner.core.env_config import env_config     # → 换成 fs_runner/config.py
  run_verify.py:110  from fs_web_testrunner.core.browser_driver import BrowserDriver  # → L2 自建 CDP 客户端
  ```
  注意：L3（`verify/workstation_check.py`）**已经自建了 CDP 客户端**、刻意不用旧的 `browser_driver`，
  L2 可以照它的做法办。**切完这两行之后，`verify/` 才真正与旧引擎无关。**
- `tools/collect.py regression` 变成 `fs_runner regression` 的包装
- **验收**：新 CLI 能复现旧入口的全部功能；**并确认 import 时不再触发任何 `core` 侧副作用**

### 第 3 步 · 隔离沙盒
- 实现 `env/sandbox.py`：只验接口参数形状。**不得**采用旧实现的"替换 requests/oracledb"那种做法 ——
  那是"接管"不是"隔离"，会让人分不清自己在测哪套后端
- **强制**沙盒结果不得为"通过"（第四节第 1 条）
- **验收**：`--env sandbox` 跑一遍，确认输出里**一条"通过"都没有**

### 第 4 步 · 删除旧物
- 删除 `core/`（旧引擎：自愈 + 沙盒 + 导入即接管）—— **这是本次重构的目的**
- 删除 `suites/`（27 文件 430K，旧引擎的用例集，紧密耦合 `core`）
- 删除 `web_runner/`（旧的 8989 UI，界面本身在推荐"全绿灯"）
- 删除 `logs/`（旧引擎日志）
- 删除 `scratch/`（616 文件 23M）
- 删除顶层 ~56 个一次性脚本（`inspect_*` 17 / `check_*` 11 / `test_*` 12 / `find_*` 6 / `click_*` 3 / `get_*` 3 / `nav_*` / `capture_*` / `reload_*` / `interact_*`）——
  已核实**没有任何文件 import 它们**
- 多个 `run_*.py`（`run_cli_tests.py` / `run_outpatient_tests.py` / `run_rules_tests.py` /
  `run_single_test.py` / `run_invasive_only.py` / `run_non_invasive_only.py` / `run_login_validator.py`）
  已并入 CLI 的一并删除
- **改判**：`cli_agent.py` / `his_agent_sdk.py` / `mcp_server.py` 是旧 WebRunner 的 `/api/*` 客户端，
  旧 UI 删了它们就是死的 —— 一并删除（除非用户明确要保留 AI 工具面）
- **保留**：`verify/`（已搬入）、`data/`、`reports/`、`tools/collect.py`、`tools/fetch_emr_spec.py`、
  `export_*_excel.py`、`update_tracking_excel.py`、`sync_insurance_status.py`、`config.py`（并入 `fs_runner/config.py`）
- **重写** `README.md`（现在整篇讲的是已删掉的旧产品）、`docs/DEPLOYMENT_AND_CLI.md`（已过期）
- **验收**：删完后 `regression` 仍三轮全绿

### 第 5 步 · 网页展示
- `fs_runner/web/app.py`：**只读**渲染 `reports/*.json`，不跑测试、不写库
- 页面三块：① 用例列表（可点开看等式） ② 未执行清单＋原因 ③ 历史红绿趋势
- 真实/沙盒分组呈现（第四节第 3 条）
- **验收**：页面上的每一条都能追溯到 evidence；沙盒结果视觉上显著区分

### 第 6 步 · 加固与自检
- 防空跑判断写入观测值（第四节第 4 条）
- 把变异自检固化成一个子命令：`python -m fs_runner selfcheck --mutation`
- 并把「非数值变异」（改字符串 / 翻标志位 / 偏移时间戳）补上 ——
  当前 66 条里只有 52 条被证明敏感，剩下 23 条(非数值断言)尚未证明

---

## 六、待确认事项（开工前先问用户，别自己决定）

1. **AI 工具面要不要留？** `cli_agent.py` / `his_agent_sdk.py` / `mcp_server.py` 是旧 WebRunner 的
   `/api/*` 客户端。旧 UI 删了它们就是死的。**本次默认删**；若用户要保留"用 AI 指挥测试"的能力，
   需要单独重做（不要复活旧 UI 来支撑它）。
2. **`data/environment_config.json` 里的 `mode` 字段可能是死配置** —— 没找到读它的地方，
   实际切换走的是 `activate_*_mode()`。重构时不要照搬这个字段。
3. **策略取值不一致**：提交在盘的 JSON 写 `STRICT`，而 `core/env_config.py` 的代码默认是
   `ADAPTIVE_MOCK`，UI 又推荐 "选项 A（全绿灯）"。这三者互相矛盾 —— 也是"结论不可信"的一部分。
   新的 `env` 只有两个值：`real` / `sandbox`，不要保留 `AUTO`。
4. **`reports/screenshots/` 716 张截图**要不要留？网页展示会用到一部分；建议保留，
   但可以按时间归档，避免仓库无限膨胀。

---

## 七、红线（与测试工作一致，不得违反）

1. **不许在没有独立等式的情况下判「通过」**
2. **不许把"没数据"写成"通过"** —— 没数据就是「未执行」并说明
3. **沙盒结果不得写入总表状态**，不得与真实结果混排
4. **不许恢复自愈/兜底逻辑**（`self_healing` 那套思路一律不要）
5. **搬迁期间不许改断言**；要改断言另开一步，且改完必须说明"哪条原来是误报"
6. 每步做完**报告并停下**，等我复核后再进下一步

---

## 八、验收标准（全部满足才算重构完成）

- [ ] `python -m fs_runner regression` 三轮全绿，**66 条**结果与基线逐条一致
- [ ] 全仓库只剩一个入口（`python -m fs_runner ...`）
- [ ] `core/`、`suites/`、`web_runner/`、`logs/`、`scratch/`、顶层一次性脚本全部删除
- [ ] **import 任何模块都不再产生副作用**（不再有"导入即接管"）
- [ ] `--env sandbox` 的输出里**零个"通过"**
- [ ] 网页能打开，每条结果可追溯到 evidence，真实/沙盒视觉分离
- [ ] **前置条件层就位**：用例声明 `requires`，缺数据走接口补齐并回读；**补不上报阻塞而非通过**；
      页面能看到"多少条用例靠自建数据才跑起来"
- [ ] **代码里不再有任何"自愈/兜底"路径**（grep 不到 `self_heal` / `healing` / `fallback.*pass`）
- [ ] `selfcheck --mutation` 可一键复现"断言是否敏感"的结论
- [ ] README 一页说清：怎么装、怎么跑、**结果是真还是假的、凭什么**

---

## 八、给执行者的话

这件事的价值不在于"代码变整齐"，而在于：
**让任何一个人打开网页时，能看出每一条绿是拿什么换来的。**

旧工具失败的教训不是"代码写得丑"，是**它让结论看起来比实际可靠**。
重构过程中任何时候想"这里先兜个底、先让它绿"，就是回到了老路上 —— 停下来报告。
