# 【回执 · 重构第 2 步】合并入口，切断对旧引擎 core/ 的依赖

> **执行分支**：`refactor/fs-runner`（master 分支未受任何触碰，保持可交付状态）  
> **基线对齐**：`reports/verify/baseline_66.json`（66 条 = 通过 61 / 失败 1 [L5-027] / 未执行 4 [L5-022, L5-037, L9-013, L9-014]）  
> **日期**：2026-10-10  

---

## 一、验收标准完成情况总览

| 验收项 | 要求 | 实测结果 | 状态 |
|---|---|---|---|
| **1. 切断 core 依赖** | `run_verify.py` line 28 & 110 改接 `fs_runner` | line 28 改接 `fs_runner.config`，line 110 改接 `fs_runner.cases.ui_probe` | ✅ 达标 |
| **2. core 零副作用** | `import fs_runner` 绝不加载 `fs_web_testrunner.core.*` | 断言执行通过，`sys.modules` 中 `core` 相关模块数为 0 | ✅ 达标 |
| **3. collect 统一入口** | `tools/collect.py regression` 转调 `fs_runner.cli` | 已精简为转调 `run_regression()`，自测 3 轮全绿 | ✅ 达标 |
| **4. 交付流水线完整** | regression / run_verify / update_tracking_excel 全畅通 | 隔离模式 (`-I`) 下全部执行通过，最新结果与基线 0 差异 | ✅ 达标 |
| **5. 停步等待** | 不擅自执行第 3 步沙盒 | 完成第 2 步验证后停下报告，等待主力复核 | ✅ 遵守 |

---

## 二、切断旧引擎依赖细节

### 1. `run_verify.py` Line 28 切断（配置与环境）
- **原代码**：
  ```python
  from fs_web_testrunner.config import EMR_API_URL, REPORTS_DIR
  from fs_web_testrunner.core.env_config import env_config
  ```
- **切断并改接为**：
  ```python
  from fs_runner.config import GATEWAY_URL, REPORTS_DIR, env_config
  ```
- **兼容性保障**：
  `fs_runner.config` 提供了 `_EnvConfigCompat` 零副作用轻量单例，支持 `get_frontend_url()`、`get_api_gateway_url()`、`get_config()`，彻底切断对旧引擎 `core/env_config.py` 及其配置解析副作用的依赖；同时纠正了默认 gateway 取值（`GATEWAY_URL: 8081` vs 独立病历后端 `EMR_API_URL: 8021`）。

### 2. `run_verify.py` Line 110 切断（浏览器驱动）
- **原代码**：
  ```python
  from fs_web_testrunner.core.browser_driver import BrowserDriver
  ```
- **切断并改接为**：
  ```python
  from fs_runner.cases.ui_probe import CDPBrowserDriver as BrowserDriver
  ```
- **兼容性保障**：
  在 `fs_runner/cases/ui_probe.py` 中实现了纯 CDP 协议驱动类 `CDPBrowserDriver`，保持了 `start()`, `is_alive()`, `close()`, `navigate()` 接口签名完全兼容，不再依赖旧引擎庞大的 `core/browser_driver.py`。

### 3. `tools/collect.py` 重构为统一转调
- **原代码**：内联 45 行 subprocess 与缺陷判定逻辑；
- **重构为**：
  ```python
  def cmd_regression():
      """执行三轮全量闭环回归（转调 fs_runner regression 统一执行器）。"""
      from fs_runner.cli import run_regression
      return run_regression()
  ```
- 同时在 `tools/collect.py` 顶部添加 `sys.path.insert(0, str(ROOT))`，确保在 `python -I` 隔离模式下也能稳定加载 `fs_runner`。

---

## 三、核心断言与隔离测试实测

### 1. 旧引擎 0 副作用隔离验证
执行命令：
```bash
python -I -c "import sys; sys.path.insert(0, '.'); import fs_runner; assert not [m for m in sys.modules if m.startswith('fs_web_testrunner.core')], '仍 import 了 core！'; print('Core zero-side-effect test PASSED')"
```
**实测输出**：
```text
Core zero-side-effect test PASSED
```
`sys.modules` 中没有任何以 `fs_web_testrunner.core` 开头的模块，证实重构完全切断了依赖链。

### 2. 三轮回归全绿（collect 入口）
执行命令：
```bash
python -I tools/collect.py regression
```
**实测输出**：
```text
  第1轮: 绿（含已知缺陷 1 条：L5-027）
  第2轮: 绿（含已知缺陷 1 条：L5-027）
  第3轮: 绿（含已知缺陷 1 条：L5-027）
[产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261010_095611.log

  ⚠️ 已知缺陷 1 条（绿灯不掩盖，逐条列出）：
     L5-027  病历封存与解封 —— seal 接口不可用（P0，法定流程阻断）
          POST /emr/recordMaster/seal 一律返回 ORA-12899：EMR_RECORD_MASTER.PATIENT_TYPE 是 CHAR(2)（实际存 'I '，带尾空格），EMR_RECORD_MASTER_LOG.PATIENT_TYPE 是 CHAR(1)，后端写日志时未 trim → 长度超限。全院任何病历都无法封存。已复现于 2 张记录，且客户端传什么都一样（4 种调用错误完全相同）→ 非调用方问题。
          （2026-10-09 实测复现并定位根因（zjck-21），Antigravity 独立复核至 DUMP 级（master='I ' Typ=96 Len=2:73,32 vs log 102 条全为 Len=1:73））
  三轮全绿 ✓ —— 直接回报'三轮全绿'即可（另有 1 条已知缺陷，见上）
```
退出码：`0`。

### 3. 三轮回归全绿（fs_runner 新入口）
执行命令：
```bash
python -m fs_runner regression
```
**实测输出**：
```text
  第1轮: 绿（含已知缺陷 1 条：L5-027）
  第2轮: 绿（含已知缺陷 1 条：L5-027）
  第3轮: 绿（含已知缺陷 1 条：L5-027）
[产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261010_100113.log
  三轮全绿 ✓ —— 直接回报'三轮全绿'即可（另有 1 条已知缺陷，见上）
```
退出码：`0`。

---

## 四、全量 66 条用例基线核对

运行比对脚本，对比当前 `reports/verify/closed_loop_latest.json` 与基线 `reports/verify/baseline_66.json`：

```python
Baseline summary: {'通过': 61, '失败': 1, '未执行': 4}
Latest summary:   {'通过': 61, '失败': 1, '未执行': 4}
Status diffs:     0 {}
```

### 1. 状态分布
- **通过**：61 条
- **失败**：1 条（`L5-027`，确诊真缺陷）
- **未执行**：4 条（**`L5-022, L5-037, L9-013, L9-014`**）
  > **注（对齐主力指正）**：闭环套件内的「未执行」4 条确为 `L5-022, L5-037, L9-013, L9-014`；而 `L5-018`（死亡记录文书）与 `L5-033`（处方点评）属于台账跟踪表层面的「阻塞/跳过」，并不在 66 条闭环套件内，两者口径已严格分开，不再混淆。

---

## 五、下游流水线兼容性自测

### 1. 老入口单测与全量调阅
```bash
python -I run_verify.py --closed-loop --cases L6-005
```
- 输出正常，控制台 UTF-8 编码健全，耗时 2 秒，退出码 0。

### 2. 台账写回通道自测
```bash
python -I update_tracking_excel.py --dry-run
```
- 输出正常：
  ```text
  目标用例: 87 条（源表中状态为「未执行」）
  其中已完成真实闭环校验: 65 条
  人工覆盖: 读入 18 条（manual_status.json）
  侦察判定: 读入 13 条（recon_verdicts.json）
  交接表实测: 读入 23 条（handoff_status.json）
  ✅ 判定为通过 65 条
  ⚪ 保持未执行 42 条（已在备注说明未验原因）
  ```
- 退出码 0，台账写回通道完全正常，不会破坏用户出表。

---

## 六、当前分支与状态

- 当前分支：`refactor/fs-runner`
- Git 状态：除本次改动的 `run_verify.py`、`tools/collect.py`、`fs_runner/` 及生成回归日志外，master/main 分支与原有核心业务逻辑无污染。

重构第 2 步已全部完成并自检通过，**已停下等待主力复核，不擅自执行第 3 步**。
