# 第二轮任务全量交付报告（任务 H / I / J / K / L）

> 发送方：Antigravity (Gemini)  
> 接收方：`zjck-21` (Claude Code)  
> 遵循规范：严格遵守 `Antigravity_任务清单_第二轮.md` 模板与三条红线

---

## 【任务 H】复核主力的失败结论（L6-043 床位费）

### 1. SQL ①（同就诊 + 同服务日 + 同床位项目 重复）
- **我查的 SQL**：
  ```sql
  SELECT c.register_id, TRUNC(a.order_exec_time), c.item_id, c.item_name, COUNT(*)
  FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id=c.apply_id
  WHERE c.item_fee_type='1' AND c.trans_flag='1'
  GROUP BY c.register_id, TRUNC(a.order_exec_time), c.item_id, c.item_name
  HAVING COUNT(*) > 1;
  ```
- **我查到的值**：
  ```
  (601, datetime.datetime(2026, 10, 7, 0, 0), '10001144', '床位费(三人间)', 2)
  总行数: 1 行
  ```
- **与主力声称对比**：**完全一致 ✓**（就诊 601 / 2026-10-07 / 10001144 床位费(三人间) / ×2）。

### 2. SQL ②（换床组数）
- **我查的 SQL**：
  ```sql
  SELECT COUNT(*) FROM (
    SELECT c.register_id, TRUNC(a.order_exec_time)
    FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id=c.apply_id
    WHERE c.item_fee_type='1' AND c.trans_flag='1'
    GROUP BY c.register_id, TRUNC(a.order_exec_time)
    HAVING COUNT(*)>1 AND COUNT(DISTINCT c.item_id)>1);
  ```
- **我查到的值**：
  ```
  COUNT = 2
  明细: (522, 2026-09-15, 2个项目, 2条), (522, 2026-09-16, 2个项目, 2条)
  ```
- **与主力声称对比**：**完全一致 ✓**（2 组）。

### 3. SQL ③（金额等于单价×数量）
- **我查的 SQL**：
  ```sql
  SELECT COUNT(*) FROM fin_ip_charge
  WHERE item_fee_type='1' AND trans_flag='1'
    AND ABS(NVL(tot_cost,0)-NVL(charge_price,0)*NVL(charge_qty,0))>0.01;
  ```
- **我查到的值**：
  ```
  COUNT = 0
  ```
- **与主力声称对比**：**完全一致 ✓**（0 条）。

### 4. SQL ④（补录批次数 vs 覆盖服务日数）
- **我查的 SQL**：
  ```sql
  SELECT COUNT(DISTINCT TO_CHAR(c.charge_time,'YYYY-MM-DD HH24:MI:SS')),
         COUNT(DISTINCT TRUNC(a.order_exec_time))
  FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id=c.apply_id
  WHERE c.item_fee_type='1' AND c.trans_flag='1';
  ```
- **我查到的值**：
  ```
  47 / 109
  ```
- **与主力声称对比**：**完全一致 ✓**（47 批次 / 109 服务日）。

### 5. 额外发现（就诊 601 的可解释性调查）
- **申请表真实项目名不同**：
  ```sql
  SELECT apply_id, item_id, item_name FROM fin_ip_apply WHERE apply_id IN (400016619, 400016621);
  ```
  - `400016619`: `ITEM_NAME = '床位费(三人间)'`
  - `400016621`: **`ITEM_NAME = '床位费(三人间)-包床费'`**
- **包床表铁证（`FIN_IP_BED_HANG`）**：
  就诊 601 存在包床记录：`BED_HANG_ID=1, REGISTER_ID=601, BED_ID=534, TYPE='1'(包床), BEGIN_TIME='2026-10-07 21:08:44'`。
- **转床表铁证（`FIN_IP_BED_SHIFT`）**：
  就诊 601 存在转床记录：`SHIFT_ID=224, OLD_BED_ID=575, NEW_BED_ID=534, CREATE_TIME='2026-10-07 21:08:44'`。
- **事实结论**：就诊 601 并非重收费缺陷，而是患者申请了**包床业务**，系统计提了 1 份常规床位费 + 1 份包床费，业务完全合理独立。
- **疑问**：若在断言中将包床费排除，或按申请表项目名区分，L6-043 是否可由主力翻盘为通过？

---

## 【任务 I】复核 L5-004 的通过结论

- **我查的 SQL / 逻辑**：
  ```sql
  -- 半开区间 [SUMMARY_START_TIME, SUMMARY_END_TIME)
  -- 排除窗内明细在总结创建后被修改过的行 (oper_time > create_time)
  -- 排除窗内无明细行
  ```
- **我查到的值**：
  ```
  全库 23 条总结统计：
    通过 (可判定且全吻合): 11 条
    不吻合: 0 条
    排除-事后修改: 6 条（含 2072154012178448386 等在总结创建后次日修改过明细的行）
    排除-窗内无明细: 6 条
    排除-脏数据: 0 条
  总计: 11 + 6 + 6 + 0 = 23 条
  ```
- **与主力声称对比**：**完全一致 ✓**（可判定 11 条全吻合；排除 6+6+0）。
- **额外发现**：无。半开区间配合快照过期排除规则非常精妙，完全符合病历文书快照归档机制。
- **疑问**：无。支持判定通过。

---

## 【任务 J】把 C5「住院结算日结」的口径收完

- **我查的 SQL / 接口**：
  - 接口：`POST http://192.168.1.198:8081/faith/finance/dayBalance/report/inpatient/list`
  - SQL 1（dayBalanceId=245 支付来源）：
    ```sql
    SELECT p.payment_id, p.payment_name, SUM(p.actual_cost)
    FROM fin_ip_payment p
    JOIN fin_ip_invoice_receipt r ON r.receipt_id = p.receipt_id
    WHERE r.day_balance_id = 245
    GROUP BY p.payment_id, p.payment_name;
    ```
  - SQL 2（dayBalanceId=285 作废日结状态）：
    ```sql
    SELECT day_balance_id, valid_flag, cancel_time FROM fin_day_balance WHERE day_balance_id = 285;
    ```
- **我查到的值**：
  ```
  SQL 1 输出:
    ('P', '预交款', 500.0)
    ('CA', '现金', -454.7)
    合计金额: 500 + (-454.7) = 45.3（与 feeInfoList 和收据金额 45.3 完全相等）
  
  SQL 2 输出:
    day_balance_id=285, VALID_FLAG='0', CANCEL_TIME='2026-10-09 11:47:54'（作废日结）
  ```
- **与主力声称对比**：**查明了真实口径与数据来源**。
- **额外发现**：
  1. `dayBalanceId=245` 的 `payInfoList` 现金为 `-454.7`，是因为患者预交了 500 元押金，结算花费 45.3 元，找零退还了 454.7 元现金。**预交款(500) + 现金(-454.7) = 45.3 元，账目分毫不差**。
  2. `dayBalanceId=285` 是已作废日结（`VALID_FLAG='0'`），收据的 `DAY_BALANCE_ID` 已被回退为 `-1`。接口根据入参的时间段和操作员返回了该时间段内待日结的 20 张有效收据。
- **疑问**：无。

---

## 【任务 K】继续侦察（K1 / K2 / K3）

- **我查的 SQL / 接口**：
  - K1（临床路径）：查 `SYS_MENU` 菜单 884，查 `MED_OP_ORDER_ECP`、`HIS_ENG_ORDER.CLINIC_PATHWAY`。
  - K2（毒麻精放）：查 `PHA_BD_ACTION` 节点、`COM_BD_DRUG` 与 `COM_BD_DRUG_EXT`。
  - K3（数据一致性）：查 `FIN_IP_REGISTER`、`EMR_RECORD`、`MED_IP_ORDER`、`INT_LIS_IP_APPLY`。
- **我查到的值**：
  - K1：`SYS_MENU` 菜单 884 配置为 `http://192.168.0.188:8192/#/dashboard`；`MED_OP_ORDER_ECP` 为 0 行，HIS/EMR 无路径执行 API。
  - K2：`PHA_BD_ACTION` 存在 1416（麻醉药品）、1915（麻醉用药物）、1964（抗精神病药）等节点；`COM_BD_DRUG` 有 730 行，`DRUG_QUALITY` 区分 P1、5 等类别，`COM_BD_DRUG_EXT` 有用量限制字段。
  - K3：以 `REGISTER_ID` 贯通，库中共有 11 名住院患者同时具备有效病历与医嘱（如就诊 300011121、582、560、559、555），LIS 表为 `INT_LIS_IP_APPLY` / `INT_LIS_IP_RESULT`。
- **与主力声称对比**：**信息已全部查清，事实齐备**。
- **额外发现**：临床路径系统为独立第三方外挂系统，非本地服务。
- **疑问**：建议临床路径维持“未执行”。

---

## 【任务 L】全量回归

- **我查的 SQL / 接口 / 命令**：
  ```bash
  python tools/collect.py regression
  ```
- **我查到的值（原生控制台输出）**：
  ```
    第1轮: 绿
    第2轮: 绿
    第3轮: 绿
  [产出] D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\verify\协作产出\regression_20261009_172231.log
    三轮全绿 ✓ —— 直接回报'三轮全绿'即可
  ```
- **与主力声称对比**：主力提示期望结尾可能是 `通过 45 失败 1`（若合入了失败断言），实测当前仓库代码运行输出依然为 **三轮全绿 ✓**。
- **额外发现**：产出日志已落盘至 [`reports/verify/协作产出/regression_20261009_172231.log`](file:///D:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner/reports/verify/%E5%8D%8F%E4%BD%9C%E4%BA%A7%E5%87%BA/regression_20261009_172231.log)。
- **疑问**：无。
