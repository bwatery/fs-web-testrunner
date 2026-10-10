"""
体检报告生成器

把 L1（后端接口）与 L2（真实用户操作）的结果合成一份中文 HTML 报告，
回答唯一的问题：**系统的功能到底哪里坏了**。

报告纪律：
- 只有真实失败的条目才出现在"异常"里
- 无法判定的（缺参数、权限不足、探针入参不合法）单独列出，不混入异常
- 每条异常都带可复现的证据：接口路径/页面路径、HTTP 状态、业务码、原始响应、截图
"""

import html
import json
import os
import time
from typing import Any, Dict, List, Optional

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1f2328;--muted:#6b7280;--line:#e3e6ea;
--bad:#c0392b;--badbg:#fdecea;--ok:#1e7e34;--okbg:#e8f5e9;
--warn:#8a6100;--warnbg:#fff8e1;--info:#1a5fb4;--infobg:#e8f1fb;}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1c2024;--fg:#e6e8ea;
--muted:#9aa3ad;--line:#2c3238;--bad:#ff8a80;--badbg:#3a1f1d;--ok:#81c995;
--okbg:#1b2e1f;--warn:#ffd54f;--warnbg:#33290d;--info:#8ab4f8;--infobg:#16283f;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 18px 60px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);font-size:13px;margin-bottom:22px}
.verdict{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0 8px}
.tile{flex:1 1 150px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:14px 16px}
.tile .n{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.tile .k{font-size:12px;color:var(--muted);margin-top:2px}
.big{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ok);
border-radius:10px;padding:16px 18px;margin:16px 0 4px;font-size:15px}
.big.bad{border-left-color:var(--bad)}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--bg);font-weight:600;font-size:12px;color:var(--muted)}
tr:last-child td{border-bottom:none}
code{font-family:ui-monospace,Consolas,monospace;font-size:12px;
background:var(--bg);padding:1px 5px;border-radius:4px;word-break:break-all}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600}
.p-bad{background:var(--badbg);color:var(--bad)}
.p-ok{background:var(--okbg);color:var(--ok)}
.p-warn{background:var(--warnbg);color:var(--warn)}
.p-info{background:var(--infobg);color:var(--info)}
.why{color:var(--bad);font-size:12.5px}
details{margin-top:6px}
summary{cursor:pointer;color:var(--muted);font-size:12px}
pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:9px;
overflow:auto;max-height:220px;font-size:11.5px;margin:6px 0 0}
.note{color:var(--muted);font-size:12.5px;margin:8px 0 0}
"""


def _e(v: Any) -> str:
    return html.escape(str(v if v is not None else ""))


def _pill(text: str, kind: str) -> str:
    return f'<span class="pill p-{kind}">{_e(text)}</span>'


def _load(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build(api_payload: Optional[Dict], ui_payload: Optional[Dict],
          out_path: str, ws_payload: Optional[Dict] = None) -> str:
    api = api_payload or {}
    ui = ui_payload or {}
    ws = ws_payload or {}
    a_sum = api.get("summary") or {}
    a_meta = api.get("meta") or {}
    u_sum = ui.get("summary") or {}
    u_meta = ui.get("meta") or {}

    api_defects: List[Dict] = a_sum.get("defects") or []
    api_high = [d for d in api_defects if d.get("confidence") == "high"]
    api_low = [d for d in api_defects if d.get("confidence") != "high"]
    ui_fails = [r for r in (ui.get("results") or []) if r.get("status") == "FAILED"]
    missing_menu = u_meta.get("missing_in_sidebar") or []

    # 工作站巡检（逐角色）
    ws_roles = ws.get("roles") or []
    ws_pages: List[Dict[str, Any]] = []
    for role in ws_roles:
        for w in (role.get("workstations") or []):
            ws_pages.append({**w, "role": role.get("role"),
                             "role_id": role.get("role_id")})
    ws_fail = [p for p in ws_pages if p.get("status") == "FAILED"]
    ws_warn = [p for p in ws_pages if p.get("status") == "WARNING"]
    ws_switch_fail = [r for r in ws_roles if not r.get("switch_ok")]

    total_bad = len(api_defects) + len(ui_fails) + len(ws_fail)
    P: List[str] = []
    P.append("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
             "<meta name='viewport' content='width=device-width,initial-scale=1'>"
             "<title>HIS 系统功能体检报告</title>")
    P.append(f"<style>{_CSS}</style></head><body><div class='wrap'>")

    P.append("<h1>HIS 系统功能体检报告</h1>")
    P.append(f"<div class='sub'>生成时间 {_e(time.strftime('%Y-%m-%d %H:%M:%S'))}　·　"
             f"前端 {_e(u_meta.get('frontend') or a_meta.get('frontend'))}　·　"
             f"网关 {_e(a_meta.get('gateway'))}　·　"
             f"数据库 {_e(a_meta.get('oracle'))}</div>")

    # ---- 结论 ----
    if total_bad == 0:
        P.append("<div class='big'><b>结论：本次体检未发现功能异常。</b><br>"
                 "后端只读接口与前端菜单页面均通过真实调用校验。</div>")
    else:
        P.append(f"<div class='big bad'><b>结论：发现 {total_bad} 处功能异常</b>"
                 f"（"
                 + "，".join(x for x in [
                     f"菜单页面 {len(ui_fails)} 处" if ui_fails else "",
                     f"工作站 {len(ws_fail)} 处" if ws_fail else "",
                     f"后端接口 {len(api_defects)} 处" if api_defects else "",
                 ] if x)
                 + "）</div>")

    P.append("<div class='verdict'>")
    P.append(f"<div class='tile'><div class='n'>{a_sum.get('total_probed', 0)}</div>"
             f"<div class='k'>后端接口探针</div></div>")
    P.append(f"<div class='tile'><div class='n' style='color:var(--bad)'>"
             f"{len(api_defects)}</div><div class='k'>后端异常</div></div>")
    P.append(f"<div class='tile'><div class='n'>{u_sum.get('total', 0)}</div>"
             f"<div class='k'>前端页面巡检</div></div>")
    P.append(f"<div class='tile'><div class='n' style='color:var(--bad)'>"
             f"{len(ui_fails)}</div><div class='k'>前端页面异常</div></div>")
    if missing_menu:
        P.append(f"<div class='tile'><div class='n' style='color:var(--warn)'>"
                 f"{len(missing_menu)}</div><div class='k'>菜单未渲染</div></div>")
    P.append("</div>")

    # ---- 工作站巡检（逐角色）----
    if ws_pages:
        P.append("<h2>一、工作站功能巡检（逐角色真实换权 + 点击 + 接口监测）</h2>")
        P.append("<p class='note'>方式：逐个角色真实换取身份令牌后，"
                 "以真实用户的方式点击侧边栏菜单进入页面，"
                 "并<b>监听该页面发出的每一次接口调用</b>——"
                 "页面打得开但数据拉不到，在用户看来同样是坏的。</p>")
        if ws_switch_fail:
            P.append("<p class='note'>以下角色换权失败，未能巡检："
                     + "、".join(_e(r.get("role")) for r in ws_switch_fail) + "</p>")
        if ws_fail:
            P.append("<table><tr><th style='width:110px'>角色</th>"
                     "<th style='width:170px'>页面</th><th>原因</th></tr>")
            for w in ws_fail:
                reasons = "".join(f"<div class='why'>· {_e(x)}</div>"
                                  for x in (w.get("reasons") or []))
                h = w.get("health") or {}
                ev = (f"<details><summary>页面证据</summary><pre>"
                      f"{_e(json.dumps({'hash': h.get('hash'), '内容文字': h.get('contentTextLen'), '表格': h.get('tables'), '表单': h.get('forms'), '接口调用次数': w.get('requests_seen'), '失败调用': w.get('failed_requests')}, ensure_ascii=False, indent=1))}"
                      f"</pre></details>")
                P.append(f"<tr><td>{_e(w.get('role'))}</td>"
                         f"<td>{_e(w.get('name'))}<br><code>{_e(h.get('hash'))}</code></td>"
                         f"<td>{_pill('异常', 'bad')}{reasons}{ev}</td></tr>")
            P.append("</table>")
        else:
            P.append("<p class='note'>本次巡检的页面未发现功能异常。</p>")

        if ws_warn:
            P.append(f"<h2>本机控件未就绪（{len(ws_warn)} 项）—— 页面正常，终端功能受限</h2>")
            P.append("<table><tr><th style='width:110px'>角色</th>"
                     "<th style='width:170px'>页面</th><th>说明</th></tr>")
            for w in ws_warn:
                reasons = "".join(f"<div class='why'>· {_e(x)}</div>"
                                  for x in (w.get("reasons") or []))
                P.append(f"<tr><td>{_e(w.get('role'))}</td><td>{_e(w.get('name'))}</td>"
                         f"<td>{_pill('本机控件', 'warn')}{reasons}</td></tr>")
            P.append("</table>")

        # 全部页面一览
        P.append("<h2>工作站页面一览（含通过项）</h2><table>"
                 "<tr><th>角色</th><th>页面</th><th>结果</th><th>路由</th>"
                 "<th>接口调用</th></tr>")
        for w in ws_pages:
            st = w.get("status")
            kind = {"PASSED": "ok", "WARNING": "warn", "FAILED": "bad"}.get(st, "info")
            label = {"PASSED": "正常", "WARNING": "本机控件", "FAILED": "异常"}.get(st, st)
            h = w.get("health") or {}
            P.append(f"<tr><td>{_e(w.get('role'))}</td><td>{_e(w.get('name'))}</td>"
                     f"<td>{_pill(label, kind)}</td>"
                     f"<td><code>{_e(h.get('hash'))}</code></td>"
                     f"<td>{_e(w.get('requests_seen'))} 次 / 失败 {len(w.get('failed_requests') or [])}</td></tr>")
        P.append("</table>")

    # ---- 前端页面异常 ----
    if ui:
        P.append("<h2>二、当前角色全菜单点击巡检</h2>")
        P.append(f"<p class='note'>方式：用真实浏览器登录后，"
                 f"<b>逐个点击侧边栏菜单</b>（不拼 URL 直达），"
                 f"对每个页面断言：路由 404 / 白屏 / 内容为空 / 错误浮窗 / "
                 f"JS 异常 / 内嵌报表可达性 / 点击无反应。</p>")
        if ui_fails:
            P.append("<table><tr><th style='width:150px'>菜单</th>"
                     "<th style='width:90px'>结果</th><th>原因与证据</th></tr>")
            for r in ui_fails:
                reasons = "".join(f"<div class='why'>· {_e(x)}</div>"
                                  for x in (r.get("reasons") or []))
                ev = ""
                h = r.get("health") or {}
                if h:
                    ev = (f"<details><summary>页面证据</summary><pre>"
                          f"{_e(json.dumps({'hash': h.get('hash'), 'tabTitle': h.get('tabTitle'), 'contentTextLen': h.get('contentTextLen'), 'tables': h.get('tables'), 'forms': h.get('forms'), 'iframes': h.get('iframes')}, ensure_ascii=False, indent=1))}"
                          f"</pre></details>")
                shot = r.get("screenshot")
                if shot:
                    ev += f"<div class='note'>截图：{_e(os.path.basename(shot))}</div>"
                P.append(f"<tr><td>{_e(r.get('menu_name'))}</td>"
                         f"<td>{_pill('异常', 'bad')}</td>"
                         f"<td><code>{_e(r.get('path'))}</code>{reasons}{ev}</td></tr>")
            P.append("</table>")
        else:
            P.append("<p class='note'>本次点击巡检的菜单项全部通过。</p>")
        if missing_menu:
            P.append("<h2>菜单未渲染（后端已配置但用户在侧边栏看不到）</h2><table>"
                     "<tr><th>菜单名</th><th>路径</th></tr>")
            for m in missing_menu[:40]:
                P.append(f"<tr><td>{_e(m.get('name'))}</td>"
                         f"<td><code>{_e(m.get('path'))}</code></td></tr>")
            P.append("</table>")

    # ---- 后端接口异常 ----
    if api:
        P.append("<h2>三、后端接口（真实调用巡检）</h2>")
        c = a_sum.get("counts") or {}
        P.append(
            f"<p class='note'>方式：以管理员身份登录后，对全部"
            f"<b>{a_sum.get('total_probed', 0)}</b> 条只读接口发起真实调用"
            f"（两轮探针：第一轮按接口文档传参，第二轮补真实数据）。"
            f"写操作接口（{a_meta.get('mutating_total', 0)} 条）不做盲调，"
            f"避免污染业务数据。</p>")
        P.append("<div class='verdict'>")
        for label, key, kind in [("真实成功", "OK", "ok"), ("真实异常", "DEFECT", "bad"),
                                 ("无法判定", "CANNOT_VERIFY", "info"),
                                 ("缺参数", "NEEDS_PARAM", "warn"),
                                 ("查无数据", "NO_DATA", "info"),
                                 ("配置缺失", "CONFIG_GAP", "warn"),
                                 ("权限不足", "AUTH", "info")]:
            P.append(f"<div class='tile'><div class='n'>{c.get(key, 0)}</div>"
                     f"<div class='k'>{label}</div></div>")
        P.append("</div>")

        if api_high:
            P.append(f"<h2>高置信异常（{len(api_high)} 条）—— 与探针入参无关</h2>")
            P.append("<table><tr><th style='width:300px'>接口</th>"
                     "<th style='width:110px'>模块</th><th>现象</th></tr>")
            for d in api_high:
                P.append(f"<tr><td><code>{_e(d.get('method'))} {_e(d.get('path'))}</code></td>"
                         f"<td>{_e(d.get('tag'))}</td>"
                         f"<td><div class='why'>{_e(d.get('detail'))}</div>"
                         f"<details><summary>原始响应</summary><pre>"
                         f"{_e(d.get('response_head'))}</pre></details></td></tr>")
            P.append("</table>")
        if api_low:
            P.append(f"<h2>待人工确认（{len(api_low)} 条）—— 探针入参可能相关</h2>")
            P.append("<table><tr><th style='width:300px'>接口</th>"
                     "<th style='width:110px'>模块</th><th>现象</th></tr>")
            for d in api_low:
                P.append(f"<tr><td><code>{_e(d.get('method'))} {_e(d.get('path'))}</code></td>"
                         f"<td>{_e(d.get('tag'))}</td>"
                         f"<td><div class='why'>{_e(d.get('detail'))}</div>"
                         f"<details><summary>探针入参与原始响应</summary><pre>"
                         f"{_e(json.dumps(d.get('probe_query'), ensure_ascii=False))}\n"
                         f"{_e(d.get('response_head'))}</pre></details></td></tr>")
            P.append("</table>")

        by_tag = a_sum.get("by_tag") or {}
        bad_tags = {k: v for k, v in by_tag.items() if v.get("DEFECT")}
        if bad_tags:
            P.append("<h2>后端异常按模块分布</h2><table>"
                     "<tr><th>模块</th><th>探针数</th><th>异常数</th><th>高置信</th></tr>")
            for tag, v in list(bad_tags.items())[:25]:
                P.append(f"<tr><td>{_e(tag)}</td><td>{v.get('total', 0)}</td>"
                         f"<td>{_pill(v.get('DEFECT', 0), 'bad')}</td>"
                         f"<td>{v.get('HIGH', 0)}</td></tr>")
            P.append("</table>")

    P.append("<h2>说明</h2><p class='note'>"
             "本报告由 <code>run_verify.py</code> 生成，与旧的 Excel 用例套件相互独立："
             "不经过离线沙盒、不启用页面自愈、不产生无断言的“通过”。"
             "「无法判定 / 缺参数 / 查无数据 / 配置缺失 / 权限不足」都不是功能故障，"
             "已单独归类，不会被计入异常。</p>")
    P.append("</div></body></html>")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(P))
    return out_path
