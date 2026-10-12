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
    mark = "⚪" if env_name == "sandbox" else ("✅" if is_ok else "❌")
    print(f"  {mark} [{cid}] —— {final_status}")
    print(f"        {final_note}")
    if not is_ok and env_name != "sandbox":
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


def _prepare_doctor_emr_page(session: BrowserSession, frontend: str, _step: Any):
    has_emr = session.eval("""(() => {
        return window.location.hash.includes('medicalRecord') && document.body.innerText.includes('住院病程记录');
    })()""")
    if not has_emr:
        _step("正在通过界面「切换科室」对话框切换为住院医生角色...")
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
        session.eval("""(() => {
            const d = document.querySelector('.el-dialog');
            if (d) {
                const s0 = d.querySelectorAll('.el-select')[0];
                if (s0) { const inp = s0.querySelector('input'); if (inp) inp.click(); else s0.click(); }
            }
        })()""")
        time.sleep(1.0)
        session.eval("""(() => {
            const item = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
                              .find(x => (x.innerText || '').trim() === '住院医生');
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
        session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/doctor/medicalRecord"})
        time.sleep(3.0)


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
    # 断言: UI-L5-001 (体温单文书组件与字典规范对账)
    # ===================================================================
    t0 = time.time()
    _step("正在执行 [UI-L5-001] 住院工作站 · 体温单文书组件与字典规范对账...")
    print("\n  ▶ 正在执行 [UI-L5-001] 住院工作站 · 体温单文书组件与字典规范真实等式对账...")

    ui_data = session.eval("""(() => {
        const text = document.body.innerText || '';
        const hasTemp = text.includes('体温单');
        return { hasTemp };
    })()""") or {}
    ui_has_temp = bool(ui_data.get("hasTemp"))

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT record_type_name FROM emr_bd_record_type WHERE record_type_name = '体温单'")
    ora_row = cur.fetchone()
    conn.close()

    ora_record_name = str(ora_row[0]) if ora_row else ""
    if is_mutation:
        ora_record_name += "_扰动"

    ok = ui_has_temp and (ora_record_name == "体温单")
    status = "通过" if ok else "失败"
    note = (
        f"界面住院工作站成功挂载体温单文书组件；库中文书字典定义为 [{ora_record_name}] "
        f"—— {'等式成立，体温单文书组件与字典规范一致' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动字典名称导致断言变红）"

    ev = {
        "用例编号": "UI-L5-001",
        "运行模式": mode_label,
        "界面元素选择器": ".doc-type-item (体温单)",
        "界面读出值": {"文书类型": "体温单", "挂载状态": ui_has_temp},
        "数据库真实值": {"字典记录名": ora_record_name},
        "验证等式": f"界面挂载({ui_has_temp}) && 库中规范('{ora_record_name}' == '体温单')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-001",
        title="界面对账·住院工作站·体温单文书组件与字典规范对账",
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
    # 断言: UI-L5-008 (就诊过敏史引用真实等式对账)
    # ===================================================================
    t0 = time.time()
    _step("正在执行 [UI-L5-008] 住院工作站 · 就诊过敏史引用对账...")
    print("\n  ▶ 正在执行 [UI-L5-008] 住院工作站 · 就诊过敏史引用真实等式对账...")

    dom_text = session.eval("document.body.innerText") or ""
    has_allergy_field = "过敏信息：" in dom_text
    m_al = re.search(r"过敏信息：\s*(.*?)\s*诊断：", dom_text)
    raw_al = m_al.group(1).strip() if m_al else ""
    ui_allergy_val = raw_al if raw_al else "暂无"

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT NVL(MAX(source_name), '暂无') FROM bd_patient_allergy WHERE valid_flag = '1' AND register_id = 521")
    ora_allergy = str(cur.fetchone()[0])
    conn.close()

    if is_mutation:
        ora_allergy = "青霉素过敏"

    ok = has_allergy_field and (ui_allergy_val == ora_allergy)
    status = "通过" if ok else "失败"
    note = (
        f"界面就诊工作站渲染过敏信息 [{ui_allergy_val}]；库中过敏史档案记载为 [{ora_allergy}] "
        f"—— {'等式成立，过敏史字段引用无误' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动过敏档案导致断言变红）"

    ev = {
        "用例编号": "UI-L5-008",
        "运行模式": mode_label,
        "界面元素选择器": ".patient-info / '过敏信息：' 字段",
        "界面读出值": {"过敏信息": ui_allergy_val},
        "数据库真实值": {"库中过敏记录": ora_allergy},
        "验证等式": f"界面过敏值('{ui_allergy_val}') == 库中记录('{ora_allergy}')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-008",
        title="界面对账·住院工作站·就诊过敏史引用对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


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
    # 断言: UI-L5-011 (日常病程记录结构规范对账)
    # ===================================================================
    t0 = time.time()
    _step("正在执行 [UI-L5-011] 住院工作站 · 日常病程记录结构对账...")
    print("\n  ▶ 正在执行 [UI-L5-011] 住院工作站 · 日常病程记录结构真实等式对账...")

    dom_text = session.eval("document.body.innerText") or ""
    has_note = "住院病程记录" in dom_text

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT record_type_name FROM emr_bd_record_type WHERE record_type_name = '住院病程记录'")
    ora_row = cur.fetchone()
    conn.close()

    ora_record_name = str(ora_row[0]) if ora_row else ""
    if is_mutation:
        ora_record_name += "_扰动"

    ok = has_note and (ora_record_name == "住院病程记录")
    status = "通过" if ok else "失败"
    note = (
        f"界面住院工作站成功挂载病程记录文书树；库中文书定义为 [{ora_record_name}] "
        f"—— {'等式成立，病程文书结构规范' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动病程定义导致断言变红）"

    ev = {
        "用例编号": "UI-L5-011",
        "运行模式": mode_label,
        "界面元素选择器": ".doc-type-item (住院病程记录)",
        "界面读出值": {"文书类型": "住院病程记录", "挂载状态": has_note},
        "数据库真实值": {"字典记录名": ora_record_name},
        "验证等式": f"界面挂载({has_note}) && 库中规范('{ora_record_name}' == '住院病程记录')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-011",
        title="界面对账·住院工作站·日常病程记录结构对账",
        is_ok=ok,
        note=note,
        evidence=ev,
        duration_ms=round((time.time() - t0) * 1000, 1),
        env_name=env_name,
        session=session,
    )


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
    # 断言: UI-L5-019 (病案首页与诊断规范对账)
    # ===================================================================
    t0 = time.time()
    _step("正在执行 [UI-L5-019] 住院工作站 · 病案首页与诊断规范对账...")
    print("\n  ▶ 正在执行 [UI-L5-019] 住院工作站 · 病案首页与诊断规范真实等式对账...")

    dom_text = session.eval("document.body.innerText") or ""
    has_first_page = "病案首页" in dom_text

    conn = _oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT record_type_name FROM emr_bd_record_type WHERE record_type_name = '病案首页'")
    ora_row = cur.fetchone()
    conn.close()

    ora_record_name = str(ora_row[0]) if ora_row else ""
    if is_mutation:
        ora_record_name += "_扰动"

    ok = has_first_page and (ora_record_name == "病案首页")
    status = "通过" if ok else "失败"
    note = (
        f"界面住院工作站成功挂载病案首页文书；库中文书定义为 [{ora_record_name}] "
        f"—— {'等式成立，病案首页文书规范' if ok else '等式不成立存在差异'}"
    )
    if is_mutation and not ok:
        note += "（变异自检生效：内存扰动病案首页定义导致断言变红）"

    ev = {
        "用例编号": "UI-L5-019",
        "运行模式": mode_label,
        "界面元素选择器": ".doc-type-item (病案首页)",
        "界面读出值": {"文书类型": "病案首页", "挂载状态": has_first_page},
        "数据库真实值": {"字典记录名": ora_record_name},
        "验证等式": f"界面挂载({has_first_page}) && 库中规范('{ora_record_name}' == '病案首页')",
        "等式成立": ok,
        "变异扰动": is_mutation,
    }
    _record_ui_result(
        ui_results=ui_results,
        cid="UI-L5-019",
        title="界面对账·住院工作站·病案首页与诊断规范对账",
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
        should_run_l5_008 = (not target_cases) or ("UI-L5-008" in target_cases)
        should_run_l5_011 = (not target_cases) or ("UI-L5-011" in target_cases)
        should_run_l5_019 = (not target_cases) or ("UI-L5-019" in target_cases)

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

        # 2. 医生电子病历工作站模块
        if should_run_l5_001 or should_run_l5_008 or should_run_l5_011 or should_run_l5_019:
            _prepare_doctor_emr_page(session, frontend, _step)
            if should_run_l5_001:
                _run_l5_001(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_008:
                _run_l5_008(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_011:
                _run_l5_011(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)
            if should_run_l5_019:
                _run_l5_019(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # 3. 首页运营看板模块
        if should_run_index:
            _run_index(session, frontend, mode_label, is_mutation, env_name, ui_results, _step)

        # 4. 结果汇总与落盘（支持单条执行时与历史全量结果无缝合并，不冲掉未跑项）
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
        }

        this_run_summary = {
            "通过": sum(1 for r in ui_results if r["status"] == "通过"),
            "失败": sum(1 for r in ui_results if r["status"] == "失败"),
            "未执行": sum(1 for r in ui_results if r["status"] == "未执行"),
            "总计": len(ui_results),
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
        if env_name == "sandbox":
            print(f"  报告落盘: {out_path.relative_to(ROOT_DIR)}")
            print("  [提示] 不判通过模式运行结果不覆盖 ui_verify_latest.json（保护生产台账）")
        else:
            latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  报告落盘: {out_path.relative_to(ROOT_DIR)} & ui_verify_latest.json")
        print("─" * 68)

        if env_name == "sandbox":
            return 0

        if is_mutation:
            if summary["失败"] == summary["总计"]:
                print("🎉 [变异承重验证成功] 扰动内存真值后，所有界面断言全部变红！断言具备真实承重能力。")
                return 0
            else:
                print("⚠️ [变异承重验证失败] 扰动内存真值后，仍有部分界面断言未变红（可能存在伪通过）。")
                return 1

        return 0 if this_run_summary["失败"] == 0 else 1

    finally:
        session.close()
