# 专题报告 · L2-122 第三方回传与整单取消（可验性侦察）

> 任务要求：LIS/PACS 回传后整单取消。线索：`INT_LIS_IP_APPLY` / `INT_LIS_IP_RESULT`。

---

## 一、侦察结论

- **判定**：**「未执行（回传数据存在，但无整单取消历史样本）」**。
- **核心结论**：
  1. 系统中**第三方 LIS 检验结果回传数据是真实存在的**：`INT_LIS_IP_RESULT` 存量 169 条检验明细，对应 17 个申请单；通过接口 `POST /faith/medical/inpatient/medicalApply/lis/result/list` 可完整拉取到检验回传结果并与库表逐项核对；
  2. 但在全库 149 个申请单中，`CANCEL_OPER_ID` 为空、`CANCEL_TIME` 为空占 **100%（整单取消记录为 0）**；
  3. 库中未曾发生过"回传后整单取消"的业务流程。根据协作纪律，不能把"无取消数据"硬写成"通过"，判定为「未执行」。

---

## 二、调查事实与硬证据

### 1. 检验申请表与结果回传表概况
- `INT_LIS_IP_APPLY`（住院检验申请单表）：共 149 行
  - 申请状态分布（`APPLY_STATE`）：
    - `'0'`（已申请/未回传）：134 条
    - `'2'`（部分报告/已出报告）：14 条
    - `'3'`（已报告）：1 条
- `INT_LIS_IP_RESULT`（住院检验结果表）：共 169 行
  - 涵盖 17 个不同的 `APPLY_ID`（如 13、116、118、120 等）；
  - 项目包括 `肝功6项`、`单核细胞比率`、`平均血红蛋白量`、`尿液分析` 等；
  - 记录了具体测定值、单位（% / pg / U/L）及异常高低标志（`H` / `L` / `N`）。

### 2. 接口拉取回传结果验证
- **接口**：`POST /faith/medical/inpatient/medicalApply/lis/result/list`
- **入参测试**：
  - 传入 `{"registerId": 315, "applyId": 13}`：
  - 接口返回 `200`，成功拉取到 3 条检验项目结果：
    - `单核细胞比率`: 11.4 %, flag: H
    - `平均血红蛋白量`: 22.5 pg, flag: L
    - `肝功6项`: 28 U/L, flag: N
  - 接口返回值与 Oracle 数据库 `INT_LIS_IP_RESULT` 逐字完全一致。

### 3. 整单取消情况排查
排查全部 149 个申请单的取消操作人及取消时间：
```sql
SELECT COUNT(*) FROM INT_LIS_IP_APPLY WHERE CANCEL_OPER_ID IS NOT NULL OR CANCEL_TIME IS NOT NULL;
```
- **结果**：**0 条**。
- 进一步检查 `INT_LIS_IP_APPLY_LIST`（明细表）：`CANCEL_OPER_ID IS NOT NULL` 同样为 **0 条**。

---

## 三、处理建议

接口与库表完全支持检验回传结果的查询与核对，但因历史运行数据中从未执行过"整单取消"，缺乏取消后申请单状态回退、医嘱作废或退费对冲的真实数据。为保证断言的真实性，如实判定为「未执行」。
