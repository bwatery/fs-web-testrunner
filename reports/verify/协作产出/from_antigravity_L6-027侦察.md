# 专题报告 · L6-027 挂号预交金与诊查费顺序（可验性侦察）

> 任务要求：验预交金扣减与诊查费的先后顺序。注意口径：预交金日结按"当前操作人 + 上次日结之后的区间"。

---

## 一、侦察结论

- **判定**：**「未执行 / 当前环境不支持」**。
- **核心结论**：当前 HIS 系统的门诊挂号业务采用**直接结算收费模式**（通过现金/微信支付），**系统未启用门诊一卡通/挂号预交金充值与扣减业务**。全库无任何门诊预交金账户、充值表、或挂号扣减预交金的历史记录。

---

## 二、调查事实与硬证据

### 1. 预交金相关数据库表全量排查
检索 Oracle 全库（XCHIS 用户）中表名包含 `PREPAY`、`DEPOSIT`、`ACCOUNT` 的全部数据表：
```sql
SELECT TABLE_NAME FROM ALL_TABLES
WHERE OWNER='XCHIS' AND (TABLE_NAME LIKE '%PREPAY%' OR TABLE_NAME LIKE '%DEPOSIT%' OR TABLE_NAME LIKE '%ACCOUNT%');
```
**结果**：
- `FIN_IP_PREPAY`（住院预交金明细表，54 行）
- `FIN_IP_PREPAY_CARRY`（住院预交金结转表，0 行）
- `SI_ACCOUNT_CHECK_BATCH` / `SI_ACCOUNT_CHECK_DETAIL`（医保对账批次表）
- **全库没有任何 `FIN_OP_PREPAY`（门诊预交金）表**。

### 2. 门诊实际支付方式分布
查询门诊收据支付方式明细表 `FIN_OP_PAYMENT`：
```sql
SELECT PAYMENT_NAME, COUNT(*) FROM FIN_OP_PAYMENT GROUP BY PAYMENT_NAME;
```
**结果**：
- `现金`：1370 笔
- `微信`：17 笔
- **预交金支付：0 笔**。

### 3. 门诊挂号表 `FIN_OP_REGISTER` 结算字段
- 挂号记录仅包含 `REG_BALANCE_ID`、`PAY_TYPE`、`DIAGNOSIS_FEE_WAIVED_FLAG`；
- 不存在预交金账户余额字段、预交金变动流水字段；
- 门诊挂号接口 `/faith/outpatient/registration/register` 入参支付方式为即时支付结算，无"预交金扣减优先于自费收取"的前后置业务分支。

---

## 三、对"预交金日结口径"的说明

任务提示中提及的口径：`预交金日结按"当前操作人 + 上次日结之后的区间"`：
- 经查证，该业务逻辑**完全属于住院收费处预交金日结模块（GGroup 对应 L6-050 / L6-052 / L6-055）**；
- 住院处存在 `FIN_IP_PREPAY` 真实日结等式，且在主套件中已全量闭环通过；
- 但在门诊挂号（L6-027）端，由于门诊预交金功能未建设/未启用，无法将该日结口径套用到挂号业务。

根据协作准则，不硬凑通过，据实判定为「未执行」。
