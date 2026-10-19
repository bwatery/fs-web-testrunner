# Antigravity 任务清单（按顺序做，做完一件回报一件）

> 背景与红线：先读同目录 `给Antigravity的对接说明.md`（三条红线 + 怎么把结果交回来）。
> 结果一律写到 `reports/verify/协作产出/from_antigravity_<主题>.md`，**贴原始输出**。
>
> 三条红线再说一遍：**不改断言、不把"没数据"写成"通过"、不覆盖源文件与 `closed_loop_latest.json`**。

---

## 任务 A · 独立复核我的数字（**最高优先**，能抓到我的错）

我声称的每个数字，你**独立从库里/接口再查一遍**，只回报「一致 / 不一致 + 你查到的值 + 你用的 SQL」。
**不要顺着我说** —— 我错了就靠这一步抓出来。

环境：`xchis/xchis@192.168.1.199:1521/orcl`；EMR 接口 `http://192.168.1.198:8021`，token 用
`POST http://192.168.1.198:8081/login {"username":"emradmin","password":"000000"}` 取，放 `Authorization: Bearer <token>`。

### A1 · L5-001 体温单
**我声称**：就诊 `342` 库里有 **158** 条有效体温记录、接口也返回 **158** 条、覆盖 **29** 个自然日。

```sql
SELECT COUNT(*) FROM emr_nurse_temperature WHERE register_id='342' AND valid_flag='1' AND measure_time IS NOT NULL;
SELECT COUNT(DISTINCT TRUNC(measure_time)) FROM emr_nurse_temperature WHERE register_id='342' AND valid_flag='1';
```
接口：`POST /emr/temperature/queryPage`，body `{"registerId":"342","pageNum":1,"pageSize":300}` → 数 `data` 数组长度
**期望**：158 / 29 / 158

### A2 · L5-003 护理记录单
**我声称**：记录单 `2060293117001416706` 库里有 **426** 个时间点，接口返回 **430** 个（**多 4 个**，我没解释清楚），
逐点比对 **3405** 个数据元值**零不一致**。

```sql
SELECT COUNT(DISTINCT nurse_data_element_index) FROM emr_nurse_record_detail WHERE record_id='2060293117001416706' AND valid_flag='1';
```
接口：`POST /emr/nurseRecordDetail/queryList`，body `{"recordId":"2060293117001416706"}` → 数 `data` 长度
**期望**：426 / 430
**额外帮我查**：接口多出来的那 4 个 `nurseDataElementIndex` 到底从哪来的？
它们既不在 `EMR_NURSE_RECORD_DETAIL` 也不在 `EMR_NURSE_RECORD_ROW_LOG` 里。
你能在**别的表**里找到这几个 index 吗？（这 4 个值的清单在 `closed_loop_latest.json` 的 L5-003 证据里）

### A3 · L5-006 修改留痕
**我声称**：记录单 `2060293117001416706` 库里有 **535** 条留痕，接口返回 **535** 条，其中 **70** 个时间点有多条留痕。

```sql
SELECT COUNT(*) FROM emr_nurse_record_row_log WHERE record_id='2060293117001416706';
SELECT COUNT(*) FROM (SELECT nurse_data_element_index FROM emr_nurse_record_row_log WHERE record_id='2060293117001416706' GROUP BY nurse_data_element_index HAVING COUNT(*)>1);
```
**期望**：535 / 70

### A4 · L5-008 元素不串患者
**我声称**：`EMR_RECORD_ITEM` 里 **23949** 条有效元素，其患者/就诊与所属文书**零例外一致**。

```sql
SELECT COUNT(*) FROM emr_record_item WHERE valid_flag='1';
SELECT COUNT(*) FROM emr_record_item i JOIN emr_record r ON r.record_id=i.record_id
 WHERE i.valid_flag='1' AND (TO_CHAR(i.patient_id)<>TO_CHAR(r.patient_id) OR TO_CHAR(i.register_id)<>TO_CHAR(r.register_id));
```
**期望**：23949 / **0**

### A5 · L5-019 病案首页
**我声称**：库 `MED_RECORD_FRONTPAGE` **4** 条，接口 `POST /med/recordFrontpage/queryPage` 也返回 **4** 条。
```sql
SELECT COUNT(*) FROM med_record_frontpage;
```
**期望**：4 / 4

### A6 · L5-023 专科模板覆盖
**我声称**：模板授权覆盖 **12 个临床专科**，每个都有已审核通过的可用模板；按科室聚合的授权条数与库**逐科一致**。
```sql
SELECT COUNT(DISTINCT g.grant_dept_id) FROM emr_bd_template_grant g WHERE g.valid_flag='1' AND g.grant_dept_id IS NOT NULL;
SELECT d.dept_name, COUNT(DISTINCT CASE WHEN t.approval_state='1' THEN g.template_id END) ok
  FROM emr_bd_template_grant g JOIN sys_dept d ON d.dept_id=g.grant_dept_id
  LEFT JOIN emr_bd_template t ON t.template_id=g.template_id AND t.valid_flag='1'
 WHERE g.valid_flag='1' AND d.dept_name LIKE '%科%' GROUP BY d.dept_name ORDER BY 2;
```
**期望**：34 个科室；`ok` 列**没有 0**（收费处不含"科"所以不在这条里）

### A7 · L9-010 住院摆药
**我声称**：对 9 组「摆药单×状态」核对，药房工作台拿到的明细与库**完全一致**。
接口：`POST http://192.168.1.198:8021`←不对，这个在 HIS 网关：
`POST http://192.168.1.198:8081/faith/pharmacy/inDispense/queryDetail`，
body 是**数组**：`[{"dispenseBillId":855,"storageDeptId":910125,"terminalId":45,"dispenseState":"PRINTED"}]`
**期望**：返回 2 条（0.9%氯化钠 + 地西泮，各 -1）
库里对照：`SELECT COUNT(*) FROM pha_dispense_apply WHERE dispense_bill_id=855 AND valid_flag='1' AND apply_state='2'` → 2

---

## 任务 B · EMR 接口摸底（**之前派过，一直没交**）

```bash
cd D:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner
python tools/fetch_emr_spec.py       # 拉 EMR 接口清单
python tools/collect.py emr-by-tag   # 按 tag 分类 + 生成用例↔接口对照草稿
```
**回报**：两个产出的行数；`emr_api_by_tag.csv` 里 tag 共几个。
⚠️ `emr_case_candidates.csv` 是**关键词粗匹配的草稿，不是结论**，你的活是把它产出来，别下判断。

---

## 任务 C · 我没碰过的模块：只读侦察

只做**信息收集**，不下结论、不改状态。对每个模块回报：**相关表（带行数）+ 相关接口 + 有没有可用数据**。

| # | 模块 | 线索 |
|---|---|---|
| C1 | **临床路径**（L5-030/031） | 表名含 `PATH`/`CLINICAL`；接口 `summary` 含"路径" |
| C2 | **毒麻精放药品**（L5-035） | `PHA_BD_ACTION` 里有"麻醉药品"节点；找药品的毒麻属性在哪 |
| C3 | **EMR 与 HIS 数据一致性**（L5-036） | 同一患者的 病历 / 医嘱 / 检验 三类数据能否互相印证 |
| C4 | **床位费自动计提**（L6-043） | `FIN_IP_CHARGE` 里 `ITEM_FEE_TYPE='1'`；**关键是找到"服务日期"存在哪一列**（`CHARGE_TIME` 是补录时间，不是计提日） |
| C5 | **住院结算日结**（L6-055） | 接口 `/faith/finance/dayBalance/report/inpatient/list`；搞清 `payInfoList` 和 `allReceiptNoList` 的数据来源 |

C4 是里面最有价值的：**卧床位费"服务日期"到底在哪一列**，找到了我就能把这条用例做出来。

---

## 任务 D · 回归（随手做）

```bash
python tools/collect.py regression     # 期望结尾打印"三轮全绿 ✓"
```
红了就**停手**，把 `reports/verify/协作产出/regression_*.log` 整个交给主力，**别自己改代码**。

---

## 做完怎么回报

一件一件来，每件写进 `reports/verify/协作产出/from_antigravity_<主题>.md`：

```
【任务 A1】L5-001 体温单
- 我查的 SQL / 接口：（原文）
- 我查到的值：（原文输出）
- 与主力声称对比：一致 / 不一致（不一致要写清差在哪）
- 疑问：
```

有疑问就问，别猜。
