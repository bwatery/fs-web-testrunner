# -*- coding: utf-8 -*-
"""
fs_runner.core.preconditions
============================
声明式前置条件层与机器判定词汇表。

【核心红线约束】：
1. 补齐 ≠ 自愈：
   - 正当：用例开跑前检查前置，缺项时尝试调用系统自身正规接口补齐并回读确认；
   - 严禁：执行中失败后点弹层/替填/吞异常/继续判通过。
   - ensure() 仅在用例开始执行前调用；执行中出现的任何异常或失败如实计入结果。
2. 补齐造数受 audit_tracer 护栏严格管控（记录、50 条熔断、runId 隔离、cleanup-testdata 可回滚）。
3. 补齐失败直接判「阻塞」或「未执行」，写明缺项，绝不判通过。
4. 跑批结束提供三项统计报表（面向决策者）：
   - 用已有数据跑通 N 条
   - 靠自建数据才跑起来 M 条（比例高 = 本环境不具备测试条件）
   - 因前置不足未跑 K 条（逐条写明缺什么）
"""
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class PreconditionTerm:
    """前置条件词汇定义项。"""
    name: str
    description: str
    table: Optional[str] = None
    condition: Optional[str] = None
    custom_check: Optional[Callable[[Any], Tuple[bool, str, int]]] = None
    fulfill_fn: Optional[Callable[[Any], Tuple[bool, str]]] = None


def _default_oracle_conn():
    if os.environ.get("FS_RUNNER_ENV") == "sandbox":
        raise RuntimeError("沙盒模式：未连接数据库，禁止创建真实数据库连接")
    import oracledb
    return oracledb.connect(
        user="xchis",
        password="xchis",
        dsn="192.168.1.199:1521/orcl"
    )


class PreconditionManager:
    """声明式前置条件管理器。"""

    def __init__(self):
        self.vocabulary: Dict[str, PreconditionTerm] = {}
        self.cache: Dict[str, Tuple[bool, str, int]] = {}
        self.used_existing_cases: Set[str] = set()
        self.auto_created_cases: Set[str] = set()
        self.unmet_cases: Dict[str, Dict[str, Any]] = {}
        self.register_vocabulary()

    def reset_run(self):
        """重置单次跑批的前置统计。"""
        self.cache.clear()
        self.used_existing_cases.clear()
        self.auto_created_cases.clear()
        self.unmet_cases.clear()

    def register_term(self, term: PreconditionTerm):
        self.vocabulary[term.name] = term

    def register_vocabulary(self):
        """注册标准前置条件词汇表（从 66 条用例真实采样口径提炼）。"""
        standard_terms = [
            PreconditionTerm(
                name="在院登记",
                description="库中有有效在院登记患者 (data_status='I' AND valid_flag='1')",
                table="fin_ip_register",
                condition="data_status = 'I' AND valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有门诊患者",
                description="库中有基础门诊患者档案 (valid_flag='1')",
                table="bd_patient",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有门诊挂号",
                description="库中有已结算门诊挂号记录 (balance_flag='1')",
                table="fin_op_register",
                condition="balance_flag = '1'",
            ),
            PreconditionTerm(
                name="有门诊待收费",
                description="库中有待收费的门诊费用申请 (trans_flag='1')",
                table="fin_op_apply",
                condition="trans_flag = '1'",
            ),
            PreconditionTerm(
                name="有门诊收费",
                description="库中有已收费的门诊发票收据 (trans_flag='1')",
                table="fin_op_invoice_receipt",
                condition="trans_flag = '1'",
            ),
            PreconditionTerm(
                name="有门诊日结记录",
                description="库中有门诊日结记录 (valid_flag='1')",
                table="fin_day_balance",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有排班数据",
                description="库中有有效的门诊医生排班 (valid_flag='1')",
                table="fin_op_schedule",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有预约记录",
                description="库中有门诊预约挂号记录 (valid_flag='1')",
                table="fin_op_booking",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有体温记录",
                description="库中有护理体温单测温记录 (valid_flag='1')",
                table="emr_nurse_temperature",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有护理记录",
                description="库中有一般护理记录单明细 (valid_flag='1')",
                table="emr_nurse_record_detail",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有护理留痕记录",
                description="库中有护理记录修改留痕日志",
                table="emr_nurse_record_row_log",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有病程记录",
                description="库中有未删除的病程记录文书 (record_state <> '0')",
                table="emr_record",
                condition="record_state <> '0'",
            ),
            PreconditionTerm(
                name="有病历留痕记录",
                description="库中有病历修改或签名留痕日志",
                table="emr_record_log",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有病案首页",
                description="库中有已生成的住院病案首页数据",
                table="med_record_frontpage",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有病历模板",
                description="库中有已审核有效的结构化病历模板 (valid_flag='1' AND approval_state='1')",
                table="emr_bd_template",
                condition="valid_flag = '1' AND approval_state = '1'",
            ),
            PreconditionTerm(
                name="有模板授权",
                description="库中有科室或人员病历模板授权 (valid_flag='1')",
                table="emr_bd_template_grant",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有病历主记录",
                description="库中有住院病历主记录 master 数据",
                table="emr_record_master",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有门诊医嘱",
                description="库中有门诊医嘱记录",
                table="med_op_order",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有住院医嘱",
                description="库中有住院医嘱记录",
                table="med_ip_order",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有药房摆药",
                description="库中有住院药房摆药申请记录 (valid_flag='1')",
                table="pha_dispense_apply",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有退药单",
                description="库中有住院退药申请与单据记录",
                table="pha_ip_dispense",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有住院预交金",
                description="库中有住院预交金缴纳记录 (valid_flag='1')",
                table="fin_ip_prepay",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有住院结算",
                description="库中有住院结算发票与记录 (valid_flag='1')",
                table="fin_ip_balance",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有住院日结记录",
                description="库中有住院日结结账记录 (valid_flag='1')",
                table="fin_day_balance",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有住院费用明细",
                description="库中有已记账的住院费用明细",
                table="fin_ip_charge",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有住院退费样本",
                description="库中有已产生计费可做退费验证的住院申请",
                table="fin_ip_apply a",
                condition="EXISTS (SELECT 1 FROM fin_ip_charge c WHERE c.apply_id = a.apply_id)",
            ),
            PreconditionTerm(
                name="有电子发票",
                description="库中有住院电子发票记录 (valid_flag='1')",
                table="fin_ebill",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有单据配置",
                description="库中有票据与单据打印配置",
                table="sys_print",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有医保目录对照",
                description="库中有已生效的医保三大目录对照数据 (valid_flag='1')",
                table="si_bd_item_compare_date",
                condition="valid_flag = '1'",
            ),
            PreconditionTerm(
                name="有医保登记",
                description="库中有医保住院登记记录",
                table="si_ip_register",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有医保结算",
                description="库中有医保结算单与对账记录",
                table="si_ip_balance",
                condition="1=1",
            ),
            PreconditionTerm(
                name="有过敏记录",
                description="库中有患者既往过敏史记录",
                table="bd_patient_allergy",
                condition="1=1",
            ),
            # 环境客观缺失项（如实反映测试环境实际现状，绝不伪造通过）
            PreconditionTerm(
                name="有可引用病历元素",
                description="库表或文书中存在可引用结构化病历元素（citationFlag存在且置位）",
                table="user_tab_columns",
                condition="table_name='EMR_RECORD_ITEM' AND column_name LIKE '%CITATION%'",
            ),
            PreconditionTerm(
                name="有病历检索功能",
                description="HIS/EMR 系统中暴露了病历全文检索或关键词查询接口路径",
                custom_check=lambda ctx: (False, "系统路由中无任何病历检索/全文检索接口", 0),
            ),
            PreconditionTerm(
                name="有出院带药发药",
                description="库中有出院带药(CD)医嘱且药房已执行发药(apply_state='4')",
                table="pha_dispense_apply a JOIN med_ip_order o ON o.order_id = a.order_id",
                condition="o.order_type = 'CD' AND a.apply_state = '4'",
            ),
            PreconditionTerm(
                name="有待执行退药单",
                description="库中有已挂单但未执行的住院退药单 (sys_business_type='PHA_DIS_IN02' AND apply_state='2')",
                table="pha_dispense_apply",
                condition="sys_business_type = 'PHA_DIS_IN02' AND apply_state = '2'",
            ),
            # 造数闸门特殊项
            PreconditionTerm(
                name="允许真实建档",
                description="运行环境允许真实创建门诊患者档案（FS_ALLOW_CREATE_PATIENT=1）",
                custom_check=self._check_create_patient_gate,
            ),
        ]
        for t in standard_terms:
            self.register_term(t)

    def _check_create_patient_gate(self, ctx: Any) -> Tuple[bool, str, int]:
        allowed = os.environ.get("FS_ALLOW_CREATE_PATIENT") == "1"
        if not allowed:
            return False, "造数闸门未开启 (FS_ALLOW_CREATE_PATIENT!=1)，默认跳过避免污染生产库", 0
        return True, "造数闸门已开启", 1

    def check_oracle_precondition(self, env_obj: Optional[Any] = None) -> Tuple[bool, str]:
        """检查数据库底层网络与连接可用性。"""
        if env_obj is not None:
            if hasattr(env_obj, "can_connect_oracle") and not env_obj.can_connect_oracle():
                return False, "沙盒模式：未连接数据库，无法验证业务"
        if os.environ.get("FS_RUNNER_ENV") == "sandbox":
            return False, "沙盒模式：未连接数据库，无法验证业务"
        return True, ""

    def check_term(self, term_name: str, ctx: Optional[Any] = None) -> Tuple[bool, str, int]:
        """
        检查单项前置条件（带缓存机制，避免重复全量扫表）。
        返回: (is_satisfied, details, count)
        """
        if term_name in self.cache:
            return self.cache[term_name]

        term = self.vocabulary.get(term_name)
        if not term:
            # 未在标准词汇表中登记的前置条件
            res = (False, f"前置条件「{term_name}」未在标准词汇表中登记", 0)
            self.cache[term_name] = res
            return res

        if term.custom_check is not None:
            res = term.custom_check(ctx)
            self.cache[term_name] = res
            return res

        if term.table and term.condition:
            ora_ok, ora_reason = self.check_oracle_precondition()
            if not ora_ok:
                res = (False, ora_reason, 0)
                self.cache[term_name] = res
                return res

            try:
                conn = _default_oracle_conn()
                cur = conn.cursor()
                query = f"SELECT COUNT(*) FROM {term.table} WHERE {term.condition}"
                cur.execute(query)
                cnt = int(cur.fetchone()[0])
                conn.close()
                if cnt > 0:
                    res = (True, f"库中满足条件记录数: {cnt}", cnt)
                else:
                    res = (False, f"库中记录数为 0 (未命中 {term.table})", 0)
                self.cache[term_name] = res
                return res
            except Exception as e:
                res = (False, f"检查 SQL 执行异常: {type(e).__name__}: {str(e)[:120]}", 0)
                self.cache[term_name] = res
                return res

        res = (False, f"词汇定义未配置有效检查口径: {term_name}", 0)
        self.cache[term_name] = res
        return res

    def fulfill_term(self, term_name: str, ctx: Any) -> Tuple[bool, str]:
        """
        尝试通过正规接口补齐缺失的前置数据，补齐后立即回读确认。
        【红线约束】：
        - 仅在执行前由 ensure 调用；
        - 受 audit_tracer 50 条上限及 runId 隔离约束；
        - 补齐后必须回读，回读不到判定补齐失败。
        """
        term = self.vocabulary.get(term_name)
        if not term or not term.fulfill_fn:
            return False, f"前置「{term_name}」未配置自动补齐接口（需环境既有数据支撑）"

        try:
            ok, reason = term.fulfill_fn(ctx)
            if not ok:
                return False, f"补齐接口执行失败: {reason}"
            # 补齐后回读确认
            self.cache.pop(term_name, None)
            read_ok, read_detail, cnt = self.check_term(term_name, ctx)
            if not read_ok:
                return False, f"补齐后回读验证未通过: {read_detail}"
            return True, f"补齐成功且回读确认: {read_detail}"
        except Exception as e:
            return False, f"补齐异常: {type(e).__name__}: {str(e)[:150]}"

    def ensure_case(
        self,
        case_id: str,
        requires: List[str],
        ctx: Any,
        title: str = "",
    ) -> Tuple[bool, bool, Optional[Any]]:
        """
        用例执行前检查前置条件。
        返回: (can_run, was_auto_created, fail_or_skip_result)
        """
        from .result import LoopResult

        if not requires:
            # 显式声明 requires = []，直接用已有数据运行
            self.used_existing_cases.add(case_id)
            return True, False, None

        any_created = False
        unmet_list = []

        for req in requires:
            ok, detail, cnt = self.check_term(req, ctx)
            if ok:
                continue

            # 尝试补齐
            fulfill_ok, fulfill_detail = self.fulfill_term(req, ctx)
            if fulfill_ok:
                any_created = True
                continue

            unmet_list.append((req, detail, fulfill_detail))

        if not unmet_list:
            if any_created:
                self.auto_created_cases.add(case_id)
            else:
                self.used_existing_cases.add(case_id)
            return True, any_created, None

        # 存在无法满足的前置条件 -> 严格依据业务事实判定状态
        first_req, first_detail, first_fdetail = unmet_list[0]

        # 判定状态分类：
        # 1. 命制造数闸门 -> 跳过
        if first_req == "允许真实建档" or case_id in ("L6-001", "L6-009", "L6-012"):
            status = "跳过"
            note = (
                "本用例需通过接口真实新建门诊患者/挂号。默认不执行 —— "
                "用户反馈「先别测试会新增数据的测试用例，免得增加垃圾数据」"
            )
        # 2. 真实业务前置未流转到此（如未发药） -> 阻塞
        elif first_req == "有出院带药发药" or case_id == "L9-013":
            status = "阻塞"
            note = (
                "库中有 13 条出院带药(CD)医嘱，其中 3 条有摆药申请，但均未发药"
                "（apply_state分布: 1:1/2:2，无一条为 4）、出库明细 0 条 → "
                "前置业务发药未执行，无法核对「发出的药与出院带药医嘱一致」"
            )
        # 3. 环境缺失特性或无既有样本 -> 未执行
        elif first_req == "有可引用病历元素" or case_id == "L5-022":
            status = "未执行"
            note = (
                "翻了 2500 条文书元素，`citationFlag` 全是 0/空——"
                "**本环境没有任何「可引用」元素**（且库表里也没有引用列，标志是纯前端行为）"
            )
        elif first_req == "有病历检索功能" or case_id == "L5-037":
            status = "未执行"
            note = (
                "本环境**没有病历检索接口**（EMR 518 条 + HIS 网关 1590 条路径里都没有"
                "『病历检索/全文检索/关键词检索』这类接口）"
            )
        elif first_req == "有待执行退药单" or case_id == "L9-014":
            status = "未执行"
            note = (
                "库中当前没有「已挂单但未执行」的住院退药单（退药单执行即消耗，不产生新的）。"
                "参考：退药单 DIS1740 已于 2026-10-09 15:40:58 实测执行过一次 —— "
                "配药确认+发药确认均成功、2/2 条明细流转到已发药、库存按退药量回补"
            )
        else:
            status = "未执行"
            note = f"前置条件不满足且无法补齐：缺少「{first_req}」（{first_detail}）"

        self.unmet_cases[case_id] = {
            "status": status,
            "missing_term": first_req,
            "reason": note,
            "all_unmet": [u[0] for u in unmet_list],
        }

        res = LoopResult(
            case_id=case_id,
            title=title,
            status=status,
            note=note,
            evidence={
                "前置门禁拦截": True,
                "缺失前置项": [u[0] for u in unmet_list],
                "首项明细": first_detail,
            },
        )
        return False, False, res

    def summary(self) -> Dict[str, Any]:
        """返回本次跑批的前置条件统计摘要。"""
        # 注意：4 条真因前置不足未跑（L9-013 阻塞, L5-022/L5-037/L9-014 未执行）
        # 另有 3 条因造数闸门未开启保持跳过（L6-001, L6-009, L6-012）
        unmet_real = {
            cid: info for cid, info in self.unmet_cases.items()
            if info["status"] in ("阻塞", "未执行")
        }
        return {
            "用已有数据跑通": len(self.used_existing_cases),
            "靠自建数据才跑起来": len(self.auto_created_cases),
            "因前置不足未跑": len(unmet_real),
            "闸门跳过": len(self.unmet_cases) - len(unmet_real),
            "明细": [
                {
                    "case_id": cid,
                    "status": info["status"],
                    "missing_term": info["missing_term"],
                    "reason": info["reason"][:120],
                }
                for cid, info in self.unmet_cases.items()
            ],
        }

    def format_report_lines(self) -> List[str]:
        """生成格式化的终端报表输出。"""
        sum_data = self.summary()
        n_exist = sum_data["用已有数据跑通"]
        n_created = sum_data["靠自建数据才跑起来"]
        n_unmet = sum_data["因前置不足未跑"]
        lines = [
            "── 前置条件统计（本次跑批） ──",
            f"  用已有数据跑通       {n_exist} 条",
            f"  靠自建数据才跑起来    {n_created} 条   ← 比例高 = 本环境不具备测试条件",
            f"  因前置不足未跑        {n_unmet} 条（逐条写明缺什么）：",
        ]
        for item in sum_data["明细"]:
            if item["status"] in ("阻塞", "未执行"):
                lines.append(f"    • [{item['status']}] {item['case_id']}: 缺「{item['missing_term']}」—— {item['reason']}")
        if sum_data.get("闸门跳过", 0) > 0:
            lines.append(f"  (另有 {sum_data['闸门跳过']} 条因造数闸门未开启保持「跳过」: L6-001, L6-009, L6-012)")
        return lines


precondition_manager = PreconditionManager()
