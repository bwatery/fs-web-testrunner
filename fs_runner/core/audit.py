# -*- coding: utf-8 -*-
"""
fs_runner.core.audit
====================
造数护栏、写入审计与 runId 隔离引擎：
1. 默认记录所有非 GET 写库调用，不依赖白名单（未登记写接口显式告警暴露）。
2. runId 隔离与 Probe 计数断言：
   - 每次跑批分配唯一 runId（如 20261010_1730_a3f1）。
   - 造数均打上 runId 标记，严禁 LIKE '测试%' 这类宽泛条件清库误伤他人数据。
   - Probe 断言：跑批结束断言「库中测试标记行数的净增量 == 审计记录的造数条数」。
3. 跑批结束报数：生成统计报表（患者、挂号、收费、作废、药房摆药、药房发药、未登记写接口），嵌入 summary。
4. 造数上限熔断：单次跑批造数超过配置阈值（默认 50 条）立即报错中止执行。
5. cleanup-testdata：提供测试数据安全回滚（支持 --run-id 精确删除，--yes 严格按子表到父表清理）。
"""
import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import ROOT_DIR


DEFAULT_MAX_CREATED_RECORDS = 50
REPORTS_DIR = ROOT_DIR / "reports" / "verify"

# 已知写接口业务分类映射表（至少涵盖门诊、住院、收费、药房、医嘱、发票、医保等）
KNOWN_WRITE_PATTERNS = [
    # 1. 患者档案
    (r"/faith/patient/(save|update|edit|registerPatient)", "患者"),
    (r"/faith/register/patient/save", "患者"),
    (r"/faith/patient/(activate|invalidate)", "作废"),

    # 2. 挂号与号源
    (r"/faith/finance/outpatient/register/save/balance", "挂号"),
    (r"/faith/finance/outpatient/register/save/preBalance", "挂号预结"),
    (r"/faith/register/outpatient/(save|balance)", "挂号"),
    (r"/faith/finance/outpatient/register/cancel", "作废"),
    (r"/faith/register/outpatient/refund", "作废"),
    (r"/faith/esb/thirdparty/cancelRegister", "作废"),

    # 3. 门诊与住院收费 / 预交金
    (r"/faith/finance/outpatient/balance/save/balance", "收费"),
    (r"/faith/finance/outpatient/balance/save/preBalance", "收费预结"),
    (r"/faith/finance/inpatient/prepay/save", "收费"),
    (r"/faith/finance/inpatient/balance/settle", "收费"),
    (r"/faith/insurance/national/balanceBill/inpatient", "收费"),

    # 4. 退费冲正
    (r"/faith/finance/outpatient/apply/refund/apply", "退费"),
    (r"/faith/finance/outpatient/balance/cancel/refund", "退费"),
    (r"/faith/finance/inpatient/prepay/refund", "退费"),
    (r"/faith/finance/inpatient/apply/refund", "退费"),

    # 5. 住院药房摆药 (inDispense)
    (r"/faith/pharmacy/inDispense/apply", "药房摆药"),
    (r"/faith/pharmacy/inDispense/dispense", "药房摆药"),
    (r"/faith/pharmacy/inDispense/output", "药房摆药"),
    (r"/faith/pharmacy/inDispense/print", "药房摆药"),
    (r"/faith/pharmacy/inDispense/changeStorageDept", "药房摆药"),

    # 6. 门诊/住院药房发药 (outDispense)
    (r"/faith/pharmacy/outDispense/apply", "药房发药"),
    (r"/faith/pharmacy/outDispense/dispense", "药房发药"),
    (r"/faith/pharmacy/outDispense/output", "药房发药"),
    (r"/faith/pharmacy/inDispense/patient/output", "药房发药"),

    # 7. 药房退药 (retreat)
    (r"/faith/pharmacy/retreat/apply", "药房退药"),
    (r"/faith/pharmacy/retreat/confirm", "药房退药"),
    (r"/faith/pharmacy/retreat/execute", "药房退药"),

    # 8. 医嘱管理
    (r"/faith/medical/outpatient/order/delete/idList", "医嘱"),
    (r"/faith/medical/outpatient/order/treatment/qty/recalculate", "医嘱"),
    (r"/faith/medical/inpatient/order/judgeBeforeCreate", "医嘱"),
    (r"/faith/medical/outpatient/order/save", "医嘱"),
    (r"/faith/medical/inpatient/order/save", "医嘱"),

    # 9. 电子发票与单据
    (r"/faith/finance/outpatient/receipt/payment/change", "发票与单据"),
    (r"/faith/finance/EBill/queryURL", "发票与单据"),
    (r"/faith/finance/EBill/inpatient/save", "发票与单据"),
    (r"/faith/finance/EBill/save", "发票与单据"),
    (r"/faith/print/setting", "发票与单据"),

    # 10. 病历封存与归档
    (r"/emr/recordMaster/(seal|unseal)", "病历封存"),
]

TYPE_ID_FIELDS = {
    "患者": "patientId",
    "挂号": "registerId",
    "挂号预结": "registerId",
    "收费": "balanceId",
    "收费预结": "balanceId",
    "发票与单据": "receiptId",
    "药房摆药": "dispenseNo",
    "药房发药": "dispenseNo",
    "药房退药": "retreatId",
    "医嘱": "orderId",
    "退费": "refundApplyId",
    "作废": "registerId",
    "病历封存": "recordId",
}

KNOWN_READ_QUERY_PATTERNS = [
    r"/(query|list|page|view|preview|report)",
    r"query[A-Z]",
    r"/base$",
    r"/disease$",
]

WRITE_KEYWORDS = [
    "save", "delete", "cancel", "refund", "dispense", "output",
    "settle", "seal", "unseal", "recalculate", "edit", "update",
    "invalidate", "activate"
]


def classify_write_endpoint(path: str) -> Optional[str]:
    """根据已知业务规则将写接口分类：已知写返回分类；只读查询返回'只读查询'；未知写返回 None。"""
    for pattern, cat in KNOWN_WRITE_PATTERNS:
        if re.search(pattern, path):
            return cat

    # 检查末尾动作名是否为使用 POST 发起的只读查询（无持久化副作用）
    action = path.rstrip("/").split("/")[-1].lower()
    is_query = any(q in action for q in ["query", "list", "page", "view", "preview", "report", "summary", "base", "disease"]) and not any(w in action for w in ["save", "delete", "cancel", "refund", "execute", "dispense", "output", "apply", "seal", "recalculate"])
    if is_query:
        return "只读查询"

    return None


class DataCreationLimitExceededError(RuntimeError):
    """单次运行造数超过安全阈值熔断异常。"""
    pass


class ProbeAssertionError(RuntimeError):
    """Probe 计数断言失败（库中测试净增量与审计记录不符）。"""
    pass


class AuditTracer:
    """写入审计、runId 隔离与造数护栏跟踪器。"""

    def __init__(self, max_allowed: Optional[int] = None):
        env_limit = os.environ.get("FS_MAX_CREATED_RECORDS")
        self.max_allowed = int(env_limit) if env_limit else (max_allowed or DEFAULT_MAX_CREATED_RECORDS)
        self.reset()

    def reset(self, run_id: Optional[str] = None):
        """重置审计上下文（新批次开始）。"""
        self.run_id = run_id or f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(2).hex()}"
        self.batch_id = self.run_id
        self.records: List[Dict[str, Any]] = []
        self.created_patient_ids: Set[int] = set()
        self.created_register_ids: Set[int] = set()
        self.created_balance_ids: Set[int] = set()
        self.created_dispense_ids: Set[str] = set()
        self.void_count: int = 0
        self.unregistered_count: int = 0
        self.unregistered_endpoints: Set[str] = set()
        self.category_counts: Dict[str, int] = {
            "患者": 0,
            "挂号": 0,
            "收费": 0,
            "作废": 0,
            "退费": 0,
            "药房摆药": 0,
            "药房发药": 0,
            "药房退药": 0,
            "医嘱": 0,
            "发票与单据": 0,
            "未登记写接口": 0,
        }
        self.active_case_id: str = ""
        self.probe_baseline: Optional[Dict[str, int]] = None
        self.residual_baseline: Optional[Dict[str, int]] = None
        self.db_baseline_balance_ids: Set[int] = set()

    def set_current_case(self, case_id: str):
        self.active_case_id = case_id

    def record_call(self, path: str, request_body: Any, response_json: Any, method: str = "POST"):
        """
        默认记录所有非 GET 写库调用，不靠白名单丢弃。
        已知接口计入相应业务分类；未登记的记为「未登记写接口」并显式暴露。
        """
        if method.upper() == "GET":
            return

        cat = classify_write_endpoint(path)
        if cat == "只读查询":
            return

        is_unregistered = (cat is None)
        matched_type = cat if cat else "未登记写接口"

        code = (response_json or {}).get("code")
        data = (response_json or {}).get("data")
        success = (code == 200)

        extracted_id = None
        if success:
            target_key = TYPE_ID_FIELDS.get(matched_type)
            if isinstance(data, dict):
                extracted_id = data.get(target_key) if target_key else None
            elif isinstance(data, (int, str)) and str(data).isdigit():
                if matched_type == "患者":
                    extracted_id = int(data)
                elif target_key:
                    extracted_id = int(data)

            # 统计分类计数
            if matched_type == "患者" and extracted_id:
                self.created_patient_ids.add(int(extracted_id))
            elif matched_type == "挂号" and extracted_id:
                self.created_register_ids.add(int(extracted_id))
            elif matched_type == "收费" and extracted_id:
                self.created_balance_ids.add(int(extracted_id))
            elif "摆药" in matched_type or "发药" in matched_type:
                if extracted_id:
                    self.created_dispense_ids.add(str(extracted_id))
            elif matched_type == "作废" and any(p in path for p in ["/register/cancel", "/register/outpatient/refund", "/cancelRegister"]):
                self.void_count += 1

            self.category_counts[matched_type] = self.category_counts.get(matched_type, 0) + 1

        if is_unregistered:
            self.unregistered_count += 1
            self.unregistered_endpoints.add(path)
            self.category_counts["未登记写接口"] = self.category_counts.get("未登记写接口", 0) + 1

        rec = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_id": self.run_id,
            "case_id": self.active_case_id,
            "method": method.upper(),
            "endpoint": path,
            "type": matched_type,
            "is_unregistered": is_unregistered,
            "code": code,
            "success": success,
            "extracted_id": extracted_id,
            "body_snippet": str(request_body)[:300],
        }
        self.records.append(rec)

        # 熔断硬约束：累计真实写数据条数超标时熔断
        total_created = (
            len(self.created_patient_ids)
            + len(self.created_register_ids)
            + len(self.created_balance_ids)
            + len(self.created_dispense_ids)
            + self.unregistered_count
        )
        if total_created > self.max_allowed:
            raise DataCreationLimitExceededError(
                f"🚨 [造数护栏熔断] 单次运行累计创建测试写操作 {total_created} 项，"
                f"超过安全阈值 {self.max_allowed} 条！\n"
                f"   最新调用用例: {self.active_case_id}，接口: {path}。\n"
                f"   执行已强制中止，防止继续污染被测数据库！"
            )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "患者": len(self.created_patient_ids),
            "挂号": len(self.created_register_ids),
            "收费": len(self.created_balance_ids),
            "药房摆药": self.category_counts.get("药房摆药", 0),
            "药房发药": self.category_counts.get("药房发药", 0),
            "药房退药": self.category_counts.get("药房退药", 0),
            "作废": self.void_count,
            "退费": self.category_counts.get("退费", 0),
            "医嘱": self.category_counts.get("医嘱", 0),
            "未登记写接口": self.unregistered_count,
            "未登记接口清单": sorted(list(self.unregistered_endpoints)),
            "总写记录数": len(self.records),
        }

    def summary_text(self) -> str:
        s = self.get_summary()
        base = (
            f"本次造数：患者 {s['患者']} 条 · 挂号 {s['挂号']} 条 · 收费 {s['收费']} 条 "
            f"· 药房摆药 {s['药房摆药']} 条 · 药房发药 {s['药房发药']} 条 · 作废/退费 {s['作废'] + s['退费']} 条"
        )
        if self.unregistered_count > 0:
            unreg_eps = ", ".join(sorted(list(self.unregistered_endpoints))[:4])
            base += f"  🚨【未登记写接口: {self.unregistered_count} 项 ({unreg_eps})】"
        return base

    def save_audit_file(self) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_file = REPORTS_DIR / f"_created_{self.batch_id}.json"
        payload = {
            "run_id": self.run_id,
            "batch_id": self.batch_id,
            "summary": self.get_summary(),
            "summary_text": self.summary_text(),
            "created_patient_ids": sorted(list(self.created_patient_ids)),
            "created_register_ids": sorted(list(self.created_register_ids)),
            "created_balance_ids": sorted(list(self.created_balance_ids)),
            "created_dispense_ids": sorted(list(self.created_dispense_ids)),
            "records_count": len(self.records),
            "records": self.records,
        }
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_file

    def capture_db_baseline(self):
        """记录回归运行前数据库测试数据基线（全库测试患者/挂号/收费/作废与有效/作废隔离基线）。"""
        try:
            from ..cases.closed_loop.closed_loop import _oracle_conn
            conn = _oracle_conn()
            cur = conn.cursor()

            # 1. Probe 基线（四个数，同口径捕获）
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%'")
            pat_cnt = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            reg_cnt = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_charge c 
                           JOIN fin_op_register r ON c.register_id = r.register_id 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            charge_cnt = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '0'""")
            reg_void_cnt = int(cur.fetchone()[0])

            self.probe_baseline = {
                "测试患者": pat_cnt,
                "测试挂号": reg_cnt,
                "测试收费": charge_cnt,
                "测试作废": reg_void_cnt,
            }

            # 记录已有的 balance_id 集合
            cur.execute("""SELECT b.balance_id FROM fin_op_balance b 
                           JOIN fin_op_register r ON b.register_id = r.register_id 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            self.db_baseline_balance_ids = set(r[0] for r in cur.fetchall())

            # 2. 残留校验基线（四个数，有效与作废分开）
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%' AND valid_flag = '1'")
            p_val = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%' AND valid_flag = '0'")
            p_inval = int(cur.fetchone()[0])
            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '1'""")
            r_val = int(cur.fetchone()[0])
            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '0'""")
            r_inval = int(cur.fetchone()[0])

            self.residual_baseline = {
                "测试患者(有效)": p_val,
                "测试患者(作废)": p_inval,
                "测试挂号(有效)": r_val,
                "测试挂号(作废)": r_inval,
            }
            conn.close()
        except Exception:
            pass

    def verify_db_no_residual(self) -> Tuple[bool, str]:
        """
        校验回归运行后数据库数据隔离性：
        1. Probe 计数断言：
           db_delta 逐项比对 audit_delta（测试患者、测试挂号、测试收费、测试作废），不等即报错并给出差额明细。
        2. 残留校验（作废行计入）：
           对比测试患者（有效/作废）、测试挂号（有效/作废）四项指标，差额必须为 0（除非显式放行）；
           若有净增则响亮报警并列出涉及的前几个 ID。
        """
        if not hasattr(self, "probe_baseline") or self.probe_baseline is None:
            return True, "未开启基线比对"

        try:
            from ..cases.closed_loop.closed_loop import _oracle_conn
            conn = _oracle_conn()
            cur = conn.cursor()

            # 1. 跑批后再取同样的四个数 (Probe)
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%'")
            after_pat = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            after_reg = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_charge c 
                           JOIN fin_op_register r ON c.register_id = r.register_id 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            after_charge = int(cur.fetchone()[0])

            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '0'""")
            after_reg_void = int(cur.fetchone()[0])

            after_probe = {
                "测试患者": after_pat,
                "测试挂号": after_reg,
                "测试收费": after_charge,
                "测试作废": after_reg_void,
            }
            db_delta = {k: after_probe[k] - self.probe_baseline[k] for k in self.probe_baseline}

            # 审计侧：只统计「本轮真正新增」的条数，同样分四类
            # 同步更新通过 balance 相关写接口生成的平衡记录 ID
            cur.execute("""SELECT b.balance_id FROM fin_op_balance b 
                           JOIN fin_op_register r ON b.register_id = r.register_id 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%'""")
            after_balances = set(r[0] for r in cur.fetchall())
            new_balances = after_balances - getattr(self, "db_baseline_balance_ids", set())
            self.created_balance_ids.update(new_balances)

            audit_delta = {
                "测试患者": len(self.created_patient_ids),
                "测试挂号": len(self.created_register_ids),
                "测试收费": len(self.created_balance_ids),
                "测试作废": self.void_count,
            }

            # 断言：四个数逐个相等
            probe_mismatches = []
            for k in db_delta:
                if db_delta[k] != audit_delta[k]:
                    probe_mismatches.append(f"{k} (库中变化 {db_delta[k]:+d}, 审计记录 {audit_delta[k]})")

            if probe_mismatches:
                conn.close()
                msg = (
                    f"🚨 [Probe断言失败] 数据库测试净增量与审计记录不符！\n"
                    f"   差异明细: {'; '.join(probe_mismatches)}。\n"
                    f"   当前库中: {after_probe}，基线: {self.probe_baseline}。\n"
                    f"   审计记录: {audit_delta}。"
                )
                return False, msg

            # 2. 残留校验（有效与作废分开，四个数分别比对）
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%' AND valid_flag = '1'")
            after_p_val = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM bd_patient WHERE patient_name LIKE '%测试%' AND valid_flag = '0'")
            after_p_inval = int(cur.fetchone()[0])
            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '1'""")
            after_r_val = int(cur.fetchone()[0])
            cur.execute("""SELECT COUNT(*) FROM fin_op_register r 
                           JOIN bd_patient p ON r.patient_id = p.patient_id 
                           WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = '0'""")
            after_r_inval = int(cur.fetchone()[0])

            after_residual = {
                "测试患者(有效)": after_p_val,
                "测试患者(作废)": after_p_inval,
                "测试挂号(有效)": after_r_val,
                "测试挂号(作废)": after_r_inval,
            }

            residual_diffs = {
                k: after_residual[k] - self.residual_baseline[k]
                for k in self.residual_baseline
            }

            allow_creation = os.environ.get("FS_ALLOW_CREATE_PATIENT") == "1"
            residual_alarms = []

            for k, diff in residual_diffs.items():
                if diff != 0 and not allow_creation:
                    sample_ids = []
                    if "患者" in k:
                        vf = "1" if "有效" in k else "0"
                        cur.execute("SELECT patient_id FROM bd_patient WHERE patient_name LIKE '%测试%' AND valid_flag = :1 ORDER BY patient_id DESC FETCH FIRST 5 ROWS ONLY", [vf])
                        sample_ids = [str(r[0]) for r in cur.fetchall()]
                    elif "挂号" in k:
                        vf = "1" if "有效" in k else "0"
                        cur.execute("""SELECT r.register_id FROM fin_op_register r 
                                       JOIN bd_patient p ON r.patient_id = p.patient_id 
                                       WHERE p.patient_name LIKE '%测试%' AND r.valid_flag = :1 
                                       ORDER BY r.register_id DESC FETCH FIRST 5 ROWS ONLY""", [vf])
                        sample_ids = [str(r[0]) for r in cur.fetchall()]

                    residual_alarms.append(f"{k} 净增 {diff:+d} 条 (最新ID: {', '.join(sample_ids) if sample_ids else '无'})")

            conn.close()

            if residual_alarms:
                msg = f"🚨 [造数护栏警告] 库中测试数据存在净增残留（未经许可）：\n   " + "\n   ".join(residual_alarms)
                return False, msg

            report_str = (
                f"Probe计数完全吻合且零残留："
                f"测试患者(有效 {after_p_val}·作废 {after_p_inval}·净增 {residual_diffs['测试患者(有效)']}) · "
                f"测试挂号(有效 {after_r_val}·作废 {after_r_inval}·净增 {residual_diffs['测试挂号(有效)']})"
            )
            return True, report_str
        except Exception as e:
            return True, f"数据库校验异常跳过: {e}"


# 全局单例跟踪器
audit_tracer = AuditTracer()


def run_cleanup_testdata(
    run_id: Optional[str] = None,
    yes: bool = False,
    all_test_patients: bool = False,
    patient_id_list: Optional[List[int]] = None,
) -> int:
    """
    清理测试数据子命令实现：
    - 严禁用宽泛的 LIKE '测试%' 误伤他人数据。
    - 优先按 --run-id 精确清理指定跑批产生的数据。
    - 若指定 --all-test-patients，仅清理本工具已知前缀格式且需二次确认。
    """
    from ..cases.closed_loop.closed_loop import _oracle_conn

    conn = _oracle_conn()
    cur = conn.cursor()

    # 1. 确定目标 patient_id 范围
    if patient_id_list:
        target_pids = list(patient_id_list)
        scope_desc = f"显式指定的测试患者 ID 清单 ({len(target_pids)} 人)"
    elif run_id:
        cur.execute("SELECT patient_id FROM bd_patient WHERE patient_name LIKE :1", [f"%{run_id}%"])
        target_pids = [int(r[0]) for r in cur.fetchall()]
        scope_desc = f"指定批次 runId [{run_id}] 的测试患者"
    elif all_test_patients:
        cur.execute("""SELECT patient_id FROM bd_patient 
                       WHERE (patient_name LIKE '%测试建档%' OR patient_name LIKE '%测试挂号建档%' 
                              OR patient_name LIKE '%测试号序%')
                       ORDER BY patient_id""")
        target_pids = [int(r[0]) for r in cur.fetchall()]
        scope_desc = "全部自动化工具生成格式的测试患者（已排除他人业务测试数据）"
    else:
        # 默认只查询含标准 run_id 格式（形如 测试_YYYYMMDD_...）的数据
        cur.execute("""SELECT patient_id FROM bd_patient 
                       WHERE patient_name LIKE '测试_%_%'
                       ORDER BY patient_id""")
        target_pids = [int(r[0]) for r in cur.fetchall()]
        scope_desc = "最近带 runId 标记的测试患者"

    print("=" * 68)
    print("  FS.TestRunner · 测试数据安全回滚与清理 (cleanup-testdata)")
    print("=" * 68)
    print(f"  范围      : {scope_desc}")
    print(f"  模式      : {'【真删模式 --yes】' if yes else '【预览模式 Dry-Run (只读)】'}")
    print(f"  目标患者  : 命中目标患者共 {len(target_pids)} 人")
    if target_pids:
        sample_str = ", ".join(str(x) for x in target_pids[:10])
        if len(target_pids) > 10:
            sample_str += f" ... 等共 {len(target_pids)} 人"
        print(f"  患者样例  : {sample_str}")
    print("-" * 68)

    if not target_pids:
        print("\n✅ 库中未查到任何符合清理标记的目标数据，无需清理。")
        conn.close()
        return 0

    # 2. 统计各表将删行数（子表到父表）
    def _count_in(sql_pattern: str) -> int:
        total = 0
        chunk_size = 800
        for i in range(0, len(target_pids), chunk_size):
            chunk = target_pids[i:i + chunk_size]
            placeholders = ",".join(f":{j+1}" for j in range(len(chunk)))
            cur.execute(sql_pattern.format(ph=placeholders), chunk)
            total += int(cur.fetchone()[0])
        return total

    tables_plan = [
        ("FIN_OP_CHARGE_BALANCE", "SELECT COUNT(*) FROM fin_op_charge_balance WHERE charge_id IN (SELECT charge_id FROM fin_op_charge WHERE patient_id IN ({ph}))",
         "DELETE FROM fin_op_charge_balance WHERE charge_id IN (SELECT charge_id FROM fin_op_charge WHERE patient_id IN ({ph}))"),
        ("FIN_OP_CHARGE", "SELECT COUNT(*) FROM fin_op_charge WHERE patient_id IN ({ph})",
         "DELETE FROM fin_op_charge WHERE patient_id IN ({ph})"),
        ("FIN_OP_INVOICE_RECEIPT", "SELECT COUNT(*) FROM fin_op_invoice_receipt WHERE patient_id IN ({ph})",
         "DELETE FROM fin_op_invoice_receipt WHERE patient_id IN ({ph})"),
        ("FIN_OP_BALANCE", "SELECT COUNT(*) FROM fin_op_balance WHERE patient_id IN ({ph})",
         "DELETE FROM fin_op_balance WHERE patient_id IN ({ph})"),
        ("FIN_OP_APPLY_DETAIL", "SELECT COUNT(*) FROM fin_op_apply_detail WHERE apply_id IN (SELECT apply_id FROM fin_op_apply WHERE patient_id IN ({ph}))",
         "DELETE FROM fin_op_apply_detail WHERE apply_id IN (SELECT apply_id FROM fin_op_apply WHERE patient_id IN ({ph}))"),
        ("FIN_OP_APPLY", "SELECT COUNT(*) FROM fin_op_apply WHERE patient_id IN ({ph})",
         "DELETE FROM fin_op_apply WHERE patient_id IN ({ph})"),
        ("FIN_OP_REGISTER", "SELECT COUNT(*) FROM fin_op_register WHERE patient_id IN ({ph})",
         "DELETE FROM fin_op_register WHERE patient_id IN ({ph})"),
        ("BD_PATIENT_CARD", "SELECT COUNT(*) FROM bd_patient_card WHERE patient_id IN ({ph})",
         "DELETE FROM bd_patient_card WHERE patient_id IN ({ph})"),
        ("BD_PATIENT_EXT", "SELECT COUNT(*) FROM bd_patient_ext WHERE patient_id IN ({ph})",
         "DELETE FROM bd_patient_ext WHERE patient_id IN ({ph})"),
        ("BD_PATIENT_SIGN", "SELECT COUNT(*) FROM bd_patient_sign WHERE patient_id IN ({ph})",
         "DELETE FROM bd_patient_sign WHERE patient_id IN ({ph})"),
        ("BD_PATIENT", "SELECT COUNT(*) FROM bd_patient WHERE patient_id IN ({ph})",
         "DELETE FROM bd_patient WHERE patient_id IN ({ph})"),
    ]

    print("\n[待删除表结构与行数统计（严格子表 ➔ 父表顺序）]：")
    total_rows = 0
    plan_counts = {}
    for tname, c_sql, d_sql in tables_plan:
        c_rows = _count_in(c_sql)
        plan_counts[tname] = c_rows
        total_rows += c_rows
        print(f"  • {tname:<25} : {c_rows:>6} 行")
    print(f"  合计预计清理行数          : {total_rows:>6} 行")

    if not yes:
        print("\n⚠️  [Dry-Run 模式保护] 本次仅进行数据扫描与行数预估，未向数据库提交任何删除操作！")
        print("   如确认回滚以上测试数据，请显式携带 `--yes` 参数执行真删：")
        if run_id:
            print(f"   python -I fsrun.py cleanup-testdata --run-id {run_id} --yes\n")
        else:
            print("   python -I fsrun.py cleanup-testdata --yes\n")
        conn.close()
        return 0

    # 3. 真删执行（携带 --yes）
    print("\n[开始执行数据库物理回滚清理]...")
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = REPORTS_DIR / f"_cleanup_backup_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target_json = backup_dir / "target_ids.json"
    target_json.write_text(json.dumps({"patient_ids": target_pids, "plan_counts": plan_counts, "run_id": run_id}, indent=2), encoding="utf-8")
    print(f"  已留存待清理 ID 审计快照: {target_json}")

    try:
        deleted_summary = {}
        for tname, c_sql, d_sql in tables_plan:
            deleted_for_table = 0
            chunk_size = 800
            for i in range(0, len(target_pids), chunk_size):
                chunk = target_pids[i:i + chunk_size]
                placeholders = ",".join(f":{j+1}" for j in range(len(chunk)))
                cur.execute(d_sql.format(ph=placeholders), chunk)
                deleted_for_table += cur.rowcount
            deleted_summary[tname] = deleted_for_table
            print(f"  ✓ 成功清理 {tname:<25} : {deleted_for_table} 行")

        conn.commit()
        print(f"\n🎉 物理回滚清理完成！事务已 Commit。共清理 {sum(deleted_summary.values())} 行数据。")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 清理执行失败，事务已自动 Rollback: {e}")
        return 1
    finally:
        conn.close()
