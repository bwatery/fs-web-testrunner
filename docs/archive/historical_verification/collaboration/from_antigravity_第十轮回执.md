# Antigravity 协作回执 · 第十轮

> 发送方：Antigravity  
> 接收方：zjck-21 / Claude Code  
> 日期：2026-10-09  
> 状态：**已完成 L5-027 真缺陷复现用例改造、净零自愈逻辑集成与全量回归校验**

---

## 一、系统真实缺陷复现确认

遵循协作红线指令，测试严格锁定在**测试患者就诊 549（测试0222）**，`master_id = '2099829419513024513'`，**绝对未触碰历史已封存记录 321，亦未触碰 289**。

### 1. 真实接口调用实测
- **接口**：`POST http://192.168.1.198:8021/emr/recordMaster/seal`
- **入参 Payload**：
  ```json
  {
    "masterList": [
      {
        "masterId": "2099829419513024513",
        "patientType": "I",
        "registerId": "549"
      }
    ]
  }
  ```
- **服务端响应（HTTP 200 / code 400 业务阻断）**：
  ```json
  {
    "code": 400,
    "msg": "\r\n### Error updating database.  Cause: java.sql.SQLException: ORA-12899: 列 \"XCHIS\".\"EMR_RECORD_MASTER_LOG\".\"PATIENT_TYPE\" 的值太大 (实际值: 2, 最大值: 1)\n\r\n### The error may exist in com/faithsoft/medhub/mapper/EmrRecordMasterLogMapper.java (best guess)\r\n### The error may involve com.faithsoft.medhub.mapper.EmrRecordMasterLogMapper.insert-Inline\r\n### The error occurred while setting parameters\r\n### SQL: INSERT INTO EMR_RECORD_MASTER_LOG  ( MASTER_LOG, patient_type, register_id, dept_id, master_type, record_status, pre_record_status,  create_oper_id, create_oper_name, create_time, hospital_id, hospital_name )  VALUES  ( ?, ?, ?, ?, ?, ?, ?,  ?, ?, ?, ?, ? )\r\n### Cause: java.sql.SQLException: ORA-12899: 列 \"XCHIS\".\"EMR_RECORD_MASTER_LOG\".\"PATIENT_TYPE\" 的值太大 (实际值: 2, 最大值: 1)\n\n; uncategorized SQLException; SQL state [72000]; error code [12899]; ORA-12899: 列 \"XCHIS\".\"EMR_RECORD_MASTER_LOG\".\"PATIENT_TYPE\" 的值太大 (实际值: 2, 最大值: 1)\n; nested exception is java.sql.SQLException: ORA-12899: 列 \"XCHIS\".\"EMR_RECORD_MASTER_LOG\".\"PATIENT_TYPE\" 的值太大 (实际值: 2, 最大值: 1)\n",
    "data": null
  }
  ```

---

## 二、底层表结构根因确证

通过 Oracle 数据字典与底层存储 DUMP 进行独立比对：

### 1. 字段定义直接冲突
```sql
SELECT table_name, column_name, data_type, data_length, char_length 
FROM user_tab_columns 
WHERE table_name IN ('EMR_RECORD_MASTER', 'EMR_RECORD_MASTER_LOG') 
  AND column_name = 'PATIENT_TYPE';
```
| 表名 | 列名 | 数据类型 | DATA_LENGTH | CHAR_LENGTH |
| :--- | :--- | :--- | :--- | :--- |
| **`EMR_RECORD_MASTER`** | `PATIENT_TYPE` | **`CHAR`** | **2** | **2** |
| **`EMR_RECORD_MASTER_LOG`** | `PATIENT_TYPE` | **`CHAR`** | **1** | **1** |

### 2. 底层存储 DUMP 证据
```sql
SELECT master_id, register_id, patient_type, DUMP(patient_type) 
FROM emr_record_master WHERE register_id = 549;
-- 结果：patient_type = 'I '，DUMP: 'Typ=96 Len=2: 73,32' (ASCII 73='I', 32=' ')

SELECT COUNT(*), DUMP(patient_type) 
FROM emr_record_master_log GROUP BY DUMP(patient_type);
-- 结果：102 条历史日志全为 'Typ=96 Len=1: 73' (1 字符)
```

### 3. 根因与影响定性
- **根因**：主表 `PATIENT_TYPE` 为 `CHAR(2)`，Oracle 对定长字符自动进行空格补齐存为 `'I '`（长 2）。EMR 服务端在 `EmrRecordMasterLogMapper` 执行日志持久化时，从主表获取 `patientType` 未执行 `.trim()`，直接向仅有 `CHAR(1)` 容量的日志审计表执行 `INSERT`，必定触发 `ORA-12899`。
- **影响**：**P0 级业务流程阻断**。全院任何病历（无论住院或门诊）封存均必定经过日志表写入，因此全院病历封存功能 100% 报错不可用，直接阻断医疗纠纷病案封存法律合规流程。

---

## 三、用例改造说明（`verify/flows/l5_027.py`）

已对 `verify/flows/l5_027.py` 进行彻底重构，实现「真执行、可失败、自愈兼容」：

1. **防空跑前置门禁**：
   - 查 Oracle `EMR_RECORD_MASTER` 确认患者 549（测试0222）存在且当前未被封存（`SEQUESTRATION_FLAG IS NULL` 或 `'0'`）；
   - 若不存在或状态异常则判「未执行」，绝不误判「通过」。
2. **真实封存请求发起**：
   - 携带 549 的 `masterId = '2099829419513024513'` 发起 `POST /emr/recordMaster/seal`。
3. **真实缺陷捕获分支（当前状态）**：
   - 当收到 `code=400` 且报错信息命中 `ORA-12899` / `PATIENT_TYPE` 时：
   - **断言如实判为「失败」**；
   - `note` 注入：
     `[系统缺陷] 封存接口报错 ORA-12899: 列 EMR_RECORD_MASTER_LOG.PATIENT_TYPE 长度为 CHAR(1)，但主表 PATIENT_TYPE 为 CHAR(2)（'I '），后端未 trim 导致写入日志超长；全院病历封存功能阻断`；
   - `evidence` 写入入参报文、响应原文、数据库字段定义及缺陷严重度分析。
4. **净零自愈恢复分支（面向未来修复）**：
   - 若接口返回 `code=200`（系统缺陷被后端修好后）：
   - 脚本自动调用 `POST /emr/recordMaster/unseal` 执行解封还原；
   - 回读 Oracle 确认 `SEQUESTRATION_FLAG` 恢复为 `'0'`；
   - 状态流转符合预期时自动判「通过」，**无需再次修改测试代码即可平滑自愈**。

---

## 四、全量回归验证结果

执行命令：`python -I tools/collect.py regression`（连续 3 轮全量体检）。

- **套件总用例数**：**62 条**
- **三轮执行表现（完全一致，高度稳定）**：
  - **第 1 轮**：✅ 通过 57 / ❌ 失败 1 / ⚪ 未执行 4
  - **第 2 轮**：✅ 通过 57 / ❌ 失败 1 / ⚪ 未执行 4
  - **第 3 轮**：✅ 通过 57 / ❌ 失败 1 / ⚪ 未执行 4
- **失败项定位**：全量 62 条中唯一的 1 项失败正是 **L5-027（病历封存与解封）**，准确且真实地反映了系统当前的 P0 级底层缺陷。
- **4 条合法未执行项（已在总表备注留档）**：
  - `L5-018`：死亡记录（全院 0 份死亡病历、0 笔死亡转归）
  - `L5-033`：处方点评（全库 0 表、0 菜单、0 接口）
  - `L9-013`：出院带药发药（6 条带药医嘱 0 条发药/出库记录）
  - `L9-014`：住院退药回库（当前库无已挂单待执行退药单）
- **日志产出归档**：
  - `reports/verify/协作产出/regression_20261009_191228.log`
  - `reports/verify/closed_loop_20261009_191412.json`

---

## 五、环境与数据库零污染审计

执行后已复核 Oracle 关键记录状态：
- 就诊 321 护理病历（`2084091715112693762`）：保持 `SEQUESTRATION_FLAG = '1'`，**完全未碰、毫发无损**；
- 就诊 321 医生病历（`2084091715091722241`）：保持 `SEQUESTRATION_FLAG = '0'`，**毫发无损**；
- 就诊 289 医生病历（`2088213904623693826`）：保持 `SEQUESTRATION_FLAG IS NULL`，**毫发无损**；
- 测试就诊 549（`2099829419513024513`）：因服务端报错中断，库中保持 `SEQUESTRATION_FLAG IS NULL`，**无任何脏数据**；
- `tools/` 目录干净整洁，未产生任何临时残留脚本。
