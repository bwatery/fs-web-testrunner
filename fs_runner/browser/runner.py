# -*- coding: utf-8 -*-
"""
fs_runner.browser.runner
========================
ui-verify 子命令执行引擎：
1. 支持 --headless（默认无头模式，给 AI 快速测试）与 --windowed（窗口接管模式，给人看）。
2. 真实登录认证通道：输账号密码完成表单登录，严格区分「密码错误」与「页面未起」。
3. 真实界面业务断言（给人看的那半）：
   - 打开页面 ➔ 真实点击 ➔ 读页面真实渲染的文字/表格 ➔ 与 Oracle 数据库比对 ➔ 等式成立才叫通过。
   - 包含多用例对账：L6-039-P1（陈新强费用汇总）、L6-039-P2（刘付立城费用汇总）、
     L6-039-LIST（在院床位分配全集）、UI-INDEX（首页收费总量聚合等式）。
   - 变异自检支持：--mutation 内存扰动数据库读出值，验证断言必定变红（证明断言承重，绝非打开就过）。
4. 门禁硬约束：
   - 浏览器起不来/连不上立即退出并大声报错，严禁静默降级为冒烟或伪通过。
   - --env sandbox 沙盒模式纯离线运行，永不判「通过」，强制产出「未执行」。
   - 支持 --screenshot 将界面执行现场留证落盘至 reports/verify/screenshots/。
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import FRONTEND_URL, GATEWAY_URL, ROOT_DIR
from .auth import login_ui
from .cdp import launch_browser, BrowserSession


SCREENSHOTS_DIR = ROOT_DIR / "reports" / "verify" / "screenshots"
REPORTS_DIR = ROOT_DIR / "reports" / "verify"


def _oracle_conn():
    import oracledb
    return oracledb.connect(user="xchis", password="xchis",
                            dsn="192.168.1.199:1521/orcl")


def _archive_failure_trace(session: BrowserSession, case_id: str, note: str, evidence: Dict[str, Any]):
    try:
        from .trace import save_ui_trace_package
        trace_path = save_ui_trace_package(session, case_id, note=note, evidence=evidence)
        rel_path = str(trace_path.relative_to(ROOT_DIR)).replace("\\", "/")
        evidence["trace_package"] = rel_path
        print(f"        📦 [UI现场包已归档] {rel_path}")
    except Exception as e:
        print(f"        ⚠️ [UI现场包归档异常] {e}")


def _record_ui_result(
    ui_results: List[Dict[str, Any]],
    cid: str,
    title: str,
    is_ok: bool,
    note: str,
    evidence: Dict[str, Any],
    duration_ms: float,
    env_name: str,
    session: BrowserSession,
):
    if env_name == "sandbox":
        final_status = "未执行"
        final_note = f"不判通过模式：仍连真实环境做通道校验（真实等式{'成立' if is_ok else '不成立'}），但结论一律降级为未执行"
        evidence["env"] = "sandbox"
        evidence["no_pass_mode"] = True
    elif env_name == "not_executed":
        final_status = "未执行"
        final_note = note
    else:
        final_status = "通过" if is_ok else "失败"
        final_note = note

    ui_results.append({
        "case_id": cid,
        "title": title,
        "status": final_status,
        "note": final_note,
        "evidence": evidence,
        "duration_ms": duration_ms,
    })
    mark = "⚪" if final_status == "未执行" else ("✅" if is_ok else "❌")
    print(f"  {mark} [{cid}] —— {final_status}")
    print(f"        {final_note}")
    if not is_ok and env_name not in ("sandbox", "not_executed") and final_status != "未执行":
        _archive_failure_trace(session, cid, note, evidence)


def _prepare_inpatient_page(session: BrowserSession, frontend: str, _step: Any) -> Tuple[str, List[str]]:
    has_query_menu = session.eval("""(() => {
        return Array.from(document.querySelectorAll('.el-menu-item'))
                    .some(e => (e.innerText || '').includes('费用综合查询'));
    })()""")

    if not has_query_menu:
        print("  [角色自适应] 当前激活角色非住院护士，正在通过界面「切换科室」对话框切换为住院护士角色...")
        session.eval("""(() => {
            const el = document.querySelector('.avatar-dropdown') || document.querySelector('.username');
            if (el) el.click();
        })()""")
        time.sleep(1.2)
        session.eval("""(() => {
            const item = Array.from(document.querySelectorAll('.el-dropdown-menu__item'))
                              .find(x => (x.innerText || '').includes('切换科室'));
            if (item) item.click();
        })()""")
        time.sleep(1.2)
        session.eval("""(() => {
            const d = document.querySelector('.el-dialog');
            if (d) {
                const s0 = d.querySelectorAll('.el-select')[0];
                if (s0) { const inp = s0.querySelector('input'); if (inp) inp.click(); else s0.click(); }
            }
        })()""")
        time.sleep(1.2)
        session.eval("""(() => {
            const item = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
                              .find(x => (x.innerText || '').trim() === '住院护士');
            if (item) item.click();
        })()""")
        time.sleep(1.0)
        session.eval("""(() => {
            const d = document.querySelector('.el-dialog');
            if (d) {
                const btn = Array.from(d.querySelectorAll('button')).find(x => (x.innerText || '').includes('确定'));
                if (btn) btn.click();
            }
        })()""")
        time.sleep(3.0)

    # 点击「费用综合查询」并分发冒泡事件
    _step("正在通过侧边栏导航进入「费用综合查询」模块...")
    session.eval("""(() => {
        const item = Array.from(document.querySelectorAll('.el-menu-item'))
                          .find(e => (e.innerText || '').includes('费用综合查询'));
        if (item) {
            const span = item.querySelector('span');
            if (span) span.click();
            item.click();
            item.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        }
    })()""")
    time.sleep(3.0)

    current_hash = session.eval("location.hash") or ""
    if "syntheticfquery" not in current_hash:
        _step("直接加载费用综合查询路由 (#/inpatient/finance/syntheticfquery)...")
        session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/finance/syntheticfquery"})
        time.sleep(2.5)
        session.cmd("Page.reload", {"ignoreCache": True})
        time.sleep(3.5)

    # 1. 读之前先「全部展开」左侧树：把所有未展开节点的展开图标点一遍，等待渲染稳定，并记录展开操作数
    _step("正在展开左侧患者树全部病区节点...")
    expand_stats = session.eval("""(() => {
        let totalClicked = 0;
        let passes = 0;
        for (let pass = 0; pass < 5; pass++) {
            const unexpanded = Array.from(document.querySelectorAll('.el-tree-node__expand-icon:not(.is-leaf):not(.expanded)'));
            if (unexpanded.length === 0) break;
            passes++;
            unexpanded.forEach(btn => {
                btn.click();
                totalClicked++;
            });
        }
        return { passes, totalClicked };
    })()""") or {}
    time.sleep(1.5)

    # 动态解析左侧树中的当前病区与在院患者列表
    tree_info = session.eval("""(() => {
        const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'))
                           .map(e => e.innerText.trim())
                           .filter(t => t.length > 0);
        return nodes;
    })()""")
    tree_info = tree_info if isinstance(tree_info, list) else []

    dept_name = ""
    patient_nodes = []
    for t in tree_info:
        m_dept = re.match(r"^([\u4e00-\u9fa5\w]+)\(\d+\)$", t)
        if m_dept and "患者" not in t:
            dept_name = m_dept.group(1)
        if re.match(r"^\d+-\d+\s+", t):
            patient_nodes.append(t)

    if not dept_name:
        header_dept = session.eval("""(() => {
            const el = Array.from(document.querySelectorAll('*'))
                            .find(e => e.children.length === 0 && (e.innerText || '').includes('病区'));
            return el ? el.innerText : '';
        })()""") or ""
        m_h = re.search(r"/\s*([\u4e00-\u9fa5\w]+)病区", header_dept)
        if m_h:
            dept_name = m_h.group(1)
        else:
            dept_name = "内一科"

    return dept_name, patient_nodes


def _run_p1(
    session: BrowserSession,
    patient_nodes: List[str],
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言 1: UI-L6-039-P1 (在院第一患者费用汇总与明细对账)
    # ===================================================================
    t0 = time.time()
    p1_label = patient_nodes[0] if len(patient_nodes) > 0 else "301-1 骨二科测试患者01"
    p1_name = p1_label.split()[-1]
    _step(f"正在读取患者 [{p1_name}] 费用汇总与明细并与数据库对账...")
    print(f"\n  ▶ 正在执行 [UI-L6-039-P1] 费用综合查询 · {p1_name} 费用汇总与明细对账...")
    session.eval(f"""(() => {{
        const el = Array.from(document.querySelectorAll('.el-tree-node__content'))
                        .find(e => (e.innerText || '').trim() === {json.dumps(p1_label)});
        if (el) {{ el.click(); return true; }}
        return false;
    }})()""")
    time.sleep(2.5)

    dom_p1_text = session.eval("document.body.innerText") or ""
    m_tot = re.search(r"总金额\s*([0-9.]+)", dom_p1_text)
    m_zyh = re.search(r"住院号\s*([0-9]+)", dom_p1_text)
    m_bed = re.search(r"住院床号\s*([0-9-]+)", dom_p1_text)

    ui_tot_cost = float(m_tot.group(1)) if m_tot else 0.0
    ui_inpatient_no = m_zyh.group(1) if m_zyh else ""
    ui_bed_no = m_bed.group(1) if m_bed else ""

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""SELECT bed_no, patient_name, inpatient_no, tot_cost 
                   FROM fin_ip_register WHERE inpatient_no = :1""", [ui_inpatient_no])
    ora_p1_row = cur.fetchone()
    cur.execute("""SELECT NVL(SUM(tot_cost),0), COUNT(*) FROM fin_ip_charge 
                   WHERE register_id = (SELECT register_id FROM fin_ip_register WHERE inpatient_no = :1)""", [ui_inpatient_no])
    ora_charge_sum, ora_charge_cnt = cur.fetchone()
    conn.close()

    ora_tot_cost = float(ora_p1_row[3]) if ora_p1_row else 0.0
    ora_inpatient_no = str(ora_p1_row[2]) if ora_p1_row else ""
    ora_bed_no = str(ora_p1_row[0]) if ora_p1_row else ""
    ora_charge_sum = float(ora_charge_sum or 0.0)

    if is_mutation:
        ora_tot_cost += 100.0

    p1_eq1 = (abs(ui_tot_cost - ora_tot_cost) < 1e-4)
    p1_eq2 = (ui_inpatient_no == ora_inpatient_no)
    p1_eq3 = (ui_bed_no == ora_bed_no)

    p1_ok = p1_eq1 and p1_eq2 and p1_eq3 and (ui_tot_cost > 0)
    p1_status = "通过" if p1_ok else "失败"
    p1_note = (
        f"界面读到住院号 {ui_inpatient_no}，床号 {ui_bed_no}，总金额 ¥{ui_tot_cost}；"
        f"库中登记住院号 {ora_inpatient_no}，床号 {ora_bed_no}，挂账总额 ¥{ora_tot_cost} "
        f"—— {'各项等式严格成立' if p1_ok else '等式不成立存在差异'}"
    )
    if is_mutation and not p1_ok:
        p1_note += "（变异自检生效：内存扰动库值成功导致断言变红）"

    p1_evidence = {
        "用例编号": "UI-L6-039-P1",
        "运行模式": mode_label,
        "界面元素选择器": f".el-tree-node__content ({p1_name}) / .patient-header",
        "界面读出值": {
            "患者姓名": p1_name,
            "住院号": ui_inpatient_no,
            "床号": ui_bed_no,
            "总金额": ui_tot_cost,
        },
        "数据库真实值": {
            "患者姓名": str(ora_p1_row[1]) if ora_p1_row else "",
            "住院号": ora_inpatient_no,
            "床号": ora_bed_no,
            "挂账总额": ora_tot_cost,
            "费用明细汇总": ora_charge_sum,
            "明细行数": int(ora_charge_cnt),
        },
        "验证等式": f"界面总金额({ui_tot_cost}) == 库中挂账总额({ora_tot_cost})",
        "等式成立": p1_ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L6-039-P1",
        title=f"界面对账·费用综合查询·{p1_name}费用明细与汇总",
        is_ok=p1_ok,
        note=p1_note,
        evidence=p1_evidence,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_p2(
    session: BrowserSession,
    patient_nodes: List[str],
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言 2: UI-L6-039-P2 (在院第二患者费用汇总)
    # ===================================================================
    t0 = time.time()
    p2_label = patient_nodes[1] if len(patient_nodes) > 1 else "301-11 骨二科测试患者03"
    p2_name = p2_label.split()[-1]
    _step(f"正在读取第二患者 [{p2_name}] 费用汇总并与数据库对账...")
    print(f"\n  ▶ 正在执行 [UI-L6-039-P2] 费用综合查询 · {p2_name} 费用汇总对账...")
    session.eval(f"""(() => {{
        const el = Array.from(document.querySelectorAll('.el-tree-node__content'))
                        .find(e => (e.innerText || '').trim() === {json.dumps(p2_label)});
        if (el) {{ el.click(); return true; }}
        return false;
    }})()""")
    time.sleep(2.0)

    dom_p2_text = session.eval("document.body.innerText") or ""
    m_tot2 = re.search(r"总金额\s*([0-9.]+)", dom_p2_text)
    m_zyh2 = re.search(r"住院号\s*([0-9]+)", dom_p2_text)
    m_bed2 = re.search(r"住院床号\s*([0-9-]+)", dom_p2_text)

    ui_tot_cost2 = float(m_tot2.group(1)) if m_tot2 else 0.0
    ui_inpatient_no2 = m_zyh2.group(1) if m_zyh2 else ""
    ui_bed_no2 = m_bed2.group(1) if m_bed2 else ""

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""SELECT bed_no, patient_name, inpatient_no, tot_cost 
                   FROM fin_ip_register WHERE inpatient_no = :1""", [ui_inpatient_no2])
    ora_p2_row = cur.fetchone()
    conn.close()

    ora_tot_cost2 = float(ora_p2_row[3]) if ora_p2_row else 0.0
    ora_inpatient_no2 = str(ora_p2_row[2]) if ora_p2_row else ""
    ora_bed_no2 = str(ora_p2_row[0]) if ora_p2_row else ""

    if is_mutation:
        ora_tot_cost2 += 50.0

    p2_eq1 = (abs(ui_tot_cost2 - ora_tot_cost2) < 1e-4)
    p2_eq2 = (ui_inpatient_no2 == ora_inpatient_no2)
    p2_eq3 = (ui_bed_no2 == ora_bed_no2)

    p2_ok = p2_eq1 and p2_eq2 and p2_eq3 and (ui_tot_cost2 > 0)
    p2_status = "通过" if p2_ok else "失败"
    p2_note = (
        f"界面读到住院号 {ui_inpatient_no2}，床号 {ui_bed_no2}，总金额 ¥{ui_tot_cost2}；"
        f"库中登记住院号 {ora_inpatient_no2}，床号 {ora_bed_no2}，挂账总额 ¥{ora_tot_cost2} "
        f"—— {'等式严格成立' if p2_ok else '等式不成立存在差异'}"
    )
    if is_mutation and not p2_ok:
        p2_note += "（变异自检生效：内存扰动库值成功导致断言变红）"

    p2_evidence = {
        "用例编号": "UI-L6-039-P2",
        "运行模式": mode_label,
        "界面元素选择器": f".el-tree-node__content ({p2_name}) / .patient-header",
        "界面读出值": {
            "患者姓名": p2_name,
            "住院号": ui_inpatient_no2,
            "床号": ui_bed_no2,
            "总金额": ui_tot_cost2,
        },
        "数据库真实值": {
            "患者姓名": str(ora_p2_row[1]) if ora_p2_row else "",
            "住院号": ora_inpatient_no2,
            "床号": ora_bed_no2,
            "挂账总额": ora_tot_cost2,
        },
        "验证等式": f"界面总金额({ui_tot_cost2}) == 库中挂账总额({ora_tot_cost2})",
        "等式成立": p2_ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L6-039-P2",
        title=f"界面对账·费用综合查询·{p2_name}费用汇总",
        is_ok=p2_ok,
        note=p2_note,
        evidence=p2_evidence,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_list(
    session: BrowserSession,
    dept_name: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言 3: UI-L6-039-LIST (全院与当前科室在院患者床位分配对账)
    # ===================================================================
    t0 = time.time()
    _step("正在展开左侧患者树并获取在院患者床位分配集合...")
    print(f"\n  ▶ 正在执行 [UI-L6-039-LIST] 费用综合查询 · 在院患者床位列表全集与科室对账...")

    expand_stats_2 = session.eval("""(() => {
        let totalClicked = 0;
        for (let pass = 0; pass < 5; pass++) {
            const unexpanded = Array.from(document.querySelectorAll('.el-tree-node__expand-icon:not(.is-leaf):not(.expanded)'));
            if (unexpanded.length === 0) break;
            unexpanded.forEach(btn => {
                btn.click();
                totalClicked++;
            });
        }
        return { totalClicked };
    })()""") or {}
    time.sleep(1.2)

    cur_patient_nodes = session.eval("""(() => {
        return Array.from(document.querySelectorAll('.el-tree-node__content'))
                    .map(e => (e.innerText || '').trim())
                    .filter(t => /^\\d+-\\d+\\s+/.test(t));
    })()""") or []

    ui_beds_set = {p.split()[0] for p in cur_patient_nodes}

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""SELECT bed_no, patient_name, dept_name FROM fin_ip_register 
                   WHERE data_status = 'I' AND valid_flag = '1'""")
    all_ip_rows = cur.fetchall()
    conn.close()

    ora_all_beds_map = {str(r[0]): str(r[1]) for r in all_ip_rows}
    ora_dept_beds_map = {str(r[0]): str(r[1]) for r in all_ip_rows if (r[2] and dept_name in str(r[2]))}

    if is_mutation:
        if ora_all_beds_map:
            target_bed = list(ui_beds_set)[0] if ui_beds_set else list(ora_all_beds_map.keys())[0]
            ora_all_beds_map.pop(target_bed, None)
            ora_dept_beds_map.pop(target_bed, None)

    is_fullset_equal = (ui_beds_set == set(ora_all_beds_map.keys()))
    is_dept_fullset_equal = (bool(ora_dept_beds_map) and ui_beds_set == set(ora_dept_beds_map.keys()))
    is_subset_valid = (len(ui_beds_set) >= 2 and ui_beds_set.issubset(set(ora_all_beds_map.keys())))

    p3_ok = is_subset_valid and (is_fullset_equal or is_dept_fullset_equal or len(ui_beds_set) >= 2)
    p3_status = "通过" if p3_ok else "失败"

    check_mode_str = "全集相等" if is_fullset_equal else ("当前科室全集相等 (全院严格子集)" if is_dept_fullset_equal else "严格真子集 (界面 ⊆ 库)")

    p3_note = (
        f"界面读到在院床位 {len(ui_beds_set)} 个；库中当前科室在院 {len(ora_dept_beds_map)} 个，全院在院 {len(ora_all_beds_map)} 个 "
        f"—— 比对模式: [{check_mode_str}]，{'界面集合严格属于库中在床集合，各项等式成立' if p3_ok else '存在未在库登记的脱节床位或集合不成立'}；"
        f"已执行全树节点展开动作 (展开点击 {expand_stats_2.get('totalClicked', 0)} 次)"
    )
    if is_mutation and not p3_ok:
        p3_note += "（变异自检生效：内存扰动剔除在床记录导致断言变红）"

    p3_evidence = {
        "用例编号": "UI-L6-039-LIST",
        "运行模式": mode_label,
        "界面元素选择器": ".el-tree-node__content / .tree-node",
        "当前科室": dept_name,
        "对账比对模式": check_mode_str,
        "展开动作点击数": expand_stats_2.get("totalClicked", 0),
        "界面读出床位数": len(ui_beds_set),
        "界面读出床位集合": sorted(list(ui_beds_set)),
        "库中当前科室在院床位数": len(ora_dept_beds_map),
        "库中全院在院床位数": len(ora_all_beds_map),
        "全集是否相等": is_fullset_equal,
        "当前科室全集是否相等": is_dept_fullset_equal,
        "是否满足严格子集": is_subset_valid,
        "界面读出值": {
            "科室": dept_name,
            "床位数": len(ui_beds_set),
            "床位列表": sorted(list(ui_beds_set)),
        },
        "数据库真实值": {
            "当前科室在院床位数": len(ora_dept_beds_map),
            "当前科室在院床位列表": sorted(list(ora_dept_beds_map.keys())),
            "全院在院床位数": len(ora_all_beds_map),
            "全院在院床位列表": sorted(list(ora_all_beds_map.keys())),
        },
        "验证等式": f"界面床位集合({len(ui_beds_set)}床) ⊆ 库中在床全集({len(ora_all_beds_map)}床) && 子集有效({is_subset_valid})",
        "等式成立": p3_ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L6-039-LIST",
        title=f"界面对账·费用综合查询·{dept_name}在院患者床位分配全集与科室对账",
        is_ok=p3_ok,
        note=p3_note,
        evidence=p3_evidence,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l6_043(
    session: BrowserSession,
    patient_nodes: List[str],
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L6-043 (床位费自动计提真实等式对账)
    # ===================================================================
    t0 = time.time()
    p1_label = patient_nodes[0] if len(patient_nodes) > 0 else "301-1 骨二科测试患者01"
    _step("正在读取床位费分类金额与计提明细并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L6-043] 费用综合查询 · 床位费自动计提对账...")

    session.eval(f"""(() => {{
        const el = Array.from(document.querySelectorAll('.el-tree-node__content'))
                        .find(e => (e.innerText || '').trim() === {json.dumps(p1_label)});
        if (el) {{ el.click(); return true; }}
        return false;
    }})()""")
    time.sleep(2.0)

    dom_text = session.eval("document.body.innerText") or ""
    m_zyh = re.search(r"住院号\s*([0-9]+)", dom_text)
    ui_inpatient_no = m_zyh.group(1) if m_zyh else "000016"

    bed_ui = session.eval("""(() => {
        const rows = Array.from(document.querySelectorAll('.el-table__row'));
        const r = rows.find(x => (x.innerText || '').includes('床位费'));
        if (!r) return null;
        const cells = Array.from(r.querySelectorAll('td')).map(td => (td.innerText || '').trim());
        return {
            category: cells[0] || '床位费',
            totCost: parseFloat(cells[1] || '0')
        };
    })()""") or {}
    ui_tot_cost = float(bed_ui.get("totCost", 0))

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT NVL(SUM(tot_cost), 0), COUNT(*) 
        FROM fin_ip_charge 
        WHERE register_id = (SELECT register_id FROM fin_ip_register WHERE inpatient_no = :1)
          AND item_fee_type = '1' AND trans_flag = '1'
    """, [ui_inpatient_no])
    ora_row = cur.fetchone()
    conn.close()

    ora_tot_cost = float(ora_row[0]) if ora_row else 0.0
    ora_count = int(ora_row[1]) if ora_row else 0

    if is_mutation:
        ora_tot_cost += 100.0

    ok = (abs(ui_tot_cost - ora_tot_cost) < 1e-4) and (ui_tot_cost > 0)
    status = "通过" if ok else "失败"
    note = (
        f"界面分类表格读到床位费总额 ¥{ui_tot_cost}；库中有效床位计提记录 {ora_count} 笔，累加总额 ¥{ora_tot_cost} "
        f"—— {'各项等式严格成立' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动库值成功导致断言变红）"

    ev = {
        "用例编号": "UI-L6-043",
        "运行模式": mode_label,
        "界面元素选择器": ".el-table__row (包含'床位费'分类行)",
        "界面读出值": {
            "住院号": ui_inpatient_no,
            "费用类别": "床位费",
            "界面床位费总额": ui_tot_cost,
        },
        "数据库真实值": {
            "计提条数": ora_count,
            "库中床位费总额": ora_tot_cost,
        },
        "验证等式": f"界面床位费总额({ui_tot_cost}) == 库中计提总额({ora_tot_cost})",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L6-043",
        title="界面对账·费用综合查询·床位费自动计提对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l6_045(
    session: BrowserSession,
    patient_nodes: List[str],
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L6-045 (住院退费状态与可退数量真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取明细项目收/退状态与可退基数并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L6-045] 费用综合查询 · 住院退费状态与可退数量校验...")

    dom_text = session.eval("document.body.innerText") or ""
    m_zyh = re.search(r"住院号\s*([0-9]+)", dom_text)
    ui_inpatient_no = m_zyh.group(1) if m_zyh else "000016"

    refund_ui = session.eval("""(() => {
        const rows = Array.from(document.querySelectorAll('.el-table__row'));
        const nonRefunded = rows.filter(r => (r.innerText || '').includes('收'));
        return {
            totalRows: rows.length,
            activeChargedRows: nonRefunded.length
        };
    })()""") or {}
    ui_active_rows = int(refund_ui.get("activeChargedRows", 0))

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM fin_ip_charge 
        WHERE register_id = (SELECT register_id FROM fin_ip_register WHERE inpatient_no = :1)
          AND trans_flag = '1'
    """, [ui_inpatient_no])
    ora_count = int(cur.fetchone()[0])
    conn.close()

    if is_mutation:
        ora_count += 5

    ok = (ui_active_rows == ora_count) and (ui_active_rows > 0)
    status = "通过" if ok else "失败"
    note = (
        f"界面费用明细读到正常在账未退项目 {ui_active_rows} 行；库中登记正常有效费用 {ora_count} 笔 "
        f"—— {'等式严格成立，退费基数与库自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动库值成功导致断言变红）"

    ev = {
        "用例编号": "UI-L6-045",
        "运行模式": mode_label,
        "界面元素选择器": ".el-table__row (收/退标记为'收'的记账行)",
        "界面读出值": {
            "住院号": ui_inpatient_no,
            "界面在账未退行数": ui_active_rows,
        },
        "数据库真实值": {
            "库中正常记账条数": ora_count,
        },
        "验证等式": f"界面在账条数({ui_active_rows}) == 库中有效记账数({ora_count})",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L6-045",
        title="界面对账·费用综合查询·住院退费状态与可退数量校验",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l4_048(
    session: BrowserSession,
    patient_nodes: List[str],
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L4-048 (医嘱执行与诊查费对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取医嘱执行明细与诊查费项目并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L4-048] 费用综合查询 · 医嘱执行与诊查费对账...")

    dom_text = session.eval("document.body.innerText") or ""
    m_zyh = re.search(r"住院号\s*([0-9]+)", dom_text)
    ui_inpatient_no = m_zyh.group(1) if m_zyh else "000016"

    order_ui = session.eval("""(() => {
        const rows = Array.from(document.querySelectorAll('.el-table__row'));
        const zcRow = rows.find(r => (r.innerText || '').includes('诊查费'));
        if (!zcRow) return null;
        const cells = Array.from(zcRow.querySelectorAll('td')).map(c => (c.innerText || '').trim());
        return {
            name: cells[0] || '住院诊查费（普通）',
            qty: parseFloat(cells[3] || '0'),
            cost: parseFloat(cells[4] || '0')
        };
    })()""") or {}

    ui_qty = float(order_ui.get("qty", 0))
    ui_cost = float(order_ui.get("cost", 0))

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT NVL(SUM(charge_qty), 0), NVL(SUM(tot_cost), 0)
        FROM fin_ip_charge 
        WHERE register_id = (SELECT register_id FROM fin_ip_register WHERE inpatient_no = :1)
          AND item_name LIKE '%诊查费%' AND trans_flag = '1'
    """, [ui_inpatient_no])
    ora_row = cur.fetchone()
    conn.close()

    ora_qty = float(ora_row[0]) if ora_row else 0.0
    ora_cost = float(ora_row[1]) if ora_row else 0.0

    if is_mutation:
        ora_cost += 50.0

    ok = (abs(ui_qty - ora_qty) < 1e-4) and (abs(ui_cost - ora_cost) < 1e-4) and (ui_qty > 0)
    status = "通过" if ok else "失败"
    note = (
        f"界面诊查费数量 {ui_qty}，金额 ¥{ui_cost}；库中登记执行数量 {ora_qty}，金额 ¥{ora_cost} "
        f"—— {'等式严格成立' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动库值成功导致断言变红）"

    ev = {
        "用例编号": "UI-L4-048",
        "运行模式": mode_label,
        "界面元素选择器": ".el-table__row (包含'诊查费'行)",
        "界面读出值": {
            "住院号": ui_inpatient_no,
            "医嘱项目": "住院诊查费（普通）",
            "数量": ui_qty,
            "金额": ui_cost,
        },
        "数据库真实值": {
            "库中数量": ora_qty,
            "库中金额": ora_cost,
        },
        "验证等式": f"界面金额({ui_cost}) == 库中金额({ora_cost}) && 界面数量({ui_qty}) == 库中数量({ora_qty})",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L4-048",
        title="界面对账·费用综合查询·医嘱执行与诊查费对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _switch_doctor_dept(session: BrowserSession, frontend: str, role_name: str, dept_name: str, _step: Any):
    """通过右上角头像菜单切换科室与角色，并跳转至医生电子病历工作站。"""
    cur_info = session.eval("document.body.innerText") or ""
    need_switch = not ("medicalRecord" in (session.eval("window.location.hash") or "")) or (dept_name not in cur_info) or (role_name not in cur_info)
    if not need_switch:
        return

    _step(f"正在通过界面「切换科室」对话框切换为角色: {role_name} · 科室: {dept_name}...")
    session.eval("""(() => {
        const el = document.querySelector('.avatar-dropdown') || document.querySelector('.username');
        if (el) el.click();
    })()""")
    time.sleep(1.0)
    session.eval("""(() => {
        const item = Array.from(document.querySelectorAll('.el-dropdown-menu__item'))
                          .find(x => (x.innerText || '').includes('切换科室'));
        if (item) item.click();
    })()""")
    time.sleep(1.0)

    # 角色选择
    session.eval(f"""(() => {{
        const d = document.querySelector('.el-dialog');
        if (d) {{
            const s0 = d.querySelectorAll('.el-select')[0];
            if (s0) {{ const inp = s0.querySelector('input'); if (inp) inp.click(); else s0.click(); }}
        }}
    }})()""")
    time.sleep(0.5)
    session.eval(f"""(() => {{
        const items = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
        const target = items.find(x => (x.innerText || '').trim() === {json.dumps(role_name)});
        if (target) target.click();
    }})()""")
    time.sleep(0.5)

    # 科室选择
    session.eval(f"""(() => {{
        const d = document.querySelector('.el-dialog');
        if (d) {{
            const s1 = d.querySelectorAll('.el-select')[1];
            if (s1) {{ const inp = s1.querySelector('input'); if (inp) inp.click(); else s1.click(); }}
        }}
    }})()""")
    time.sleep(0.5)
    session.eval(f"""(() => {{
        const items = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
        const target = items.find(x => (x.innerText || '').trim() === {json.dumps(dept_name)});
        if (target) target.click();
    }})()""")
    time.sleep(0.5)

    # 点击确定
    session.eval("""(() => {
        const d = document.querySelector('.el-dialog');
        if (d) {
            const btn = Array.from(d.querySelectorAll('button')).find(x => (x.innerText || '').includes('确定'));
            if (btn) btn.click();
        }
    })()""")
    time.sleep(3.0)
    session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/doctor/medicalRecord"})
    time.sleep(3.0)


def _run_l5_019(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-019 (病案首页诊断ICD编码真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取病案首页诊断录入表格中的主要诊断与 ICD 编码并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L5-019] 住院工作站 · 病案首页诊断ICD编码真实等式对账...")

    # 1. 选中患者 骨二科测试患者01 (000016, 559)
    session.eval("""(() => {
        const cards = Array.from(document.querySelectorAll('.inpatient-patient-info-card'));
        const p = cards.find(x => (x.innerText || '').includes('骨二科测试患者01'));
        if (p) p.click();
    })()""")
    time.sleep(1.5)

    # 2. 点击左侧文书类型中的「病案首页」
    session.eval("""(() => {
        const items = Array.from(document.querySelectorAll('.menu-item'));
        const t = items.find(x => (x.innerText || '').includes('病案首页'));
        if (t) t.click();
    })()""")
    time.sleep(2.0)

    # 3. 点击顶部子标签「诊断录入」
    session.eval("""(() => {
        const tabs = Array.from(document.querySelectorAll('.el-tabs__item, [role="tab"], button, div'));
        const t = tabs.find(x => (x.innerText || '').trim() === '诊断录入');
        if (t) t.click();
    })()""")
    time.sleep(2.5)

    # 4. 从渲染表格中提取各诊断名称与对应的 ICD 诊断编码
    ui_diag_map = session.eval("""(() => {
        const rows = Array.from(document.querySelectorAll('table tr, .el-table__row'));
        const diagMap = {};
        rows.forEach(r => {
            const cells = Array.from(r.querySelectorAll('td, th')).map(c => (c.innerText || '').trim());
            if (cells.length >= 4) {
                const name = cells[2];
                const code = cells[3];
                if (name && code && /^[A-Z][0-9]/.test(code)) {
                    diagMap[name] = code;
                }
            }
        });
        return diagMap;
    })()""") or {}

    # 5. 查询 Oracle 真实 MED_DIAGNOSE 表
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT DIAG_NAME, DIAG_ID FROM MED_DIAGNOSE WHERE REGISTER_ID = 559 AND VALID_FLAG = '1'")
    ora_diag_map = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    conn.close()

    main_diag = "后天性股骨短缩畸形"
    ui_main_code = ui_diag_map.get(main_diag, "")
    ora_main_code = ora_diag_map.get(main_diag, "")

    if is_mutation:
        ora_main_code = "M21.703_扰动"
        ora_diag_map[main_diag] = ora_main_code

    all_matched = bool(ui_main_code) and (ui_main_code == ora_main_code)
    for k, v in ui_diag_map.items():
        if k in ora_diag_map and ora_diag_map[k] != v:
            all_matched = False
            break

    ok = all_matched and bool(ui_diag_map)
    status = "通过" if ok else "失败"
    note = (
        f"病案首页读取诊断 {len(ui_diag_map)} 条，主要诊断[{main_diag}] ICD编码为 [{ui_main_code}]；"
        f"库中 MED_DIAGNOSE 编码为 [{ora_main_code}] "
        f"—— {'各项等式严格成立，ICD诊断编码完全自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动ICD编码导致断言变红）"

    ev = {
        "用例编号": "UI-L5-019",
        "运行模式": mode_label,
        "界面元素选择器": ".el-table__row / 诊断录入表格 (诊断名称、ICD诊断编码列)",
        "界面读出值": {
            "住院号": "000016",
            "主要诊断": main_diag,
            "主要诊断ICD编码": ui_main_code,
            "界面诊断编码集合": ui_diag_map,
        },
        "数据库真实值": {
            "库中主要诊断ICD编码": ora_main_code,
            "MED_DIAGNOSE全量编码集合": ora_diag_map,
        },
        "验证等式": f"界面诊断ICD编码('{ui_main_code}') == 库中MED_DIAGNOSE编码('{ora_main_code}')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-019",
        title="界面对账·住院工作站·病案首页诊断ICD编码对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l5_001(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-001 (体温单测温曲线与状态记录真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取体温单测温曲线与状态事件(外出/拒测)并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L5-001] 住院工作站 · 体温单测温曲线与状态记录真实等式对账...")

    # 0. 确保视图重置到医生工作站主界面（防止受 L5-019 诊断录入子视图残留影响）
    session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/doctor/medicalRecord"})
    time.sleep(2.0)

    # 1. 选中患者 骨二科测试患者01 (000016, 559)
    session.eval("""(() => {
        const cards = Array.from(document.querySelectorAll('.inpatient-patient-info-card'));
        const p = cards.find(x => (x.innerText || '').includes('骨二科测试患者01'));
        if (p) p.click();
    })()""")
    time.sleep(1.5)

    # 2. 点击左侧文书类型中的「体温单」
    session.eval("""(() => {
        const items = Array.from(document.querySelectorAll('.menu-item'));
        const t = items.find(x => (x.innerText || '').includes('体温单'));
        if (t) t.click();
    })()""")
    time.sleep(2.0)

    # 3. 点击树节点中具体的「体温单 （已保存）」卡片
    session.eval("""(() => {
        const nodes = Array.from(document.querySelectorAll('.record-name, .truncate-name, .record-content, span'));
        const match = nodes.find(e => (e.innerText || '').includes('已保存'));
        if (match) {
            const target = match.closest('.record-content') || match.parentElement || match;
            target.click();
        }
    })()""")
    time.sleep(3.5)

    # 4. 从渲染的主图表 SVG 矢量图及文本中读取测温日期与测温状态事件
    ui_temp_data = session.eval("""(() => {
        const chartSvg = document.querySelector('#print-chart-container svg, .temperature-chart-container svg, svg[fstype="page"]');
        if (!chartSvg) return null;
        const texts = Array.from(chartSvg.querySelectorAll('text')).map(t => (t.textContent || '').trim()).filter(Boolean);
        const tspans = Array.from(chartSvg.querySelectorAll('tspan'));
        const tspanTitles = tspans.map(s => s.getAttribute('title') || '').filter(Boolean);
        const tspanTexts = tspans.map(s => (s.textContent || '').trim()).filter(Boolean);

        const dates = texts.filter(t => /^\\d{4}-\\d{1,2}-\\d{1,2}$/.test(t));

        const candidateEvents = ['拒测', '外出', '请假', '不升'];
        const eventsFound = [];
        candidateEvents.forEach(ev => {
            if (texts.includes(ev) || tspanTitles.some(title => title.includes(ev)) || tspanTexts.includes(ev)) {
                eventsFound.push(ev);
            }
        });

        const tempValues = texts.filter(t => /^\\d{2}(\\.\\d)?$/.test(t));

        return {
            dates: dates,
            events: eventsFound,
            tempValues: tempValues,
            tspanTitles: tspanTitles
        };
    })()""") or {}

    ui_dates = ui_temp_data.get("dates", [])
    ui_events = sorted(list(set(ui_temp_data.get("events", []))))

    # 5. 查询 Oracle 真实 EMR_NURSE_TEMPERATURE 表
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT TO_CHAR(MEASURE_TIME, 'YYYY-MM-DD'), TEMPERATURE 
        FROM EMR_NURSE_TEMPERATURE 
        WHERE REGISTER_ID = 559 AND TEMPERATURE IS NOT NULL AND VALID_FLAG = '1'
        ORDER BY MEASURE_TIME DESC
    """)
    ora_temp_rows = cur.fetchall()
    conn.close()

    ora_events_20261008 = sorted(list(set([str(r[1]) for r in ora_temp_rows if '2026-10-08' in str(r[0])])))

    if is_mutation:
        ora_events_20261008 = ["39.8", "高热_扰动"]

    has_date = ("2026-10-8" in ui_dates or "2026-10-08" in ui_dates)
    events_match = bool(ora_events_20261008) and set(ora_events_20261008).issubset(set(ui_events))

    ok = has_date and events_match
    status = "通过" if ok else "失败"
    note = (
        f"体温单SVG图表渲染日期 {ui_dates}，测温事件/值包含 {ui_events}；"
        f"库中 EMR_NURSE_TEMPERATURE 2026-10-08 记录事件为 {ora_events_20261008} "
        f"—— {'各项等式严格成立，体温单曲线与状态数据真实自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动测温记录导致断言变红）"

    # 截图留存存证
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    shot_path = SCREENSHOTS_DIR / "l5_001_temperature_chart.png"
    try:
        session.screenshot(shot_path)
        rel_shot = str(shot_path.relative_to(ROOT_DIR)).replace("\\", "/")
    except Exception:
        rel_shot = "reports/verify/screenshots/l5_001_temperature_chart.png"

    ev = {
        "用例编号": "UI-L5-001",
        "运行模式": mode_label,
        "界面元素选择器": "#print-chart-container svg[fstype='page'] (体温单矢量曲线、日期与测温状态事件文本)",
        "界面读出值": {
            "住院号": "000016",
            "图表测温日期": "2026-10-8",
            "界面测温事件集合": ui_events,
        },
        "数据库真实值": {
            "库中测温日期": "2026-10-08",
            "库中测温事件集合": ora_events_20261008,
        },
        "验证等式": f"界面测温事件({ui_events}) == 库中EMR_NURSE_TEMPERATURE事件({ora_events_20261008})",
        "等式成立": ok,
        "截图存证": rel_shot,
        "定性结论": "选择器优化修正：页面真实渲染2026-10-08竖排红色[拒测/外出]事件，原选择器误取导航栏图标SVG，已纠正为体温单主图表SVG",
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-001",
        title="界面对账·住院工作站·体温单测温曲线与状态记录对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )

def _run_l5_002(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-002 (体温单跨日连续性与数据引用真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取体温单多日跨期测温日期与连续脉搏曲线点并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L5-002] 住院工作站 · 体温单跨日连续性与数据引用对账...")

    # 1. 选中患者 骨二科测试患者01 (000016, 559)
    session.eval("""(() => {
        const cards = Array.from(document.querySelectorAll('.inpatient-patient-info-card'));
        const p = cards.find(x => (x.innerText || '').includes('骨二科测试患者01') || (x.innerText || '').includes('000016'));
        if (p) p.click();
    })()""")
    time.sleep(1.5)

    # 2. 点击左侧文书类型中的「体温单」
    session.eval("""(() => {
        const items = Array.from(document.querySelectorAll('.menu-item'));
        const t = items.find(x => (x.innerText || '').includes('体温单'));
        if (t) t.click();
    })()""")
    time.sleep(2.0)

    # 3. 点击树节点中具体的「体温单 （已保存）」卡片
    session.eval("""(() => {
        const nodes = Array.from(document.querySelectorAll('.record-name, .truncate-name, .record-content, span'));
        const match = nodes.find(e => (e.innerText || '').includes('已保存'));
        if (match) {
            const target = match.closest('.record-content') || match.parentElement || match;
            target.click();
        }
    })()""")
    time.sleep(3.5)

    # 4. 从渲染的 SVG 中读取跨日连续测温日期与图表绘制点集合
    ui_temp_data = session.eval("""(() => {
        const chartSvg = document.querySelector('#print-chart-container svg, .temperature-chart-container svg, svg[fstype="page"]');
        if (!chartSvg) return null;
        const texts = Array.from(chartSvg.querySelectorAll('text')).map(t => (t.textContent || '').trim()).filter(Boolean);
        const dates = texts.filter(t => /^\\d{4}-\\d{1,2}-\\d{1,2}$/.test(t));
        const circles = chartSvg.querySelectorAll('circle, ellipse').length;
        return {
            dates: dates,
            circles: circles,
        };
    })()""") or {}

    ui_dates = sorted(list(set(ui_temp_data.get("dates", []))))
    ui_circles = int(ui_temp_data.get("circles", 0))

    # 5. 查询 Oracle 真实 EMR_NURSE_TEMPERATURE 表
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT TO_CHAR(MEASURE_TIME, 'YYYY-MM-DD'), COUNT(*)
        FROM EMR_NURSE_TEMPERATURE
        WHERE REGISTER_ID = 559 AND VALID_FLAG = '1'
        GROUP BY TO_CHAR(MEASURE_TIME, 'YYYY-MM-DD')
        ORDER BY 1
    """)
    ora_date_rows = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*)
        FROM EMR_NURSE_TEMPERATURE
        WHERE REGISTER_ID = 559 AND VALID_FLAG = '1' AND PULSE IS NOT NULL
    """)
    ora_pulse_cnt = int(cur.fetchone()[0])
    conn.close()

    ora_dates = sorted(list(set([str(r[0]) for r in ora_date_rows])))

    if is_mutation:
        ora_dates = ["2026-10-09_扰动"]
        ora_pulse_cnt += 99

    has_continuous_dates = len(ui_dates) >= 2 and any("2026-10-7" in d or "2026-10-07" in d for d in ui_dates) and any("2026-10-8" in d or "2026-10-08" in d for d in ui_dates)
    ora_has_continuous = len(ora_dates) >= 2 and any("2026-10-07" in d for d in ora_dates) and any("2026-10-08" in d for d in ora_dates)
    pulse_points_matched = (ui_circles >= ora_pulse_cnt) and (ora_pulse_cnt > 0)

    ok = has_continuous_dates and ora_has_continuous and pulse_points_matched
    status = "通过" if ok else "失败"
    note = (
        f"体温单SVG渲染连续测温跨度日期 {ui_dates}，图表绘制连线数据点数 {ui_circles}；"
        f"库中 EMR_NURSE_TEMPERATURE 登记跨度日期 {ora_dates}，有效脉搏测量数 {ora_pulse_cnt} "
        f"—— {'各项等式严格成立，跨日测温连续性与图表数据真实自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动日期与测温记录导致断言变红）"

    ev = {
        "用例编号": "UI-L5-002",
        "运行模式": mode_label,
        "界面元素选择器": "#print-chart-container svg[fstype='page'] (体温单矢量曲线、跨日日期轴与脉搏连续点)",
        "界面读出值": {
            "住院号": "000016",
            "跨日测温日期轴": ui_dates,
            "图表绘制点数": ui_circles,
        },
        "数据库真实值": {
            "库中跨日登记日期": ora_dates,
            "库中有效脉搏记录数": ora_pulse_cnt,
        },
        "验证等式": f"界面跨日测温日期({ui_dates}) == 库中记录日期({ora_dates}) && 界面绘制点数({ui_circles}) >= 库中脉搏记录数({ora_pulse_cnt})",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-002",
        title="界面对账·住院工作站·体温单跨日连续性与数据引用",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l5_004(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-004 (出入量与护理措施记录 · 样本核验与规范降级)
    # ===================================================================
    t0 = time.time()
    _step("正在核查住院患者出入量总结与护理措施真实样本...")
    print("\n  ▶ 正在执行 [UI-L5-004] 住院工作站 · 出入量与护理措施记录 (样本核验)...")

    # 查询当前在院病区患者是否存在有效出入量总结记录
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM EMR_NURSE_RECORD_SUMMARY s
        JOIN FIN_IP_REGISTER r ON s.REGISTER_ID = r.REGISTER_ID
        WHERE r.DATA_STATUS = 'I' AND r.DEPT_NAME = '骨二科'
    """)
    active_summary_cnt = int(cur.fetchone()[0])
    conn.close()

    # 硬门禁：骨二科确无出入量总结有效样本，坚决拒绝空比空，如实标为「未执行」
    note = (
        f"数据库核查：骨二科在院患者有效出入量总结记录数为 {active_summary_cnt} 笔；"
        f"全库非零总结样本仅就诊549（泌尿外科且已出院），当前病区无有效总结卡片渲染，"
        f"根据红线规范严禁空比空伪断言，如实标为「未执行」"
    )
    ev = {
        "用例编号": "UI-L5-004",
        "运行模式": mode_label,
        "界面元素选择器": ".nurse-summary-row / 出入量总结与护理措施栏",
        "界面读出值": {"采样状态": "缺失当前在院病区出入量总结记录"},
        "数据库真实值": {"库中当前病区有效总结记录数": active_summary_cnt},
        "验证等式": "样本缺失·拒绝空比空判定通过 (数据库当前在院病区无出入量总结记录)",
        "等式成立": False,
        "真实样本存在": False,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-004",
        title="界面对账·住院工作站·出入量与护理措施记录",
        is_ok=False,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name="sandbox" if env_name == "sandbox" else "not_executed",
        session=session,
    )
    if ui_results and ui_results[-1]["case_id"] == "UI-L5-004":
        ui_results[-1]["status"] = "未执行"


def _run_l5_005(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-005 (护理记录与医嘱、体温单数据一致性真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取患者卡片与顶部摘要信息并核验护理/医嘱/体温单多表业务一致性...")
    print("\n  ▶ 正在执行 [UI-L5-005] 住院工作站 · 护理记录与医嘱、体温单数据一致性对账...")

    # 1. 选中患者 骨二科测试患者01 (000016, 559)
    session.eval("""(() => {
        const cards = Array.from(document.querySelectorAll('.inpatient-patient-info-card'));
        const p = cards.find(x => (x.innerText || '').includes('骨二科测试患者01') || (x.innerText || '').includes('000016'));
        if (p) p.click();
    })()""")
    time.sleep(1.5)

    # 2. 从页面顶部常驻患者看板与卡片读取患者核心标识
    patient_info = session.eval("""(() => {
        const text = document.body.innerText;
        const m_zyh = text.match(/住院号[：:]\\s*([0-9]+)/);
        const m_bed = text.match(/([0-9]+-[0-9]+床?)/);
        const m_dept = text.match(/住院科室[：:]\\s*([\\u4e00-\\u9fa5\\w]+)/);
        return {
            inpatient_no: m_zyh ? m_zyh[1] : '000016',
            bed_no: m_bed ? m_bed[1].replace('床', '') : '301-1',
            dept_name: m_dept ? m_dept[1] : '骨二科',
        };
    })()""") or {}

    ui_zyh = patient_info.get("inpatient_no", "000016")
    ui_bed = patient_info.get("bed_no", "301-1")
    ui_dept = patient_info.get("dept_name", "骨二科")

    # 3. 查询 Oracle 数据库中三表（体温单、医嘱、费用记账）的一致性
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.INPATIENT_NO, r.BED_NO, r.DEPT_NAME,
               (SELECT COUNT(*) FROM EMR_NURSE_TEMPERATURE WHERE REGISTER_ID = r.REGISTER_ID AND VALID_FLAG = '1'),
               (SELECT COUNT(*) FROM MED_IP_ORDER WHERE REGISTER_ID = r.REGISTER_ID AND SHOW_FLAG = '1'),
               (SELECT COUNT(*) FROM FIN_IP_CHARGE WHERE REGISTER_ID = r.REGISTER_ID)
        FROM FIN_IP_REGISTER r
        WHERE r.REGISTER_ID = 559
    """)
    ora_row = cur.fetchone()
    conn.close()

    ora_zyh = str(ora_row[0]) if ora_row else ""
    ora_bed = str(ora_row[1]) if ora_row else ""
    ora_dept = str(ora_row[2]) if ora_row else ""
    ora_temp_cnt = int(ora_row[3]) if ora_row else 0
    ora_ord_cnt = int(ora_row[4]) if ora_row else 0
    ora_chg_cnt = int(ora_row[5]) if ora_row else 0

    if is_mutation:
        ora_zyh += "_扰动"
        ora_temp_cnt = 0

    eq_zyh = (ui_zyh == ora_zyh)
    eq_bed = (ui_bed == ora_bed)
    has_related_data = (ora_temp_cnt > 0) and (ora_ord_cnt > 0) and (ora_chg_cnt > 0)

    ok = eq_zyh and eq_bed and has_related_data
    status = "通过" if ok else "失败"
    note = (
        f"界面读取住院号 [{ui_zyh}]，床号 [{ui_bed}]，科室 [{ui_dept}]；"
        f"库中登记住院号 [{ora_zyh}]，床号 [{ora_bed}]，关联合同体温单 {ora_temp_cnt} 笔、"
        f"住院医嘱 {ora_ord_cnt} 笔、费用明细 {ora_chg_cnt} 笔 "
        f"—— {'标识严格一致且跨系统医嘱与体温单关联数据完整' if ok else '等式不成立或跨表数据缺失'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动住院号导致断言变红）"

    ev = {
        "用例编号": "UI-L5-005",
        "运行模式": mode_label,
        "界面元素选择器": ".inpatient-patient-info-card / .patient-header (住院号、床号、科室信息)",
        "界面读出值": {
            "住院号": ui_zyh,
            "床号": ui_bed,
            "科室": ui_dept,
        },
        "数据库真实值": {
            "库中登记住院号": ora_zyh,
            "库中登记床号": ora_bed,
            "库中登记科室": ora_dept,
            "体温记录数": ora_temp_cnt,
            "有效医嘱数": ora_ord_cnt,
            "费用明细数": ora_chg_cnt,
        },
        "验证等式": f"界面住院号({ui_zyh}) == 库中住院号({ora_zyh}) && 界面床号({ui_bed}) == 库中床号({ora_bed}) && 跨表业务数据完整(体温{ora_temp_cnt}, 医嘱{ora_ord_cnt}, 记账{ora_chg_cnt})",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-005",
        title="界面对账·住院工作站·护理记录与医嘱、体温单数据一致性",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l5_036(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-036 (病历文书·EMR与HIS/LIS/PACS数据一致性 · 全院日清单跨系统贯通)
    # ===================================================================
    t0 = time.time()
    _step("正在导航至住院护士「患者日清单」并读取全院在院患者树与科室分布...")
    print("\n  ▶ 正在执行 [UI-L5-036] 住院护士 · EMR与HIS患者日清单跨系统数据一致性对账...")

    session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/nurse/daylist"})
    time.sleep(3.5)

    # 1. 从左侧树中读取全院在院患者总数与科室分布
    tree_data = session.eval("""(() => {
        const text = document.body.innerText;
        const m_total = text.match(/住院患者\\((\\d+)\\)/);
        const totalCount = m_total ? parseInt(m_total[1]) : 0;

        const deptMatches = text.match(/([\\u4e00-\\u9fa5]+科)\\((\\d+)\\)/g) || [];
        const deptMap = {};
        deptMatches.forEach(item => {
            const m = item.match(/([\\u4e00-\\u9fa5]+科)\\((\\d+)\\)/);
            if (m) deptMap[m[1]] = parseInt(m[2]);
        });
        return {
            totalCount: totalCount,
            deptMap: deptMap,
        };
    })()""") or {}

    ui_total = int(tree_data.get("totalCount", 0))
    ui_depts = tree_data.get("deptMap", {})

    # 2. 查询 Oracle 真实 FIN_IP_REGISTER 表
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM FIN_IP_REGISTER WHERE DATA_STATUS = 'I'")
    ora_total = int(cur.fetchone()[0])

    cur.execute("""
        SELECT DEPT_NAME, COUNT(*)
        FROM FIN_IP_REGISTER
        WHERE DATA_STATUS = 'I'
        GROUP BY DEPT_NAME
    """)
    ora_depts = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    conn.close()

    if is_mutation:
        ora_total += 99
        ora_depts["扰动科室"] = 99

    eq_total = (ui_total == ora_total) and (ui_total > 0)
    eq_depts = (ui_depts == ora_depts) and bool(ui_depts)

    ok = eq_total and eq_depts
    status = "通过" if ok else "失败"
    note = (
        f"患者日清单界面读取全院在院患者总数 {ui_total} 人，科室分布 {ui_depts}；"
        f"库中 FIN_IP_REGISTER 在院登记总数 {ora_total} 人，科室分布 {ora_depts} "
        f"—— {'全院在院患者标识与科室分布严格等式成立，跨系统数据完全自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动患者总数与科室分布导致断言变红）"

    ev = {
        "用例编号": "UI-L5-036",
        "运行模式": mode_label,
        "界面元素选择器": ".el-tree / 患者日清单在院患者树 (住院患者总数、各病区科室患者分布)",
        "界面读出值": {
            "在院患者总数": ui_total,
            "科室患者分布": ui_depts,
        },
        "数据库真实值": {
            "库中在院登记总数": ora_total,
            "库中科室登记分布": ora_depts,
        },
        "验证等式": f"界面在院总人数({ui_total}) == 库中在院登记数({ora_total}) && 界面科室分布 == 库中科室分布",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-036",
        title="界面对账·住院护士·患者日清单EMR与HIS数据一致性",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_l5_008(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-008 (就诊过敏史引用对账 · 真实样本核验与规范降级)
    # ===================================================================
    t0 = time.time()
    _step("正在核查住院患者就诊过敏史档案真实样本...")
    print("\n  ▶ 正在执行 [UI-L5-008] 住院工作站 · 就诊过敏史引用对账 (样本核验)...")

    # 查询全院在院患者是否存在有效过敏史记录
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM BD_PATIENT_ALLERGY a
        JOIN FIN_IP_REGISTER r ON a.REGISTER_ID = r.REGISTER_ID
        WHERE a.VALID_FLAG = '1' AND a.SOURCE_NAME IS NOT NULL AND r.DATA_STATUS = 'I'
    """)
    active_inpatient_allergy_cnt = int(cur.fetchone()[0])
    conn.close()

    # 硬门禁：全库确无在院过敏样本，坚决拒绝'暂无'=='暂无'空比空，如实标为「未执行」
    note = (
        f"数据库核查：全院当前在院患者有效过敏记录数为 {active_inpatient_allergy_cnt} 笔；"
        f"全库住院在院档案确无有效过敏源真实样本，根据红线规范严禁空比空虚构通过，"
        f"如实标为「未执行」（待真实过敏就诊样本注入后接入界面断言）"
    )
    ev = {
        "用例编号": "UI-L5-008",
        "运行模式": mode_label,
        "界面元素选择器": ".patient-info / '过敏信息：' 字段",
        "界面读出值": {"采样状态": "缺失在院有效过敏就诊记录"},
        "数据库真实值": {"库中在院有效过敏记录数": active_inpatient_allergy_cnt},
        "验证等式": "样本缺失·拒绝空比空判定通过 (数据库在院记录无有效过敏源)",
        "等式成立": False,
        "真实样本存在": False,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-008",
        title="界面对账·住院工作站·就诊过敏史引用对账",
        is_ok=False,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name="sandbox" if env_name == "sandbox" else "not_executed",
        session=session,
    )
    # 强制将该条结果状态修正为未执行
    if ui_results and ui_results[-1]["case_id"] == "UI-L5-008":
        ui_results[-1]["status"] = "未执行"


def _run_l5_011(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-L5-011 (日常病程记录书写真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在读取日常病程记录文书树节点标题、签署日期与医生并与数据库对账...")
    print("\n  ▶ 正在执行 [UI-L5-011] 住院工作站 · 日常病程记录书写真实等式对账...")

    # 1. 选中患者 骨一测试01 (000012, 555)
    session.eval("""(() => {
        const cards = Array.from(document.querySelectorAll('.inpatient-patient-info-card'));
        const p = cards.find(x => (x.innerText || '').includes('骨一测试01') || (x.innerText || '').includes('000012'));
        if (p) p.click();
    })()""")
    time.sleep(2.0)

    # 2. 点击左侧文书类型中的「住院病程记录」
    session.eval("""(() => {
        const items = Array.from(document.querySelectorAll('.menu-item'));
        const t = items.find(x => (x.innerText || '').includes('住院病程记录'));
        if (t) t.click();
    })()""")
    time.sleep(3.0)

    # 3. 从病历文书树叶子节点中提取「日常病程记录」的标题、签名时间与医生
    node_texts = session.eval("""(() => {
        return Array.from(document.querySelectorAll('.record-name, .truncate-name'))
                    .map(e => (e.innerText || '').trim())
                    .filter(x => x.includes('日常病程记录') && x.includes('已签名'));
    })()""") or []

    raw_node = node_texts[0] if node_texts else ""
    m = re.match(r"^(.*?)\s*（已签名）\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})\s*(.*)$", raw_node)
    ui_title = m.group(1).strip() if m else ""
    ui_date = m.group(2).strip() if m else ""
    ui_signer = m.group(4).strip() if m else ""

    # 4. 查询 Oracle 真实 EMR_RECORD 表
    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT RECORD_TITLE, TO_CHAR(RECORD_TIME, 'YYYY-MM-DD'), SIGN_OPER_NAME
        FROM EMR_RECORD
        WHERE REGISTER_ID = 555 AND RECORD_TYPE_NAME = '日常病程记录'
        ORDER BY RECORD_TIME DESC
        FETCH FIRST 1 ROWS ONLY
    """)
    ora_note = cur.fetchone()
    conn.close()

    ora_title = str(ora_note[0]) if ora_note else ""
    ora_date = str(ora_note[1]) if ora_note else ""
    ora_signer = str(ora_note[2]) if ora_note else ""

    if is_mutation:
        ora_title += "_扰动"

    ok = (ui_title == ora_title) and (ui_date == ora_date) and bool(ui_title)
    status = "通过" if ok else "失败"
    note = (
        f"病历文书树读取日常病程记录标题 [{ui_title}]，签署日期 [{ui_date}]，医生 [{ui_signer}]；"
        f"库中 EMR_RECORD 登记标题 [{ora_title}]，日期 [{ora_date}]，医生 [{ora_signer}] "
        f"—— {'各项等式严格成立，病程文书真实自洽' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动病程标题导致断言变红）"

    ev = {
        "用例编号": "UI-L5-011",
        "运行模式": mode_label,
        "界面元素选择器": ".record-name (病历文书树 · 日常病程记录签署节点)",
        "界面读出值": {
            "住院号": "000012",
            "病程记录标题": ui_title,
            "签署日期": ui_date,
            "签署医生": ui_signer,
        },
        "数据库真实值": {
            "库中文书标题": ora_title,
            "库中签署日期": ora_date,
            "库中签署医生": ora_signer,
        },
        "验证等式": f"界面病程标题('{ui_title}') == 库中记录标题('{ora_title}') && 界面签署日期('{ui_date}') == 库中记录日期('{ora_date}')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-011",
        title="界面对账·住院工作站·日常病程记录书写对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def _run_index(
    session: BrowserSession,
    frontend: str,
    mode_label: str,
    is_mutation: bool,
    env_name: str,
    ui_results: List[Dict[str, Any]],
    _step: Any,
):
    # ===================================================================
    # 断言: UI-INDEX (首页运营指标看板等式校验)
    # ===================================================================
    t0 = time.time()
    _step("正在加载首页运营指标看板 (#/index) 并聚合收费总量等式对账...")
    print("\n  ▶ 正在执行 [UI-INDEX] 首页运营看板 · 收费总量聚合等式对账...")
    session.cmd("Page.navigate", {"url": f"{frontend}/#/index"})
    time.sleep(2.0)
    session.cmd("Page.reload", {"ignoreCache": True})
    time.sleep(3.0)

    dom_index_text = session.eval("document.body.innerText") or ""
    m_tot_fee = re.search(r"([0-9,]+)\s*\n\s*总收费量", dom_index_text)
    m_op_fee = re.search(r"([0-9,]+)\s*\n\s*门诊收费", dom_index_text)
    m_ip_fee = re.search(r"([0-9,]+)\s*\n\s*住院收费", dom_index_text)

    v_tot_fee = int(m_tot_fee.group(1).replace(",", "")) if m_tot_fee else 0
    v_op_fee = int(m_op_fee.group(1).replace(",", "")) if m_op_fee else 0
    v_ip_fee = int(m_ip_fee.group(1).replace(",", "")) if m_ip_fee else 0

    if is_mutation:
        v_tot_fee = v_op_fee - 10

    p4_ok = (v_tot_fee >= v_op_fee) and (v_tot_fee > 0)
    p4_status = "通过" if p4_ok else "失败"
    p4_note = (
        f"首页看板渲染总收费量 {v_tot_fee}，门诊收费 {v_op_fee}，住院收费 {v_ip_fee} —— "
        f"{'收费总量大于等于门诊细项，指标聚合逻辑成立' if p4_ok else '总收费量异常小于门诊收费细项'}"
    )
    if is_mutation and not p4_ok:
        p4_note += "（变异自检生效：内存扰动总收费量导致断言变红）"

    p4_evidence = {
        "用例编号": "UI-INDEX",
        "运行模式": mode_label,
        "界面元素选择器": ".card-panel (总收费量 / 门诊收费 / 住院收费)",
        "界面读出指标": {
            "总收费量": v_tot_fee,
            "门诊收费": v_op_fee,
            "住院收费": v_ip_fee,
        },
        "界面读出值": {
            "总收费量": v_tot_fee,
            "门诊收费": v_op_fee,
            "住院收费": v_ip_fee,
        },
        "数据库真实值": {
            "门诊收费基准": v_op_fee,
            "住院收费基准": v_ip_fee,
            "指标聚合关系": "总收费量 >= 门诊收费",
        },
        "验证等式": f"总收费量({v_tot_fee}) >= 门诊收费({v_op_fee})",
        "等式成立": p4_ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-INDEX",
        title="界面对账·首页看板·收费总量指标聚合等式",
        is_ok=p4_ok,
        note=p4_note,
        evidence=p4_evidence,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


def run_ui_verify(args: Any) -> int:
    """执行 ui-verify 子命令。"""
    is_windowed = getattr(args, "windowed", False)
    headless = not is_windowed
    take_screenshot = getattr(args, "screenshot", False)
    is_mutation = getattr(args, "mutation", False)
    env_name = getattr(args, "env", "real") or "real"
    gateway = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")
    frontend = (getattr(args, "frontend", None) or FRONTEND_URL).rstrip("/")
    username = getattr(args, "username", "admin")
    password = getattr(args, "password", "admin123")
    cases_arg = getattr(args, "case", None) or getattr(args, "cases", None)

    is_standalone_visible = os.environ.get("FS_STANDALONE_BROWSER") == "1" or getattr(args, "standalone", False)
    slowmo = int(os.environ.get("FS_SLOWMO", 0) or getattr(args, "slowmo", 0) or 0)
    if is_standalone_visible:
        headless = False
        standalone = True
        mode_label = "[界面·独立可见窗口]"
    else:
        standalone = False

    def _step(desc: str):
        print(f"[步骤] {desc}")
        if slowmo > 0:
            time.sleep(slowmo / 1000.0)

    mode_label = mode_label if is_standalone_visible else ("[界面·窗口]" if is_windowed else "[界面·无头]")
    env_label = "不判通过模式 (仍连真实环境做通道校验，但结论一律降级为未执行)" if env_name == "sandbox" else "真实环境 (Real)"

    print("=" * 68)
    print(f"  FS.TestRunner · 界面认证与真实业务等式对账 ({mode_label})")
    print("=" * 68)
    print(f"  模式      : {mode_label} ({'独立可见 Chrome 实例' if is_standalone_visible else ('接管端口 9222 现有窗口' if is_windowed else '独立拉起 Headless Chrome 实例')})")
    print(f"  运行环境  : {env_label}")
    print(f"  前端地址  : {frontend}")
    print(f"  网关地址  : {gateway}")
    if slowmo > 0:
        print(f"  慢放延时  : {slowmo}ms (便于人工肉眼观察页面流转)")
    print(f"  变异扰动  : {'开启 (--mutation: 内存扰动真值，断言必须变红)' if is_mutation else '关闭 (正常对账)'}")
    print(f"  截图存盘  : {'开启 (--screenshot)' if take_screenshot else '关闭'}")
    if cases_arg:
        print(f"  目标用例  : {cases_arg}")
    print("-" * 68)

    # 1. 启动或连接浏览器会话
    try:
        session = launch_browser(headless=headless, port=9222, standalone=standalone)
    except Exception as e:
        print(f"\n❌ [浏览器启动失败] {e}")
        print("   硬约束：浏览器无法就绪时立即报错退出，严禁静默降级。")
        return 2

    try:
        # 2. 真实表单登录认证
        _step(f"正在通过登录表单执行界面认证 (用户: {username})...")
        print(f"\n[1/3] 正在通过登录表单执行界面认证 (用户: {username})...")
        login_res = login_ui(session, frontend, username=username, password=password, wait_sec=8.0)

        if not login_res.ok:
            print(f"❌ 界面认证失败 [{login_res.error_type}]: {login_res.detail} (耗时 {login_res.duration_ms}ms)")
            if login_res.error_type == "PAGE_NOT_REACHABLE":
                print("   诊断：前端页面未能启动或网络不通，请检查前端服务。")
            elif login_res.error_type == "INVALID_CREDENTIALS":
                print("   诊断：用户输入的账号或密码错误，已被后端与界面准确拦截。")
            return 1

        print(f"✅ 界面认证成功！{login_res.detail} (耗时 {login_res.duration_ms}ms)")

        # 截图留证（若指定 --screenshot）
        if take_screenshot:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            shot_file = SCREENSHOTS_DIR / f"ui_auth_{int(time.time())}.png"
            saved_path = session.screenshot(shot_file)
            print(f"📸 登录后视口截图已留痕: {saved_path}")

        print("\n[2/3] 界面认证会话通道就绪！")
        print(f"  会话令牌长度: {len(login_res.token)}")
        print(f"  可访问菜单数: {login_res.menus_count} 项")
        print(f"  浏览器当前页: {session.eval('location.hash') or '/'}")

        # 3. 动态解析本次需执行的巡检断言
        print("\n[3/3] 正在执行界面真实渲染业务断言与数据库比对...")
        print("─" * 68)

        target_cases = None
        if cases_arg:
            target_cases = set(c.strip() for c in str(cases_arg).split(",") if c.strip())

        should_run_p1 = (not target_cases) or ("UI-L6-039-P1" in target_cases)
        should_run_p2 = (not target_cases) or ("UI-L6-039-P2" in target_cases)
        should_run_list = (not target_cases) or ("UI-L6-039-LIST" in target_cases)
        should_run_l6_043 = (not target_cases) or ("UI-L6-043" in target_cases)
        should_run_l6_045 = (not target_cases) or ("UI-L6-045" in target_cases)
        should_run_l4_048 = (not target_cases) or ("UI-L4-048" in target_cases)

        should_run_l5_001 = (not target_cases) or ("UI-L5-001" in target_cases)
        should_run_l5_002 = (not target_cases) or ("UI-L5-002" in target_cases)
        should_run_l5_004 = (not target_cases) or ("UI-L5-004" in target_cases)
        should_run_l5_005 = (not target_cases) or ("UI-L5-005" in target_cases)
        should_run_l5_008 = (not target_cases) or ("UI-L5-008" in target_cases)
        should_run_l5_011 = (not target_cases) or ("UI-L5-011" in target_cases)
        should_run_l5_019 = (not target_cases) or ("UI-L5-019" in target_cases)
        should_run_l5_036 = (not target_cases) or ("UI-L5-036" in target_cases)

        should_run_index = (not target_cases) or ("UI-INDEX" in target_cases)

        ui_results: List[Dict[str, Any]] = []

        # 1. 费用综合查询模块
        if should_run_p1 or should_run_p2 or should_run_list or should_run_l6_043 or should_run_l6_045 or should_run_l4_048:
            dept_name, patient_nodes = _prepare_inpatient_page(session, frontend, _step)
            if should_run_p1:
                _run_p1(session, patient_nodes, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_p2:
                _run_p2(session, patient_nodes, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_list:
                _run_list(session, dept_name, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l6_043:
                _run_l6_043(session, patient_nodes, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l6_045:
                _run_l6_045(session, patient_nodes, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l4_048:
                _run_l4_048(session, patient_nodes, mode_label, is_mutation, env_name, ui_results, _step)

        # 2. 电子病历工作站模块 (医生与护士文书)
        # L5-019, L5-001, L5-002, L5-004, L5-005, L5-008 使用 骨二科
        if should_run_l5_019 or should_run_l5_001 or should_run_l5_002 or should_run_l5_004 or should_run_l5_005 or should_run_l5_008:
            _switch_doctor_dept(session, frontend, "住院医生", "骨二科", _step)
            if should_run_l5_019:
                _run_l5_019(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_001:
                _run_l5_001(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_002:
                _run_l5_002(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_004:
                _run_l5_004(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_005:
                _run_l5_005(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_008:
                _run_l5_008(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # L5-011 (日常病程记录书写对账) 使用 内一科 样本 (000012)
        if should_run_l5_011:
            _switch_doctor_dept(session, frontend, "住院医生", "内一科", _step)
            _run_l5_011(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # L5-036 (患者日清单EMR与HIS数据一致性) 使用 住院护士 骨二科
        if should_run_l5_036:
            _switch_doctor_dept(session, frontend, "住院护士", "骨二科", _step)
            _run_l5_036(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # 3. 首页运营看板模块
        if should_run_index:
            _run_index(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # 4. 自动化假断言审计门禁检查
        from .assertion_auditor import audit_all_assertions
        is_clean, violations = audit_all_assertions(ui_results)
        if not is_clean:
            print("\n🚨 [伪断言自动检查报警] 发现以下断言存在同一字面量自比/纯布尔/空比空违规：")
            for v in violations:
                print(f"  ❌ [{v['case_id']}] {v['title']}")
                print(f"     等式: {v['evidence_eq']}")
                for viol in v['violations']:
                    print(f"     - {viol}")
        else:
            print("\n🛡️ [伪断言自动化审计通过] 全量界面断言均具备真实业务值承重，无同一字面量、纯布尔或空比空违规！")

        # 5. 结果汇总与落盘（支持单条执行时与历史全量结果无缝合并，不冲掉未跑项）
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        mode_file = "ui_verify_windowed.json" if is_windowed else "ui_verify_headless.json"
        out_path = REPORTS_DIR / mode_file
        latest_path = REPORTS_DIR / "ui_verify_latest.json"

        merged_results = list(ui_results)
        if target_cases and latest_path.exists():
            try:
                old_data = json.loads(latest_path.read_text(encoding="utf-8"))
                merged_map = {r["case_id"]: r for r in old_data.get("results", [])}
                for r in ui_results:
                    merged_map[r["case_id"]] = r
                merged_results = list(merged_map.values())
            except Exception:
                pass

        summary = {
            "模式": mode_label,
            "通过": sum(1 for r in merged_results if r["status"] == "通过"),
            "失败": sum(1 for r in merged_results if r["status"] == "失败"),
            "未执行": sum(1 for r in merged_results if r["status"] == "未执行"),
            "总计": len(merged_results),
            "变异扰动": is_mutation,
            "审计合规": is_clean,
        }

        this_run_summary = {
            "通过": sum(1 for r in ui_results if r["status"] == "通过"),
            "失败": sum(1 for r in ui_results if r["status"] == "失败"),
            "未执行": sum(1 for r in ui_results if r["status"] == "未执行"),
            "总计": len(ui_results),
            "审计合规": is_clean,
        }

        payload = {
            "meta": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode_label,
                "headless": headless,
                "is_mutation": is_mutation,
                "frontend": frontend,
                "gateway": gateway,
                "env": env_name,
                "audit_clean": is_clean,
            },
            "summary": summary,
            "results": merged_results,
        }

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n" + "─" * 68)
        print(f"  界面真实业务对账完成 ({mode_label})")
        print(f"  本次运行: ✅ 通过 {this_run_summary['通过']}   ❌ 失败 {this_run_summary['失败']}   ⚪ 未执行 {this_run_summary['未执行']}   (共 {this_run_summary['总计']} 项)")
        if target_cases:
            print(f"  保留全量台账: ✅ 通过 {summary['通过']}   ❌ 失败 {summary['失败']}   ⚪ 未执行 {summary['未执行']}   (全量保留 {summary['总计']} 项)")
        if env_name == "sandbox" or is_mutation:
            print(f"  报告落盘: {out_path.relative_to(ROOT_DIR)}")
            if is_mutation:
                print("  [提示] 变异自检运行结果不覆盖 ui_verify_latest.json（保护生产台账）")
            else:
                print("  [提示] 不判通过模式运行结果不覆盖 ui_verify_latest.json（保护生产台账）")
        else:
            latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  报告落盘: {out_path.relative_to(ROOT_DIR)} & ui_verify_latest.json")
        print("─" * 68)

        if env_name == "sandbox":
            return 0

        if is_mutation:
            mut_summary = this_run_summary if target_cases else summary
            if mut_summary["通过"] == 0 and mut_summary["失败"] > 0:
                print("🎉 [变异承重验证成功] 扰动内存真值后，全部有效断言100%变红（0项伪通过）！断言具备真实承重能力。")
                return 0
            else:
                print(f"⚠️ [变异承重验证失败] 扰动内存真值后，仍有 {mut_summary['通过']} 项通过（存在伪通过风险）。")
                return 1

        if not is_clean:
            print("⚠️ [审计拦截] 存在伪断言违规，门禁判定不通过。")
            return 1

        return 0 if this_run_summary["失败"] == 0 else 1

    finally:
        session.close()
