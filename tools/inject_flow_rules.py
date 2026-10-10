# -*- coding: utf-8 -*-
"""
tools/inject_flow_rules.py
==========================
自动为所有 Flow 函数注入 requires_rules 声明，保证与 YAML 规则库双向 100% 对齐。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CASE_RULES = {
    "L0-010": ["RULE_SI_CATALOG_CHECK"],
    "L2-105": ["CONV_OP_ORDER_NEXT_COMB", "RULE_IP_01", "RULE_IP_02", "RULE_IP_03", "RULE_IP_05", "RULE_OP_04"],
    "L2-107": ["CONV_OP_ORDER_NEXT_COMB", "CONV_SAMPLE_IMMUTABLE_SORT", "RULE_IP_01", "RULE_IP_02"],
    "L4-048": ["RULE_IP_04", "RULE_OP_04"],
    "L5-001": [],
    "L5-002": [],
    "L5-003": [],
    "L5-004": [],
    "L5-005": [],
    "L5-006": [],
    "L5-008": [],
    "L5-010": [],
    "L5-011": [],
    "L5-012": [],
    "L5-013": [],
    "L5-014": [],
    "L5-015": [],
    "L5-016": [],
    "L5-019": [],
    "L5-020": [],
    "L5-021": [],
    "L5-022": ["CONV_GATE_OBSERVATION_EXPLICIT"],
    "L5-023": [],
    "L5-024": [],
    "L5-025": ["CONV_MUTATION_NON_NUMERIC"],
    "L5-026": [],
    "L5-027": ["CONV_CHAR_PAD_SPACE_OVERFLOW"],
    "L5-028": [],
    "L5-036": ["CONV_CROSS_SYS_DEPT_DISTINCTION", "CONV_INPATIENT_SAMPLE_INCOMPLETE"],
    "L5-037": ["CONV_GATE_OBSERVATION_EXPLICIT"],
    "L6-001": ["CONV_ADMIN_TOKEN_ONCE", "CONV_ID_CARD_COLLISION_SEED", "RULE_OP_01"],
    "L6-002": [],
    "L6-004": ["CONV_PATIENT_INVALIDATE_SEMANTICS"],
    "L6-005": ["CONV_EQUAL_SCOPE_ASSERTION", "CONV_SAMPLE_AVOID_EMPTY_SET", "RULE_OP_01", "RULE_OP_02", "RULE_OP_03", "RULE_OP_07"],
    "L6-008": ["CONV_MUTATION_NON_NUMERIC", "RULE_OP_02", "RULE_OP_07"],
    "L6-009": ["CONV_ID_CARD_COLLISION_SEED", "CONV_REG_GRADE_DICT_DRIFT"],
    "L6-012": ["CONV_REG_GRADE_DICT_DRIFT", "CONV_REG_NOON_SERIAL"],
    "L6-014": [],
    "L6-015": ["CONV_REFUNDABLE_REG_ROWS"],
    "L6-018": ["RULE_IP_01", "RULE_IP_05", "RULE_IP_06"],
    "L6-020": ["CONV_OP_DAY_BALANCE_SCOPE"],
    "L6-024": ["CONV_OP_UNPAID_SEE_NO_GROUP"],
    "L6-025": ["CONV_OP_CHARGE_APPLY_CHAIN"],
    "L6-026": ["CONV_GATE_OBSERVATION_EXPLICIT", "RULE_FIN_CASHIER_SEGMENT", "RULE_OP_05", "RULE_OP_08"],
    "L6-028": ["CONV_OP_CHARGE_APPLY_CHAIN"],
    "L6-032": ["CONV_OP_DAY_BALANCE_SCOPE"],
    "L6-033": ["CONV_RECEIPT_PAYMENT_ACTIVE"],
    "L6-036": ["CONV_OP_DAY_BALANCE_SCOPE"],
    "L6-038": [],
    "L6-039": [],
    "L6-043": [],
    "L6-045": [],
    "L6-046": ["CONV_MUTATION_NON_NUMERIC", "CONV_OP_CHARGE_APPLY_CHAIN", "RULE_IP_07", "RULE_OP_05", "RULE_OP_06", "RULE_OP_08"],
    "L6-047": ["CONV_ADMIN_TOKEN_ONCE", "CONV_MUTATION_NON_NUMERIC", "CONV_REFUND_DEPT_ISOLATION", "RULE_IP_07", "RULE_OP_06", "RULE_OP_08"],
    "L6-050": ["CONV_PREPAY_DAY_BALANCE_SCOPE", "RULE_IP_06"],
    "L6-052": ["RULE_IP_08"],
    "L6-055": [],
    "L6-056": ["RULE_EBILL_RED_BLUE_OFFSET"],
    "L6-063": ["CONV_NO_SPECULATIVE_EQUATION"],
    "L6-064": ["CONV_EXCEL_IMAGE_DIMENSION"],
    "L6-068": ["RULE_IP_08"],
    "L9-010": ["RULE_PHA_DISPENSE_PRIORITY"],
    "L9-011": ["CONV_ASSERTION_HONEST_EVIDENCE", "CONV_DEAD_CONFIG_FALLBACK_ORDER", "CONV_DISPENSE_ORDER_SPLIT", "CONV_DRUG_QUALITY_DICT", "RULE_PHA_DISPENSE_PRIORITY", "RULE_PHA_INFUSION_QUALITY"],
    "L9-012": ["CONV_DISPENSE_ORDER_SPLIT", "CONV_DISPENSE_QTY_CONVERSION", "CONV_PHA_DISPENSE_OUTPUTTED", "RULE_IP_04", "RULE_PHA_DISPENSE_NOT_OVER_SUPPLY"],
    "L9-013": ["CONV_DISPENSE_QTY_CONVERSION", "CONV_GATE_OBSERVATION_EXPLICIT", "CONV_MUTATION_NON_NUMERIC", "RULE_PHA_DISPENSE_NOT_OVER_SUPPLY"],
    "L9-014": ["CONV_GATE_OBSERVATION_EXPLICIT", "CONV_PHA_DISPENSE_OUTPUTTED", "RULE_IP_07"],
}


def process_file(path: Path):
    text = path.read_text(encoding="utf-8")
    modified = False

    # 匹配 def flow_Lxx_xxx(ctx: Ctx) -> LoopResult:
    def repl(match):
        nonlocal modified
        full = match.group(0)
        fn_name = match.group(2)
        # 从函数名提取 case_id, 如 flow_L6_001 -> L6-001
        m_cid = re.match(r"flow_(L\d+)_([0-9a-zA-Z]+)", fn_name)
        if not m_cid:
            return full
        cid = f"{m_cid.group(1)}-{m_cid.group(2)}"
        if cid not in CASE_RULES:
            return full

        rules = CASE_RULES[cid]
        # 检查是否已经注入了 requires_rules
        after_def = text[match.end():match.end() + 200]
        if "requires_rules =" in after_def:
            return full

        modified = True
        return f"{full}\n    requires_rules = {repr(rules)}"

    new_text = re.sub(r"(def\s+(flow_\w+)\s*\([^)]*\)\s*->\s*LoopResult\s*:)", repl, text)

    # 在各模块末尾为 flow 函数绑定属性与 FLOW_RULES
    if path.name == "closed_loop.py":
        if "flow_L6_001.requires_rules" not in new_text:
            # 在 _FLOWS 定义之后批量绑定
            target = "_FLOWS: Dict[str, Callable[[Ctx], LoopResult]] = {"
            m_pos = new_text.find(target)
            if m_pos != -1:
                # 寻找 _FLOWS 字典闭合括号
                close_pos = new_text.find("}", m_pos)
                if close_pos != -1:
                    bind_lines = [
                        "\n\n# 显式绑定各 flow 的 requires_rules 属性",
                        "for _cid, _fn in list(_FLOWS.items()):",
                        "    from ...rules.registry import registry as _reg",
                        "    # 也可以从 FLOW_RULES 或 CASE_RULES 注入",
                    ]
                    # 直接静态绑定
                    static_binds = []
                    for cid, rules in CASE_RULES.items():
                        fn_name = f"flow_{cid.replace('-', '_')}"
                        if f"def {fn_name}" in new_text:
                            static_binds.append(f"{fn_name}.requires_rules = {repr(rules)}")
                    static_bind_block = "\n".join(static_binds) + "\n\nFLOW_RULES = {cid: getattr(fn, 'requires_rules', []) for cid, fn in _FLOWS.items()}\n"
                    new_text = new_text[:close_pos + 2] + "\n" + static_bind_block + new_text[close_pos + 2:]
                    modified = True
    else:
        # 子模块 flows/*.py
        m_flows = re.search(r"FLOWS\s*=\s*\{([^}]+)\}", new_text)
        if m_flows:
            flows_content = m_flows.group(1)
            pairs = re.findall(r"['\"](L\d+-[0-9a-zA-Z]+)['\"]\s*:\s*(\w+)", flows_content)
            extra_binds = []
            for cid, fn in pairs:
                if cid in CASE_RULES and f"{fn}.requires_rules" not in new_text:
                    extra_binds.append(f"{fn}.requires_rules = {repr(CASE_RULES[cid])}")
            if extra_binds:
                insert_pos = m_flows.start()
                bind_block = "\n".join(extra_binds) + "\n\n"
                flow_rules_block = "\n\nFLOW_RULES = {\n" + "".join(f'    "{cid}": {fn}.requires_rules,\n' for cid, fn in pairs if cid in CASE_RULES) + "}\n"
                new_text = new_text[:insert_pos] + bind_block + new_text[insert_pos:] + flow_rules_block
                modified = True

    if modified:
        path.write_text(new_text, encoding="utf-8")
        print(f"[OK] Injected rules into {path.name}")


def main():
    target_files = [
        ROOT / "fs_runner" / "cases" / "closed_loop" / "closed_loop.py"
    ] + list((ROOT / "fs_runner" / "cases" / "closed_loop" / "flows").glob("*.py"))

    for f in target_files:
        if f.name.startswith("__"):
            continue
        process_file(f)


if __name__ == "__main__":
    main()

