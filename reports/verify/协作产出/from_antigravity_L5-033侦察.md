# 专题报告 · L5-033 处方点评与不合理用药统计（可验性侦察）

> 任务要求：先侦察有没有点评表/接口与运行数据。没有就报未执行。

---

## 一、侦察结论

- **判定**：**「未执行（系统无此功能模块）」**。
- **核心结论**：
  1. 当前 HIS/EMR 系统**未开发或部署处方点评与合理用药监测模块**；
  2. 数据库底层无任何处方点评规则表、点评任务表、抽检批次表或不合理用药日志表；
  3. 系统菜单 `SYS_MENU` 中无点评或合理用药相关菜单项；
  4. 后端 OpenAPI 规范 `data/api_spec.json` 中不存在处方点评、用药审查拦截、或合理用药统计报表接口。

---

## 二、调查事实与硬证据

### 1. 数据库底层表检索（0 张匹配表）
在 Oracle 库（XCHIS 模式）中全量检索包含点评、合理用药、审方等关键词的表：
```sql
SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER='XCHIS' AND (
    TABLE_NAME LIKE '%COMMENT%' OR TABLE_NAME LIKE '%RATIONAL%' OR TABLE_NAME LIKE '%REVIEW%'
    OR TABLE_NAME LIKE '%PRESCRIPTION%' OR TABLE_NAME LIKE '%RECIPE_AUDIT%'
);
```
- **匹配结果**：**0 张表**。

### 2. 菜单与权限检索（0 个功能项）
检索系统菜单配置表 `SYS_MENU`：
```sql
SELECT MENU_NAME, PERMS FROM SYS_MENU
WHERE MENU_NAME LIKE '%点评%' OR MENU_NAME LIKE '%合理用药%' OR MENU_NAME LIKE '%审方%';
```
- **匹配结果**：**0 条记录**（药房与医务工作台未挂载处方点评功能入口）。

### 3. OpenAPI 接口规范审计（0 个点评接口）
审查 `data/api_spec.json` 中的全部接口路径：
- 检索 `comment`、`rational`、`review`、`prescription`、`点评`、`不合理`：
- 匹配到的接口仅为退款方案预览（`refund/allocation/plan/preview`）、换科预览检查（`deptShift/previewCheck`）、医嘱单打印预览（`execOrderBill/print/preview`）等与用药点评无关的常规业务 preview；
- 无任何处方抽取、规则匹配、药师点评打分、不合理用药公示相关的 API。

---

## 三、处理建议

系统确无该功能模块，根据规范据实判定为「未执行（无此功能模块）」。
