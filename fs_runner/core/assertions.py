# -*- coding: utf-8 -*-
"""
fs_runner.core.assertions
=========================
规则断言原语与结构化记录引擎。
为 LoopResult 提供 assert_rule(...) 核心实现：
1. 校验 rule_id 必须存在于 YAML 规则库中，不存在抛出 RuleNotFoundError（含调用方源码文件名与行号）。
2. 支持丰富的关系算子：==, !=, <, <=, >, >=, in, not_in, set_eq, subset, row_eq。
3. 结构化记录每条断言详情：
   {"rule": rule_id, "ok": bool, "等式": "人话描述", "两边": sides_dict, "statement": rule.statement, "desc": desc}
4. 聚合遵循规则并提供反向反查。
"""
import inspect
from typing import Any, Dict, List, Optional, Set, Tuple


class RuleNotFoundError(RuntimeError):
    """断言引用了未在规则库中登记的规则 ID。"""
    pass


def _eval_op(lhs: Any, op: str, rhs: Any, tolerance: float = 1e-6) -> Tuple[bool, str]:
    """计算关系算子并生成人话等式描述。"""
    op_clean = str(op).strip().lower()

    if op_clean in ("==", "=", "eq"):
        if isinstance(lhs, (int, float)) and isinstance(rhs, (int, float)):
            ok = abs(float(lhs) - float(rhs)) <= tolerance
        else:
            ok = (lhs == rhs)
        eq_text = f"{lhs} == {rhs}"
        return ok, eq_text

    if op_clean in ("!=", "<>", "ne"):
        if isinstance(lhs, (int, float)) and isinstance(rhs, (int, float)):
            ok = abs(float(lhs) - float(rhs)) > tolerance
        else:
            ok = (lhs != rhs)
        eq_text = f"{lhs} != {rhs}"
        return ok, eq_text

    if op_clean in ("<", "lt"):
        ok = float(lhs) < float(rhs) - tolerance
        eq_text = f"{lhs} < {rhs}"
        return ok, eq_text

    if op_clean in ("<=", "le"):
        ok = float(lhs) <= float(rhs) + tolerance
        eq_text = f"{lhs} <= {rhs}"
        return ok, eq_text

    if op_clean in (">", "gt"):
        ok = float(lhs) > float(rhs) + tolerance
        eq_text = f"{lhs} > {rhs}"
        return ok, eq_text

    if op_clean in (">=", "ge"):
        ok = float(lhs) >= float(rhs) - tolerance
        eq_text = f"{lhs} >= {rhs}"
        return ok, eq_text

    if op_clean in ("in",):
        ok = lhs in rhs
        eq_text = f"{lhs} in {rhs}"
        return ok, eq_text

    if op_clean in ("not_in", "not in"):
        ok = lhs not in rhs
        eq_text = f"{lhs} not in {rhs}"
        return ok, eq_text

    if op_clean in ("set_eq", "set==", "set_equal"):
        s_lhs = set(lhs) if not isinstance(lhs, set) else lhs
        s_rhs = set(rhs) if not isinstance(rhs, set) else rhs
        ok = (s_lhs == s_rhs)
        l_sample = sorted(list(s_lhs))[:5]
        r_sample = sorted(list(s_rhs))[:5]
        eq_text = f"集合(条数:{len(s_lhs)}) {l_sample} == 集合(条数:{len(s_rhs)}) {r_sample}"
        return ok, eq_text

    if op_clean in ("subset", "subset_of"):
        s_lhs = set(lhs) if not isinstance(lhs, set) else lhs
        s_rhs = set(rhs) if not isinstance(rhs, set) else rhs
        ok = s_lhs.issubset(s_rhs)
        eq_text = f"子集 {sorted(list(s_lhs))[:5]} ⊆ 全集 {sorted(list(s_rhs))[:5]}"
        return ok, eq_text

    if op_clean in ("row_eq", "tuple_eq"):
        t_lhs = tuple(str(x) if x is not None else "" for x in lhs)
        t_rhs = tuple(str(x) if x is not None else "" for x in rhs)
        ok = (t_lhs == t_rhs)
        eq_text = f"逐行字段 {t_lhs} == {t_rhs}"
        return ok, eq_text

    raise ValueError(f"未知的关系算子: '{op}' (支持 ==, !=, <, <=, >, >=, in, not_in, set_eq, subset, row_eq)")


def execute_assert_rule(
    result_obj: Any,
    rule_id: str,
    lhs: Any,
    op: str,
    rhs: Any,
    sides: Dict[str, Any],
    desc: str = "",
    tolerance: float = 1e-6,
) -> bool:
    """执行并记录一条规则断言。"""
    from ..rules.registry import registry
    registry.ensure_loaded()

    # 1. 严格校验规则 ID 是否存在
    rule = registry.get_rule(rule_id)
    if not rule:
        caller = inspect.currentframe().f_back.f_back
        c_file = caller.f_code.co_filename if caller else "unknown"
        c_line = caller.f_lineno if caller else 0
        raise RuleNotFoundError(
            f"❌ 断言引用了未在 YAML 规则库中登记的规则 ID: '{rule_id}'！\n"
            f"   触发位置: {c_file}:{c_line}\n"
            f"   硬约束：不许声明未登记的规则，请在 business_rules.yaml 或 conventions.yaml 中补充声明。"
        )

    # 2. 算子求值
    ok, eq_repr = _eval_op(lhs, op, rhs, tolerance=tolerance)

    # 3. 构造结构化描述（人话）
    human_eq = f"{desc}（{eq_repr}）" if desc else eq_repr

    assertion_item = {
        "rule": rule_id,
        "ok": bool(ok),
        "等式": human_eq,
        "两边": sides,
        "statement": rule.statement,
        "desc": desc,
    }

    # 4. 挂载到结果对象
    if not hasattr(result_obj, "assertions") or result_obj.assertions is None:
        result_obj.assertions = []
    result_obj.assertions.append(assertion_item)

    # 5. 若断言失败，且当前结果状态为通过或 PENDING，标为失败
    if not ok:
        current_status = getattr(result_obj, "status", None)
        if current_status in ("通过", "PENDING"):
            result_obj.status = "失败"
            fail_note = f"违反规则 [{rule_id}]: {human_eq}"
            if getattr(result_obj, "note", None):
                result_obj.note = f"{result_obj.note}；{fail_note}"
            else:
                result_obj.note = fail_note

    return ok
