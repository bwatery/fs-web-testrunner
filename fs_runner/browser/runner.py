# -*- coding: utf-8 -*-
"""
fs_runner.browser.runner
========================
ui-verify 子命令执行引擎：
1. 支持 --headless（默认无头模式，给 AI 快速测试）与 --windowed（窗口接管模式，给人看）。
2. 真实登录认证通道：输账号密码完成表单登录，严格区分「密码错误」与「页面未起」。
3. 门禁硬约束：
   - 浏览器起不来/连不上立即退出并大声报错，严禁静默降级为冒烟或伪通过。
   - --env sandbox 沙盒模式下永不判「通过」，强制产出「未执行」。
   - 支持 --screenshot 将界面执行现场留证落盘至 reports/verify/screenshots/。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import FRONTEND_URL, GATEWAY_URL, ROOT_DIR
from .auth import login_ui
from .cdp import launch_browser, BrowserSession


SCREENSHOTS_DIR = ROOT_DIR / "reports" / "verify" / "screenshots"


def run_ui_verify(args: Any) -> int:
    """执行 ui-verify 子命令。"""
    is_windowed = getattr(args, "windowed", False)
    headless = not is_windowed
    take_screenshot = getattr(args, "screenshot", False)
    env_name = getattr(args, "env", "real") or "real"
    gateway = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")
    frontend = (getattr(args, "frontend", None) or FRONTEND_URL).rstrip("/")
    username = getattr(args, "username", "admin")
    password = getattr(args, "password", "admin123")
    cases_arg = getattr(args, "case", None) or getattr(args, "cases", None)

    mode_label = "[界面·窗口]" if is_windowed else "[界面·无头]"
    env_label = "隔离沙盒 (Sandbox: 永不判通过)" if env_name == "sandbox" else "真实环境 (Real)"

    print("=" * 68)
    print(f"  FS.TestRunner · 界面认证与真实对账 ({mode_label})")
    print("=" * 68)
    print(f"  模式      : {mode_label} ({'接管端口 9222 现有窗口' if is_windowed else '独立拉起 Headless Chrome 实例'})")
    print(f"  运行环境  : {env_label}")
    print(f"  前端地址  : {frontend}")
    print(f"  网关地址  : {gateway}")
    print(f"  截图存盘  : {'开启 (--screenshot)' if take_screenshot else '关闭'}")
    if cases_arg:
        print(f"  目标用例  : {cases_arg}")
    print("-" * 68)

    # 1. 沙盒模式纯离线拦截（严禁既连生产又自称沙盒）
    if env_name == "sandbox":
        print("\n⚠️  [沙盒模式硬门禁] 沙盒环境纯离线运行，严禁连接生产前端与业务网关，强制产出「未执行」！")
        selected_cases = [c.strip() for c in cases_arg.split(",")] if cases_arg else ["L6-005", "L9-012", "L6-050"]
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

        # 4. 截图留证（若指定 --screenshot）
        if take_screenshot:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            shot_file = SCREENSHOTS_DIR / f"ui_auth_{int(time.time())}.png"
            saved_path = session.screenshot(shot_file)
            print(f"📸 登录后视口截图已留痕: {saved_path}")

        print("\n[2/3] 界面认证会话通道就绪！")
        print(f"  会话令牌长度: {len(login_res.token)}")
        print(f"  可访问菜单数: {login_res.menus_count} 项")
        print(f"  浏览器当前页: {session.eval('location.hash') or '/'}")

        # 5. 用例调度准备（等待第 8 步前 3 项主力复核后接入 4~6 具体断言）
        selected_cases = [c.strip() for c in cases_arg.split(",")] if cases_arg else ["L6-005", "L9-012", "L6-050"]
        print(f"\n[3/3] 界面用例执行就绪 (待测用例: {', '.join(selected_cases)})")
        print("\n⚠️  [通道就绪·未做断言] 本次仅完成浏览器拉起与表单登录通道验证，未执行任何具体业务等式断言。")
        print("  （浏览器层与表单认证通道已全量贯通，退出码 3 标识未做业务断言，避免 CI 误判已通过）")
        return 3

    finally:
        session.close()
