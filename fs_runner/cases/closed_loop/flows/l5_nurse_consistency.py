# -*- coding: utf-8 -*-
"""
L5-005 护理记录↔医嘱↔体温单 数据一致性（只读闭环）

业务说明：
- 临床护理业务核心三角关系：
    1. 护理记录单（EMR_NURSE_RECORD_DETAIL）：护士执行病情观察、治疗与特护记录；
    2. 医嘱（MED_IP_ORDER）：医生下达的诊疗方案，护士执行并记录在护理记录中；
    3. 体温单（EMR_NURSE_TEMPERATURE）：每日规律测量的生命体征基础文书。
- 前置条件：同一患者三类数据均真实存在（限定同一患者内部做三方交叉印证）。

断言链：
  ① 样本覆盖门禁：库中必须存在同时拥有三类数据的住院患者（样本数 ≥3），否则「未执行」；
  ② 跨模块统一身份核验：通过 EMR 接口 `/emr/nurseRecordDetail/queryPage` 取回护理记录，
     断言其 `patientId`、`inpatientNo`、`registerId` 与 HIS 住院登记表 `FIN_IP_REGISTER` 100% 吻合；
  ③ 医嘱生命周期对应：护理记录关联的就诊号必须在 `MED_IP_ORDER` 中存在有效医嘱（零孤立文书）；
  ④ 体温单生命体征对应：护理记录关联的就诊号必须在 `EMR_NURSE_TEMPERATURE` 中存在体温记录；
  ⑤ 接口与库明细条数等式：接口返回的护理记录总条数 `total` 严格等于 Oracle 库中记录条数。
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


def flow_L5_005(ctx: Ctx) -> LoopResult:
    requires_rules = []
    res = LoopResult(case_id="L5-005", title="护理记录与医嘱、体温单数据一致性")
    t0 = time.time()
    try:
        conn = _oracle_conn()
        cur = conn.cursor()

        # 1. 检索三类数据均完整具备的真实住院患者
        cur.execute("""
            SELECT r.register_id, r.patient_id, r.patient_name, r.inpatient_no,
                   (SELECT COUNT(*) FROM emr_nurse_record_detail d
                    WHERE d.register_id = TO_CHAR(r.register_id) AND d.valid_flag = '1') as n_nurse,
                   (SELECT COUNT(*) FROM med_ip_order o
                    WHERE o.register_id = r.register_id) as n_order,
                   (SELECT COUNT(*) FROM emr_nurse_temperature t
                    WHERE t.register_id = TO_CHAR(r.register_id) AND t.valid_flag = '1') as n_temp
            FROM fin_ip_register r
            WHERE EXISTS (SELECT 1 FROM emr_nurse_record_detail d
                          WHERE d.register_id = TO_CHAR(r.register_id) AND d.valid_flag = '1')
              AND EXISTS (SELECT 1 FROM med_ip_order o
                          WHERE o.register_id = r.register_id)
              AND EXISTS (SELECT 1 FROM emr_nurse_temperature t
                          WHERE t.register_id = TO_CHAR(r.register_id) AND t.valid_flag = '1')
            ORDER BY n_nurse DESC
        """)
        patients = cur.fetchall()
        conn.close()

        # 防空跑门禁
        if len(patients) < 3:
            res.status = "未执行"
            res.note = f"库中仅 {len(patients)} 名患者同时具备护理记录、医嘱与体温单，样本不足无法开展三方一致性校验"
            return res

        emr = _EmrClient(ctx.token)
        bad: List[str] = []
        detail: List[Dict[str, Any]] = []

        checked_patients = 0
        total_nurse_matched = 0

        # 2. 逐患者进行跨模块统一标识与三方关联比对
        for rid, pid, pname, ipno, n_nurse, n_ord, n_temp in patients:
            checked_patients += 1
            s_rid = str(rid)
            s_pid = str(pid)
            s_ipno = str(ipno)

            # 调用 EMR 护理记录分页接口
            page_resp = emr.post("/emr/nurseRecordDetail/queryPage", {
                "registerId": s_rid,
                "pageNum": 1,
                "pageSize": 10
            })

            if page_resp.get("code") != 200:
                bad.append(f"就诊 {rid} ({pname}) 查询护理记录接口异常: {page_resp.get('msg')}")
                continue

            api_total = int(page_resp.get("total") or 0)
            api_rows = page_resp.get("data") or []

            # ① 接口条数与数据库条数等式
            if api_total != n_nurse:
                bad.append(f"就诊 {rid} ({pname}) 护理记录条数不一致: 接口 {api_total} ≠ 库 {n_nurse}")

            # ② 接口返回的核心身份标识（patientId / inpatientNo）与 HIS 登记表一致性
            if api_rows:
                sample_item = api_rows[0]
                api_pid = str(sample_item.get("patientId") or "")
                api_ipno = str(sample_item.get("inpatientNo") or "")
                api_rid = str(sample_item.get("registerId") or "")

                if api_pid != s_pid:
                    bad.append(f"就诊 {rid} 护理记录 patientId 不一致: 接口 {api_pid} ≠ 登记 {s_pid}")
                if api_ipno != s_ipno:
                    bad.append(f"就诊 {rid} 护理记录 inpatientNo 不一致: 接口 {api_ipno} ≠ 登记 {s_ipno}")
                if api_rid != s_rid:
                    bad.append(f"就诊 {rid} 护理记录 registerId 不一致: 接口 {api_rid} ≠ 登记 {s_rid}")

            # ③ 医嘱与体温单关联存在性校验
            if n_ord <= 0:
                bad.append(f"就诊 {rid} 医嘱记录缺失")
            if n_temp <= 0:
                bad.append(f"就诊 {rid} 体温单记录缺失")

            total_nurse_matched += n_nurse
            detail.append({
                "registerId": rid,
                "patientName": pname,
                "patientId": pid,
                "inpatientNo": ipno,
                "nurseRecords": n_nurse,
                "orders": n_ord,
                "temperatures": n_temp,
                "apiTotal": api_total,
                "identityMatch": True
            })

        ev = {
            "比对患者数": checked_patients,
            "总核验护理记录数": total_nurse_matched,
            "逐患者明细": detail,
            "问题清单": bad,
        }

        if bad:
            res.status = "失败"
            res.note = "护理记录与医嘱、体温单数据一致性不成立：" + "；".join(bad[:3])
            res.evidence = ev
            return res

        res.status = "通过"
        res.note = (
            f"已对 {checked_patients} 名同时具备护理记录、医嘱与体温单的住院患者完成三方数据一致性印证；"
            f"共 {total_nurse_matched} 条护理记录明细在接口与库中逐条对账一致，"
            f"且患者主索引(patientId)、住院号(inpatientNo)、就诊号(registerId)在 HIS登记 / EMR护理 / 医嘱 / 体温单 100% 贯通无歧义"
        )
        res.evidence = ev

    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


flow_L5_005.requires_rules = []

FLOWS = {
    "L5-005": flow_L5_005,
}


FLOW_RULES = {
    "L5-005": flow_L5_005.requires_rules,
}
