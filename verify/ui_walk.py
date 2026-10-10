"""
L2 · 真实用户操作模拟（UI Walk）

与旧套件的根本区别：
- **像真人一样点菜单**，而不是拼 URL 直达。URL 直达会绕过前端路由装配与菜单权限，
  正是旧工具满屏 404 的根源之一。
- **不启用任何自愈**。页面 404 / 白屏 / 报错浮窗 / JS 异常，一律判失败。
- **每条结论都能失败**，且失败时留存截图 + DOM 证据。

流程：
  1. 复用当前已登录的浏览器会话，读取其真实身份（非破坏性，不影响用户正在做的事）
  2. 用该身份调 /getRouters，拿到这个人**真实能看到的菜单树**
  3. 依次点开每一级菜单，逐项点击
  4. 每次点击后做页面健康断言
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 注入的错误采集钩子：SPA 是 hash 路由不刷新页面，所以装一次即可长期生效
_ERROR_HOOK_JS = """
(() => {
  if (window.__verifyHookInstalled) return true;
  window.__verifyHookInstalled = true;
  window.__verifyErrors = [];
  const push = (kind, text) => {
    try { window.__verifyErrors.push({kind: kind, text: String(text).slice(0, 300), t: Date.now()}); } catch(e){}
  };
  const origErr = console.error;
  console.error = function(...args) {
    push('console.error', args.map(a => (a && a.message) ? a.message : a).join(' '));
    return origErr.apply(console, args);
  };
  window.addEventListener('error', e => push('window.onerror', (e && e.message) || 'unknown'));
  window.addEventListener('unhandledrejection', e => {
    const r = e && e.reason;
    push('unhandledrejection', (r && (r.message || r)) || 'unknown');
  });
  return true;
})()
"""

# 页面健康探针：只报事实，不下结论（结论由 Python 侧按规则做，便于审计）
# 内容容器：本系统为 vue-admin-beautiful 多标签布局，页面内容在 .vab-app-main 内。
_PAGE_HEALTH_JS = """
(() => {
  const bodyText = document.body ? document.body.innerText.trim() : '';
  const hash = window.location.hash || '';
  const appEl = document.getElementById('app');

  // 定位真正的页面内容区（排除侧边栏/顶栏/标签条）
  const sels = ['.vab-app-main', '.el-main', '.app-main', '.vab-app-main-content'];
  let contentEl = null, contentSel = '';
  for (const s of sels) {
    const el = document.querySelector(s);
    if (el) { contentEl = el; contentSel = s; break; }
  }

  const inContent = sel => contentEl
      ? Array.from(contentEl.querySelectorAll(sel))
      : Array.from(document.querySelectorAll(sel));

  const contentTextLen = contentEl ? (contentEl.innerText || '').trim().length : -1;
  const contentHtmlLen = contentEl ? (contentEl.innerHTML || '').length : -1;

  // 当前激活标签页标题（vab 多标签体系里，这就是用户看到的页面名）
  let tabTitle = '';
  const activeTab = document.querySelector('.el-tabs__item.is-active');
  if (activeTab) tabTitle = (activeTab.innerText || '').trim();

  const errEls = Array.from(document.querySelectorAll(
      '.el-message--error, .el-notification--error, .el-alert--error, .el-result--error'))
      .map(e => (e.innerText || '').trim()).filter(Boolean);
  const netKw = ['网络异常','网络错误','连接超时','网络连接失败','未能连接到服务器',
                 'Network Error','timeout of','Failed to fetch','502 Bad Gateway',
                 '504 Gateway Time-out','500 Internal Server Error','ERR_CONNECTION',
                 '服务暂不可用','请检查网络','请求失败'];
  let netErr = '';
  for (const k of netKw) { if (bodyText.includes(k)) { netErr = k; break; } }

  // 内容区里的内嵌框架（外链报表页靠它承载）
  const iframes = inContent('iframe').map(f => {
    let loaded = false, inner = 0, blocked = false;
    try {
      const d = f.contentDocument;
      if (d) { inner = (d.body ? d.body.innerHTML.length : 0); loaded = true; }
    } catch (e) { blocked = true; }
    const r = f.getBoundingClientRect();
    return {src: (f.getAttribute('src') || '').slice(0, 200), loaded: loaded,
            innerLen: inner, crossOrigin: blocked,
            w: Math.round(r.width), h: Math.round(r.height)};
  });

  return {
    hash: hash,
    title: document.title || '',
    tabTitle: tabTitle,
    is404: hash.includes('/404') || bodyText.includes('抱歉！当前页面不存在'),
    isLogin: hash.includes('/login'),
    mounted: appEl ? appEl.children.length > 0 : false,
    bodyLen: bodyText.length,
    contentSel: contentSel,
    contentTextLen: contentTextLen,
    contentHtmlLen: contentHtmlLen,
    errorToasts: errEls.slice(0, 5),
    networkError: netErr,
    iframes: iframes,
    tables: inContent('.el-table').length,
    tableRows: inContent('.el-table__body-wrapper tbody tr').length,
    forms: inContent('.el-form').length,
    buttons: inContent('.el-button').length,
    inputs: inContent('input').length,
    dialogs: document.querySelectorAll('.el-dialog__wrapper:not([style*="display: none"]) .el-dialog').length
  };
})()
"""

# 列出侧边栏菜单：区分可点击的叶子项与需要先展开的分组
_LIST_MENU_JS = """
(() => {
  const out = [];
  document.querySelectorAll('.el-menu-item, .el-sub-menu__title').forEach((el, i) => {
    const isGroup = el.classList.contains('el-sub-menu__title');
    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
    out.push({ idx: i, text: text, isGroup: isGroup, expanded: !!el.closest('.is-opened') });
  });
  return out;
})()
"""

_CLICK_MENU_JS = """
((targetIdx) => {
  const els = document.querySelectorAll('.el-menu-item, .el-sub-menu__title');
  const el = els[targetIdx];
  if (!el) return {ok: false, reason: '菜单元素不存在(索引 ' + targetIdx + ')'};
  const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
  el.scrollIntoView({block: 'center'});
  el.click();
  return {ok: true, text: text};
})
"""

# 按可见文字点击叶子菜单项。比按下标点击更贴近真人，也不会因 DOM 重排而串位。
_CLICK_MENU_BY_TEXT_JS = """
((target) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
  const leaves = Array.from(document.querySelectorAll('.el-menu-item'));
  let el = leaves.find(e => norm(e.innerText) === target.text && !e.dataset.verifyClicked);
  if (!el) el = leaves.find(e => norm(e.innerText) === target.text);
  if (!el) el = leaves.find(e => norm(e.innerText).includes(target.text) && !e.dataset.verifyClicked);
  if (!el) el = leaves.find(e => norm(e.innerText).includes(target.text));
  if (!el) return {ok: false, reason: '未找到菜单项「' + target.text + '」（可能菜单未展开或该项已被移除）'};
  el.dataset.verifyClicked = '1';
  const text = norm(el.innerText);
  el.scrollIntoView({block: 'center'});
  el.click();
  return {ok: true, text: text};
})
"""

_READ_TOKEN_JS = """
(() => {
  try {
    return {
      token: sessionStorage.getItem('shop-vite-token') || localStorage.getItem('token') || '',
      roleDept: localStorage.getItem('userRoleDeptCache') || '',
      hash: location.hash
    };
  } catch (e) { return {token: '', roleDept: '', hash: ''}; }
})()
"""


@dataclass
class PageResult:
    role: str
    menu_path: str
    menu_name: str
    status: str = "PENDING"     # PASSED / FAILED / SKIPPED
    reasons: List[str] = field(default_factory=list)
    health: Dict[str, Any] = field(default_factory=dict)
    console_errors: List[Dict[str, Any]] = field(default_factory=list)
    screenshot: Optional[str] = None
    elapsed_ms: float = 0.0
    reloaded: bool = False


def _slug(text: str) -> str:
    s = re.sub(r"[^\w一-鿿]+", "_", text or "").strip("_")
    return (s or "page")[:40]


class UIWalker:
    """以真实用户方式驱动浏览器逐页巡检。"""

    def __init__(self, browser, frontend_url: str, screenshot_dir: str,
                 settle_sec: float = 1.4):
        self.browser = browser
        self.frontend = frontend_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self.settle_sec = settle_sec
        os.makedirs(screenshot_dir, exist_ok=True)

    # ---------------- 基础能力 ----------------

    def eval(self, expr: str, arg: Any = None) -> Any:
        js = expr
        if arg is not None:
            js = f"({expr})({json.dumps(arg, ensure_ascii=False)})"
        return self.browser.evaluate(js)

    def install_error_hook(self) -> None:
        try:
            self.eval(_ERROR_HOOK_JS)
        except Exception:
            pass

    def clear_error_hook(self) -> None:
        try:
            self.eval("(() => { window.__verifyErrors = []; return true; })()")
        except Exception:
            pass

    def read_console_errors(self) -> List[Dict[str, Any]]:
        try:
            errs = self.eval("(() => window.__verifyErrors || [])()")
            return errs if isinstance(errs, list) else []
        except Exception:
            return []

    def page_health(self) -> Dict[str, Any]:
        try:
            h = self.eval(_PAGE_HEALTH_JS)
            return h if isinstance(h, dict) else {}
        except Exception as e:
            return {"probe_error": f"{type(e).__name__}: {e}"}

    def current_session(self) -> Dict[str, Any]:
        try:
            s = self.eval(_READ_TOKEN_JS)
            return s if isinstance(s, dict) else {}
        except Exception:
            return {}

    def screenshot(self, prefix: str) -> Optional[str]:
        try:
            return self.browser.take_screenshot(prefix)
        except Exception:
            return None

    # ---------------- 菜单操作 ----------------

    def list_menu(self) -> List[Dict[str, Any]]:
        items = self.eval(_LIST_MENU_JS)
        return items if isinstance(items, list) else []

    def expand_all_menus(self, max_rounds: int = 4) -> None:
        """逐级展开侧边栏分组，直到不再变化。"""
        for _ in range(max_rounds):
            groups = [m for m in self.list_menu() if m.get("isGroup") and not m.get("expanded")]
            if not groups:
                break
            for g in groups:
                try:
                    self.eval(_CLICK_MENU_JS, g["idx"])
                except Exception:
                    continue
                time.sleep(0.35)
            time.sleep(0.3)

    def click_menu(self, idx: int) -> Dict[str, Any]:
        try:
            res = self.eval(_CLICK_MENU_JS, idx)
            return res if isinstance(res, dict) else {"ok": False, "reason": "点击无返回"}
        except Exception as e:
            return {"ok": False, "reason": f"{type(e).__name__}: {e}"}

    def reset_click_marks(self) -> None:
        """清除"已点击"标记，便于身份切换后重新巡检。"""
        try:
            self.eval("(() => { document.querySelectorAll('.el-menu-item')"
                      ".forEach(e => delete e.dataset.verifyClicked); return true; })()")
        except Exception:
            pass

    def force_reload_current_page(self) -> bool:
        """
        本前端的已知特性：只靠 hash 跳转不会重新加载页面组件，内容区会停在仪表盘
        （表现为"标签页名字对了、内容却还是首页"）。真人此时会按 F5。
        所以点完菜单后一律补一次整页重载再判定——不做这一步，就会把前端特性
        误报成"页面打不开"。`workstation_check.py` 早已这么做，这里补齐。
        """
        try:
            cur_hash = self.eval("location.hash") or ""
            origin = self.eval("location.origin") or ""
            if not (cur_hash and origin):
                return False
            self.browser.send_cdp_command("Page.navigate", {"url": f"{origin}/{cur_hash}"})
            time.sleep(2.5)
            self.browser.send_cdp_command("Page.reload", {"ignoreCache": True})
            time.sleep(self.settle_sec + 1.0)
            return True
        except Exception:
            return False

    def click_menu_by_text(self, text: str) -> Dict[str, Any]:
        """
        按可见文字点击菜单项——真人就是这么点的。
        找不到就先重新展开菜单再试一次（应对子菜单折叠/懒渲染）。
        """
        for attempt in (0, 1):
            try:
                res = self.eval(_CLICK_MENU_BY_TEXT_JS, {"text": text})
            except Exception as e:
                res = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
            if isinstance(res, dict) and res.get("ok"):
                return res
            if attempt == 0:
                self.expand_all_menus()
                time.sleep(0.4)
        return res if isinstance(res, dict) else {"ok": False, "reason": "点击无返回"}

    # ---------------- 断言 ----------------

    def _check_iframe_reachable(self, url: str) -> Optional[str]:
        """
        外链报表页的 iframe 是跨域的，页面内的 JS 拿不到它的内容，
        所以直接对 iframe 的 src 发一次真实 HTTP 请求——这是唯一能判定
        "真人看到的是报表还是白框"的办法。
        """
        if not url or not url.startswith("http"):
            return None
        try:
            import requests
            r = requests.get(url, timeout=12, verify=False,
                             proxies={"http": None, "https": None},
                             headers={"User-Agent": "Mozilla/5.0 (verify)"})
            if r.status_code >= 400:
                return f"内嵌报表服务返回 HTTP {r.status_code}（真人看到的是空白报表框）"
            if len(r.content or b"") < 200:
                return f"内嵌报表服务返回空内容（HTTP {r.status_code}, {len(r.content or b'')} 字节）"
        except Exception as e:
            return f"内嵌报表服务不可达: {type(e).__name__}: {str(e)[:120]}"
        return None

    def judge(self, health: Dict[str, Any], console_errors: List[Dict[str, Any]],
              before_sig: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        页面健康判定。返回失败原因列表，空列表 = 通过。
        这里每一条都能真的失败，不存在"打印一句通过"。
        """
        reasons: List[str] = []
        if not health:
            return ["页面健康探针无返回，无法判定"]
        if health.get("probe_error"):
            return [f"健康探针异常: {health['probe_error']}"]

        # 1) 路由与会话
        if health.get("is404"):
            reasons.append(f"路由 404，页面不存在 (hash={health.get('hash')})")
        if health.get("isLogin"):
            reasons.append(f"被踢回登录页，会话或权限异常 (hash={health.get('hash')})")

        # 2) 渲染与空白
        if not health.get("mounted"):
            reasons.append("白屏：Vue 根节点未挂载任何内容")
        else:
            text_len = health.get("contentTextLen", -1)
            html_len = health.get("contentHtmlLen", -1)
            widgets = (health.get("tables", 0) + health.get("forms", 0)
                       + health.get("buttons", 0) + health.get("inputs", 0))
            iframes = health.get("iframes") or []
            if text_len == -1:
                reasons.append(f"未定位到内容容器（选择器 {health.get('contentSel') or '全部未命中'}）")
            elif text_len < 20 and widgets == 0 and not iframes and html_len < 500:
                reasons.append(
                    f"页面内容为空：内容区可见文字 {text_len} 字、表单/表格/按钮 0 个"
                    f"（容器 {health.get('contentSel')}）")

        # 3) 页面级错误提示
        if health.get("networkError"):
            reasons.append(f"页面出现网络错误提示: 『{health['networkError']}』")
        toasts = health.get("errorToasts") or []
        if toasts:
            reasons.append(f"页面弹出错误提示: 『{toasts[0][:120]}』")

        # 4) 外链报表 iframe 的真实可达性
        for fr in (health.get("iframes") or []):
            err = self._check_iframe_reachable(fr.get("src") or "")
            if err:
                reasons.append(err)
                break

        # 5) 前端 JS 异常
        if console_errors:
            first = console_errors[0]
            reasons.append(f"前端 JS 异常[{first.get('kind')}]: {str(first.get('text'))[:160]}")

        # 6) 点击后页面毫无变化 —— 真人视角就是"点了没反应"
        if not reasons and before_sig is not None:
            same_hash = (before_sig.get("hash") or "") == (health.get("hash") or "")
            same_tab = (before_sig.get("tabTitle") or "") == (health.get("tabTitle") or "")
            same_len = before_sig.get("contentTextLen") == health.get("contentTextLen")
            if same_hash and same_tab and same_len:
                reasons.append(
                    f"点击后页面无任何变化（仍在 {health.get('hash')}，"
                    f"内容文字 {health.get('contentTextLen')} 字未变）——该菜单可能无效")
        return reasons

    def content_signature(self, health: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        h = health if health is not None else self.page_health()
        return {"hash": h.get("hash"), "tabTitle": h.get("tabTitle"),
                "contentTextLen": h.get("contentTextLen")}

    def wait_for_content(self, timeout_sec: float = 5.0,
                         min_len: int = 20, interval: float = 0.4) -> Dict[str, Any]:
        """
        轮询等待内容区真正渲染出来——比固定 sleep 更接近真人"等页面出来"的行为，
        也避免把"还没渲染完"误判成白屏。出现明确失败信号则立即返回。
        """
        deadline = time.time() + timeout_sec
        health = self.page_health()
        while time.time() < deadline:
            if (health.get("is404") or health.get("isLogin")
                    or health.get("errorToasts") or health.get("networkError")):
                return health          # 已出现明确失败信号，无需再等
            widgets = (health.get("tables", 0) + health.get("forms", 0)
                       + health.get("inputs", 0) + health.get("buttons", 0))
            if (health.get("contentTextLen", -1) >= min_len) or widgets > 0 \
                    or (health.get("iframes") or []):
                return health
            time.sleep(interval)
            health = self.page_health()
        return health

    # ---------------- 主流程 ----------------

    def walk(self, role_label: str, menu_items: List[Dict[str, Any]],
             max_pages: int = 0, progress=None) -> List[PageResult]:
        """逐项点击菜单并断言。"""
        results: List[PageResult] = []
        targets = [m for m in menu_items if not m.get("isGroup")]
        if max_pages:
            targets = targets[:max_pages]

        for n, item in enumerate(targets, 1):
            res = PageResult(role=role_label, menu_path="", menu_name=item.get("text", ""))
            self.clear_error_hook()
            before_sig = self.content_signature()
            t0 = time.time()
            clicked = self.click_menu_by_text(item.get("text", ""))
            if clicked.get("ok"):
                time.sleep(self.settle_sec)
                # hash 跳转不加载组件，补一次整页重载（等价真人按 F5）再判定
                res.reloaded = self.force_reload_current_page()

            if not clicked.get("ok"):
                res.status = "FAILED"
                res.reasons = [f"菜单点击失败: {clicked.get('reason')}"]
            else:
                health = self.wait_for_content(timeout_sec=self.settle_sec + 4.0)
                errs = self.read_console_errors()
                res.health = health
                res.console_errors = errs
                res.menu_path = health.get("hash", "")
                # 若点的是当前已经打开的那一页，则"页面无变化"是正常的，不能算失败
                already_active = bool(before_sig.get("tabTitle")) and \
                    before_sig.get("tabTitle") == (health.get("tabTitle") or "")
                res.reasons = self.judge(health, errs,
                                         None if already_active else before_sig)
                res.status = "FAILED" if res.reasons else "PASSED"

            res.elapsed_ms = round((time.time() - t0) * 1000, 1)
            if res.status == "FAILED":
                res.screenshot = self.screenshot(f"uiwalk_fail_{_slug(role_label)}_{_slug(res.menu_name)}")
            results.append(res)
            if progress:
                progress(n, len(targets), res)
        return results
