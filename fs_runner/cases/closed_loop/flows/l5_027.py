# -*- coding: utf-8 -*-
"""
L5-027 病历封存与解封（真实闭环与缺陷复现）

业务说明：
- 病历封存（seal）：医患纠纷或特定法律要求下，对终末病历执行封存，锁定病历并阻断篡改。
- 病历解封（unseal）：经授权后对封存病历解除封存状态。
- 目标选定：测试患者 就诊 549（测试0222），master_id = '2099829419513024513'。
  （严禁触碰 321 这一全库唯一历史已封存记录，严禁用 289）。

闭环与断言逻辑：
1. 前置防空跑校验：查 Oracle EMR_RECORD_MASTER 确认 549 记录存在且当前未处于封存态（SEQUESTRATION_FLAG IS NULL 或 '0'）；
   同时获取底层列定义（EMR_RECORD_MASTER 与 EMR_RECORD_MASTER_LOG）；
2. 发起真实封存调用：POST /emr/recordMaster/seal；
3. 分支判定：
   - 若返回 code=200（未来缺陷修复后）：
     立即调用 POST /emr/recordMaster/unseal 进行净零解封还原，并回读数据库确认 SEQUESTRATION_FLAG 恢复为 '0'，判「通过」；
   - 若返回 code=400 且提示 ORA-12899 / PATIENT_TYPE（当前真实缺陷）：
     如实判「失败」，note 注入缺陷根因分析，evidence 记录完整请求、响应报文及表结构定义；
   - 若返回其他错误，判「失败」并记录原始报错。
"""

import time
from typing import Any, Dict

import requests

from ..closed_loop import Ctx, LoopResult, _oracle_conn

EMR_BASE = "http://192.168.1.198:8021"

# 目标测试患者：固定为就诊 549（测试0222），绝对禁止触碰 321 / 289
TARGET_REGISTER_ID = "549"
TARGET_MASTER_ID = "2099829419513024513"
TARGET_PATIENT_TYPE = "I"


class _EmrClient:
    """EMR 客户端（复用 HIS JWT 令牌）。"""
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
            return {"code": -1, "msg": f"{type(e).__name__}: {e}"[:180]}


def flow_L5_027(ctx: Ctx) -> LoopResult:
    """病历封存与解封：EMR 主记录封存状态流转与历史日志核验（已知缺陷 L5-027 承载用例）。"""
    res = LoopResult(case_id="L5-027", title="病历封存与解封")
    t0 = time.time()
    try:
        # 1. 前置数据库检查：防空跑与表结构证据收集
        conn = _oracle_conn()
        cur = conn.cursor()

        # 查测试记录当前状态
        cur.execute("""
            SELECT master_id, register_id, master_type, sequestration_flag, patient_type
            FROM emr_record_master
            WHERE master_id = :1 AND register_id = :2
        """, [TARGET_MASTER_ID, TARGET_REGISTER_ID])
        target_row = cur.fetchone()

        if not target_row:
            conn.close()
            res.status = "未执行"
            res.note = f"防空跑拦截：测试患者就诊 {TARGET_REGISTER_ID} (masterId={TARGET_MASTER_ID}) 在 EMR_RECORD_MASTER 中不存在"
            return res

        curr_master_id, curr_reg_id, curr_mtype, curr_seq_flag, curr_ptype = target_row
        if curr_seq_flag == "1":
            conn.close()
            res.status = "未执行"
            res.note = f"防污染拦截：测试记录 {TARGET_MASTER_ID} 当前已被封存(flag=1)，不能用于封存测试"
            return res

        # 提取字段长度定义作为底层证据
        cur.execute("""
            SELECT table_name, column_name, data_type, data_length, char_length 
            FROM user_tab_columns 
            WHERE table_name IN ('EMR_RECORD_MASTER', 'EMR_RECORD_MASTER_LOG') 
              AND column_name = 'PATIENT_TYPE'
            ORDER BY table_name ASC
        """)
        col_defs = {
            r[0]: {
                "column": r[1],
                "dataType": r[2],
                "dataLength": r[3],
                "charLength": r[4]
            }
            for r in cur.fetchall()
        }
        conn.close()

        # 2. 调用真实封存接口
        emr = _EmrClient(ctx.token)
        seal_payload = {
            "masterList": [
                {
                    "masterId": TARGET_MASTER_ID,
                    "patientType": TARGET_PATIENT_TYPE,
                    "registerId": TARGET_REGISTER_ID,
                }
            ]
        }

        seal_resp = emr.post("/emr/recordMaster/seal", seal_payload)
        resp_code = seal_resp.get("code")
        resp_msg = str(seal_resp.get("msg") or "")

        ev = {
            "测试目标": {
                "registerId": TARGET_REGISTER_ID,
                "masterId": TARGET_MASTER_ID,
                "patientType": TARGET_PATIENT_TYPE,
                "masterType": curr_mtype,
                "initialSequestrationFlag": curr_seq_flag,
            },
            "封存请求": {
                "url": "POST /emr/recordMaster/seal",
                "payload": seal_payload,
            },
            "封存响应": {
                "code": resp_code,
                "msg": resp_msg,
            },
            "底层数据库字段定义证据": col_defs,
        }

        # 3. 分支判定
        # 分支 A：命中已知系统缺陷（当前真实生产与测试环境状态）
        if resp_code == 400 and ("ORA-12899" in resp_msg or "PATIENT_TYPE" in resp_msg):
            res.status = "失败"
            res.note = (
                "[系统缺陷] 封存接口报错 ORA-12899: 列 EMR_RECORD_MASTER_LOG.PATIENT_TYPE 长度为 CHAR(1)，"
                "但主表 PATIENT_TYPE 为 CHAR(2)（'I '），后端未 trim 导致写入日志超长；全院病历封存功能阻断"
            )
            ev["缺陷定性"] = {
                "缺陷级别": "P0/P1",
                "影响范围": "全院任何病历（门诊/住院）封存均无法完成，直接阻断医疗纠纷病案封存法律合规流程",
                "根因分析": (
                    "EMR_RECORD_MASTER.PATIENT_TYPE 定义为 CHAR(2)（定长存入 'I ' 带尾随空格），"
                    "而日志审计表 EMR_RECORD_MASTER_LOG.PATIENT_TYPE 仅定义为 CHAR(1)。"
                    "后端服务在 EmrRecordMasterLogMapper 执行 INSERT 时直接搬运主表字段且未做 trim()，"
                    "触发 Oracle ORA-12899 字段值超长异常。"
                ),
            }
            res.evidence = ev
            return res

        # 分支 B：未来缺陷修复后接口返回成功（净零自愈链路）
        if resp_code == 200:
            # 查库核实是否成功置为 '1'
            conn = _oracle_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT sequestration_flag FROM emr_record_master WHERE master_id = :1
            """, [TARGET_MASTER_ID])
            flag_after_seal = cur.fetchone()[0]

            # 立即调用解封接口实施净零还原
            unseal_resp = emr.post("/emr/recordMaster/unseal", seal_payload)
            cur.execute("""
                SELECT sequestration_flag FROM emr_record_master WHERE master_id = :1
            """, [TARGET_MASTER_ID])
            flag_after_unseal = cur.fetchone()[0]
            conn.close()

            ev["净零解封还原"] = {
                "封存后库值": flag_after_seal,
                "解封响应": unseal_resp,
                "解封后库值": flag_after_unseal,
            }

            if flag_after_seal == "1" and flag_after_unseal in ("0", None):
                res.status = "通过"
                res.note = (
                    f"病历封存与解封闭环执行成功：就诊 {TARGET_REGISTER_ID} 封存接口成功置 flag='1'，"
                    f"随后净零解封成功恢复 flag='{flag_after_unseal}'"
                )
                res.evidence = ev
                return res
            else:
                res.status = "失败"
                res.note = f"封存与解封状态流转不符合预期：封存后={flag_after_seal}，解封后={flag_after_unseal}"
                res.evidence = ev
                return res

        # 分支 C：其他异常响应
        res.status = "失败"
        res.note = f"封存接口调用异常: code={resp_code}, msg={resp_msg[:160]}"
        res.evidence = ev

    except Exception as e:
        res.status = "失败"
        res.note = f"执行异常: {type(e).__name__}: {str(e)[:180]}"
    finally:
        res.duration_ms = round((time.time() - t0) * 1000, 1)

    return res


flow_L5_027.requires_rules = ['CONV_CHAR_PAD_SPACE_OVERFLOW']

FLOWS = {
    "L5-027": flow_L5_027,
}


FLOW_RULES = {
    "L5-027": flow_L5_027.requires_rules,
}
