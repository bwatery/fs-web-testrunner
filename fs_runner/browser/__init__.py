# -*- coding: utf-8 -*-
"""
fs_runner.browser
=================
自建 CDP 浏览器层与真实界面认证通道：
1. 原生 CDP 通信协议（基于 websocket，带事件缓冲与完整异常捕获）
2. 双模式运行：--headless（独立起实例，给 AI 快速测试）与 --windowed（接管 9222，给人看）
3. 真实表单登录（拒绝注入 token，严格区分密码错 vs 页面未起）
4. 真实界面文本/DOM 抓取与屏幕截图留证
"""
from .cdp import BrowserSession, launch_browser
from .auth import login_ui, LoginError, LoginResult

__all__ = [
    "BrowserSession",
    "launch_browser",
    "login_ui",
    "LoginError",
    "LoginResult",
]
