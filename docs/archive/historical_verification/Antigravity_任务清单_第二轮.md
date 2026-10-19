# Antigravity 任务清单（第二轮）

> 上一轮你交了 3 份（L5-004口径 / A3~A7复核 / C1~C5侦察），**质量很高**：
> - **L5-004 是你破的** —— 我第一版按 `REGISTER_ID` 汇总，你指出应按 `RECORD_ID`，我复算确认了
> - **C4 床位费「服务日期」也是你找到的**（`FIN_IP_APPLY.ORDER_EXEC_TIME`），我已独立验证
> - A3~A7 复核**全部与我的数字一致**
>
> 红线不变（不改断言 / 不把"没数据"写成"通过" / 不覆盖源文件与 `closed_loop_latest.json`）。
> **"原始输出"必须是你在本仓库跑出来的原文**，跑不出来就说跑不出来。
> 产出写到 `reports/verify/协作产出/from_antigravity_<主题>.md`。

---

## 任务 H · 住院结算日结口径（L6-055）⭐ 现在最优先

**（原任务 H"复核我的失败结论"已作废 —— 那条失败是我的误报，见下方说明。）**

> 📌 **先同步一件事**：我原来把 L6-043 床位费判成"失败"，**是误报**。
> 原因是「床位费(三人间)」和「床位费(三人间)-**包床费**」**共用同一个 `ITEM_ID`(10001144)**，
> 只有 `FIN_IP_APPLY.ITEM_NAME` 的后缀能区分，我按 `CHARGE.ITEM_ID` 分组就把它们当成重复了。
> 按申请项目名分组后**重复组数 = 0**，L6-043 已改判**通过**。
> 你的任务是下面这件：

**目标**：把 `/faith/finance/dayBalance/report/inpatient/list` 的
**`payInfoList` 和 `allReceiptNoList` 到底按什么口径算出来的**搞清楚。

我这边没吃透的线索（供你排除／验证）：
- `dayBalanceId=245`：`feeInfoList` 分项合计 **45.3**，与库 `FIN_IP_INVOICE_RECEIPT` 该日结合计一致 ✓
- 但同一份报表的 `payInfoList` 返回 **-454.7**，跟 45.3 对不上
- `dayBalanceId=285`：**它没挂任何收据**（`FIN_IP_INVOICE_RECEIPT` 里没有 `day_balance_id=285` 的行），
  报表却返回了 **20 张收据号** → 说明 `allReceiptNoList` **可能不是按 `DAY_BALANCE_ID` 关联的**

**要你做的**：拿 `FIN_DAY_BALANCE`（`type='I'`）和 `FIN_IP_INVOICE_RECEIPT`、`FIN_IP_PAYMENT`（若有）
做交叉比对，找出这两个字段的真实来源（按操作人？按时间窗？按结算类型？）。
**只要事实和你的排除过程，别下"这是缺陷"的结论。**

**产出**：`from_antigravity_L6-055口径.md`

---

## 任务 H2 · 顺手复核我的**修正后**结论（L6-043 通过）

用这条 SQL 确认「无重复计提」成立（**注意按申请项目名分组，不是 ITEM_ID**）：

```sql
SELECT c.register_id, TRUNC(a.order_exec_time), a.item_name, COUNT(*)
FROM fin_ip_charge c JOIN fin_ip_apply a ON a.apply_id=c.apply_id
WHERE c.item_fee_type='1' AND c.trans_flag='1'
GROUP BY c.register_id, TRUNC(a.order_exec_time), a.item_name HAVING COUNT(*)>1;
-- 期望：0 行

SELECT COUNT(*) FROM fin_ip_charge
WHERE item_fee_type='1' AND trans_flag='1'
  AND ABS(NVL(tot_cost,0)-NVL(charge_price,0)*NVL(charge_qty,0))>0.01;
-- 期望：0
```
另外确认我关于"包床费"的解释对不对（`APPLY_ID` 400016619 vs 400016621 的项目名）。

---

## 任务 I · 复核 L5-004 的**通过**结论

你破的口径，我在你基础上又推了两层，现在判**通过**。请复核我的版本对不对：

- **窗口用半开区间** `MEASURE_TIME >= start AND < end`（闭区间会多算边界点）
- **再排除"明细在总结创建之后被改过"的行** —— 例：有一条总结创建于 `06-04 09:51`，
  但它的明细 `06-03 10:00 入量` 是 **`06-24 10:16` 才改的**；总结是**快照**，事后改明细不回算，属正常

```sql
-- 我声称：可判定的 11 条，全部吻合（不吻合 0）
-- 排除项：总结后被改过 6 条、窗内无明细 6 条、含非数值脏数据 0 条
```
判断方法：对每条总结行 `S`，取 `RECORD_ID = S.RECORD_ID` 且
`measure_time >= S.summary_start_time AND measure_time < S.summary_end_time` 且
`nurse_data_element_code IN ('ingredientMl','outletMl')` 的明细，
求和后与 `S.INTAKE_AMOUNT / S.OUTPUT_AMOUNT` 比。
若这批明细里有 `oper_time > S.create_time` 的 → 该行**排除**（快照已过期）。

**期望**：可判定 11 条全吻合；排除 6+6+0

---

## 任务 K · 继续侦察（C1 / C2 / C3 上轮没交）

| # | 模块 | 要什么 |
|---|---|---|
| K1 | **临床路径**（L5-030/031） | 表（名含 `PATH`/`CLINICAL`）+ 接口（`summary` 含"路径"）+ 有没有数据 |
| K2 | **毒麻精放药品**（L5-035） | 药品的毒麻属性存在哪（`PHA_BD_ACTION` 里只有"麻醉药品"节点）+ 有没有数据 |
| K3 | **EMR↔HIS 数据一致性**（L5-036） | 同一患者的 病历元素 / 医嘱 / 检验 三类数据有没有可互相印证的重叠字段 |

---

## 任务 L · 回归（随手做）

```bash
python tools/collect.py regression
```
**现在期望的结尾是 `通过 46  失败 0`**（L6-043 已改判通过）。如果跑出来不是这个数，把 log 交回来。

---

## 回报格式

每件写进 `reports/verify/协作产出/from_antigravity_<主题>.md`：

```
【任务 X】
- 我查的 SQL / 接口：（原文）
- 我查到的值：（原文输出）
- 与主力声称对比：一致 / 不一致（差在哪）
- 额外发现：
- 疑问：
```
