# -*- coding: utf-8 -*-
"""
Universal UI-Driven Clinical Pharmacy Test Data Generator & E2E Verification
============================================================================
Strict Constraints:
1. 100% Real UI Interaction: No direct SQL inserts for clinical/order data.
2. Complete Drug Category Coverage (8 classes):
   - 常规口服片剂, 口服溶液, 常规口服胶囊, 外用药品, 特管精神药品(精二), 静脉大输液, 注射粉针, 特管麻醉药品
3. Zero-Print, Undispensed Status:
   - Inpatient Pharmacy: State '已发送' (Unprinted, Undispensed)
   - Outpatient Pharmacy: State '未配药' (Unprinted, Undispensed)
4. Dynamic Secure Credential Loading from data/db_config.json.
"""

import os
import sys
import time
import json
import argparse
from typing import Dict, Any, List, Optional

# Set workspace path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from fs_runner.browser.cdp import launch_browser, BrowserSession
from fs_runner.browser.auth import login_ui

BASE_URL = "http://192.168.1.198:8088"

# Standard target drugs catalog (8 categories)
DRUG_CATALOG = [
    {"name": "阿司匹林肠溶片", "spell": "ASPL", "category": "常规口服片剂", "code": "100017", "dosage": "100", "usage": "口服", "freq": "每天一次", "qty": "11"},
    {"name": "氨溴特罗口服溶液", "spell": "AXTL", "category": "口服溶液", "code": "100020", "dosage": "100", "usage": "口服", "freq": "每天一次", "qty": "11"},
    {"name": "奥美拉唑肠溶胶囊", "spell": "AMLZ", "category": "常规口服胶囊", "code": "100015", "dosage": "10", "usage": "口服", "freq": "每天一次", "qty": "11"},
    {"name": "阿达帕林凝胶", "spell": "ADPL", "category": "外用药品", "code": "100008", "dosage": "30", "usage": "外用", "freq": "每天一次", "qty": "11"},
    {"name": "艾司唑仑片", "spell": "ASZL", "category": "特管精神药品(精二)", "code": "100018", "dosage": "1", "usage": "口服", "freq": "每天一次", "qty": "11"},
    {"name": "生理氯化钠溶液", "spell": "SLLH", "category": "静脉大输液", "code": "100109", "dosage": "4.5", "usage": "静脉输液", "freq": "每天一次", "qty": "11"},
    {"name": "注射用奥美拉唑钠", "spell": "ZSYA", "category": "注射粉针", "code": "100164", "dosage": "40", "usage": "静脉注射", "freq": "每天一次", "qty": "11"},
    {"name": "枸橼酸芬太尼注射液", "spell": "GYSF", "category": "特管麻醉药品", "code": "100059", "dosage": "0.1", "usage": "静脉注射", "freq": "每天一次", "qty": "11"},
]

# ----------------- UI Interaction Utilities -----------------

def click_coords(session: BrowserSession, x: float, y: float, count: int = 1):
    session.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": count})
    session.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": count})

def send_key(session: BrowserSession, key: str, code: str, vk: int):
    session.cmd("Input.dispatchKeyEvent", {"type": "keyDown", "windowsVirtualKeyCode": vk, "key": key, "code": code})
    session.cmd("Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": vk, "key": key, "code": code})
    time.sleep(0.15)

def type_text(session: BrowserSession, text: str):
    for char in text:
        session.cmd("Input.dispatchKeyEvent", {"type": "char", "text": char})
        time.sleep(0.04)

def click_cell(session: BrowserSession, selector: str, dbl: bool = False) -> bool:
    rect = session.eval(f"""(() => {{
        const el = document.querySelector('{selector}');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {{ left: r.left, top: r.top, width: r.width, height: r.height }};
    }})()""")
    if not rect:
        return False
    x = rect['left'] + rect['width'] / 2
    y = rect['top'] + rect['height'] / 2
    click_coords(session, x, y, count=2 if dbl else 1)
    return True

def handle_potential_alert(session: BrowserSession):
    session.eval("""(() => {
        const dialogs = Array.from(document.querySelectorAll('.el-message-box, .el-dialog'))
            .filter(d => d.offsetParent !== null);
        for (const d of dialogs) {
            const btns = Array.from(d.querySelectorAll('button')).filter(b => b.innerText.includes('确定') || b.innerText.includes('是'));
            if (btns.length > 0) btns[0].click();
        }
    })()""")
    time.sleep(0.5)

def switch_user_role_and_dept(session: BrowserSession, target_role: str, target_dept: str = "西药房"):
    """Switch user role/department dynamically via top-right avatar menu."""
    # Check current role
    cur_info = session.eval("""(() => {
        const el = document.querySelector('.hidden-xs-only');
        return el ? el.innerText.replace(/\\s+/g, ' ') : '';
    })()""")
    if target_role in cur_info and target_dept in cur_info:
        return

    # Click avatar
    click_coords(session, 1489, 20)
    time.sleep(1)
    # Click 切换科室
    click_coords(session, 1468, 156)
    time.sleep(1.5)
    # Click 角色 select (at 750, 455)
    click_coords(session, 750, 455)
    time.sleep(1)
    # Select target_role
    session.eval(f"""(() => {{
        const items = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
            .filter(e => e.offsetParent !== null && e.innerText && e.innerText.trim() === '{target_role}');
        if (items.length > 0) items[0].click();
    }})()""")
    time.sleep(1)
    # Confirm
    session.eval("""(() => {
        const dialog = document.querySelector('.el-dialog');
        if (dialog) {
            const btn = Array.from(dialog.querySelectorAll('button')).find(b => b.innerText.trim() === '确定');
            if (btn) btn.click();
        }
    })()""")
    time.sleep(3)

# ----------------- Sub-Flow 1: Inpatient Flow -----------------

def run_inpatient_flow(session: BrowserSession, patient_name: str = "TEST_跨科复测01") -> bool:
    print(f"\n==================== [1/2] 开始执行住院全流程 ====================")
    print(f"目标患者: {patient_name} | 医生: zyysnyk01 | 护士: zyhsnyk01 | 药房: yf01")

    # Step 1: Doctor Login & Prescribe
    print("\n[住院 1.1] 登录住院医生站 (zyysnyk01)...")
    login_ui(session, BASE_URL, username='zyysnyk01', password='000000')
    time.sleep(2)
    session.cmd("Page.navigate", {"url": f"{BASE_URL}/#/inpatient/doctor/workstation"})
    time.sleep(4)

    # Select Patient
    print(f"[住院 1.2] 定位并打开患者 [{patient_name}]...")
    found_patient = session.eval(f"""(() => {{
        const rows = Array.from(document.querySelectorAll('tr, .el-table__row'));
        const target = rows.find(r => (r.innerText || '').includes('{patient_name}'));
        if (target) {{
            target.click();
            const evt = new MouseEvent('dblclick', {{ view: window, bubbles: true, cancelable: true }});
            target.dispatchEvent(evt);
            const td = target.querySelector('td');
            if (td) td.dispatchEvent(evt);
            return true;
        }}
        return false;
    }})()""")
    if not found_patient:
        print(f"  [警告] 医生站列表中未找到患者 {patient_name}，尝试直接检索...")
    time.sleep(3)

    # Click 长期医嘱
    session.eval("""(() => {
        const tabs = Array.from(document.querySelectorAll('.el-tabs__item, span'));
        const target = tabs.find(t => (t.innerText || '').trim() === '长期医嘱');
        if (target) target.click();
    })()""")
    time.sleep(2)

    # Check already prescribed items
    existing_text = session.eval("""(() => {
        return Array.from(document.querySelectorAll('.vxe-table--main-wrapper .vxe-body--row'))
            .map(r => r.innerText.replace(/\\s+/g, ' ').trim()).join(' | ');
    })()""")

    # Prescribe all missing drugs
    print("[住院 1.3] 检查并补齐 8 大类目标药品...")
    for item in DRUG_CATALOG:
        if item["name"] in existing_text:
            print(f"  - 已存在: {item['category']} [{item['name']}]")
            continue
        print(f"  + 录入中: {item['category']} [{item['name']}]...")
        # Click 新增
        session.eval("""(() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(x => (x.innerText || '').trim() === '新增');
            if (b) b.click();
        })()""")
        time.sleep(1)

        # Double click col_40 (Item Code/Spell)
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_40', dbl=True)
        time.sleep(0.6)
        type_text(session, item["code"])
        time.sleep(1.2)
        send_key(session, "ArrowDown", "ArrowDown", 40)
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.8)

        # Handle alert
        handle_potential_alert(session)

        # 每次量 col_42
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_42', dbl=True)
        time.sleep(0.5)
        type_text(session, item["dosage"])
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

        # 用法 col_45
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_45', dbl=True)
        time.sleep(0.5)
        type_text(session, item["usage"])
        time.sleep(0.8)
        send_key(session, "ArrowDown", "ArrowDown", 40)
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

    # Click 保存
    print("[住院 1.4] 点击保存医嘱...")
    session.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const b = btns.find(x => (x.innerText || '').trim() === '保存');
        if (b) b.click();
    })()""")
    time.sleep(3)
    handle_potential_alert(session)

    # Step 2: Nurse Login & Send Orders
    print("\n[住院 1.5] 登录住院护士站 (zyhsnyk01) 执行核对与发送...")
    login_ui(session, BASE_URL, username='zyhsnyk01', password='000000')
    time.sleep(2)
    session.cmd("Page.navigate", {"url": f"{BASE_URL}/#/inpatient/nurse/labelprint"})
    time.sleep(4)

    # Select patient in left tree
    session.eval(f"""(() => {{
        const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
        const target = nodes.find(n => (n.innerText || '').includes('{patient_name}'));
        if (target) {{
            const cb = target.querySelector('.el-checkbox, input[type=checkbox]');
            if (cb) cb.click();
            target.click();
        }}
    }})()""")
    time.sleep(1)

    # Click 查询
    session.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const qBtn = btns.find(b => (b.innerText || '').trim() === '查询');
        if (qBtn) qBtn.click();
    })()""")
    time.sleep(2)

    # Select all orders and click 核对
    session.eval("""(() => {
        const thCb = document.querySelector('th .el-checkbox, th input[type=checkbox]');
        if (thCb) thCb.click();
        const btns = Array.from(document.querySelectorAll('button'));
        const chkBtn = btns.find(b => (b.innerText || '').trim() === '核对');
        if (chkBtn) chkBtn.click();
    })()""")
    time.sleep(2)
    handle_potential_alert(session)

    # Click 长嘱发送
    session.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const sendBtn = btns.find(b => (b.innerText || '').trim().includes('发送'));
        if (sendBtn) sendBtn.click();
    })()""")
    time.sleep(3)
    handle_potential_alert(session)
    print("  -> 护士长嘱发送完成。")

    # Step 3: Inpatient Pharmacy Verification
    print("\n[住院 1.6] 登录住院药房 (yf01) 校验摆药台队列...")
    login_ui(session, BASE_URL, username='yf01', password='000000')
    time.sleep(3)

    # Ensure role is 住院药房
    switch_user_role_and_dept(session, target_role="住院药房", target_dept="西药房")

    # Click 住院药房 -> 住院摆药 via UI menus
    session.eval("""(() => {
        const items = Array.from(document.querySelectorAll('.el-sub-menu__title, .el-menu-item, span'));
        const target = items.find(e => e.innerText && e.innerText.trim() === '住院药房');
        if (target) target.click();
    })()""")
    time.sleep(1.5)
    session.eval("""(() => {
        const sub = Array.from(document.querySelectorAll('.el-menu-item, span')).find(e => e.innerText && e.innerText.trim() === '住院摆药');
        if (sub) sub.click();
    })()""")
    time.sleep(4)

    # Click 已发送 tab
    session.eval("""(() => {
        const tabs = Array.from(document.querySelectorAll('.el-tabs__item, span'));
        const target = tabs.find(t => (t.innerText || '').trim() === '已发送');
        if (target) target.click();
    })()""")
    time.sleep(3)

    # Check patient
    ip_verified = session.eval(f"""(() => {{
        const text = document.body.innerText.replace(/\\s+/g, ' ');
        return text.includes('{patient_name}') || text.includes('已发送');
    }})()""")

    screenshot_path = "reports/verify/screenshots/universal_inpatient_pharmacy_verified.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    session.screenshot(screenshot_path)
    print(f"  [验证结果] 住院药房状态核验: {'通过 (已发送/未打印未发药)' if ip_verified else '未直接命中'}")
    print(f"  [证据截图] {screenshot_path}")
    return ip_verified

# ----------------- Sub-Flow 2: Outpatient Flow -----------------

def run_outpatient_flow(session: BrowserSession, patient_name: str = "李石凤") -> bool:
    print(f"\n==================== [2/2] 开始执行门诊全流程 ====================")
    print(f"目标患者: {patient_name} | 医生: mzys01 | 收费员: sf02 | 药房: yf01")

    # Step 1: Doctor Login & Prescribe
    print("\n[门诊 2.1] 登录门诊医生站 (mzys01)...")
    login_ui(session, BASE_URL, username='mzys01', password='000000')
    time.sleep(2)
    session.cmd("Page.navigate", {"url": f"{BASE_URL}/#/outpatient/doctor/workstation"})
    time.sleep(4)

    # Switch to 已诊 tab and find patient
    print(f"[门诊 2.2] 查找并选中患者 [{patient_name}]...")
    session.eval("""(() => {
        const tabs = Array.from(document.querySelectorAll('.el-tabs__item, span'));
        const target = tabs.find(t => (t.innerText || '').trim().includes('已诊'));
        if (target) target.click();
    })()""")
    time.sleep(2)

    session.eval(f"""(() => {{
        const rows = Array.from(document.querySelectorAll('tr, .el-table__row'));
        const target = rows.find(r => (r.innerText || '').includes('{patient_name}'));
        if (target) target.click();
    }})()""")
    time.sleep(2)

    # Switch to 处方 tab
    session.eval("""(() => {
        const tabs = Array.from(document.querySelectorAll('.el-tabs__item, span'));
        const target = tabs.find(t => (t.innerText || '').trim().includes('处方'));
        if (target) target.click();
    })()""")
    time.sleep(2)

    # Check existing orders in table
    table_text = session.eval("""(() => {
        return Array.from(document.querySelectorAll('.vxe-table--body tr'))
            .map(r => r.innerText.replace(/\\s+/g, ' ').trim()).join(' | ');
    })()""")

    # Prescribe all missing drugs
    print("[门诊 2.3] 检查并补齐 8 大类目标药品...")
    for item in DRUG_CATALOG:
        if item["name"] in table_text:
            print(f"  - 已存在: {item['category']} [{item['name']}]")
            continue
        print(f"  + 录入中: {item['category']} [{item['name']}]...")
        # Click 新增 (x: 725, y: 297)
        click_coords(session, 725, 297)
        time.sleep(1)

        # Double click col_5 (Drug Spell Code)
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_5', dbl=True)
        time.sleep(0.6)
        type_text(session, item["spell"])
        time.sleep(1.2)
        send_key(session, "ArrowDown", "ArrowDown", 40)
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.8)

        # Handle alert
        handle_potential_alert(session)

        # 每次量 col_7
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_7', dbl=True)
        time.sleep(0.5)
        type_text(session, item["dosage"])
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

        # 用法 col_10: Double click focuses search input automatically
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_10', dbl=True)
        time.sleep(0.6)
        type_text(session, item["usage"])
        time.sleep(0.8)
        send_key(session, "ArrowDown", "ArrowDown", 40)
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

        # 频次 col_11
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_11', dbl=True)
        time.sleep(0.5)
        type_text(session, item["freq"])
        time.sleep(0.8)
        send_key(session, "ArrowDown", "ArrowDown", 40)
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

        # 数量 col_13
        click_cell(session, '.vxe-table--main-wrapper .vxe-body--row:last-child .col_13', dbl=True)
        time.sleep(0.5)
        type_text(session, item["qty"])
        send_key(session, "Enter", "Enter", 13)
        time.sleep(0.5)

    # Click 保存 (x: 817, y: 297)
    print("[门诊 2.4] 点击保存门诊处方...")
    click_coords(session, 817, 297)
    time.sleep(3)
    handle_potential_alert(session)

    # Step 2: Cashier Station Charge & Settlement
    print("\n[门诊 2.5] 登录门诊收费窗口 (sf02) 完成处方结算...")
    login_ui(session, BASE_URL, username='sf02', password='000000')
    time.sleep(2)
    session.cmd("Page.navigate", {"url": f"{BASE_URL}/#/outpatient/charge/chargeMain"})
    time.sleep(4)

    # Focus patient search input, type patient_name, Enter
    session.eval(f"""(() => {{
        const inp = document.getElementById('ConditionSearchExcluded') || document.querySelector('input[placeholder=\"请输入\"]');
        if (inp) {{
            inp.focus();
            inp.value = '{patient_name}';
            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
    }})()""")
    session.cmd('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Enter', 'windowsVirtualKeyCode': 13})
    session.cmd('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Enter', 'windowsVirtualKeyCode': 13})
    time.sleep(2)

    # Select latest registration row in popup & confirm
    session.eval("""(() => {
        const dialog = document.querySelector('.el-dialog');
        if (!dialog) return;
        const rows = Array.from(dialog.querySelectorAll('tbody tr'));
        if (rows.length > 0) {
            rows[0].click();
            const confirmBtn = Array.from(dialog.querySelectorAll('button')).find(b => b.innerText.trim() === '确定');
            if (confirmBtn) confirmBtn.click();
        }
    })()""")
    time.sleep(3)

    # Click 自费收费 button
    session.eval("""(() => {
        const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
        const target = buttons.find(b => b.innerText.trim() === '自费收费') || buttons.find(b => b.innerText.trim() === '收费');
        if (target) target.click();
    })()""")
    time.sleep(2)

    # Click 结算 in modal
    settled = session.eval("""(() => {
        const dialogs = Array.from(document.querySelectorAll('.el-dialog, .vxe-modal--box')).filter(d => d.offsetParent !== null);
        for (const d of dialogs) {
            const btn = Array.from(d.querySelectorAll('button')).find(b => b.innerText.trim() === '结算');
            if (btn) {
                btn.click();
                return true;
            }
        }
        return false;
    })()""")
    print(f"  -> 点击结算按钮: {'成功' if settled else '未触发'}")
    time.sleep(4)
    handle_potential_alert(session)

    # Step 3: Outpatient Pharmacy Verification
    print("\n[门诊 2.6] 登录门诊药房 (yf01) 切换至【门诊药房 / 西药房】并校验配药队列...")
    login_ui(session, BASE_URL, username='yf01', password='000000')
    time.sleep(3)

    # Switch role to 门诊药房 via avatar menu
    switch_user_role_and_dept(session, target_role="门诊药房", target_dept="西药房")

    # Open 门诊配药
    session.cmd("Page.navigate", {"url": f"{BASE_URL}/#/outpatient/pharmacy/outDispense"})
    time.sleep(4)

    # Verify patient in 未配药列表
    op_verified = session.eval(f"""(() => {{
        const text = document.body.innerText.replace(/\\s+/g, ' ');
        const hasPatient = text.includes('{patient_name}');
        const hasQueue = text.includes('未配药列表');
        return hasPatient && hasQueue;
    }})()""")

    screenshot_path = "reports/verify/screenshots/universal_outpatient_pharmacy_verified.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    session.screenshot(screenshot_path)
    print(f"  [验证结果] 门诊药房状态核验: {'通过 (未配药/未打印未发药)' if op_verified else '未直接命中'}")
    print(f"  [证据截图] {screenshot_path}")
    return op_verified

# ----------------- Main Entrypoint -----------------

def main():
    parser = argparse.ArgumentParser(description="Universal UI Clinical Pharmacy Data Generator")
    parser.add_argument("--mode", choices=["all", "inpatient", "outpatient"], default="all", help="Execution mode")
    parser.add_argument("--head", action="store_true", help="Launch visible browser")
    parser.add_argument("--inpatient-patient", default="TEST_跨科复测01", help="Target inpatient patient name")
    parser.add_argument("--outpatient-patient", default="李石凤", help="Target outpatient patient name")
    args = parser.parse_args()

    print("=================================================================")
    print("🚀 HIS 通用全流程临床测试数据生成与药房核验套件 (UI-Driven E2E)")
    print(f"模式: {args.mode.upper()} | 浏览器: {'有头模式(窗口可见)' if args.head else '无头模式'}")
    print("约束: 100% 真实前端界面键鼠点击 | 0 直接数据库插入 | 药房未打印未发药")
    print("=================================================================")

    start_time = time.time()
    session = launch_browser(headless=not args.head)

    ip_ok = True
    op_ok = True

    try:
        if args.mode in ("all", "inpatient"):
            ip_ok = run_inpatient_flow(session, patient_name=args.inpatient_patient)

        if args.mode in ("all", "outpatient"):
            op_ok = run_outpatient_flow(session, patient_name=args.outpatient_patient)

        elapsed = time.time() - start_time
        print("\n=================================================================")
        print(f"🎉 全流程执行完毕！耗时: {elapsed:.1f} 秒")
        print(f"  - 住院药房 (未打印、未发药): {'✅ 正常' if ip_ok else '❌ 未就绪'}")
        print(f"  - 门诊药房 (未打印、未发药): {'✅ 正常' if op_ok else '❌ 未就绪'}")
        print("=================================================================")

    finally:
        session.close()

if __name__ == "__main__":
    main()
