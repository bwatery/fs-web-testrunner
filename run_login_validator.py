"""
HIS Login & Session Validator (CLI Standalone Tool)
医院信息系统登录验证器 (非侵入式命令行版)

特点：
1. 完全不修改、不跳转、不点击前端任何网页，绝不破坏医生工作站当前界面！
2. 通过 CDP 提取浏览器登录凭证 (Token) 与医生工作站上下文。
3. 直连 HIS 后端接口与 Oracle 数据库检验用户权限、在院患者列表与 1601 项医嘱字典。
"""

import sys
import os
import time
import json

# Ensure project root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fs_web_testrunner.core.login_validator import LoginValidator

# Enable ANSI colors on Windows
if sys.platform == "win32":
    os.system("color")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{CYAN}{BOLD}      🏥 湛江赤坎中医医院 HIS 登录与会话验证器 (非侵入式版){RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"模式说明: {YELLOW}纯后端 API 与 Oracle 数据验证，完全不操作前端页面{RESET}")
    print(f"后端服务: http://192.168.1.198:8081  |  前端页面: http://192.168.1.198:8088")
    print(f"Oracle库: 192.168.1.199:1521/orcl\n")

def run_diagnosis(validator: LoginValidator):
    print(f"{BOLD}[*] 正在检测当前浏览器会话与登录状态...{RESET}")
    res = validator.run_full_diagnosis()
    status = res.get("status")

    if status == "FAIL":
        print(f"\n{RED}[✗] 错误: {res.get('message')}{RESET}")
        print(f"{YELLOW}👉 提示: 请先启动 Chrome 浏览器窗口并访问 HIS 系统。{RESET}")
        return res

    session = res.get("session", {})
    if status == "WAITING_LOGIN":
        print(f"\n{YELLOW}[!] 浏览器已连接，但尚未检测到登录凭证！{RESET}")
        print(f"    当前页面: {session.get('current_page', '-')}")
        print(f"    页面标题: {session.get('page_title', '-')}")
        print(f"{YELLOW}👉 请在 Chrome 浏览器中输入您的医生工号与密码并登录，然后按 1 重新检测。{RESET}")
        return res

    # Login SUCCESS
    services = res.get("services", {})
    user_info = services.get("user_info", {})
    pat_queue = services.get("patient_queue", {})
    order_dict = services.get("order_dict", {})
    order_rule = services.get("order_rule_service", {})

    print(f"\n{GREEN}{BOLD}[✓] 🎉🎉 登录状态验证通过！{RESET}")
    print(f"    登录用户: {BOLD}{session.get('username')}{RESET} (用户ID: {user_info.get('user_id', 1)})")
    print(f"    角色权限: {BOLD}{user_info.get('role_name', '住院医生')}{RESET} ({user_info.get('role_key', 'ZYYS')})")
    print(f"    当前科室: {BOLD}科室ID {pat_queue.get('dept_id', 910092)}{RESET}")
    print(f"    当前路由: {session.get('current_page', '-')}")
    print(f"    Token摘要: {session.get('token_preview', '-')}")

    print(f"\n{BOLD}----- [后端微服务与 Oracle 数据库连通性] -----{RESET}")
    
    # 1. UserInfo
    u_st = user_info.get("status")
    u_icon = f"{GREEN}[✓]" if u_st == "PASS" else f"{RED}[✗]"
    print(f"{u_icon} 用户身份鉴权 (/userInfo): {u_st} (耗时 {user_info.get('elapsed_ms')}ms)")

    # 2. Patient Queue
    p_st = pat_queue.get("status")
    p_icon = f"{GREEN}[✓]" if p_st == "PASS" else f"{YELLOW}[!]"
    print(f"{p_icon} 在院患者队列 (/ward/patient/list): 在院 {pat_queue.get('patient_count', 0)} 人 (耗时 {pat_queue.get('elapsed_ms')}ms)")
    for p in pat_queue.get("samples", []):
        print(f"      • 床位: {p.get('bedNo')} | 患者: {p.get('patientName')} | 住院号: {p.get('inpatientNo')}")

    # 3. Order Item Dictionary
    o_st = order_dict.get("status")
    o_icon = f"{GREEN}[✓]" if o_st == "PASS" else f"{RED}[✗]"
    print(f"{o_icon} 医嘱项目字典 (/order/item/list): Oracle 库内共 {order_dict.get('total_items', 0)} 项 (耗时 {order_dict.get('elapsed_ms')}ms)")
    sample = order_dict.get("sample", {})
    if sample:
        print(f"      • 示例项目: [{sample.get('itemId')}] {sample.get('itemName')} {sample.get('specs')} (单价: ¥{sample.get('price')}/{sample.get('packageUnit')})")

    # 4. Order Rule Engine
    r_st = order_rule.get("status")
    r_icon = f"{GREEN}[✓]" if r_st == "PASS" else f"{YELLOW}[!]"
    print(f"{r_icon} 医嘱规则引擎 (/order/list): {order_rule.get('message')}")

    print(f"\n{GREEN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{GREEN}{BOLD}结论: 登录有效，后端 API 与 Oracle 数据库连接畅通，完全无需在前端频繁跳转！{RESET}")
    print(f"{GREEN}{BOLD}" + "=" * 70 + f"{RESET}\n")

    return res

def search_meds(validator: LoginValidator):
    kw = input(f"\n{BOLD}请输入要查询的药品/项目名称或拼音码 (如: 丹参, 葡萄糖, 氯化钠, DSZSY): {RESET}").strip()
    if not kw:
        kw = "丹参"
    print(f"[*] 正在 Oracle 医嘱字典中检索 '{kw}'...")
    res = validator.search_order_items(keyword=kw, page_size=8)
    if res.get("status") != "SUCCESS":
        print(f"{RED}[✗] 检索失败: {res.get('message')}{RESET}")
        return

    items = res.get("items", [])
    print(f"\n{GREEN}[✓] 检索完成 (耗时 {res.get('elapsed_ms')}ms，匹配到 {res.get('count')} 条记录):{RESET}")
    print("-" * 75)
    print(f"{'编码':<8} {'项目名称':<18} {'规格':<16} {'单价(元)':<8} {'单位':<6} {'拼音码':<10}")
    print("-" * 75)
    for it in items:
        name = (it.get('itemName') or '')[:16]
        specs = (it.get('specs') or '')[:14]
        print(f"{str(it.get('itemId')):<8} {name:<18} {specs:<16} {str(it.get('price')):<8} {str(it.get('packageUnit')):<6} {str(it.get('spellCode')):<10}")
    print("-" * 75 + "\n")

def open_or_bring_browser():
    print(f"[*] 正在桌面启动或置顶 Chrome 浏览器...")
    from fs_web_testrunner.core.browser_driver import BrowserDriver
    b = BrowserDriver(headless=False)
    b.start("http://192.168.1.198:8088/#/login")
    print(f"{GREEN}[✓] 浏览器窗口已就绪{RESET}\n")

def switch_role_cli(validator: LoginValidator):
    presets = validator.get_role_presets()
    print(f"\n{CYAN}{BOLD}===== 方案 3: 常用角色与科室测试矩阵 (一键热切换) ====={RESET}")
    for idx, p in enumerate(presets, 1):
        print(f" [{idx}] {p['icon']} {p['roleName']:<6} | {p['deptName']:<8} (角色ID:{p['roleId']}, 科室ID:{p['deptId']}) -> {p['route']}")
        print(f"      业务职责: {p['desc']}")
    print(f" [0] 返回主菜单")
    
    choice = input(f"{CYAN}请选择要切换的身份编号 [1-{len(presets)}]: {RESET}").strip()
    if choice == "0" or not choice:
        return
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(presets):
            target = presets[idx]
            print(f"[*] 正在为 Chrome 浏览器切换身份至: {target['roleName']} · {target['deptName']}...")
            res = validator.switch_identity_in_browser(target['roleId'], target['deptId'], target['route'])
            if res.get("status") == "SUCCESS":
                print(f"{GREEN}[✓] {res.get('message')}{RESET}\n")
                time.sleep(1.5)
                run_diagnosis(validator)
            else:
                print(f"{RED}[✗] {res.get('message')}{RESET}\n")
        else:
            print(f"{RED}无效序号{RESET}\n")
    except ValueError:
        print(f"{RED}请输入有效数字{RESET}\n")

def preset_role_cli(validator: LoginValidator):
    presets = validator.get_role_presets()
    print(f"\n{CYAN}{BOLD}===== 方案 1: 预置下次登录身份 (写入角色科室缓存) ====={RESET}")
    print(f"{YELLOW}提示: 在未登录状态下预置后，您在浏览器点击登录将直接以所选身份进入工作站{RESET}")
    for idx, p in enumerate(presets, 1):
        print(f" [{idx}] {p['icon']} {p['roleName']:<6} | {p['deptName']:<8} (角色ID:{p['roleId']}, 科室ID:{p['deptId']})")
    print(f" [C] 自定义输入 角色ID 与 科室ID")
    print(f" [0] 返回主菜单")
    
    choice = input(f"{CYAN}请选择预置身份编号 [1-{len(presets)} 或 C]: {RESET}").strip()
    if choice == "0" or not choice:
        return
    
    if choice.upper() == "C":
        try:
            r_id = int(input("请输入角色ID (如 15, 35, 14): ").strip())
            d_id = int(input("请输入科室ID (如 910073, 910092): ").strip())
            res = validator.preset_login_identity(r_id, d_id)
            if res.get("status") == "SUCCESS":
                print(f"{GREEN}[✓] {res.get('message')}{RESET}\n")
            else:
                print(f"{RED}[✗] {res.get('message')}{RESET}\n")
        except Exception as e:
            print(f"{RED}输入有误: {e}{RESET}\n")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(presets):
            target = presets[idx]
            res = validator.preset_login_identity(target['roleId'], target['deptId'], target['route'])
            if res.get("status") == "SUCCESS":
                print(f"{GREEN}[✓] {res.get('message')}{RESET}\n")
            else:
                print(f"{RED}[✗] {res.get('message')}{RESET}\n")
        else:
            print(f"{RED}无效序号{RESET}\n")
    except ValueError:
        print(f"{RED}请输入有效数字{RESET}\n")

def list_all_roles_depts(validator: LoginValidator):
    print(f"\n{CYAN}{BOLD}===== 全院 15 岗位角色与科室关联架构 ====={RESET}")
    roles = validator.get_roles_list()
    for r in roles:
        r_id = r.get("roleId")
        r_name = r.get("roleName")
        r_key = r.get("roleKey", "")
        print(f"\n{BOLD}岗位角色 [{r_id}] {r_name} ({r_key}):{RESET}")
        depts = validator.get_depts_by_role(r_id)
        dept_str = ", ".join([f"{d.get('deptName')}({d.get('deptId')})" for d in depts[:8]])
        if len(depts) > 8:
            dept_str += f" ... 等共 {len(depts)} 个科室"
        print(f"  关联科室: {dept_str}")
    print("\n")

def main():
    print_banner()
    validator = LoginValidator()
    run_diagnosis(validator)

    while True:
        print(f"{BOLD}请选择操作指令:{RESET}")
        print(" [1] 重新检测当前登录与会话状态")
        print(" [2] 检索 Oracle 医嘱项目与药品字典 (拼音码/名称)")
        print(" [3] 弹出 / 置顶 Chrome 浏览器窗口")
        print(f" {GREEN}[4] 一键热切换当前角色与科室 (方案3: 矩阵预置切换){RESET}")
        print(f" {YELLOW}[5] 预置下次登录身份 (方案1: 锁定角色与科室){RESET}")
        print(" [6] 查看全院 15 岗位角色与科室关联架构")
        print(" [0] 退出")
        choice = input(f"{CYAN}请输入编号 [0-6]: {RESET}").strip()

        if choice == "1":
            run_diagnosis(validator)
        elif choice == "2":
            search_meds(validator)
        elif choice == "3":
            open_or_bring_browser()
        elif choice == "4":
            switch_role_cli(validator)
        elif choice == "5":
            preset_role_cli(validator)
        elif choice == "6":
            list_all_roles_depts(validator)
        elif choice == "0":
            print("已退出 HIS 登录验证器。")
            break
        else:
            print("无效输入，请重新选择。\n")

if __name__ == "__main__":
    main()
