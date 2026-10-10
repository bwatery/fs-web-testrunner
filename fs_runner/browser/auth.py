# -*- coding: utf-8 -*-
"""
fs_runner.browser.auth
======================
真实界面认证通道：
1. 真实表单模拟输入账号与密码（基于 Vue 3 响应式原型 setter），绝不通过直接注入 token 伪造登录。
2. 严格区分失败根因：
   - PAGE_NOT_REACHABLE: 前端服务未启动、白页或登录表单未渲染
   - INVALID_CREDENTIALS: 账号或密码错误（捕获 Element Plus 真实报错 Toast）
   - TIMEOUT / OTHER: 登录请求超时或会话未生效
3. 登录成功后回读并验证 sessionStorage 中的会话令牌与侧边栏菜单状态。
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .cdp import BrowserSession


class LoginError(RuntimeError):
    """界面认证异常基类。"""
    def __init__(self, message: str, error_type: str = "LOGIN_FAILED"):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class LoginResult:
    ok: bool
    error_type: Optional[str] = None
    detail: str = ""
    token: str = ""
    menus_count: int = 0
    duration_ms: float = 0.0


def login_ui(
    session: BrowserSession,
    frontend_url: str,
    username: str = "admin",
    password: str = "admin123",
    wait_sec: float = 7.0,
) -> LoginResult:
    """通过真实浏览器页面表单执行登录认证。

    参数:
        session: 已启动的 BrowserSession 实例
        frontend_url: 前端服务根地址（如 http://127.0.0.1:8080）
        username: 登录用户名
        password: 登录密码
        wait_sec: 登录点击后等待会话生效的超时时间
    """
    t0 = time.time()
    fe = frontend_url.rstrip("/")

    # 1. 导航至登录页面并排查「页面没起来」
    login_url = f"{fe}/#/login"
    try:
        session.navigate(login_url, wait_sec=2.0)
    except Exception as e:
        dur = round((time.time() - t0) * 1000, 1)
        return LoginResult(
            ok=False,
            error_type="PAGE_NOT_REACHABLE",
            detail=f"页面没起来：导航至 {login_url} 发生异常 ({e})",
            duration_ms=dur,
        )

    # 清理遗留会话令牌以确保证实认证
    session.eval("(() => { try { sessionStorage.removeItem('shop-vite-token'); } catch(e){} return true; })()")
    session.reload(ignore_cache=True, wait_sec=2.5)

    # 2. 检查登录页输入表单元素是否存在（区分"页面没起来" vs 正常渲染）
    form_check = session.eval("""(() => {
        const ins = Array.from(document.querySelectorAll('input'));
        const u = ins.find(i => i.type === 'text') || ins[0];
        const pw = ins.find(i => i.type === 'password') || ins[1];
        const btn = Array.from(document.querySelectorAll('button'))
                         .find(b => (b.innerText || '').includes('登录'));
        if (!u && !pw && !btn) {
            return { ready: false, reason: '页面未能渲染任何输入框或登录按钮（白页或路由异常）' };
        }
        if (!u || !pw) {
            return { ready: false, reason: '未找到用户名或密码输入框' };
        }
        if (!btn) {
            return { ready: false, reason: '未找到登录按钮' };
        }
        return { ready: true };
    })()""")

    if not isinstance(form_check, dict) or not form_check.get("ready"):
        reason = (form_check or {}).get("reason", "登录界面未渲染完成")
        dur = round((time.time() - t0) * 1000, 1)
        return LoginResult(
            ok=False,
            error_type="PAGE_NOT_REACHABLE",
            detail=f"页面没起来：{reason}",
            duration_ms=dur,
        )

    # 3. 填入账号与密码（使用 Vue 3 HTMLInputElement 原型 setter 触发响应式更新）
    u_json = json.dumps(username)
    pw_json = json.dumps(password)

    fill_res = session.eval(f"""(() => {{
        const ins = Array.from(document.querySelectorAll('input'));
        const u = ins.find(i => i.type === 'text') || ins[0];
        const pw = ins.find(i => i.type === 'password') || ins[1];
        const btn = Array.from(document.querySelectorAll('button'))
                         .find(b => (b.innerText || '').includes('登录'));

        const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
        const setVal = (el, val) => {{
            desc.set.call(el, val);
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }};

        setVal(u, {u_json});
        setVal(pw, {pw_json});

        btn.click();
        return {{ ok: true }};
    }})()""")

    if not isinstance(fill_res, dict) or not fill_res.get("ok"):
        dur = round((time.time() - t0) * 1000, 1)
        return LoginResult(
            ok=False,
            error_type="FORM_FILL_FAILED",
            detail="表单数据注入或登录按钮点击失败",
            duration_ms=dur,
        )

    # 4. 轮询等待登录结果，捕获「账号密码错」或登录成功跳转
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        time.sleep(0.4)
        session.drain(0.2)

        # 检查是否捕获到 Element Plus 错误 Toast / 表单错误提示 / 文本提示
        err_info = session.eval("""(() => {
            const elMsg = document.querySelector('.el-message--error')
                       || document.querySelector('.el-notification--error')
                       || document.querySelector('.el-message__content')
                       || document.querySelector('.el-form-item__error');
            if (elMsg) {
                const txt = (elMsg.innerText || elMsg.textContent || '').trim();
                if (txt) return txt;
            }
            // 扫描包含认证失败文案的叶子元素
            const errKeywords = ['用户不存在', '密码错误', '账号错误', '验证码错误', '登录失败'];
            for (const el of document.querySelectorAll('div, span, p')) {
                if (el.children.length === 0) {
                    const t = (el.innerText || el.textContent || '').trim();
                    for (const kw of errKeywords) {
                        if (t.includes(kw)) return t;
                    }
                }
            }
            return null;
        })()""")

        if err_info:
            dur = round((time.time() - t0) * 1000, 1)
            return LoginResult(
                ok=False,
                error_type="INVALID_CREDENTIALS",
                detail=f"账号密码错：界面提示「{err_info}」",
                duration_ms=dur,
            )

        # 检查是否跳转成功且 sessionStorage 拥有 token
        login_status = session.eval("""(() => {
            const h = location.hash || '';
            const notLoginHash = (h.indexOf('/login') === -1) && (h.length > 2);
            const token = sessionStorage.getItem('shop-vite-token') || '';
            const menus = document.querySelectorAll('.el-menu-item').length;
            return {
                redirected: notLoginHash,
                hasToken: (token.length > 0),
                token: token,
                menus: menus
            };
        })()""")

        if isinstance(login_status, dict) and login_status.get("redirected") and login_status.get("hasToken"):
            dur = round((time.time() - t0) * 1000, 1)
            tok = login_status.get("token", "")
            menus = int(login_status.get("menus", 0))
            return LoginResult(
                ok=True,
                detail=f"界面认证成功（侧边栏菜单 {menus} 项，会话已确证）",
                token=tok,
                menus_count=menus,
                duration_ms=dur,
            )

    # 超时未生效
    dur = round((time.time() - t0) * 1000, 1)
    # 取当前 hash 与界面文本协助诊断
    current_hash = session.eval("location.hash") or ""
    return LoginResult(
        ok=False,
        error_type="TIMEOUT_OR_BLOCKED",
        detail=f"登录在 {wait_sec} 秒内未完成会话跳转（当前页面 Hash: {current_hash}，无明确报错弹出）",
        duration_ms=dur,
    )
