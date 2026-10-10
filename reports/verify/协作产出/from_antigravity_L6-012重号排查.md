# L6-012 偶发红灯深度排查与根因分析

> **排查结论前置**：
> 这**不是**系统的"真重号缺陷"，而是**断言 SQL 遗漏了「午别（`SEE_NOON_ID`）」维度导致的假警报**。
> 系统门诊排班的业务规则是：**每个午别（上午/下午/晚上）号源独立从 1 开始编号**。
> 第 1 轮回归报出的 1 组重复，是「**下午 3 号**（有效）」与用例连挂产生的「**晚上 3 号**（连挂时有效）」在全天跨午别碰撞；而第 2/3 轮连挂分配到 7 号以上，避开了下午的有效号，因此偶发变绿。

---

## 1. 定位 SQL 与碰撞组提取

在执行第 1 轮回归（`2026-10-09 17:38:11`）时，用例 `flow_L6_012` 在连挂 5 个号后执行了以下断言 SQL：

```sql
-- flow_L6_012 既有断言 SQL
SELECT COUNT(*) FROM (
  SELECT see_serial_id FROM fin_op_register
  WHERE register_doct_id = :1 AND valid_flag = '1'
    AND see_serial_id IS NOT NULL
    AND TRUNC(see_begin_time) = (
        SELECT TRUNC(see_begin_time) FROM fin_op_register
        WHERE register_id = :2)
  GROUP BY see_serial_id HAVING COUNT(*) > 1)
```

通过回溯数据库当天（2026-10-09）`REGISTER_DOCT_ID = 1` 的挂号流水，精准定位到撞车的那一组记录为 **`SEE_SERIAL_ID = '3'`**：

```sql
-- 提取碰撞组完整原始记录
SELECT register_id, patient_id, register_dept_id, register_doct_id,
       see_noon_id, see_serial_id, daily_serial_id, valid_flag,
       TO_CHAR(register_time, 'YYYY-MM-DD HH24:MI:SS') AS reg_time,
       TO_CHAR(see_begin_time, 'YYYY-MM-DD HH24:MI:SS') AS see_time,
       TO_CHAR(update_time, 'YYYY-MM-DD HH24:MI:SS') AS update_time
FROM fin_op_register
WHERE register_id IN (300011139, 300011880)
ORDER BY register_id;
```

---

## 2. 碰撞组全部原始字段

| 字段 | 记录 A（既有有效挂号） | 记录 B（第 1 轮回归用例连挂） |
| :--- | :--- | :--- |
| **REGISTER_ID** | `300011139` | `300011880` |
| **PATIENT_ID** | `1581113`（患者：9.28测试） | `1581330`（测试患者） |
| **REGISTER_DOCT_ID** | `1`（系统管理员） | `1`（系统管理员） |
| **SEE_NOON_ID** | **`2`（下午班）** | **`3`（晚班）** |
| **SEE_SERIAL_ID** | **`'3'`** | **`'3'`** |
| **DAILY_SERIAL_ID** | **`1423`**（全日绝对流水） | **`1740`**（全日绝对流水） |
| **VALID_FLAG** | **`'1'`**（有效） | **`'1'`**（用例断言瞬间处于有效，随后第③步退号置为 `'0'`） |
| **挂号时间** | `2026-10-09 15:19:12` | `2026-10-09 17:38:09` |
| **就诊排班时间** | `2026-10-09 14:30:00` | `2026-10-09 17:30:00` |
| **更新/退号时间** | `2026-10-09 15:19:12` | `2026-10-09 17:38:09` |

---

## 3. 为什么第 1 轮红、第 2/3 轮变绿？

1. **第 1 轮运行（17:38:09）**：
   - 用例向接口发起连挂 5 次，由于时间已到 17:38，系统自动匹配到晚班（`SEE_NOON_ID = 3`）。
   - 晚班号源池独立从 1 递增，用例成功挂出：`2, 3, 4, 5, 6` 号（`300011878` ~ `300011886`）。
   - 执行断言时，因断言 SQL 的 `GROUP BY` **只按 `see_serial_id` 分组、未限制 `see_noon_id`**，导致：
     - 下午的 3 号（`300011139`, VALID_FLAG='1'）
     - 晚上的 3 号（`300011880`, VALID_FLAG='1'）
     被聚合在一起，`COUNT(*) = 2 > 1`，断言返回 `pool_dup = 1`，触发报错：
     `❌ L6-012 号序/挂号费闭环不成立：同一医生同天有 1 组「有效挂号」号序重复`。
   - 用例随后在第 ③ 步执行退号，将这 5 个号全部置为 `VALID_FLAG = '0'`。

2. **第 2 轮运行（17:38:40）**：
   - 用例再次连挂 5 个号，晚班号源池继续分配，挂出：`7, 8, 9, 10, 11` 号（`300011890` ~ `300011898`）。
   - 当天下午遗留的有效号只有 `1` 号（`300011135`）和 `3` 号（`300011139`）。
   - `7, 8, 9, 10, 11` 与下午的有效号没有交集，跨午别聚合未发生碰撞，`pool_dup = 0`，全绿通过！

3. **第 3 轮运行（17:39:11）**：
   - 用例挂出：`13, 14, 15, 16, 17` 号，同样未碰撞到 1 和 3，全绿通过！

---

## 4. 业务判断依据：是真重号还是设计规律？

### 依据 1：门诊排班的分午别编号机制
在标准 HIS 门诊挂号体系中，医生的排班号源是按「午别/排班班次」（`SEE_NOON_ID`：上午、下午、晚班）分别管理的。
- 上午有 1~N 号，下午有 1~N 号，晚上有 1~N 号；
- 患者挂下午 3 号是在 14:30 候诊，挂晚上 3 号是在 17:30 候诊，两者互不干扰；
- 全天全局唯一的单调递增流水号是 **`DAILY_SERIAL_ID`**（记录 A 为 1423，记录 B 为 1740，绝对不重复）。

### 依据 2：同午别下全库历史重复数为 0
在全库历史所有数据中，执行以下查询（加上 `SEE_NOON_ID` 条件）：
```sql
SELECT TRUNC(see_begin_time), register_doct_id, see_noon_id, see_serial_id, COUNT(*)
FROM fin_op_register
WHERE valid_flag = '1' AND see_serial_id IS NOT NULL
GROUP BY TRUNC(see_begin_time), register_doct_id, see_noon_id, see_serial_id
HAVING COUNT(*) > 1;
```
**查询结果：0 行！全库历史在同一午别下，有效挂号号序从未发生过重复！**

### 依据 3：号源回收（退号复用）机制真实存在且受严格控重
库中当天下午还存在真实的号源回收记录：
- `300011547`：挂出 `71` 号，随后退号（`VALID_FLAG = '0'`）；
- `300011562`：回收 `71` 号并再次分配给后续挂号；
- 系统在复用 `71` 号时，原记录已处于 `VALID_FLAG = '0'`，**绝不会同时出现两个 `VALID_FLAG = '1'` 的同号记录**。

---

## 5. 建议（不改动您的断言，仅供参考）

若后续要彻底消除此偶发红灯，断言 SQL 的子查询只需补齐午别约束：
```sql
-- 建议改进（供主力采纳）：
SELECT COUNT(*) FROM (
  SELECT see_serial_id FROM fin_op_register
  WHERE register_doct_id = :1 AND valid_flag = '1'
    AND see_serial_id IS NOT NULL
    AND see_noon_id = (SELECT see_noon_id FROM fin_op_register WHERE register_id = :2)
    AND TRUNC(see_begin_time) = (SELECT TRUNC(see_begin_time) FROM fin_op_register WHERE register_id = :2)
  GROUP BY see_serial_id HAVING COUNT(*) > 1)
```
这样既坚守了"同医生同排班班次有效挂号绝不重号"的业务底线，又不会误伤跨午别的正常重号。
