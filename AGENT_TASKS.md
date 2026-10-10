# 派工单 · 给 Antigravity / 协作方直接执行

> **你只负责"跑 + 如实回报"，不负责判断对错。**
> 完整背景读 `reports/verify/并行协作说明.md`，口径速查读 `reports/verify/交接文档.md` 第 5 节。
> 详细任务说明读 `reports/verify/分工与任务卡.md`。

---

## ⛔ 三条红线（违反即返工，比做不完更严重）

1. **不许改断言、不许改判定逻辑。** 跑出"失败"就是失败——把**原始输出原样贴回来**，
   让主力判是"真缺陷"还是"断言写错了"。**自己改绿 = 交付假结论。**
2. **不许把"没数据/没条件"写成"通过"。** 状态只有三种：通过 / 失败 / 未执行。
3. **不许覆盖**：`D:\workapp\ZJCK\HIS_EMR上线测试用例追踪表_合并版.xlsx`（源文件）、
   `reports/verify/closed_loop_latest.json`（全量覆盖会冲掉别人的证据）。
   产出**一律另存**。

**不许改这些文件**：`verify/closed_loop.py`、`verify/flows/*.py`、`run_verify.py`、`update_tracking_excel.py`。
要改先问主力。

---

## 一、开跑前的自检（30 秒）

```bash
cd D:/CSsoft/AI/googleAntiGravity/cliProject/fs_web_testrunner
python -c "import oracledb, requests, openpyxl; print('依赖 OK')"
python run_verify.py --closed-loop --cases L6-036     # 期望：通过 1  失败 0
```

上面这条不绿，**停下来先回报**，别继续。

---

## 二、任务（每条几分钟到十几分钟）

### 任务 1 · 全量回归（最高频）

```bash
python tools/collect.py regression
```

- **期望**：结尾打印 `三轮全绿 ✓`
- **产出**：`reports/verify/协作产出/regression_*.log`
- **如果是红的**：**停手**，把那个 log 整个交给主力，不要自己动代码

### 任务 2 · 采集类产出（一次性，跑完就够）

```bash
python tools/collect.py api-by-tag
python tools/collect.py tables
python tools/collect.py evidence-index
python tools/collect.py pending-grouped
```

- **产出**：`reports/verify/协作产出/` 下 5 个 CSV
- **回报**：每个文件的行数 + 有没有报错
- 这些是**给主力找口径用的素材**，你不用读内容、不用分析

### 任务 3 · EMR 接口摸底（**新解锁，优先做**）

EMR（病历文书）是**独立后端**，不在 HIS 网关上：

| 项 | 值 |
|---|---|
| EMR 后端 | `http://192.168.1.198:8021` ← 来自 `http://192.168.1.198:8088/config.js` 的运行时配置 |
| 鉴权 | **直接认 HIS 的 JWT**，`Authorization: Bearer <token>`（用 `emradmin`/`000000` 登录 8081 拿） |
| 接口数 | **518 条**，Swagger 在 `http://192.168.1.198:8021/v2/api-docs` |

```bash
python tools/fetch_emr_spec.py     # 刷新接口清单 -> data/emr_api_spec.json
python tools/collect.py emr-by-tag # 按 tag 分类 + 生成 L5 用例与候选接口的对照草稿
```

- **产出**：`reports/verify/协作产出/emr_api_by_tag.csv`、`emr_case_candidates.csv`
- **回报**：两个文件的行数；`emr_api_by_tag.csv` 里 tag 一共几个
- ⚠️ `emr_case_candidates.csv` 是**关键词粗匹配的草稿，不是结论**，主力确认后才算数。
  你的任务是**把草稿产出来**，不要自己下判断说"某用例对应某接口"

### 任务 4 · 全角色菜单巡检（要先问用户）

```bash
python run_verify.py --workstations
```

- ⚠️ 这个模式会**驱动用户自己开着的 Chrome**（CDP 9222）。**跑之前必须先问一句方不方便。**
- **产出**：`reports/verify/workstation_latest.json`
- **只报"新增的异常"**，老问题不用重复报：
  - 住院医生 → 医生返修（**真缺陷，已上报**，别再报）
  - 住院药房 → 药品出入库（**权限问题，已跳过**，别再报）

### 任务 4 · 独立复核（唯一带一点判断的活）

主力写完一条用例后会给你**断言和它声称的数字**。你要做的是**从库里独立再查一遍**：

1. 照主力给的 SQL（或自己写等价的）去查
2. 对比：**一致 / 不一致**
3. 回报：**你查的 SQL 原文 + 查询结果 + 结论**

你**不需要判断谁对**。你只要保证"我确实查了，查到的就是这个数"。
**主力的数字错了，就靠这一步抓出来——所以千万别"顺着它说"。**

---

## 三、回报格式（统一，别自由发挥）

```
【任务 N】结果
- 命令 ：
- 结果 ：（贴原始输出，不要改写、不要只写"成功"）
- 判定 ：符合预期 / 不符合预期
- 产出 ：（文件路径）
- 疑问 ：（没有就写"无"）
```

---

## 四、绝对不要做的事

| 别做 | 为什么 |
|---|---|
| 改 `verify/closed_loop.py` 里的断言让它变绿 | 这是这个项目**存在的原因**——上一版工具就是这么造出 237 条假"通过"的 |
| 把 `未执行` 改写成 `通过` | 没验就是没验 |
| 直接改 `D:\workapp\ZJCK` 下的 xlsx | 那是源文件 |
| 自己新建挂号 / 自己造收费数据 | 收过费就永久退不了号，会往库里塞"假的可退挂号" |
| 数据库 `INSERT/UPDATE/DELETE` | 只读查询可以，写操作一律找主力 |
| 覆盖 `closed_loop_latest.json` | 会冲掉别人的证据 |

---

## 五、环境速查

| 项 | 值 |
|---|---|
| 网关 | `http://192.168.1.198:8081` |
| 登录 | `POST /login {"username":"admin","password":"admin123"}` |
| Oracle | `xchis/xchis@192.168.1.199:1521/orcl` |
| 前端 | `http://192.168.1.198:8088` |
| Chrome CDP | 9222（**用户自己开着的窗口，动它之前先问**） |

**最容易踩的三个坑**（详见交接文档 5.1/5.5）：
1. 前端 **hash 跳转不加载组件** —— 点完菜单内容区还是仪表盘，要整页重载
2. 日结报表**必须传 `dayBalanceId`** —— 只传时间区间永远返回 0
3. **"接口返回 200 就算过"不是断言** —— 那叫装饰
