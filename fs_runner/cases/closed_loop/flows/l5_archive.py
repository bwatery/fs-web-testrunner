# -*- coding: utf-8 -*-
"""
L5-028 病历归档与调阅授权（只读闭环）

业务说明：
- 病历生命周期终末流转：医生完成病历书写后提交归档；归档后文书进入锁定状态，
  仅限授权人员通过病案调阅借阅；若遇医疗纠纷或质控封存，则触发病历封存。
- EMR 状态主表：`EMR_RECORD_MASTER`，按 `REGISTER_ID`（就诊流水号）和
  `MASTER_TYPE`（D 医生 / N 护理）维护病历主状态。
- 关键状态字段：
    - `ARCHIVE_FLAG`: 归档标志（'1' 已归档 / None 或 '0' 未归档）
    - `SEQUESTRATION_FLAG`: 封存标志（'1' 已封存 / '0' 已解封 / None 未封存）
    - `MEDICAL_BURROW_FLAG`: 病历调阅标志（'0' 未借阅 / '1' 已借阅）

断言原则：
  ① 只读探测：严禁调用 archive / seal / unseal / borrow 等变更接口，保持生产/测试库零污染。
  ② 防空跑：先查 Oracle `EMR_RECORD_MASTER`，若无归档/封存/调阅样本，则置「未执行」；
  ③ 双向等式断言：调用 EMR 真实读接口 `/emr/recordMaster/queryPage`，
     断言其返回的 `archiveFlag`、`sequestrationFlag`、`medicalBurrowFlag`
     与库中 `ARCHIVE_FLAG`、`SEQUESTRATION_FLAG`、`MEDICAL_BURROW_FLAG` 逐字段严格相等（可失败断言）。
"""

import time
from typing import Any, Dict, List
import requests
from ..closed_loop import Ctx, LoopResult, _oracle_conn

EMR_BASE = "http://192.168.1.198:8021"


class _EmrClient:
    """EMR 客户端（避免与 l5_emr 循环导入）。"""
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


def flow_L5_028(ctx: Ctx) -> LoopResult:
    requires_rules = []
    res = LoopResult(case_id="L5-028", title="病历归档与调阅授权")
    t0 = time.time()
    try:
        # 1. 从 Oracle 提取具备真实流转状态的病案主记录样本（只读）
        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT master_id, register_id, master_type,
                   archive_flag, sequestration_flag, medical_burrow_flag,
                   TO_CHAR(archive_time, 'YYYY-MM-DD HH24:MI:SS'),
                   TO_CHAR(sequestration_time, 'YYYY-MM-DD HH24:MI:SS')
            FROM emr_record_master
            WHERE archive_flag IS NOT NULL
               OR sequestration_flag IS NOT NULL
               OR medical_burrow_flag IS NOT NULL
            ORDER BY register_id DESC, master_type ASC
        """)
        db_rows = cur.fetchall()
        conn.close()

        # 2. 防空跑门禁：样本不足时返回「未执行」，绝不误判「通过」
        if not db_rows:
            res.status = "未执行"
            res.note = "EMR_RECORD_MASTER 库中无归档、封存或调阅状态记录，缺少真实流转样本"
            res.evidence = {"防空跑观测": {"主记录流转样本数": 0}}
            return res

        # 按就诊号分组组织基准数据
        reg_map: Dict[str, List[Dict[str, Any]]] = {}
        for mid, rid, mtype, a_flag, s_flag, b_flag, a_time, s_time in db_rows:
            reg_map.setdefault(str(rid), []).append({
                "master_id": str(mid),
                "master_type": mtype,
                "archive_flag": str(a_flag) if a_flag is not None else None,
                "sequestration_flag": str(s_flag) if s_flag is not None else None,
                "medical_burrow_flag": str(b_flag) if b_flag is not None else None,
                "archive_time": a_time,
                "sequestration_time": s_time,
            })

        emr = _EmrClient(ctx.token)
        bad: List[str] = []
        detail: List[Dict[str, Any]] = []

        total_checked_records = 0
        archived_count = 0
        sealed_count = 0
        burrow_count = 0

        # 3. 逐个就诊调用 EMR 真实只读分页接口比对
        for rid, db_masters in reg_map.items():
            resp = emr.post("/emr/recordMaster/queryPage", {
                "registerId": rid,
                "pageNum": 1,
                "pageSize": 10,
            })

            if resp.get("code") != 200:
                bad.append(f"就诊 {rid} 查询病案主记录接口失败: {resp.get('msg')}")
                continue

            api_items = resp.get("data") or []
            if not isinstance(api_items, list) or not api_items:
                bad.append(f"就诊 {rid} 接口返回为空，但库中存在 {len(db_masters)} 条主记录")
                continue

            api_by_type = {it.get("masterType"): it for it in api_items if isinstance(it, dict)}

            for db_m in db_masters:
                mtype = db_m["master_type"]
                type_label = "医生病历" if mtype == "D" else ("护理病历" if mtype == "N" else f"类型{mtype}")
                api_m = api_by_type.get(mtype)

                if not api_m:
                    bad.append(f"就诊 {rid} {type_label} 主记录在接口中缺失")
                    continue

                total_checked_records += 1

                # 归一化字段值进行双向严格等式断言
                api_a = str(api_m.get("archiveFlag")) if api_m.get("archiveFlag") is not None else None
                api_s = str(api_m.get("sequestrationFlag")) if api_m.get("sequestrationFlag") is not None else None
                api_b = str(api_m.get("medicalBurrowFlag")) if api_m.get("medicalBurrowFlag") is not None else None

                db_a = db_m["archive_flag"]
                db_s = db_m["sequestration_flag"]
                db_b = db_m["medical_burrow_flag"]

                # ① 归档状态等式断言
                if api_a != db_a:
                    bad.append(f"就诊 {rid} {type_label} 归档状态不一致: 接口={api_a} ≠ 库={db_a}")
                elif db_a == "1":
                    archived_count += 1

                # ② 封存状态等式断言
                if api_s != db_s:
                    bad.append(f"就诊 {rid} {type_label} 封存状态不一致: 接口={api_s} ≠ 库={db_s}")
                elif db_s == "1":
                    sealed_count += 1

                # ③ 调阅状态等式断言
                if api_b != db_b:
                    bad.append(f"就诊 {rid} {type_label} 调阅状态不一致: 接口={api_b} ≠ 库={db_b}")
                elif db_b == "0":
                    burrow_count += 1

                detail.append({
                    "registerId": rid,
                    "masterType": mtype,
                    "typeLabel": type_label,
                    "archiveFlag": {"api": api_a, "db": db_a, "match": api_a == db_a},
                    "sequestrationFlag": {"api": api_s, "db": db_s, "match": api_s == db_s},
                    "medicalBurrowFlag": {"api": api_b, "db": db_b, "match": api_b == db_b},
                })

        ev = {
            "防空跑观测": {
                "主记录流转样本数": len(db_rows),
                "比对就诊数": len(reg_map),
                "命中已归档数": archived_count,
                "命中已封存数": sealed_count,
            },
            "比对就诊数": len(reg_map),
            "比对主记录数": total_checked_records,
            "命中已归档(1)记录数": archived_count,
            "命中已封存(1)记录数": sealed_count,
            "命中调阅标记(0)记录数": burrow_count,
            "核对明细": detail,
            "问题清单": bad,
        }

        # 4. 判定是否有足够业务深度的样本被真实校验
        # ⚠️ 修正（zjck-21）：**覆盖不足 ≠ 系统缺陷**。样本里没有"已归档/已封存"的记录，
        #    说明的是"本轮没验到那个状态"，应当报「未执行」并说明，**不能报「失败」** ——
        #    否则样本一变就会造出一个假缺陷。（原实现把它 append 进 bad → 失败。）
        if not bad and (archived_count < 1 or sealed_count < 1):
            ev["覆盖不足"] = {"已归档样本数": archived_count, "已封存样本数": sealed_count}
            res.status = "未执行"
            res.note = (f"库中带流转状态的主记录共 {len(reg_map)} 名就诊 / {total_checked_records} 条，"
                        f"但样本未同时覆盖「已归档(1)」与「已封存(1)」两种状态"
                        f"（已归档 {archived_count} 条、已封存 {sealed_count} 条）——"
                        f"覆盖不足，不足以核对完整的归档/封存链路")
            res.evidence = ev
            return res

        if bad:
            res.status = "失败"
            res.note = "病历归档与调阅状态一致性不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (
            f"已对 {len(reg_map)} 名就诊的 {total_checked_records} 条医生/护理病案主记录完成双向对账；"
            f"接口读取的归档状态（已归档 {archived_count} 条）、"
            f"封存状态（已封存 {sealed_count} 条）、"
            f"调阅标志（未调阅 {burrow_count} 条）与 Oracle EMR_RECORD_MASTER 库值 100% 严格一致"
        )
        res.evidence = ev

    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


flow_L5_028.requires_rules = []

FLOWS = {
    "L5-028": flow_L5_028,
}


FLOW_RULES = {
    "L5-028": flow_L5_028.requires_rules,
}
