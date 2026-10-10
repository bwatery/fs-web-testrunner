"""
工作站功能巡检（Workstation Check）

针对用户的真实问题："菜单里的工作站是否正常？"

普通巡检只能回答"页面能不能打开"。但页面打得开、里面的数据却拉不到，
在用户看来同样是坏的。所以这里在打开页面的同时**监听该页面发出的所有 XHR/fetch**，
把 4xx/5xx 与前端异常一并采集——这才是"工作站是否真的能用"。

实现上自建一个带事件缓冲的 CDP 客户端，因为 core/browser_driver.py 的
send_cdp_command 会丢弃非应答事件，拿不到 Network.responseReceived。
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
import websocket

# 记录最近一次的前端 origin：重载时需要它来拼完整 URL
recent_origin = [""]

_CDP_HOST = "127.0.0.1"
_CDP_PORT = 9222


class CDPPage:
    """带事件缓冲的极简 CDP 客户端（只连已有页面，不启动新浏览器）。"""

    def __init__(self, port: int = _CDP_PORT, host: str = _CDP_HOST):
        self.port = port
        self.host = host
        self.ws: Optional[websocket.WebSocket] = None
        self._id = 0
        self.events: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        tabs = requests.get(f"http://{self.host}:{self.port}/json", timeout=4,
                            proxies={"http": None, "https": None}).json()
        page = next((t for t in tabs if t.get("type") == "page"), None)
        if not page:
            return False
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20)
        self.cmd("Runtime.enable")
        self.cmd("Network.enable")
        self.cmd("Page.enable")
        return True

    def cmd(self, method: str, params: Optional[Dict[str, Any]] = None,
            timeout: float = 20.0) -> Dict[str, Any]:
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error'].get('message')}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)          # 缓冲事件，稍后消费
        raise TimeoutError(f"CDP {method} 超时")

    def drain(self, timeout: float = 1.0) -> List[Dict[str, Any]]:
        """把缓冲里的事件取走，顺带再抽一会儿新事件。"""
        end = time.time() + timeout
        self.ws.settimeout(0.25)
        try:
            while time.time() < end:
                try:
                    raw = self.ws.recv()
                except Exception:
                    continue
                if not raw:
                    continue
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                if "method" in m:
                    self.events.append(m)
        finally:
            self.ws.settimeout(20)
        out, self.events = self.events, []
        return out

    def eval(self, expr: str) -> Any:
        r = self.cmd("Runtime.evaluate",
                     {"expression": expr, "returnByValue": True, "awaitPromise": True})
        v = r.get("result", {})
        return v["value"] if "value" in v else v.get("description")

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass


def _is_api_url(url: str) -> bool:
    return (":8081" in url) or ("/api" in url) or ("/faith/" in url)


def _is_local_control(url: str) -> bool:
    """本机控件服务：127.0.0.1 / localhost 上的打印、授权、加解密等客户端控件。"""
    return ("127.0.0.1" in url) or ("localhost" in url)


def _layer_of(url: str) -> str:
    """
    把失败调用归类，因为三类失败的处置方式完全不同：
      网关    —— 后端系统故障，必须报
      外部服务 —— 报表服务器等第三方系统，用户会直接看到白页，也要报
      本机控件 —— 终端上没装/没启动的控件，属环境问题，页面本身不受影响
    """
    if _is_api_url(url):
        return "网关"
    if _is_local_control(url):
        return "本机控件"
    return "外部服务"


def _is_benign_failure(url: str, error_text: str) -> bool:
    """明显不算问题的失败：自定义协议、浏览器主动取消、静态资源缺失。"""
    if url.startswith(("infectupload:", "about:", "data:", "blob:", "chrome")):
        return True
    if "ERR_ABORTED" in (error_text or "") or "NS_BINDING_ABORTED" in (error_text or ""):
        return True          # 页面切换导致的取消，不算故障
    # 静态资源缺失与业务功能无关（PWA 清单、图标、sourcemap 等），不算故障
    low = url.lower().split("?")[0]
    for suffix in (".webmanifest", ".ico", ".map", ".png", ".jpg", ".svg",
                   ".woff", ".woff2", ".ttf", ".css"):
        if low.endswith(suffix):
            return True
    return False


def _analyze_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    从 CDP 事件流里挑出"调用失败"和"前端异常"。

    不能只看 8081 网关：工作站页面还会调用外部报表服务、以及本机控件服务，
    这些失败用户都能感知到，所以除自定义协议外一律纳入统计，只是分层归类。
    """
    failed: List[Dict[str, Any]] = []
    exceptions: List[str] = []
    pending: Dict[str, str] = {}
    seen_requests = 0

    for ev in events:
        m = ev.get("method")
        p = ev.get("params") or {}
        if m == "Network.requestWillBeSent":
            req = p.get("request") or {}
            url = req.get("url") or ""
            pending[p.get("requestId")] = url
            if not _is_benign_failure(url, ""):
                seen_requests += 1
        elif m == "Network.responseReceived":
            rid = p.get("requestId")
            resp = p.get("response") or {}
            status = resp.get("status") or 0
            url = resp.get("url") or pending.get(rid) or ""
            if status >= 400 and not _is_benign_failure(url, ""):
                failed.append({"url": url, "status": status, "layer": _layer_of(url)})
            pending.pop(rid, None)
        elif m == "Network.loadingFailed":
            rid = p.get("requestId")
            err = p.get("errorText") or "请求失败"
            url = pending.pop(rid, "")
            if url and not _is_benign_failure(url, err):
                failed.append({"url": url, "status": 0, "error": err,
                               "layer": _layer_of(url)})
        elif m == "Runtime.exceptionThrown":
            d = (p.get("exceptionDetails") or {})
            txt = (d.get("exception") or {}).get("description") or d.get("text") or ""
            if txt:
                exceptions.append(str(txt).split("\n")[0][:200])
    return {"failed_requests": failed, "exceptions": exceptions,
            "requests_seen": seen_requests}


@dataclass
class WorkstationResult:
    role: str
    role_id: Optional[int]
    dept_id: Optional[int]
    name: str
    opened: bool = False
    status: str = "PENDING"          # PASSED / FAILED / SKIPPED
    reasons: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    failed_requests: List[Dict[str, Any]] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    requests_seen: int = 0
    reloaded: bool = False
    health: Dict[str, Any] = field(default_factory=dict)
    screenshot: Optional[str] = None


# 页面健康（与 ui_walk 同源，改为在 CDPPage 上执行）
_HEALTH_JS = """
(() => {
  const bodyText = document.body ? document.body.innerText.trim() : '';
  const hash = window.location.hash || '';
  const sels = ['.vab-app-main', '.el-main', '.app-main'];
  let el = null, sel = '';
  for (const s of sels) { const e = document.querySelector(s); if (e) { el = e; sel = s; break; } }
  const q = s => el ? el.querySelectorAll(s).length : 0;
  let tabTitle = '';
  const at = document.querySelector('.el-tabs__item.is-active');
  if (at) tabTitle = (at.innerText || '').trim();
  return {
    hash: hash, tabTitle: tabTitle, contentSel: sel,
    is404: hash.includes('/404') || bodyText.includes('抱歉！当前页面不存在'),
    isLogin: hash.includes('/login'),
    contentTextLen: el ? (el.innerText || '').trim().length : -1,
    tables: q('.el-table'), rows: q('.el-table__body-wrapper tbody tr'),
    forms: q('.el-form'), buttons: q('.el-button'), inputs: q('input'),
    iframes: q('iframe'),
    errorToasts: Array.from(document.querySelectorAll(
        '.el-message--error,.el-notification--error,.el-alert--error')).map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,3)
  };
})()
"""


def check_workstation(page: CDPPage, role_label: str, menu_text: str,
                      role_id: Optional[int] = None, dept_id: Optional[int] = None,
                      settle_sec: float = 5.0,
                      screenshot_dir: Optional[str] = None) -> WorkstationResult:
    """打开一个工作站菜单项，校验它是否真的可用。"""
    res = WorkstationResult(role=role_label, role_id=role_id, dept_id=dept_id,
                            name=menu_text)
    # 回到首页再点，模拟真人从菜单进入
    try:
        page.cmd("Runtime.evaluate",
                 {"expression": "location.hash = '#/index'"})
        time.sleep(1.2)
        page.drain(0.4)
    except Exception:
        pass

    before = page.eval("location.hash") or ""
    click_js = """(() => {
        const norm = s => (s||'').replace(/\\s+/g,' ').trim();
        const target = %s;
        const items = () => Array.from(document.querySelectorAll('.el-menu-item'));
        let el = items().find(e => norm(e.innerText) === target);
        if (!el) {   // 菜单可能折叠
          document.querySelectorAll('.el-sub-menu__title').forEach(e => e.click());
          el = items().find(e => norm(e.innerText) === target);
        }
        if (!el) el = items().find(e => norm(e.innerText).includes(target));
        if (!el) el = items().find(e => target.includes(norm(e.innerText)) && norm(e.innerText).length > 3);
        if (!el) {
          return {ok: false, available: items().map(e => norm(e.innerText)).filter(Boolean).slice(0, 30)};
        }
        el.scrollIntoView({block:'center'}); el.click();
        return {ok: true, text: norm(el.innerText)};
    })()""" % json.dumps(menu_text, ensure_ascii=False)
    clicked = page.eval(click_js)

    if not (isinstance(clicked, dict) and clicked.get("ok")):
        avail = (clicked or {}).get("available") or []
        res.reasons.append(
            f"菜单中找不到「{menu_text}」，无法进入该工作站"
            + (f"（当前侧边栏可见菜单：{'、'.join(avail[:15])}）" if avail else ""))
        res.status = "FAILED"
        return res

    time.sleep(settle_sec)

    # 本前端的已知特性：只靠 hash 跳转不会加载页面组件，内容区会停在仪表盘
    # （表现为"标签页名字对了、内容却还是首页"）。真人此时会按 F5。
    # 所以点完菜单后一律补一次整页重载再判定——不做这个，就会把前端特性误报成页面故障。
    try:
        cur_hash = page.eval("location.hash") or ""
        origin = page.eval("location.origin") or recent_origin[0]
        if origin:
            recent_origin[0] = origin
        if cur_hash and origin:
            page.cmd("Page.navigate", {"url": f"{origin}/{cur_hash}"})
            time.sleep(2.5)
            page.cmd("Page.reload", {"ignoreCache": True})
            time.sleep(settle_sec + 1.0)
            res.reloaded = True
    except Exception:
        pass

    events = page.drain(1.1)
    analysis = _analyze_events(events)
    health = page.eval(_HEALTH_JS) or {}
    res.health = health if isinstance(health, dict) else {}
    res.failed_requests = analysis["failed_requests"]
    res.exceptions = analysis["exceptions"]
    res.requests_seen = analysis.get("requests_seen", 0)
    res.opened = True

    h = res.health
    hard: List[str] = []      # 真正的功能故障
    soft: List[str] = []      # 本机控件/终端环境未就绪，页面本身是好的

    if h.get("is404"):
        hard.append(f"路由 404 (hash={h.get('hash')})")
    if h.get("isLogin"):
        hard.append("被踢回登录页")
    if h.get("contentTextLen", -1) == -1:
        hard.append("未定位到内容容器")
    elif h.get("contentTextLen", 0) < 20 and not (h.get("tables") or h.get("forms")
                                                  or h.get("iframes")):
        hard.append(f"内容区为空（文字 {h.get('contentTextLen')} 字）")
    toasts = h.get("errorToasts") or []
    if toasts:
        hard.append(f"页面弹出错误提示: 『{toasts[0][:120]}』")
    if res.exceptions:
        hard.append(f"前端 JS 异常: {res.exceptions[0][:160]}")

    if res.failed_requests:
        # 分层处置：后端网关 / 外部服务失败必须报；
        # 本机控件（打印、授权等）用户暂未安装，本轮只记录不判定，避免噪声
        gw = [f for f in res.failed_requests if f.get("layer") == "网关"]
        ext = [f for f in res.failed_requests if f.get("layer") == "外部服务"]
        local = [f for f in res.failed_requests if f.get("layer") == "本机控件"]
        if gw:
            s = gw[0]
            hard.append(f"页面加载时 {len(gw)} 个后端接口调用失败，"
                        f"例如 HTTP {s.get('status')} {str(s.get('url'))[:110]}")
        if ext:
            s = ext[0]
            detail = s.get("error") or f"HTTP {s.get('status')}"
            hard.append(f"{len(ext)} 次外部服务调用失败（{detail}，"
                        f"{str(s.get('url'))[:90]}）——用户看到的是空白内容")
        if local:
            res.notes.append(
                f"另有 {len(local)} 次本机控件调用失败（打印/授权控件未安装），"
                f"按约定本轮不判定")

    if res.requests_seen == 0 and not hard:
        # 首页等纯展示页确实不发请求，这不算故障，但也不能声称已验证其数据
        res.notes.append("页面打开期间未观察到接口调用，无法判定其数据加载是否正常")

    # 点了菜单却停在原页面 = 该功能入口无效。
    # 例外：巡检前本来就在 #/index，点「首页」自然不动，这不是故障。
    already_home = (h.get("hash") or "").startswith("#/index") and \
                   (before or "").startswith("#/index")
    if h.get("hash") == before and not hard and not already_home:
        hard.append(f"点击后未离开原页面（仍为 {before}）——该菜单功能入口无效")

    res.reasons = hard
    res.status = "FAILED" if hard else "PASSED"
    if res.status == "FAILED" and screenshot_dir:
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
            r = page.cmd("Page.captureScreenshot", {"format": "png"})
            p = os.path.join(screenshot_dir,
                             f"ws_fail_{int(time.time())}.png")
            import base64
            with open(p, "wb") as f:
                f.write(base64.b64decode(r.get("data", "")))
            res.screenshot = p
        except Exception:
            pass
    return res


def _expected_menu_names(gateway: str, token: str) -> List[str]:
    """用某一身份的令牌取 /getRouters，得到该角色**应该**在侧边栏看到的菜单名。"""
    try:
        r = requests.get(f"{gateway.rstrip('/')}/getRouters",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=15, proxies={"http": None, "https": None})
        data = (r.json() or {}).get("data") or []
    except Exception:
        return []
    out: List[str] = []

    def walk(nodes):
        for n in nodes or []:
            if (n.get("menuType") == "C" and str(n.get("visible", "0")) == "0"
                    and (n.get("component") or "") != "Layout"
                    and (n.get("menuName") or "").strip()):
                out.append((n.get("menuName") or "").strip())
            walk(n.get("children") or [])
    walk(data)
    return out


def login_real(page: CDPPage, frontend: str, username: str = "admin",
               password: str = "admin123", wait_sec: float = 8.0) -> Dict[str, Any]:
    """
    用登录页表单真实登录。

    ⚠️ 绝不写入 localStorage.userRoleDeptCache：
    该键由前端自己维护，结构是 {userId: {roleId: deptId}}。
    早先版本在这里直接 c[roleId]=deptId 把它压平，导致 getUserInfo 抛
    "Cannot create property '14' on number '1'"，整个前端登录卡死。
    任何需要动它的代码都必须保留原结构，或者干脆不碰。
    """
    out: Dict[str, Any] = {"ok": False, "detail": ""}
    try:
        page.cmd("Page.navigate", {"url": f"{frontend.rstrip('/')}/#/login"})
        time.sleep(3)
        page.drain(0.5)
        page.eval("""(() => { try { sessionStorage.removeItem('shop-vite-token'); } catch(e){} return true; })()""")
        page.cmd("Page.reload", {"ignoreCache": True})
        time.sleep(4)

        filled = page.eval("""(() => {
            const ins = Array.from(document.querySelectorAll('input'));
            const u = ins.find(i => i.type === 'text') || ins[0];
            const pw = ins.find(i => i.type === 'password') || ins[1];
            if (!u || !pw) return {ok: false, reason: '登录页找不到输入框'};
            // Vue 3 的 v-model 只认原型上的 value setter，直接赋值不会触发更新
            const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            const set = (el, v) => { desc.set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
            set(u, %s); set(pw, %s);
            const btn = Array.from(document.querySelectorAll('button'))
                             .find(b => (b.innerText || '').includes('登录'));
            if (!btn) return {ok: false, reason: '登录页找不到登录按钮'};
            btn.click();
            return {ok: true};
        })()""" % (json.dumps(username), json.dumps(password)))

        if not (isinstance(filled, dict) and filled.get("ok")):
            out["detail"] = f"登录表单操作失败: {(filled or {}).get('reason')}"
            return out

        time.sleep(wait_sec)
        page.drain(0.6)
        ok = page.eval("(location.hash.indexOf('/login') === -1)")
        tok_len = page.eval("(sessionStorage.getItem('shop-vite-token')||'').length") or 0
        menus = page.eval("document.querySelectorAll('.el-menu-item').length") or 0
        if not ok or not tok_len:
            # 取一次前端异常，便于定位（这类错误此前正是被我写坏的缓存引起的）
            errs = page.eval("(() => (window.__verifyErrors||[]).slice(0,2))()")
            out["detail"] = (f"登录未生效（hash={page.eval('location.hash')}, "
                             f"token={tok_len}）")
            if errs:
                out["detail"] += f"；前端异常: {str(errs)[:160]}"
            return out
        out["ok"] = True
        out["menus"] = menus
        out["detail"] = f"已登录，侧边栏 {menus} 项"
    except Exception as e:
        out["detail"] = f"登录异常: {type(e).__name__}: {str(e)[:110]}"
    return out


def switch_role_via_ui(page: CDPPage, role_name: str, dept_name: str,
                       wait_sec: float = 6.0) -> Dict[str, Any]:
    """
    通过界面自身的「切换角色」对话框换权——这是这个前端唯一正确的换权方式。
    不走令牌注入，因此不会破坏前端自己的会话状态。
    """
    out: Dict[str, Any] = {"ok": False, "detail": ""}
    try:
        # 1. 打开右上角用户下拉（用稳定的 .avatar-dropdown，不靠文字猜）
        opened = page.eval("""(() => {
            const el = document.querySelector('.avatar-dropdown')
                    || document.querySelector('.user-avatar')
                    || document.querySelector('.username');
            if (!el) return false;
            el.click(); return true;
        })()""")
        if not opened:
            out["detail"] = "找不到右上角用户下拉入口"
            return out
        time.sleep(1.2)

        # 2. 点「切换角色」
        clicked = page.eval("""(() => {
            const el = Array.from(document.querySelectorAll('.el-dropdown-menu__item'))
                            .find(x => (x.innerText || '').includes('切换'));
            if (!el) return false;
            el.click(); return true;
        })()""")
        if not clicked:
            out["detail"] = "下拉菜单里没有「切换角色」项"
            return out
        time.sleep(2.0)

        # 3. 在对话框里依次选择角色与科室
        for sel_idx, target in ((0, role_name), (1, dept_name)):
            if not target:
                continue
            page.eval(f"""(() => {{
                const d = Array.from(document.querySelectorAll('.el-dialog'))
                               .find(x => x.offsetParent !== null);
                if (!d) return false;
                const s = d.querySelectorAll('.el-select')[{sel_idx}];
                if (!s) return false;
                const inp = s.querySelector('input');
                if (inp) inp.click(); else s.click();
                return true;
            }})()""")
            time.sleep(1.2)
            picked = page.eval(
                f"""(() => {{
                    const opts = Array.from(document.querySelectorAll(
                        '.el-select-dropdown__item')).filter(o => o.offsetParent !== null);
                    const el = opts.find(o => (o.innerText || '').trim() === {json.dumps(target)})
                            || opts.find(o => (o.innerText || '').includes({json.dumps(target)}));
                    if (!el) return false;
                    el.click(); return true;
                }})()""")
            if not picked:
                out["detail"] = f"下拉里找不到「{target}」"
                return out
            time.sleep(1.0)

        # 4. 确定
        page.eval("""(() => {
            const d = Array.from(document.querySelectorAll('.el-dialog'))
                           .find(x => x.offsetParent !== null);
            if (!d) return false;
            const b = Array.from(d.querySelectorAll('button'))
                           .find(x => (x.innerText || '').trim() === '确定');
            if (!b) return false;
            b.click(); return true;
        })()""")
        time.sleep(wait_sec)
        page.drain(0.6)
        menus = page.eval("""(() => Array.from(document.querySelectorAll('.el-menu-item'))
            .map(e => (e.innerText||'').replace(/\\s+/g,' ').trim()).filter(Boolean))()""")
        menus = menus if isinstance(menus, list) else []
        out["menus"] = menus
        if not menus:
            out["detail"] = "切换后侧边栏为空"
            return out
        out["ok"] = True
        out["detail"] = f"已通过界面切换，侧边栏 {len(menus)} 项"
    except Exception as e:
        out["detail"] = f"界面切换异常: {type(e).__name__}: {str(e)[:110]}"
    return out


def switch_role(page: CDPPage, gateway: str, role_id: int, dept_id: int,
                frontend: str, wait_sec: float = 7.0,
                prev_menus: Optional[List[str]] = None,
                role_name: str = "", dept_name: str = "") -> Dict[str, Any]:
    """
    换权：/login -> /exchangeLogin 换取该角色令牌 -> 写入 sessionStorage -> 重载。

    ⚠️ 只写 shop-vite-token，**绝不写 localStorage.userRoleDeptCache**。
    那个键由前端自己维护、结构是 {userId:{roleId:deptId}}；
    早先版本往里压平写导致 getUserInfo 抛
    "Cannot create property '14' on number '1'"，把整个前端登录卡死。

    换权后必须**回读校验**：新令牌要能取到该角色的菜单配置、且侧边栏确实渲染出来。
    校验不过就返回失败，绝不默认成功。
    """
    out: Dict[str, Any] = {"ok": False, "detail": "", "menus": []}
    expected: List[str] = []
    try:
        # 同一 login 令牌只能换一次权，所以每次都重新登录
        r = requests.post(f"{gateway.rstrip('/')}/login",
                          json={"username": "admin", "password": "admin123"},
                          timeout=10, proxies={"http": None, "https": None})
        base_tok = (r.json() or {}).get("data")
        if not base_tok:
            out["detail"] = f"管理员登录失败: HTTP {r.status_code}"
            return out
        r2 = requests.post(f"{gateway.rstrip('/')}/exchangeLogin",
                           headers={"Authorization": f"Bearer {base_tok}",
                                    "Content-Type": "application/json"},
                           json={"roleId": role_id, "deptId": dept_id},
                           timeout=10, proxies={"http": None, "https": None})
        body = r2.json() or {}
        tok = body.get("data")
        if body.get("code") != 200 or not tok:
            out["detail"] = f"换权被拒绝: {body.get('msg') or body}"
            return out
        expected = _expected_menu_names(gateway, tok)
        if not expected:
            out["detail"] = "该角色没有取到菜单配置，无法校验换权是否生效"
            return out
    except Exception as e:
        out["detail"] = f"换权请求异常: {type(e).__name__}: {str(e)[:110]}"
        return out

    last_detail = ""
    for attempt in range(3):
        try:
            page.eval("(()=>{ sessionStorage.setItem('shop-vite-token', %s); return true; })()"
                      % json.dumps(tok))
            page.cmd("Page.navigate", {"url": f"{frontend.rstrip('/')}/#/index"})
            time.sleep(1.0)
            page.cmd("Page.reload", {"ignoreCache": True})
        except Exception:
            page.cmd("Page.navigate", {"url": f"{frontend.rstrip('/')}/#/index"})
        time.sleep(wait_sec)
        page.drain(0.8)

        menus = page.eval("""(() => Array.from(document.querySelectorAll('.el-menu-item'))
            .map(e => (e.innerText||'').replace(/\\s+/g,' ').trim()).filter(Boolean))()""")
        menus = menus if isinstance(menus, list) else []
        out["menus"] = menus
        if not menus:
            last_detail = "换权后侧边栏为空（前端可能仍未接受该令牌）"
            continue
        rendered = {m.strip() for m in menus}
        missing = [n for n in expected if n not in rendered]
        if missing:
            last_detail = (f"换权未生效：侧边栏缺少该角色应有的 {len(missing)} 个菜单"
                           f"（如 {missing[0]}）")
            continue
        if prev_menus and set(prev_menus) == rendered and set(expected) != rendered:
            last_detail = "换权未生效：侧边栏菜单与上一个角色完全相同"
            continue

        out["ok"] = True
        out["expected"] = expected
        out["detail"] = (f"已切换并校验通过，侧边栏 {len(menus)} 项"
                         + (f"（第 {attempt + 1} 次重载生效）" if attempt else ""))
        return out

    out["detail"] = last_detail or "换权未生效"
    return out


def list_workstations(page: CDPPage, keyword: str = "") -> List[str]:
    """
    列出当前侧边栏的菜单项。
    keyword 为空则返回全部——用户问的"菜单里的工作站"，多数是各角色的主工作页面，
    未必字面叫"工作站"，所以默认全量巡检，可用关键词收窄。
    """
    try:
        items = page.eval("""(() => {
            const norm = s => (s||'').replace(/\\s+/g,' ').trim();
            document.querySelectorAll('.el-sub-menu__title').forEach(e => e.click());
            return Array.from(document.querySelectorAll('.el-menu-item'))
                        .map(e => norm(e.innerText)).filter(Boolean);
        })()""")
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    seen, out = set(), []
    for t in items:
        if (not keyword or keyword in t) and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def summarize(results: List[WorkstationResult]) -> Dict[str, Any]:
    failed = [r for r in results if r.status == "FAILED"]
    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": [{
            "role": r.role, "role_id": r.role_id, "dept_id": r.dept_id,
            "name": r.name, "status": r.status, "reasons": r.reasons,
            "failed_requests": r.failed_requests[:10],
            "exceptions": r.exceptions[:5],
            "health": r.health, "screenshot": r.screenshot,
        } for r in results],
    }
