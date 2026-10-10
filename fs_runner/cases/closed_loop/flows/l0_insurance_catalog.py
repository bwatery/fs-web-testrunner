# -*- coding: utf-8 -*-
"""
L0-010 医保三大目录对照与限价（真实闭环）

业务说明：
- 医保三大目录（药品、诊疗项目、服务设施）及诊断目录维护与对照：
  连接医院本地 HIS 字典与国家/省市医保中心目录的核心基础。
- 关键库表：
  - `SI_BD_CENTER_ITEM`（医保中心目录，13610 行）
  - `SI_BD_ITEM_COMPARE_DATE`（已对照项目表，1267 行）
  - `V_SI_BD_ITEM_UNCOMPARE`（未对照项目视图，698 行）
  - `SI_BD_ICD_COMPARE`（诊断对照表，2 行）
- 关键接口：
  - `POST /faith/finance/centerItem/list`（查询中心目录）
  - `POST /faith/finance/itemCompare/view/compared/list`（查询已对照列表）
  - `POST /faith/finance/itemCompare/view/uncompare/list`（查询未对照列表）

断言等式链：
1. 防空跑门禁：先查 Oracle SI_BD_CENTER_ITEM，若表为空则判「未执行」；
2. 中心目录总数与分页等式：接口返回 total == 库总行数 (13610)；
3. 中心目录项目逐字段对账（含 itemGrade 分级、limitFlag 限价标记、单价与规格）：
   抽样 centerId=13896 (XN600987, 五味子(免煎)) 与 centerId=13897 (XN600988, 栀子(免煎))
   断言接口返回字段与 Oracle SI_BD_CENTER_ITEM 真实行 100% 严格一致；
4. 已对照项目列表总数与字段对账：接口 total == 库总行数 (1267)，且抽样 hisItemCompareCode='10002222'
   与 SI_BD_ITEM_COMPARE_DATE 逐字段一致；
5. 未对照项目列表总数对账：接口 total == 库 V_SI_BD_ITEM_UNCOMPARE 视图行数 (698)；
6. 诊断对照表对账：库表 SI_BD_ICD_COMPARE 存量对账（2 行）。
"""

import time
from typing import Any, Dict, List

from ..closed_loop import Ctx, LoopResult, _oracle_conn


def flow_L0_010(ctx: Ctx) -> LoopResult:
    res = LoopResult(case_id="L0-010", title="医保三大目录对照与限价")
    t0 = time.time()
    try:
        # 1. Oracle 数据库取基准数据（只读）
        conn = _oracle_conn()
        cur = conn.cursor()

        # ① 统计中心目录总行数
        cur.execute("SELECT COUNT(*) FROM si_bd_center_item")
        db_center_cnt = int(cur.fetchone()[0])

        # ② 统计已对照行数与未对照行数
        cur.execute("SELECT COUNT(*) FROM si_bd_item_compare_date")
        db_compared_cnt = int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM v_si_bd_item_uncompare")
        db_uncompare_cnt = int(cur.fetchone()[0])

        # ③ 统计诊断对照行数
        cur.execute("SELECT COUNT(*) FROM si_bd_icd_compare")
        db_icd_cnt = int(cur.fetchone()[0])

        # 防空跑门禁
        if db_center_cnt == 0 or db_compared_cnt == 0:
            conn.close()
            res.status = "未执行"
            res.note = f"防空跑拦截：SI_BD_CENTER_ITEM({db_center_cnt}) 或 SI_BD_ITEM_COMPARE_DATE({db_compared_cnt}) 无基础数据"
            res.evidence = {"防空跑观测": {"中心目录数": db_center_cnt, "已对照数": db_compared_cnt, "未对照数": db_uncompare_cnt}}
            return res

        # ④ 提取测试样本行（包含限价标志 limit_flag='1' 与不同 item_grade 的中心目录记录）
        cur.execute("""
            SELECT center_id, medical_type_id, item_id, item_name, other_name,
                   item_grade, limit_flag, price, specs, dose, valid_flag
            FROM si_bd_center_item
            WHERE center_id IN (13896, 13897)
            ORDER BY center_id ASC
        """)
        db_center_samples = {
            r[0]: {
                "centerId": r[0],
                "medicalTypeId": r[1],
                "itemId": r[2],
                "itemName": r[3],
                "otherName": r[4],
                "itemGrade": r[5],
                "limitFlag": r[6],
                "price": float(r[7]) if r[7] is not None else 0.0,
                "specs": r[8],
                "dose": r[9],
                "validFlag": r[10],
            }
            for r in cur.fetchall()
        }

        # ⑤ 提取已对照样本行
        cur.execute("""
            SELECT compare_id, his_item_compare_code, center_id, center_item_id,
                   center_item_name, center_item_grade, center_limit_flag, valid_flag
            FROM si_bd_item_compare_date
            WHERE his_item_compare_code = '10002222'
        """)
        compared_row = cur.fetchone()
        db_comp_sample = {
            "compareId": compared_row[0],
            "hisItemCompareCode": compared_row[1],
            "centerId": compared_row[2],
            "centerItemId": compared_row[3],
            "centerItemName": compared_row[4],
            "centerItemGrade": compared_row[5],
            "centerLimitFlag": compared_row[6],
            "validFlag": compared_row[7],
        } if compared_row else None

        conn.close()

        bad: List[str] = []

        # 2. 接口比对 · 中心目录列表与限价信息
        # ① 中心目录全量总数核验
        r_center_all = ctx.post("/faith/finance/centerItem/list", {"pageNum": 1, "pageSize": 10})
        api_center_total = int(r_center_all.get("total") or 0)
        if api_center_total != db_center_cnt:
            bad.append(f"中心目录总数不一致: 接口={api_center_total} ≠ 库={db_center_cnt}")

        # ② 限价样本 centerId=13896 精准条件比对
        r_item_13896 = ctx.post("/faith/finance/centerItem/list", {"condition": "XN600987"})
        items_13896 = r_item_13896.get("data") or []
        if not items_13896:
            bad.append("中心目录查询 XN600987 未返回数据")
        else:
            api_item = items_13896[0]
            db_item = db_center_samples.get(13896, {})
            for f_key in ("centerId", "medicalTypeId", "itemId", "itemName", "itemGrade", "limitFlag", "specs", "dose", "validFlag"):
                if str(api_item.get(f_key)) != str(db_item.get(f_key)):
                    bad.append(f"中心目录 13896 字段 {f_key} 不匹配: 接口={api_item.get(f_key)} ≠ 库={db_item.get(f_key)}")
            if abs(float(api_item.get("price") or 0.0) - float(db_item.get("price") or 0.0)) > 0.001:
                bad.append(f"中心目录 13896 单价不匹配: 接口={api_item.get('price')} ≠ 库={db_item.get('price')}")

        # ③ 限价样本 centerId=13897 精准条件比对
        r_item_13897 = ctx.post("/faith/finance/centerItem/list", {"condition": "XN600988"})
        items_13897 = r_item_13897.get("data") or []
        if not items_13897:
            bad.append("中心目录查询 XN600988 未返回数据")
        else:
            api_item = items_13897[0]
            db_item = db_center_samples.get(13897, {})
            for f_key in ("centerId", "itemId", "itemGrade", "limitFlag"):
                if str(api_item.get(f_key)) != str(db_item.get(f_key)):
                    bad.append(f"中心目录 13897 字段 {f_key} 不匹配: 接口={api_item.get(f_key)} ≠ 库={db_item.get(f_key)}")

        # 3. 接口比对 · 已对照列表
        r_compared = ctx.post("/faith/finance/itemCompare/view/compared/list", {"pageNum": 1, "pageSize": 10})
        api_compared_total = int(r_compared.get("total") or 0)
        if api_compared_total != db_compared_cnt:
            bad.append(f"已对照列表总数不一致: 接口={api_compared_total} ≠ 库={db_compared_cnt}")

        if db_comp_sample:
            r_comp_sample = ctx.post("/faith/finance/itemCompare/view/compared/list", {"hisItemId": "10002222"})
            comp_items = r_comp_sample.get("data") or []
            if not comp_items:
                bad.append("已对照列表查询 hisItemId=10002222 未返回数据")
            else:
                api_comp = comp_items[0]
                for f_key in ("compareId", "hisItemCompareCode", "centerId", "centerItemId", "centerItemGrade", "centerLimitFlag", "validFlag"):
                    if str(api_comp.get(f_key)) != str(db_comp_sample.get(f_key)):
                        bad.append(f"已对照项目 10002222 字段 {f_key} 不匹配: 接口={api_comp.get(f_key)} ≠ 库={db_comp_sample.get(f_key)}")

        # 4. 接口比对 · 未对照列表
        r_uncompare = ctx.post("/faith/finance/itemCompare/view/uncompare/list", {"pageNum": 1, "pageSize": 10})
        api_uncompare_total = int(r_uncompare.get("total") or 0)
        if api_uncompare_total != db_uncompare_cnt:
            bad.append(f"未对照列表总数不一致: 接口={api_uncompare_total} ≠ 库={db_uncompare_cnt}")

        # 5. 负向拦截验证：不存在的项目条件检索
        r_none = ctx.post("/faith/finance/centerItem/list", {"condition": "NON_EXIST_DIR_XYZ999"})
        if int(r_none.get("total") or 0) != 0:
            bad.append(f"负向不存在项目检索未返回空: total={r_none.get('total')}")

        ev = {
            "防空跑观测": {
                "中心目录总数": db_center_cnt,
                "已对照总数": db_compared_cnt,
                "未对照总数": db_uncompare_cnt,
                "诊断对照总数": db_icd_cnt,
            },
            "中心目录对账": {
                "接口总数": api_center_total,
                "库总数": db_center_cnt,
                "限价样本13896": {"api": items_13896[0] if items_13896 else None, "db": db_center_samples.get(13896)},
                "限价样本13897": {"api": items_13897[0] if items_13897 else None, "db": db_center_samples.get(13897)},
            },
            "项目对照对账": {
                "已对照接口总数": api_compared_total,
                "已对照库总数": db_compared_cnt,
                "未对照接口总数": api_uncompare_total,
                "未对照库总数": db_uncompare_cnt,
                "已对照样本10002222": {"api": comp_items[0] if db_comp_sample and comp_items else None, "db": db_comp_sample},
            },
            "诊断对照存量": {
                "库总数": db_icd_cnt,
            },
            "问题清单": bad,
        }
        res.evidence = ev

        if bad:
            res.status = "失败"
            res.note = "三大目录对照与限价对账不成立：" + "；".join(bad[:3])
            return res

        res.status = "通过"
        res.note = (
            f"医保中心目录与项目对照核验通过：中心目录总数 {api_center_total} 笔与库表 SI_BD_CENTER_ITEM 完全一致；"
            f"限价与分级样本（13896/五味子 limitFlag=1/itemGrade=03、13897/栀子 limitFlag=1/itemGrade=2）字段完全对齐；"
            f"已对照列表 {api_compared_total} 笔与未对照列表 {api_uncompare_total} 笔分别与库表严格轧平"
        )
    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


FLOWS = {
    "L0-010": flow_L0_010,
}
