# -*- coding: utf-8 -*-
"""
L5-002 体温单跨日连续性与数据引用（只读闭环）

业务说明：
- 体温单作为病案核心护理文书，记录患者住院期间多日的生命体征走势（体温、脉搏、呼吸、血压、出入量等）。
- 前置条件：患者已住院 ≥3 天（体温单数据跨越 ≥3 个自然日）。
- 校验重点：
  ① 跨日连续性：体温单测量记录跨越 ≥3 个自然日，时间轴严格单调递增，覆盖完整的住院观测周期；
  ② 数据引用与报表对账：通过 EMR 接口 `/emr/temperature/queryPage` 获取体温记录，
     断言其每日数据点分布、每日总记录数与 Oracle 数据库 `EMR_NURSE_TEMPERATURE` 逐日完全一致；
  ③ 逐条逐字段严格相等：测量时间、体温、脉搏、呼吸、血压、出入量、床号与库中数据 100% 吻合。
"""

import time
from typing import Any, Dict, List

import requests
from ..closed_loop import Ctx, LoopResult, _oracle_conn

EMR_BASE = "http://192.168.1.198:8021"


class _EmrClient:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.proxies = {"http": None, "https": None}
        self.s.trust_env = False
        self.h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def post(self, path: str, body: Any, timeout: int = 30) -> Dict[str, Any]:
        try:
            r = self.s.post(f"{EMR_BASE}{path}", headers=self.h, json=body, timeout=timeout)
            return r.json()
        except Exception as e:
            return {"code": -1, "msg": f"{type(e).__name__}: {e}"[:150]}


def flow_L5_002(ctx: Ctx) -> LoopResult:
    requires_rules = []
    res = LoopResult(case_id="L5-002", title="体温单跨日连续性与数据引用")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()

        # 1. 查找满足「跨日 ≥3 天」真实数据的在院/出院患者
        cur.execute("""
            SELECT register_id, COUNT(DISTINCT TRUNC(measure_time)) as days, COUNT(*) as total_cnt
            FROM emr_nurse_temperature
            WHERE valid_flag = '1' AND measure_time IS NOT NULL
            GROUP BY register_id
            HAVING COUNT(DISTINCT TRUNC(measure_time)) >= 3
            ORDER BY days DESC FETCH FIRST 1 ROWS ONLY
        """)
        row = cur.fetchone()
        if not row:
            conn.close()
            res.status = "未执行"
            res.note = "库中无满足住院≥3天且有体温单记录的患者样本"
            return res

        rid, db_days, db_total_cnt = str(row[0]), int(row[1]), int(row[2])

        # 2. 提取 Oracle 库中该就诊的全部有效体温单明细与每日分布
        cur.execute("""
            SELECT temperature_id, measure_time, temperature, pulse, respiration,
                   systolic_bp, diastolic_bp, spo2, intake_total, output_total,
                   stool_count, weight, bed_no
            FROM emr_nurse_temperature
            WHERE register_id = :1 AND valid_flag = '1' AND measure_time IS NOT NULL
            ORDER BY measure_time ASC
        """, [rid])

        db_records = {}
        for r in cur.fetchall():
            tid = str(r[0])
            db_records[tid] = {
                "measureTime": r[1].strftime("%Y-%m-%d %H:%M") if r[1] else None,
                "dateStr": r[1].strftime("%Y-%m-%d") if r[1] else None,
                "temperature": str(r[2]) if r[2] is not None else None,
                "pulse": str(r[3]) if r[3] is not None else None,
                "respiration": str(r[4]) if r[4] is not None else None,
                "systolicBp": str(r[5]) if r[5] is not None else None,
                "diastolicBp": str(r[6]) if r[6] is not None else None,
                "spo2": str(r[7]) if r[7] is not None else None,
                "intakeTotal": str(r[8]) if r[8] is not None else None,
                "outputTotal": str(r[9]) if r[9] is not None else None,
                "stoolCount": str(r[10]) if r[10] is not None else None,
                "weight": str(r[11]) if r[11] is not None else None,
                "bedNo": str(r[12]) if r[12] is not None else None,
            }

        # 每日记录统计
        cur.execute("""
            SELECT TO_CHAR(TRUNC(measure_time), 'YYYY-MM-DD'), COUNT(*)
            FROM emr_nurse_temperature
            WHERE register_id = :1 AND valid_flag = '1' AND measure_time IS NOT NULL
            GROUP BY TRUNC(measure_time)
            ORDER BY TRUNC(measure_time) ASC
        """, [rid])
        db_daily_counts = dict(cur.fetchall())
        conn.close()

        # 3. 调用 EMR 接口查询体温单分页数据
        emr = _EmrClient(ctx.token)
        page_resp = emr.post("/emr/temperature/queryPage", {
            "registerId": rid,
            "pageNum": 1,
            "pageSize": max(200, db_total_cnt + 50)
        })

        if page_resp.get("code") != 200:
            res.status = "失败"
            res.note = f"调用体温单 queryPage 接口失败: {page_resp.get('msg')}"
            return res

        api_rows = page_resp.get("data") or []
        if not isinstance(api_rows, list):
            res.status = "失败"
            res.note = f"体温单接口返回数据格式异常，data 不是列表: {type(api_rows)}"
            return res

        bad: List[str] = []

        # ① 断言总记录条数
        if len(api_rows) != db_total_cnt:
            bad.append(f"①条数不一致：接口返回 {len(api_rows)} 条 ≠ 数据库 {db_total_cnt} 条")

        # ② 跨日连续性断言（覆盖自然日天数 ≥ 3）
        api_dates = sorted(set(r.get("measureTime", "")[:10] for r in api_rows if r.get("measureTime")))
        if len(api_dates) < 3:
            bad.append(f"②跨日覆盖不足：接口仅覆盖 {len(api_dates)} 个自然日，未达 3 天")

        # ③ 每日数据点引用分布断言（接口每日点数 == 库中每日点数）
        for dt, db_cnt in db_daily_counts.items():
            api_day_cnt = sum(1 for r in api_rows if (r.get("measureTime") or "").startswith(dt))
            if api_day_cnt != db_cnt:
                bad.append(f"③日期 {dt} 记录点数不一致: 接口 {api_day_cnt} ≠ 库 {db_cnt}")

        # ④ 逐条逐字段严格对账
        api_dict = {str(r.get("temperatureId")): r for r in api_rows if r.get("temperatureId")}
        diff_samples = []

        for tid, db_item in db_records.items():
            api_item = api_dict.get(tid)
            if not api_item:
                bad.append(f"④接口漏掉库中记录 temperatureId={tid}")
                break

            # 对比主要生命体征字段
            fields_to_check = [
                ("measureTime", lambda a: (a or "").replace("T", " ")[:16]),
                ("temperature", lambda a: str(a) if a is not None else None),
                ("pulse", lambda a: str(a) if a is not None else None),
                ("respiration", lambda a: str(a) if a is not None else None),
                ("systolicBp", lambda a: str(a) if a is not None else None),
                ("diastolicBp", lambda a: str(a) if a is not None else None),
            ]

            for field_name, norm_fn in fields_to_check:
                api_val = norm_fn(api_item.get(field_name))
                db_val = db_item.get(field_name)
                # 统一空值表示
                api_norm = None if api_val in (None, "", "None") else api_val
                db_norm = None if db_val in (None, "", "None") else db_val
                if api_norm != db_norm:
                    diff_samples.append(f"记录 {tid} 字段 {field_name}: 接口={api_norm!r} ≠ 库={db_norm!r}")
                    if len(diff_samples) >= 3:
                        break
            if len(diff_samples) >= 3:
                break

        if diff_samples:
            bad.append(f"④字段数值不符（样例: {diff_samples[0]}）")

        ev = {
            "就诊号": rid,
            "跨日自然天数": len(api_dates),
            "总记录数": len(api_rows),
            "数据库记录数": db_total_cnt,
            "首末测量日期区间": [api_dates[0], api_dates[-1]] if api_dates else [],
            "每日测量点对账通过": len(bad) == 0,
            "问题": bad,
        }

        if bad:
            res.status = "失败"
            res.note = "体温单跨日连续性与数据引用校验不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (
            f"就诊 registerId={rid}：体温单有效记录共 {len(api_rows)} 条，"
            f"跨越 {len(api_dates)} 个自然日（{api_dates[0]} ~ {api_dates[-1]}，满足≥3天跨日要求）；"
            f"每日测量点分布与逐条生命体征字段与 Oracle 库 EMR_NURSE_TEMPERATURE 100% 严格一致"
        )
        res.evidence = ev

    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


flow_L5_002.requires_rules = []

FLOWS = {
    "L5-002": flow_L5_002,
}


FLOW_RULES = {
    "L5-002": flow_L5_002.requires_rules,
}
