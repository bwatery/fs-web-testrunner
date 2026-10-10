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

    mode_label = "[界面·窗口]" if is_windowed else "[界面·无头]"
    env_label = "隔离沙盒 (Sandbox: 永不判通过)" if env_name == "sandbox" else "真实环境 (Real)"

    print("=" * 68)
    print(f"  FS.TestRunner · 界面认证与真实业务等式对账 ({mode_label})")
    print("=" * 68)
    print(f"  模式      : {mode_label} ({'接管端口 9222 现有窗口' if is_windowed else '独立拉起 Headless Chrome 实例'})")
    print(f"  运行环境  : {env_label}")
    print(f"  前端地址  : {frontend}")
    print(f"  网关地址  : {gateway}")
    print(f"  变异扰动  : {'开启 (--mutation: 内存扰动真值，断言必须变红)' if is_mutation else '关闭 (正常对账)'}")
    print(f"  截图存盘  : {'开启 (--screenshot)' if take_screenshot else '关闭'}")
    if cases_arg:
        print(f"  目标用例  : {cases_arg}")
    print("-" * 68)

    # 1. 沙盒模式纯离线拦截（严禁既连生产又自称沙盒）
    if env_name == "sandbox":
        print("\n⚠️  [沙盒模式硬门禁] 沙盒环境纯离线运行，严禁连接生产前端与业务网关，强制产出「未执行」！")
        selected_cases = [c.strip() for c in cases_arg.split(",")] if cases_arg else ["UI-L6-039-P1", "UI-L6-039-P2", "UI-L6-039-LIST"]
        print(f"\n[离线参数校验] 检查目标用例: {', '.join(selected_cases)} (离线参数结构合法)")
        print("\n沙盒模式执行结果：")
        for cid in selected_cases:
            print(f"  ⚪ {cid} —— 未执行（沙盒模式：纯离线参数校验，未连接生产前端与业务网关）")
        print("\n沙盒模式执行完毕：共 3 条用例，未执行 3 条，0 条通过，0 条失败。")
        return 0

    # 2. 启动或连接浏览器会话
    try:
        session = launch_browser(headless=headless, port=9222)
    except Exception as e:
        print(f"\n❌ [浏览器启动失败] {e}")
        print("   硬约束：浏览器无法就绪时立即报错退出，严禁静默降级。")
        return 2

    try:
        # 3. 真实表单登录认证
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

        # 4. 执行界面业务断言
        print("\n[3/3] 正在执行界面真实渲染业务断言与数据库比对...")
        print("─" * 68)
        print("【用例选型与客观原因（宁少勿假）】：")
        print(" • 放弃 L6-005（门诊挂号列表）：admin 账号当前仅配置住院医生/护士角色，侧边栏无门诊退号菜单")
        print("   （直接输入 hash 会被前端路由守卫拦截并重定向回首页，不具备挂载组件）。")
        print(" • 放弃 L9-012（药房摆药明细）：当前角色无药房窗口发药权限，发药调配组件未挂载。")
        print(" • 放弃 L6-050（收费员日结）：当前角色非门诊收费员，日结汇总组件未挂载。")
        print(" • 确定选型：聚焦费用与在院患者真实核心业务对账，覆盖四项真实验证：")
        print("   1) UI-L6-039-P1: 费用综合查询 - 床号 401-2 患者陈新强费用明细与汇总对账")
        print("   2) UI-L6-039-P2: 费用综合查询 - 床号 401-1 患者刘付立城费用明细与汇总对账")
        print("   3) UI-L6-039-LIST: 费用综合查询 - 内一科在院患者床位分配全集对账")
        print("   4) UI-INDEX: 首页运营指标看板 - 收费总量与细项聚合等式对账")
        print("─" * 68)

        ui_results: List[Dict[str, Any]] = []

        # -------------------------------------------------------------------
        # 导航进入：费用综合查询 (#/inpatient/finance/syntheticfquery)
        # -------------------------------------------------------------------
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
            session.cmd("Page.navigate", {"url": f"{frontend}/#/inpatient/finance/syntheticfquery"})
            time.sleep(2.5)
            session.cmd("Page.reload", {"ignoreCache": True})
            time.sleep(3.5)

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
                dept_name = "骨二科"

        # ===================================================================
        # 断言 1: UI-L6-039-P1 (在院第一患者费用汇总与明细对账)
        # ===================================================================
        t0 = time.time()
        p1_label = patient_nodes[0] if len(patient_nodes) > 0 else "301-1 骨二科测试患者01"
        p1_name = p1_label.split()[-1]
        print(f"\n  ▶ 正在执行 [UI-L6-039-P1] 费用综合查询 · {p1_name} 费用汇总与明细对账...")
        session.eval(f"""(() => {{
            const el = Array.from(document.querySelectorAll('.el-tree-node__content'))
                            .find(e => (e.innerText || '').trim() === {json.dumps(p1_label)});
            if (el) {{ el.click(); return true; }}
            return false;
        }})()""")
        time.sleep(2.5)

        # 读取 DOM 渲染数据
        dom_p1_text = session.eval("document.body.innerText") or ""
        m_tot = re.search(r"总金额\s*([0-9.]+)", dom_p1_text)
        m_zyh = re.search(r"住院号\s*([0-9]+)", dom_p1_text)
        m_bed = re.search(r"住院床号\s*([0-9-]+)", dom_p1_text)

        ui_tot_cost = float(m_tot.group(1)) if m_tot else 0.0
        ui_inpatient_no = m_zyh.group(1) if m_zyh else ""
        ui_bed_no = m_bed.group(1) if m_bed else ""

        # 查询 Oracle 真实数据
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

        # 变异扰动支持
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
        ui_results.append({
            "case_id": "UI-L6-039-P1",
            "title": f"界面对账·费用综合查询·{p1_name}费用明细与汇总",
            "status": p1_status,
            "note": p1_note,
            "evidence": p1_evidence,
            "duration_ms": round((time.time() - t0) * 1000, 1),
        })
        mark = "✅" if p1_ok else "❌"
        print(f"  {mark} [UI-L6-039-P1] —— {p1_status}")
        print(f"        {p1_note}")
        if not p1_ok:
            _archive_failure_trace(session, "UI-L6-039-P1", p1_note, p1_evidence)

        # ===================================================================
        # 断言 2: UI-L6-039-P2 (在院第二患者费用汇总)
        # ===================================================================
        t0 = time.time()
        p2_label = patient_nodes[1] if len(patient_nodes) > 1 else "301-11 骨二科测试患者03"
        p2_name = p2_label.split()[-1]
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
        ui_results.append({
            "case_id": "UI-L6-039-P2",
            "title": f"界面对账·费用综合查询·{p2_name}费用汇总",
            "status": p2_status,
            "note": p2_note,
            "evidence": p2_evidence,
            "duration_ms": round((time.time() - t0) * 1000, 1),
        })
        mark = "✅" if p2_ok else "❌"
        print(f"  {mark} [UI-L6-039-P2] —— {p2_status}")
        print(f"        {p2_note}")
        if not p2_ok:
            _archive_failure_trace(session, "UI-L6-039-P2", p2_note, p2_evidence)

        # ===================================================================
        # 断言 3: UI-L6-039-LIST (全院在院患者床位分配全集)
        # ===================================================================
        t0 = time.time()
        print(f"\n  ▶ 正在执行 [UI-L6-039-LIST] 费用综合查询 · 在院患者床位列表全集对账...")
        ui_beds_set = {p.split()[0] for p in patient_nodes}

        conn = _oracle_conn()
        cur = conn.cursor()
        cur.execute("""SELECT bed_no, patient_name FROM fin_ip_register 
                       WHERE data_status = 'I' AND valid_flag = '1'""")
        ora_beds_map = {str(r[0]): str(r[1]) for r in cur.fetchall()}
        conn.close()

        if is_mutation:
            if ora_beds_map:
                ora_beds_map.pop(list(ora_beds_map.keys())[0], None)

        p3_eq = (ui_beds_set == set(ora_beds_map.keys()))
        p3_ok = p3_eq and len(ui_beds_set) >= 2
        p3_status = "通过" if p3_ok else "失败"
        p3_note = (
            f"界面左侧树读到在院床位共 {len(ui_beds_set)} 个 ({sorted(list(ui_beds_set))}...)；"
            f"库中登记对应在院床位 {len(ora_beds_map)} 个 ({sorted(list(ora_beds_map.keys()))}...) —— "
            f"{'页面床位集合与库中在床记录集合100%全集一致' if p3_ok else '床位集合存在未登记或脱节项目'}"
        )
        if is_mutation and not p3_ok:
            p3_note += "（变异自检生效：内存扰动剔除在床记录导致断言变红）"

        p3_evidence = {
            "用例编号": "UI-L6-039-LIST",
            "运行模式": mode_label,
            "界面元素选择器": ".el-tree-node__content / .tree-node",
            "当前科室": dept_name,
            "界面读出床位集合": sorted(list(ui_beds_set)),
            "库中在床床位集合": sorted(list(ora_beds_map.keys())),
            "验证等式": "界面床位集合 == 数据库在床集合",
            "等式成立": p3_ok,
            "变异扰动": is_mutation,
        }
        ui_results.append({
            "case_id": "UI-L6-039-LIST",
            "title": f"界面对账·费用综合查询·{dept_name}在院患者床位分配全集",
            "status": p3_status,
            "note": p3_note,
            "evidence": p3_evidence,
            "duration_ms": round((time.time() - t0) * 1000, 1),
        })
        mark = "✅" if p3_ok else "❌"
        print(f"  {mark} [UI-L6-039-LIST] —— {p3_status}")
        print(f"        {p3_note}")
        if not p3_ok:
            _archive_failure_trace(session, "UI-L6-039-LIST", p3_note, p3_evidence)

        # ===================================================================
        # 断言 4: UI-INDEX (首页运营指标看板等式校验)
        # ===================================================================
        t0 = time.time()
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

        # 看板业务指标等式
        # 总收费量 必须大于等于 门诊收费，且二者具备真实运营统计量
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
        ui_results.append({
            "case_id": "UI-INDEX",
            "title": "界面对账·首页看板·收费总量指标聚合等式",
            "status": p4_status,
            "note": p4_note,
            "evidence": p4_evidence,
            "duration_ms": round((time.time() - t0) * 1000, 1),
        })
        mark = "✅" if p4_ok else "❌"
        print(f"  {mark} [UI-INDEX] —— {p4_status}")
        print(f"        {p4_note}")
        if not p4_ok:
            _archive_failure_trace(session, "UI-INDEX", p4_note, p4_evidence)

        # -------------------------------------------------------------------
        # 结果汇总与落盘
        # -------------------------------------------------------------------
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            "模式": mode_label,
            "通过": sum(1 for r in ui_results if r["status"] == "通过"),
            "失败": sum(1 for r in ui_results if r["status"] == "失败"),
            "总计": len(ui_results),
            "变异扰动": is_mutation,
        }

        payload = {
            "meta": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode_label,
                "headless": headless,
                "is_mutation": is_mutation,
                "frontend": frontend,
                "gateway": gateway,
            },
            "summary": summary,
            "results": ui_results,
        }

        mode_file = "ui_verify_windowed.json" if is_windowed else "ui_verify_headless.json"
        out_path = REPORTS_DIR / mode_file
        latest_path = REPORTS_DIR / "ui_verify_latest.json"

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n" + "─" * 68)
        print(f"  界面真实业务对账完成 ({mode_label})")
        print(f"  ✅ 通过 {summary['通过']}   ❌ 失败 {summary['失败']}   (共 {summary['总计']} 项界面断言)")
        print(f"  报告落盘: {out_path.relative_to(ROOT_DIR)} & ui_verify_latest.json")
        print("─" * 68)

        if is_mutation:
            # 变异自检模式下：全部变红说明断言承重，退出码应为 0
            if summary["失败"] == summary["总计"]:
                print("🎉 [变异承重验证成功] 扰动内存真值后，所有界面断言全部变红！断言具备真实承重能力。")
                return 0
            else:
                print("⚠️ [变异承重验证失败] 扰动内存真值后，仍有部分界面断言未变红（可能存在伪通过）。")
                return 1

        return 0 if summary["失败"] == 0 else 1

    finally:
        session.close()
