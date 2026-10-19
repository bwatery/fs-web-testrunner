# 【回执 · 重构第 4 步】清理旧物（彻底移除旧引擎、旧用例集与一次性脚本）

> **执行分支**：`refactor/fs-runner`（master/main 分支未受任何触碰，保持可交付状态）  
> **基线对齐**：`reports/verify/baseline_66.json`（66 条 = 通过 61 / 失败 1 [L5-027] / 未执行 4 [L5-022, L5-037, L9-013, L9-014]）  
> **日期**：2026-10-10  

---

## 一、清理前后资产清单对比（完整统计）

| 资产分类 | 路径 / 模式 | 清理前文件数 | 清理前体积 | 版本管理状态 | 清理方式 | 清理后状态 |
|---|---|---|---|---|---|---|
| **旧引擎核心** | `core/` | 24 | 473.5 KB (484,878 B) | Git 跟踪 (12 py) + 字节码 | `git rm -r core` + 目录彻底清除 | 彻底移除 (0 文件) |
| **旧用例集** | `suites/` | 54 | 767.4 KB (785,804 B) | Git 跟踪 (27 py) + 字节码 | `git rm -r suites` + 目录彻底清除 | 彻底移除 (0 文件) |
| **旧 WebRunner 平台** | `web_runner/` | 38 | 562.4 KB (575,869 B) | Git 跟踪 (前端静态 + 后端路由) | `git rm -r web_runner` + 目录彻底清除 | 彻底移除 (0 文件) |
| **旧运行日志** | `logs/` | 3 | 4,525.6 KB (4,634,177 B) | 未跟踪目录 (占用句柄已终止) | 终止旧 `run_runner` 进程后清除 | 彻底移除 (0 文件) |
| **临时脚本与数据** | `scratch/` | 648 | 21,578.1 KB (22,095,956 B) | 85 文件 Git 跟踪 + 563 文件未跟踪 | `git rm -r scratch` + 本地目录清除 | 彻底移除 (0 文件) |
| **顶层一次性脚本与旧入口** | 根目录 67 个脚本 | 67 | 127.3 KB (130,366 B) | 全部 Git 跟踪 (67 py) | `git rm` (67 文件逐项移除) | 彻底移除 (0 文件) |
| **合计拟清理资产** | —— | **834** | **27.38 MB (28,707,050 B)** | —— | **Git 版本控制删除 + 目录清除** | **全部清理完毕** |

---

## 二、清理明细清单

### 1. 顶层 67 个一次性脚本与旧入口（全部走 `git rm`）
- **`inspect_*` (17 个)**: `inspect_app_main.py`, `inspect_calc_main.py`, `inspect_cells.py`, `inspect_current_vue_route.py`, `inspect_dialog_btns.py`, `inspect_dialog_detail.py`, `inspect_doctor_dom.py`, `inspect_form.py`, `inspect_main_container.py`, `inspect_medical_dom.py`, `inspect_ouwei_cells.py`, `inspect_patient_search.py`, `inspect_patient_search_real.py`, `inspect_settlement.py`, `inspect_top_menu.py`, `inspect_vue_router.py`, `inspect_vxe_events.py`
- **`check_*` (11 个)**: `check_console_err.py`, `check_db.py`, `check_html_text.py`, `check_login.py`, `check_nurse_routes.py`, `check_page.py`, `check_patient_context.py`, `check_reg.py`, `check_role_routes.py`, `check_settle.py`, `check_storage.py`
- **`test_*` (12 个)**: `test_all_billing_routes.py`, `test_capture_cases.py`, `test_click_cell.py`, `test_click_sel.py`, `test_dblclick_cell.py`, `test_dual_runner.py`, `test_patient_click.py`, `test_plan_b_ouwei.py`, `test_select_patient.py`, `test_settlement_nav.py`, `test_synthetic_click.py`, `test_synthetic_fees.py`
- **`find_*` (6 个)**: `find_calc_chunk.py`, `find_calc_details.py`, `find_inpatient_views.py`, `find_routes.py`, `find_routes_v2.py`, `find_token.py`
- **`click_*` (3 个)**: `click_ouwei_and_check.py`, `click_patient_select_tab.py`, `click_workstation_menu.py`
- **`get_*` (3 个)**: `get_all_routes.py`, `get_caught_routes.py`, `get_routers.py`
- **其他一次性交互/调试 (4 个)**: `nav_workstation.py`, `capture_shot.py`, `reload_chrome.py`, `interact_settlement.py`
- **已被 CLI 取代的旧 `run_*.py` (8 个)**: `run_cli_tests.py`, `run_outpatient_tests.py`, `run_rules_tests.py`, `run_single_test.py`, `run_invasive_only.py`, `run_non_invasive_only.py`, `run_login_validator.py`, `run_runner.py`
- **旧 WebRunner AI 工具面客户端 (3 个)**: `cli_agent.py`, `his_agent_sdk.py`, `mcp_server.py`

### 2. 严格保留的核心资产
- **根目录保留的 7 个 `.py` 文件**：
  1. `run_verify.py`（体检与闭环统一入口，已解耦 `core`）
  2. `update_tracking_excel.py`（台账写回工具）
  3. `export_insurance_excel.py`（医保交接导出）
  4. `export_print_excel.py`（打印交接导出）
  5. `sync_insurance_status.py`（状态同步）
  6. `config.py`（旧配置兼容层，已将 `env_config` 改接至 `fs_runner.config`，彻底不依赖 `core`）
  7. `cleanup_fake_pass.py`（假通过清理工具）
- **保留的核心目录**：
  - `fs_runner/`（重构后的统一核心包）
  - `verify/`（薄壳兼容层，转发至 `fs_runner.cases.closed_loop`）
  - `tools/`（`collect.py`, `fetch_emr_spec.py`, `mutation_selfcheck.py` 等运维脚本）
  - `data/`（API 规格缓存、Oracle 凭据等）
  - `reports/`（测试报告、证据、基线与协作产出）
  - `docs/` 与 `examples/`

---

## 三、清理后核心验证实测

### 1. 回归全量三轮验证（`tools/collect.py regression`）
执行命令：
```bash
python -I tools/collect.py regression
```
**原始终端输出**：
```text
D:\CSsoft\compiler\python\Python311\Lib\site-packages\requests\__init__.py:109: RequestsDependencyWarning: urllib3 (2.2.3) or chardet (7.4.3)/charset_normalizer (3.4.7) doesn't match a supported version!
  warnings.warn(
  第1轮: 绿（含已知缺陷 1 条：L5-027）
  第2轮: 绿（含已知缺陷 1 条：L5-027）
  第3轮: 绿（含已知缺陷 1 条：L5-027）
[产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261010_103440.log

  ⚠️ 已知缺陷 1 条（绿灯不掩盖，逐条列出）：
     L5-027  病历封存与解封 —— seal 接口不可用（P0，法定流程阻断）
          POST /emr/recordMaster/seal 一律返回 ORA-12899：EMR_RECORD_MASTER.PATIENT_TYPE 是 CHAR(2)（实际存 'I '，带尾空格），EMR_RECORD_MASTER_LOG.PATIENT_TYPE 是 CHAR(1)，后端写日志时未 trim → 长度超限。全院任何病历都无法封存。已复现于 2 张记录，且客户端传什么都一样（4 种调用错误完全相同）→ 非调用方问题。
          （2026-10-09 实测复现并定位根因（zjck-21），Antigravity 独立复核至 DUMP 级（master='I ' Typ=96 Len=2:73,32 vs log 102 条全为 Len=1:73））
  三轮全绿 ✓ —— 直接回报'三轮全绿'即可（另有 1 条已知缺陷，见上）
```
- 退出码：`0`。

### 2. 基线 66 条状态与集合完全一致
比对脚本：
```python
Baseline summary: {'通过': 61, '失败': 1, '未执行': 4}
Latest summary:   {'通过': 61, '失败': 1, '未执行': 4}
Status diffs:     0 {}
Missing env tags: 0
```
- 用例集合差：0；状态差：0。
- 通过：61 条 / 失败：1 条 (`L5-027`) / 未执行：4 条 (`L5-022, L5-037, L9-013, L9-014`)。

### 3. `core/` 清除后各入口畅通性确认
- **`run_verify.py --closed-loop`**：
  ```bash
  python -I run_verify.py --closed-loop --cases L6-005
  ```
  实测输出：✅ 通过，耗时 2s，退出码 0。无任何残留 `core` 报错。
- **`update_tracking_excel.py --dry-run`**：
  ```bash
  python -I update_tracking_excel.py --dry-run
  ```
  实测输出：正常读入最新 65 条结果，出表通道 100% 可用。
- **全局代码扫描**：
  在所有保留的代码目录及文件中扫描 `fs_web_testrunner.core` / `from core`，匹配命中数为 0。

---

第 4 步（清理旧物）已全部完成并通过验证，旧引擎与废弃代码已彻底剔除，**已停下等待主力复核，不擅自启动第 5 步（网页展示）**。
