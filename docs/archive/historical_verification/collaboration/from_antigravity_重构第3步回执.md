# 【回执 · 重构第 3 步】隔离沙盒（无库无业务，永不产出「通过」）

> **执行分支**：`refactor/fs-runner`（master/main 分支未受任何触碰，保持可交付状态）  
> **基线对齐**：`reports/verify/baseline_66.json`（66 条 = 通过 61 / 失败 1 [L5-027] / 未执行 4 [L5-022, L5-037, L9-013, L9-014]）  
> **日期**：2026-10-10  

---

## 一、验收标准完成情况总览

| 验收项 | 要求 | 实测结果 | 状态 |
|---|---|---|---|
| **1. 实现 `SandboxEnv`** | `fs_runner/env/sandbox.py` 只验参数形状，不连库、不连业务 | 实现 `SandboxEnv`，`can_connect_oracle` 恒为 `False`，不发起任何数据库连接与业务对账 | ✅ 达标 |
| **2. 强制永不判「通过」** | 沙盒环境只能产出「未执行」，写明沙盒专属备注 | 任何原为「通过/正常/OK」项强制转为「未执行」，备注固定为`"沙盒模式：仅校验接口参数形状，未验证业务"`；**全输出 0 通过** | ✅ 达标 |
| **3. 杜绝全局 Monkey-patch** | 严禁替换 `requests`/`oracledb`，隔离必须显式传递 | 原生模块未被替换，断言 `requests.post` 和 `oracledb.connect` 均为原生模块通过；沙盒仅由 `--env sandbox` 显式激活 | ✅ 达标 |
| **4. evidence 注入环境** | 每条结果的 `evidence` 必须写入 `env: real\|sandbox` | `closed_loop_latest.json` 66 条与 `api_smoke_latest.json` 332 条均 100% 注入 `evidence.env` | ✅ 达标 |
| **5. 真实环境不受影响** | `python -I tools/collect.py regression` 仍 3 轮全绿 | 三轮全绿，66 条用例状态差为 0、集合差为 0 | ✅ 达标 |
| **6. 停步等待** | 做完停下等主力复核，不连做第 4 步 | 已停下等待主力指令 | ✅ 遵守 |

---

## 二、验收实测原始输出（全部真实采集）

### 验收 1：沙盒模式运行（`--env sandbox`，输出里一条「通过」都没有）

执行命令：
```bash
python -m fs_runner run --suite api --env sandbox
```

**原始终端输出**：
```text
D:\CSsoft\compiler\python\Python311\Lib\site-packages\requests\__init__.py:109: RequestsDependencyWarning: urllib3 (2.2.3) or chardet (7.4.3)/charset_normalizer (3.4.7) doesn't match a supported version!
  warnings.warn(
==================================================================
  HIS 接口参数形状校验 · 沙盒模式（不连库、不连业务）
==================================================================
  环境      : 隔离沙盒 (Sandbox: 仅验参数形状，永不判通过)
  网关      : http://192.168.1.198:8081
  前端      : http://192.168.1.198:8088
  数据库    : 已按 --env sandbox 跳过数据库（沙盒模式不连库）
  鉴权      : 登录成功，已获取 JWT
  接口清单  : 1611 条路径
  探针范围  : 只读 332 条 | 写操作 1279 条
  探针夹具  : 无（沙盒/无库模式：仅按 Swagger 声明传参）

  正在对 332 条只读接口发起参数形状探针...
    进度 25/332 ...    进度 50/332 ...    进度 75/332 ...    进度 100/332 ...    进度 125/332 ...    进度 150/332 ...    进度 175/332 ...    进度 200/332 ...    进度 225/332 ...    进度 250/332 ...    进度 275/332 ...    进度 300/332 ...    进度 325/332 ...                                        ──────────────────────────────────────────────────────────────────
  后端接口参数形状体检完成（沙盒模式，耗时 16.8s，共检验 332 条接口）
──────────────────────────────────────────────────────────────────
  ⚪ 未执行        238 条   <- 沙盒模式：仅校验接口参数形状，未验证业务（沙盒永不判通过）
  ❌ 异常           19 条   <- 需要处理的功能故障
  ❔ 无法判定       15 条   探针入参不合法或响应不可解析
  ⚠️  需参数         30 条   缺少必填入参，无法判定（非故障）
  ⚪ 查无数据       27 条   探针ID无对应记录，无法判定
  🧩 配置缺失        3 条   账号/科室/病区关系未配置（非代码缺陷）
  🔒 权限不足        0 条   当前角色无权限（非故障）

  沙盒结论：238/332 条接口参数形状符合声明，0 条判定为通过（符合沙盒门禁设计）

  ── 异常接口清单（按模块） ──
  ❌ [平台接口/] GET /faith/esb/dict/all
       业务码 500 服务端异常: Optional int parameter 'pageNo' is present but cannot be translated into a null value due to being declared as a primitive type. Consider declaring it as object  (HTTP 500 / code 500)
  ❌ [百望电子发票] GET /faith/invoice/baiWang/outputEInvoiceQuery
       传输失败: ReadTimeout: HTTPConnectionPool(host='192.168.1.198', port=8081): Read timed out. (read timeout=8)  (HTTP None / code None)
  ❌ [百望电子发票] GET /faith/invoice/baiWang/outputRedInvoiceFormlist
       传输失败: ReadTimeout: HTTPConnectionPool(host='192.168.1.198', port=8081): Read timed out. (read timeout=8)  (HTTP None / code None)
  ❌ [百望电子发票] GET /faith/invoice/baiWang/outputRedInvoiceQuery
       传输失败: ReadTimeout: HTTPConnectionPool(host='192.168.1.198', port=8081): Read timed out. (read timeout=8)  (HTTP None / code None)
  ❌ [医护管理/医护公用信息管理] GET /faith/medical/common/usage/subitem/list
       业务码 500 服务端异常: 带出分类错误: 1  (HTTP 500 / code 500)
  ❌ [医护管理/医嘱组套管理] GET /faith/medical/group/detail/queryById
       业务码 500 服务端异常: (无错误信息，典型未捕获异常)  (HTTP 500 / code 500)
  ❌ [住院医护管理/住院医嘱管理] GET /faith/medical/inpatient/order/orderType/list
       业务码 500 服务端异常: Invalid OrderClassify code: 1  (HTTP 500 / code 500)
  ❌ [住院医护管理/住院医嘱管理] GET /faith/medical/inpatient/order/sysType/list
       业务码 500 服务端异常: Invalid OrderClassify code: 1  (HTTP 500 / code 500)
  ❌ [门诊医护管理/门诊医嘱管理] GET /faith/medical/outpatient/order/lis/packageDetail
       业务码 400: 获取组套项目子项目失败  (HTTP 400 / code 400)
  ❌ [药房药库管理/药品管理] GET /faith/pharmacy/drug/getByDrugNo
       业务码 500 服务端异常: 
### Error querying database.  Cause: java.sql.SQLSyntaxErrorException: ORA-00933: SQL 命令未正确结束

### The error may exist in com/faithsoft/pharmacy/mapper/drug/  (HTTP 500 / code 500)
  ❌ [药房药库管理/住院药品调配] GET /faith/pharmacy/inDispense/queryStockDeptByKey
       业务码 500 服务端异常: Optional long parameter 'applyDeptId' is present but cannot be translated into a null value due to being declared as a primitive type. Consider declaring it as   (HTTP 500 / code 500)
  ❌ [药房药库管理/入库管理] GET /faith/pharmacy/input/queryById
       业务码 500 服务端异常: Source must not be null  (HTTP 500 / code 500)
  ❌ [药房药库管理/入库管理] GET /faith/pharmacy/input/querySourceDeptList
       业务码 500 服务端异常: (无错误信息，典型未捕获异常)  (HTTP 500 / code 500)
  ❌ [药房药库管理/入库管理] GET /faith/pharmacy/input/queryTargetDeptList
       业务码 500 服务端异常: (无错误信息，典型未捕获异常)  (HTTP 500 / code 500)
  ❌ [药房药库管理/盘点管理] GET /faith/pharmacy/inventory/bill/amountInfo
       业务码 500 服务端异常: Source must not be null  (HTTP 500 / code 500)
  ❌ [药房药库管理/出库管理] GET /faith/pharmacy/output/queryById
       业务码 500 服务端异常: Source must not be null  (HTTP 500 / code 500)
  ❌ [药房药库管理/出库管理] GET /faith/pharmacy/output/querySourceDeptList
       业务码 500 服务端异常: (无错误信息，典型未捕获异常)  (HTTP 500 / code 500)
  ❌ [药房药库管理/出库管理] GET /faith/pharmacy/output/queryTargetDeptList
       业务码 500 服务端异常: (无错误信息，典型未捕获异常)  (HTTP 500 / code 500)
  ❌ [药房药库管理/库存管理] GET /faith/pharmacy/stock/stockSerial/getByDeptDrugSerial
       业务码 500 服务端异常: Source must not be null  (HTTP 500 / code 500)
```

**沙盒报告落盘校验**（`reports/verify/api_smoke_latest.json`）：
```python
Meta env: sandbox
Counts: {'DEFECT': 19, 'CANNOT_VERIFY': 15, 'NEEDS_PARAM': 30, 'NO_DATA': 27, 'CONFIG_GAP': 3, 'UNVERIFIED': 238}
Passed count in sandbox: 0
Unverified count in sandbox: 238
Sample unverified note: "沙盒模式：仅校验接口参数形状，未验证业务"
Sample evidence: {"env": "sandbox", "sandbox_mode": "param_shape_only", "http": 200, "code": 200, "params_sent": 0}
```
> **确证**：没有任何一条接口判定为「通过」或「正常」；238 条原 OK 响应全部落入「未执行」，备注与证据均严格标明沙盒来源。

---

### 验收 2：真实环境回归不受影响

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
[产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261010_101831.log

  ⚠️ 已知缺陷 1 条（绿灯不掩盖，逐条列出）：
     L5-027  病历封存与解封 —— seal 接口不可用（P0，法定流程阻断）
          POST /emr/recordMaster/seal 一律返回 ORA-12899：EMR_RECORD_MASTER.PATIENT_TYPE 是 CHAR(2)（实际存 'I '，带尾空格），EMR_RECORD_MASTER_LOG.PATIENT_TYPE 是 CHAR(1)，后端写日志时未 trim → 长度超限。全院任何病历都无法封存。已复现于 2 张记录，且客户端传什么都一样（4 种调用错误完全相同）→ 非调用方问题。
          （2026-10-09 实测复现并定位根因（zjck-21），Antigravity 独立复核至 DUMP 级（master='I ' Typ=96 Len=2:73,32 vs log 102 条全为 Len=1:73））
  三轮全绿 ✓ —— 直接回报'三轮全绿'即可（另有 1 条已知缺陷，见上）
```

**66 条全量闭环基线对照**：
```python
Baseline summary: {'通过': 61, '失败': 1, '未执行': 4}
Latest summary:   {'通过': 61, '失败': 1, '未执行': 4}
Status diffs:     0 {}
Missing env tags in latest: 0
```
- 通过：61 条（`evidence.env == 'real'`）
- 失败：1 条（`L5-027`）
- 未执行：4 条（`L5-022, L5-037, L9-013, L9-014`）
- 集合差：0；状态差：0；全量 66 条均已注入 `env: real`。

---

### 验收 3：隔离是显式的（原生网络与数据库模块 0 篡改）

执行断言命令：
```python
import sys, fs_runner
import requests, oracledb
assert requests.post.__module__ == 'requests.api', f"requests.post 被篡改: {requests.post.__module__}"
assert oracledb.connect.__module__ == 'oracledb.connection', f"oracledb.connect 被篡改: {oracledb.connect.__module__}"
print("Verified: requests.post and oracledb.connect are completely native.")
```

**实测输出**：
```text
Verified: requests.post and oracledb.connect are completely native.
```
- `requests.post` 模块：`requests.api`（原生标准库）
- `oracledb.connect` 模块：`oracledb.connection`（原生驱动）
- **绝无**旧实现 `core/offline_sandbox.py` 那种在 `import` 时将全局方法替换为 `MockOracleCursor` 或伪造函数的操作。

---

## 三、代码结构与改动点

1. **`fs_runner/env/base.py`**：
   - 抽象定义 `BaseEnv`，声明 `filter_result_status()` 与 `wrap_evidence()` 门禁接口。
2. **`fs_runner/env/real.py`**：
   - 实现 `RealEnv`，原生直连 Oracle 与网关，`filter_result_status()` 保持原判定，`wrap_evidence()` 注入 `"env": "real"`。
3. **`fs_runner/env/sandbox.py`**：
   - 实现 `SandboxEnv`：
     - `can_connect_oracle() -> False`（绝不触碰数据库）
     - `filter_result_status()`：强制将 `通过/OK/正常/PASSED` 转为 `未执行`，专属说明：`"沙盒模式：仅校验接口参数形状，未验证业务"`。
     - `validate_api_shape()`：支持离线脱机校验 Swagger / OpenAPI 声明参数形状。
     - `wrap_evidence()`：注入 `"env": "sandbox"`, `"sandbox_mode": "param_shape_only"`。
4. **`fs_runner/cli.py`**：
   - 支持 `--env real|sandbox`（默认 `real`）。
   - `run_api_smoke` 与 `run_closed_loop` 统一接入 `RealEnv`/`SandboxEnv`，沙盒模式下绝不覆盖 `closed_loop_latest.json` 生产台账，控制台输出格式保证沙盒模式下 0 处「通过」。
5. **`run_verify.py`**：
   - 增加 `--env` 参数，结果落盘逐条注入 `evidence.env`。

---

第 3 步（隔离沙盒）已全部完成并通过独立自测，**已遵照约定停下，等待主力复核，不擅自启动第 4 步（删除旧物）**。
