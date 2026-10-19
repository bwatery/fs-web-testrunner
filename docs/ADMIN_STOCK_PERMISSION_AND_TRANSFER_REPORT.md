# 管理员物资仓库与全病区权限配置及库存流转验收报告

## 1. 远程代码合并与推送回执

- **当前分支与合并**：
  - 本地重构与端到端药学自动化套件开发分支 `refactor/fs-runner` 已顺利合并入主分支 `main`（Fast-forward）。
  - 核心新增内容：
    - `tools/generate_ui_clinical_pharmacy_data.py`（纯 UI 临床药学端到端全流程自动造数工具）
    - `docs/UNIVERSAL_PHARMACY_E2E_WORKFLOW.md`（通用规范 SOP 文档）
    - 安全配置护栏（`.gitignore` 强化保护 `data/db_config.json` 绝不外泄）
- **远程推送状态**：
  - 执行 `git push origin main` 成功推送到 GitHub 远程仓库：
  - 远程引用：`05fcbff..565d2e7  main -> main`（35 commits 完整同步）。

---

## 2. 物资仓库与全病区权限配置清单

针对管理员（`admin`, `USER_ID = 1`），完成了**物资仓库（卫材库 910057）**与**全部 6 大病区**的完整库房属性与操作权限赋予：

| 配置维度 | 关联数据表 | 变更明细 | 业务意义 |
| :--- | :--- | :--- | :--- |
| **库房属性定义** | `SYS_DEPT` | 将 6 大病区（`910130..910135`）的 `STOCK_FLAG` 更新为 `'1'` | 使得前端库房选择器能将各病区作为独立二级库/病区库识别 |
| **科室归属赋权** | `SYS_USER_ROLE_DEPT` | 插入 21 条记录（覆盖角色 39 药库管理、角色 37 住院药房、角色 1 系统管理员在 卫材库 及 6 大病区的归属） | 赋予管理员切换到卫材库及任意病区的工作权限 |
| **转入转出权限** | `SYS_USER_ROLE_DEPT_PERMISSION` | 插入 266 条操作权限记录（权限项包含 `101, 10001..10020`） | 赋予调拨入库（`10004`）、调拨出库（`10015`）、领药出库（`10014`）、科室领用（`10017`）、直接出入库等全套动作权限 |
| **耗材类别准入** | `PHA_BD_STOCK_TYPE` | 插入 14 条记录（卫材库 + 6大病区在业务类型 `I` 及 `O` 下开放 `DRUG_TYPE = 'M'` 耗材类目） | 允许各库房管理、调配与核算耗材（M）物资 |
| **调拨供应链路** | `PHA_BD_STOCK_DEPT` | 插入 6 条调拨记录（`STORAGE_DEPT_ID = 910057` 卫材库 $\rightarrow$ `APPLY_DEPT_ID` 6 大病区，`DRUG_TYPE = 'M'`） | 建立卫材库向各病区供应、调拨耗材的合法业务通道 |

---

## 3. 前端 UI 真实交互验证

### 3.1 管理员切换【药库管理】与【卫材库】
登录 `admin` 后点击右上角头像呼出【切换科室】，药库管理角色下已完整展现全部目标科室：
- **可选科室集**：`卫材库`、`中药库`、`西药库`、`骨二科病区`、`内一科病区`、`康复科病区`、`内二科病区`、`骨一科病区`、`骨三科病区`。
![管理员切换至卫材库](file:///d:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/screenshots/admin_switched_to_wz.png)

### 3.2 药品/物资出库工作台（转出）
路由：`#/storage/drugOutStorage`
- **支持的转出模式**：
  - `直接出库`
  - `退库`
  - `领药出库`
  - `调拨出库`（支持从卫材库调拨转出至各病区库）
  - `科室领用出库`（支持病区科室直接申领出库）
  - `盘亏出库 / 报损报废 / 其它出库`
![出库工作台](file:///d:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/screenshots/drug_out_storage_page.png)

### 3.3 药品/物资入库工作台（转入）
路由：`#/storage/drugInStorage`
- **支持的转入模式**：
  - `入库`（外部供应商采购入库）
  - `调拨入库`（接收总库或其他库房调入的物资）
  - `内部退库 / 外部退库`
  - `随入即出`
  - `盘盈入库 / 其它入库`
![入库工作台](file:///d:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/screenshots/drug_in_storage_page.png)

### 3.4 库存管理台（实时库存盘点与台账）
路由：`#/storage/storageInfo`
- 具备实时台账查询、明细下钻、出入库流水核对功能。
![库存总览](file:///d:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/screenshots/storage_info_page.png)
