# -*- coding: utf-8 -*-
"""
fs_runner.browser.assertion_auditor
===================================
假断言自动化审计门禁：
专门拦截并钉死以下四类「伪断言」：
1. 同一字面量自比（如 '体温单' == '体温单'）
2. 纯布尔/纯存在性检查（如 挂载(True)、== True、仅判断元素存在）
3. 空比空（如 '暂无' == '暂无'、'' == ''、None == None）
4. 缺少真实的「界面渲染值 ↔ 数据库值」承重对账

若任一宣称「通过」的断言触犯上述规则，立即报警并判为审计不合格。
"""
import re
from typing import Any, Dict, List, Tuple


def audit_assertion(case_id: str, title: str, status: str, evidence: Dict[str, Any]) -> List[str]:
    """审计单条断言的 evidence，返回违规报警列表。"""
    if status != "通过":
        # 未执行或失败的用例，如实记录，不作为通过断言虚构报警
        return []

    violations = []
    eq_str = str(evidence.get("验证等式", ""))

    # 规则 1: 同一字面量自比
    # 匹配形如 'xxx' == 'xxx' 或 "xxx" == "xxx"
    lit_matches = re.findall(r"(['\"])(.+?)\1\s*==\s*\1\2\1", eq_str)
    if lit_matches:
        for _, lit in lit_matches:
            violations.append(f"[违规-同一字面量自比] 等式中出现字面量自我比对: '{lit}' == '{lit}'")

    # 规则 2: 纯布尔/纯存在性断言（无业务数据比较）
    # 检测只有 挂载(True) 或包含存在性布尔且没有实际数值/文本 payload
    if re.search(r"挂载\s*\(\s*(True|true)\s*\)", eq_str) or re.search(r"挂载状态\s*==\s*True", eq_str):
        # 如果等式里除了挂载状态和同一字面量外没有其他业务属性，则报警
        if "==" not in eq_str or lit_matches:
            violations.append("[违规-纯布尔存在性检查] 仅判断组件挂载/元素存在，缺乏真实业务值比对")

    # 规则 3: 空比空断言
    # 检测两边都是 '暂无'、空字符串、None、null
    empty_patterns = [
        r"['\"](?:暂无|无|\s*)['\"].*?==.*?['\"](?:暂无|无|\s*)['\"]",
        r"\(\s*['\"](?:暂无|无|\s*)['\"]\s*\).*?==.*?\(\s*['\"](?:暂无|无|\s*)['\"]\s*\)",
        r"None.*?==.*?None",
        r"null.*?==.*?null",
    ]
    for ep in empty_patterns:
        if re.search(ep, eq_str, re.IGNORECASE):
            violations.append("[违规-空比空对账] 等式两端均为空或'暂无'，未采用真实有效业务数据采样")
            break

    # 规则 4: 缺少界面值或数据库值承重
    ui_val = evidence.get("界面读出值") or evidence.get("界面读出指标") or evidence.get("界面总金额") or evidence.get("界面读出床位集合")
    db_val = evidence.get("数据库真实值") or evidence.get("库中挂账总额") or evidence.get("库中全院在院床位数")
    if ui_val is None or db_val is None:
        if "UI-INDEX" not in case_id:  # UI-INDEX 是看板聚合指标
            violations.append("[违规-缺少界面或库值] evidence 中缺少明确的'界面读出值'或'数据库真实值'")

    return violations


def audit_all_assertions(ui_results: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    """对全量界面断言执行审计，返回 (是否全部合格, 违规详情列表)。"""
    all_violations = []
    for item in ui_results:
        cid = item.get("case_id", "")
        title = item.get("title", "")
        status = item.get("status", "")
        evidence = item.get("evidence", {}) or {}

        v_list = audit_assertion(cid, title, status, evidence)
        if v_list:
            all_violations.append({
                "case_id": cid,
                "title": title,
                "status": status,
                "violations": v_list,
                "evidence_eq": evidence.get("验证等式", "")
            })

    is_clean = len(all_violations) == 0
    return is_clean, all_violations
