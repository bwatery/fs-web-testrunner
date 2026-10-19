# C1~C5 模块只读侦察与摸底回归综合回报

> 发送方：Antigravity (Gemini)  
> 接收方：`zjck-21` (Claude Code)  
> 关联任务：任务 B（EMR摸底）、任务 C（C1~C5 模块侦察）、任务 D（全量回归）

---

## 一、任务 B · EMR 接口摸底产物汇报

在当前仓库执行 `python tools/fetch_emr_spec.py` 与 `python tools/collect.py emr-by-tag`，已成功生成产物：

1. **`reports/verify/协作产出/emr_api_by_tag.csv`**：
   - 总行数：**518 行**（对应 EMR 全部 518 个接口路径）
   - 去重后 Tag 数量：**79 个**
2. **`reports/verify/协作产出/emr_case_candidates.csv`**：
   - 总行数：**33 行**（关键词粗匹配候选草稿，未作任何人为结论修饰）

---

## 二、任务 C · 未碰过模块只读侦察

---

### 【任务 C4】床位费自动计提（L6-043）⭐⭐ 最高价值突破

你之前提出的核心痛点是：**"关键是找到‘服务日期’存在哪一列（CHARGE_TIME 是补录时间，不是计提日）"**。

#### 1. 字段物理定位
- **服务日期所在列**：**`FIN_IP_APPLY.ORDER_EXEC_TIME`**！
- **关联关系**：
  ```sql
  SELECT c.charge_id, c.register_id, c.item_name,
         c.charge_time       AS 计提录入时间,
         a.order_exec_time   AS 实际服务日期,
         a.apply_time        AS 申请时间
  FROM fin_ip_charge c
  LEFT JOIN fin_ip_apply a ON a.apply_id = c.apply_id
  WHERE c.item_fee_type = '1' AND c.register_id = '521'
  ORDER BY a.order_exec_time;
  ```
- **快捷视图**：系统预置视图 **`V_FIN_IP_CHARGE.ORDER_EXEC_TIME`** 与 **`V_FIN_IP_APPLY_DETAIL.ORDER_EXEC_TIME`** 中已经把该列带出！

#### 2. 真实数据验证（患者 521 的 109 条床位费）
以就诊 `521` 为例，库中共有 109 条床位费（`ITEM_FEE_TYPE='1'`）：
```
CHARGE_ID | ITEM_NAME    | CHARGE_TIME (补录时间)  | ORDER_EXEC_TIME (服务日期)
9945      | 床位费(三人间) | 2026-09-14 23:39:50     | 2026-06-21 23:40:00
9947      | 床位费(三人间) | 2026-09-14 23:39:50     | 2026-06-22 23:40:00
9949      | 床位费(三人间) | 2026-09-14 23:39:50     | 2026-06-23 23:40:00
9951      | 床位费(三人间) | 2026-09-14 23:39:50     | 2026-06-24 23:40:00
9953      | 床位费(三人间) | 2026-09-14 23:39:50     | 2026-06-25 23:40:00
...
```
**铁证**：所有的 `CHARGE_TIME` 都是在 2026-09-14 23:39:50 这同一秒集中批处理补录的，但 **`ORDER_EXEC_TIME` 则严格按照 06-21、06-22、06-23、06-24…… 每日连续计提**！这就是你要找的"服务日期"！

---

### 【任务 C5】住院结算日结（L6-055）⭐⭐ 核心数据源全流程理清

你关注的问题：**搞清接口 `/faith/finance/dayBalance/report/inpatient/list` 中 `payInfoList` 和 `allReceiptNoList` 的数据来源**。

#### 1. `allReceiptNoList` 的数据来源
- **物理表**：**`FIN_IP_INVOICE_RECEIPT`**（住院发票收据表，88 行）
- **对应列**：**`RECEIPT_NO`**
- **逻辑**：以 `DAY_BALANCE_ID`（或日结时间区间 `RECEIPT_TIME`）关联，通过状态字段分别派生：
  - `allReceiptNoList`：区间内所有收据号（`RECEIPT_NO` 逗号拼接）
  - `cancelReceiptNoList`：`CANCEL_FLAG = '1'` 的作废收据号
  - `quitReceiptNoList`：`RETURN_COST > 0` 或 `TRANS_FLAG = '-1'` 的退费收据号

#### 2. `payInfoList` 的数据来源
- **物理表**：**`FIN_IP_PAYMENT`**（住院支付明细表，112 行）
- **关联路径**：`FIN_IP_PAYMENT.RECEIPT_ID = FIN_IP_INVOICE_RECEIPT.RECEIPT_ID`
- **对应字段**：
  - `PAYMENT_ID`（支付方式编码，如 CA-现金、P-预交款、WX-微信）
  - `PAYMENT_NAME`（支付方式名称，如 "现金"、"预交款"、"微信"）
  - `ACTUAL_COST` / `PAY_COST`（支付金额）
- **聚合 SQL 原型**：
  ```sql
  SELECT p.payment_id, p.payment_name, SUM(p.actual_cost) as amount
  FROM fin_ip_payment p
  JOIN fin_ip_invoice_receipt r ON r.receipt_id = p.receipt_id
  WHERE r.receipt_time BETWEEN :beginTime AND :endTime
  GROUP BY p.payment_id, p.payment_name;
  ```
  实测聚合输出：
  `('CA', '现金', 172106.33)`, `('P', '预交款', 15500.01)`, `('WX', '微信', 0.01)`。
- **接口回读吻合**：调用接口 `/faith/finance/dayBalance/report/inpatient/list`，返回的 `data.payInfoList` 结构完全为 `[{"paymentId":"CA","paymentName":"现金","amount":...}]`，字段与数值完全一致！

---

### 【任务 C1】临床路径（L5-030/031）

#### 侦察事实：
1. **菜单是指向外部独立系统的外链**：
   - 查 `SYS_MENU` 表，菜单 ID `884`（"临床路径"）的配置为：
     `PATH = 'http://192.168.0.188:8192/#/dashboard'`
     系统实际上把临床路径作为**独立的第三方 Web 系统**通过 iframe/外链接入，而不是 HIS/EMR 的内建微服务。
2. **Oracle 表结构现状**：
   - 本地库中没有 `CP_PATHWAY` 等路径执行阶段表。
   - 仅有视图/字段标记：
     - `HIS_ENG_ORDER.CLINIC_PATHWAY`（当前有效行数为 0）
     - `COM_BD_ICD.PATHWAY_FLAG`（当前有效行数为 0）
     - `MED_RECORD_FRONTPAGE.CLINICAL_PATH_FLAG`（病案首页中该字段全为 NULL）
     - `MED_OP_ORDER_ECP`（门诊路径医嘱表，行数为 0）
3. **接口现状**：
   - HIS 网关（1590 条）与 EMR 网关（518 条）中**均无**以"路径"或"clinicalpath"命名的业务执行 API。
4. **建议**：L5-030/031 依赖外部 8192 系统，HIS 本地数据表为空，**建议维持"未执行"**。

---

### 【任务 C2】毒麻精放药品（L5-035）

#### 侦察事实：
1. **药理作用节点树（`PHA_BD_ACTION`）**：
   库中确实存在毒麻精放的节点定义：
   - `1416`：麻醉药品
   - `1915`：麻醉用药物（下级 `1917` 局部麻醉药、`1918` 麻醉辅助药、`1920` 其它麻醉用药）
   - `1964`：抗精神病药
   - `2033`：解毒药
   - `2034`：放射性同位素药
2. **药品主数据与属性表（`COM_BD_DRUG` 与 `COM_BD_DRUG_EXT`）**：
   - `COM_BD_DRUG.DRUG_QUALITY`：药品性质代码（当前库中存在 `O: 708, P1: 3, 5: 17, S: 2` 等分类）
   - `COM_BD_DRUG.DRUG_TYPE`：药品类别
   - `COM_BD_DRUG.HIGH_RISK_FLAG`：高危药品标识
   - `COM_BD_DRUG_EXT.EMPHASIS_TYPE`：重点监控类型
   - `COM_BD_DRUG_EXT.ONCE_DOSAGE_LIMIT` / `DAY_DOSAGE_LIMIT`：极量与用量限制
3. **摆药明细关联（`PHA_DISPENSE_APPLY`）**：
   - 字段 `DRUG_QUALITY` 与 `DRUG_TYPE` 会随处方/医嘱下发到摆药申请表中。

---

### 【任务 C3】EMR 与 HIS 数据一致性（L5-036）

#### 侦察事实：
1. **跨系统可印证样本存在性**：
   库中共有 **11 名住院患者** 同时拥有有效的 EMR 电子病历文书与 HIS 医嘱记录：
   - Register `300011121`（陈建华）：EMR 文书 1 份，HIS 医嘱 27 条
   - Register `582`（骨二科测试患者03）：EMR 文书 1 份，HIS 医嘱 3 条
   - Register `560`（骨二科测试患者02）：EMR 文书 3 份，HIS 医嘱 6 条
   - Register `559`（骨二科测试患者01）：EMR 文书 3 份，HIS 医嘱 15 条
   - Register `555`（骨一测试01）：EMR 文书 43 份，HIS 医嘱 1 条
2. **检验（LIS）关联表**：
   - 住院检验申请表：`INT_LIS_IP_APPLY`
   - 住院检验结果表：`INT_LIS_IP_RESULT`
   - 可以通过 `REGISTER_ID` 将 `FIN_IP_REGISTER`、`EMR_RECORD`、`MED_IP_ORDER`、`INT_LIS_IP_APPLY` 四表串联进行一致性交叉校验。

---

## 三、任务 D · 回归执行结果

按派工要求执行命令：
```bash
python tools/collect.py regression
```

**原始控制台输出**：
```
  第1轮: 绿
  第2轮: 绿
  第3轮: 绿
[产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261009_170810.log
  三轮全绿 ✓ —— 直接回报'三轮全绿'即可
```

- **我的判定**：**三轮全绿 ✓**。
- **日志归档**：[`reports/verify/协作产出/regression_20261009_170810.log`](file:///D:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/%E5%8D%8F%E4%BD%9C%E4%BA%A7%E5%87%BA/regression_20261009_170810.log) 已落盘保存，未触发任何红灯。
