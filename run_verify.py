"""
FS.TestRunner · 真实验证体检入口
=================================
一条命令回答："系统的功能到底有没有异常？"

与旧 TestEngine 完全独立：不经过自愈、离线沙盒或任何假断言路径。
每一条结论都来自对目标环境的真实调用，且每条判定都有能让它失败的现实。

用法：
    python run_verify.py                # 后端接口真体检（默认）
    python run_verify.py --limit 100    # 先小样本试跑
    python run_verify.py --workers 16   # 加大并发
    python run_verify.py --no-oracle    # 不连数据库，仅按 Swagger 声明传参
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from fs_web_testrunner.config import EMR_API_URL, REPORTS_DIR  # noqa: E402
from fs_web_testrunner.core.env_config import env_config       # noqa: E402
from fs_web_testrunner.verify import api_surface, fixtures, smoke_api  # noqa: E402

VERIFY_DIR = Path(REPORTS_DIR) / "verify"
SPEC_CACHE = Path(BASE_DIR) / "data" / "api_spec.json"

# 已验证可用的 Oracle 账号（environment_config.json 里的 his_test 实测无效）
_ORACLE_FALLBACKS = [
    {"user": "xchis", "password": "xchis"},
]

BUCKET_LABEL = {
    "OK": "正常",
    "DEFECT": "异常",
    "NEEDS_PARAM": "需参数",
    "NO_DATA": "查无数据",
    "AUTH": "权限不足",
    "CANNOT_VERIFY": "无法判定",
}


def _resolve_oracle_cfg(use_oracle: bool):
    """返回 (可用配置, 说明)。会尝试配置文件里的账号，再回退到已验证账号。"""
    if not use_oracle:
        return None, "已按 --no-oracle 跳过数据库"
    base = dict(env_config.get_config().get("oracle") or {})
    if not base:
        return None, "配置中无 oracle 段落"
    candidates = [base] + [
        {**base, **fb} for fb in _ORACLE_FALLBACKS
        if fb.get("user") != base.get("user")
    ]
    try:
        import oracledb
    except ImportError:
        return None, "未安装 oracledb，降级为纯接口探针"
    for idx, cfg in enumerate(candidates):
        try:
            conn = oracledb.connect(
                user=cfg.get("user"), password=cfg.get("password"),
                dsn=f"{cfg.get('host')}:{cfg.get('port', 1521)}/"
                    f"{cfg.get('service_name') or cfg.get('service')}",
            )
            conn.close()
            if idx > 0:
                return cfg, (f"配置账号 {base.get('user')} 无效，"
                             f"已改用实测可用账号 {cfg.get('user')}（建议修正 environment_config.json）")
            return cfg, f"数据库连通 ({cfg.get('user')}@{cfg.get('host')})"
        except Exception as e:
            last = str(e)[:90]
            continue
    return None, f"数据库不可达（{last}），降级为纯接口探针"


def _flatten_menu_names(nodes, out=None, prefix=""):
    """
    把 /getRouters 的树拍平成"真人应该在侧边栏看到"的菜单项。

    过滤规则（缺一不可，否则会大量误判为"菜单缺失"）：
      - menuType == 'C'      才是可点击的页面
      - visible == '0'       才应显示在侧边栏；'1' 是隐藏路由（页面内页签用）
      - component != 'Layout'  纯目录节点不渲染成菜单项
    """
    out = out if out is not None else []
    for n in nodes or []:
        path = str(n.get("path") or "")
        external = path.startswith("http") or "http://" in path or "https://" in path
        full = path if external else f"{prefix}/{path}".replace("//", "/")
        if (n.get("menuType") == "C"
                and str(n.get("visible", "0")) == "0"
                and (n.get("component") or "") != "Layout"):
            out.append({"name": (n.get("menuName") or "").strip(),
                        "path": full,
                        "component": n.get("component") or "",
                        "external": external})
        _flatten_menu_names(n.get("children") or [], out, full)
    return out


def _run_ui_walk(args, gateway: str, frontend: str) -> int:
    """L2 · 真实用户操作模拟：像真人一样点开每一级菜单，逐页断言。"""
    import requests
    from fs_web_testrunner.core.browser_driver import BrowserDriver
    from fs_web_testrunner.verify.ui_walk import UIWalker

    shots = str(Path(REPORTS_DIR) / "screenshots" / "uiwalk")
    print(f"\n{'─' * 66}")
    print("  L2 · 真实用户操作模拟（逐页点击菜单巡检）")
    print(f"{'─' * 66}")

    try:
        browser = BrowserDriver(headless=False)
        browser.start(f"{frontend}/#/index")
        if not browser.is_alive():
            print("  [致命] 无法连接/启动 Chrome，UI 巡检中止。")
            return 2
    except Exception as e:
        print(f"  [致命] 浏览器不可用：{e}")
        return 2

    walker = UIWalker(browser, frontend, shots)
    walker.install_error_hook()

    sess = walker.current_session()
    token = sess.get("token") or ""
    print(f"  当前会话    : {sess.get('hash') or '(未知)'}")
    if not token:
        print("  [致命] 未能从浏览器读取登录令牌，UI 巡检中止（请确认浏览器已登录目标系统）。")
        return 2

    # 交叉核对：后端配置的菜单 vs 侧边栏真实渲染出来的菜单
    expected: List[Dict[str, Any]] = []
    try:
        r = requests.get(f"{gateway}/getRouters",
                         headers={"Authorization": f"Bearer {token}"}, timeout=15,
                         proxies={"http": None, "https": None})
        if r.status_code == 200:
            expected = _flatten_menu_names(r.json().get("data") or [])
    except Exception as e:
        print(f"  [提示] 无法获取后端菜单配置，将只按侧边栏实际内容巡检：{e}")

    walker.expand_all_menus()
    rendered = [m for m in walker.list_menu() if not m.get("isGroup")]
    rendered_names = {(m.get("text") or "").strip() for m in rendered}
    print(f"  后端菜单    : {len(expected)} 项（可点击叶子）")
    print(f"  侧边栏渲染  : {len(rendered)} 项")

    missing = [e for e in expected
               if not e["external"] and e["name"] and e["name"] not in rendered_names]
    if missing:
        print(f"  ⚠️  {len(missing)} 项后端已配置但侧边栏未渲染（真人点不到）：")
        for m in missing[:10]:
            print(f"       - {m['name']}  ({m['path']})")

    if args.max_pages:
        rendered = rendered[:args.max_pages]

    print(f"\n  开始逐项点击巡检（共 {len(rendered)} 项）...")

    def _progress(n, total, res):
        mark = "❌" if res.status == "FAILED" else "✅"
        print(f"  {mark} [{n}/{total}] {res.menu_name[:24]:26s} -> {res.menu_path[:52]}")
        for reason in res.reasons[:2]:
            print(f"          ↳ {reason[:150]}")

    results = walker.walk(args.role_label or "当前角色", rendered,
                          progress=_progress)

    failed = [r for r in results if r.status == "FAILED"]
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = {
        "meta": {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "frontend": frontend,
                 "role": args.role_label or "当前会话身份",
                 "expected_menu_count": len(expected),
                 "missing_in_sidebar": missing},
        "summary": {"total": len(results), "passed": len(results) - len(failed),
                    "failed": len(failed)},
        "results": [{
            "menu_name": r.menu_name, "path": r.menu_path, "status": r.status,
            "reasons": r.reasons, "elapsed_ms": r.elapsed_ms,
            "screenshot": r.screenshot,
            "health": {k: v for k, v in (r.health or {}).items() if k != "containers"},
            "console_errors": r.console_errors,
        } for r in results],
    }
    ui_path = Path(REPORTS_DIR) / "verify" / f"ui_walk_{ts}.json"
    latest = Path(REPORTS_DIR) / "verify" / "ui_walk_latest.json"
    ui_path.parent.mkdir(parents=True, exist_ok=True)
    for p in (ui_path, latest):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"\n  ── L2 巡检结果 ──")
    print(f"  ✅ 页面正常    {len(results) - len(failed):>4} 项")
    print(f"  ❌ 页面异常    {len(failed):>4} 项")
    if missing:
        print(f"  🚫 菜单缺失    {len(missing):>4} 项（配置了但侧边栏没有）")
    print(f"  详细报告 : {ui_path}")
    try:
        rp = _write_report()
        print(f"  体检报告 : {rp}")
    except Exception as e:
        print(f"  [提示] 报告生成失败: {e}")
    return 0


# 各角色巡检配置：(roleId, deptId, 角色名)
# roleId=1 系统管理员 在本环境不存在（接口报 user.role.dept.not.exists），故不列入
WORKSTATION_ROLES = [
    (14, 2, "门诊收费"),
    (15, 910073, "门诊医生"),
    (34, 2, "住院收费"),
    (35, 910092, "住院医生"),
    (36, 910131, "住院护士"),
    (37, 910127, "住院药房"),
]


def _run_workstations(args, gateway: str, frontend: str) -> int:
    """
    L3 · 工作站功能巡检。
    回答用户的原话："菜单里的工作站是否正常"。
    逐个角色真实换权后，找出侧边栏里所有含"工作站"的菜单项并逐一实测。
    """
    from fs_web_testrunner.verify import workstation_check as wc

    shots = str(Path(REPORTS_DIR) / "screenshots" / "workstation")
    print(f"\n{'─' * 66}")
    print("  L3 · 工作站功能巡检（逐角色换权 + 真实点击 + 接口调用监测）")
    print(f"{'─' * 66}")

    page = wc.CDPPage()
    if not page.connect():
        print("  [致命] 无法连接 Chrome CDP，工作站巡检中止。")
        return 2

    roles = WORKSTATION_ROLES
    if args.role_ids:
        wanted = {int(x) for x in str(args.role_ids).split(",") if x.strip()}
        roles = [r for r in roles if r[0] in wanted]
        if not roles:
            print(f"  [致命] --role-ids 未匹配到任何已知角色，可选："
                  f"{[r[0] for r in WORKSTATION_ROLES]}")
            return 2

    # 先真实登录（走登录页表单，不注入令牌——注入会破坏前端会话）
    lg = wc.login_real(page, frontend, args.username, args.password)
    print(f"  登录      : {lg.get('detail')}")
    if not lg.get("ok"):
        print("  [致命] 登录未成功，工作站巡检中止。")
        page.close()
        return 2

    all_results: List[Dict[str, Any]] = []
    total_pass = total_fail = 0
    prev_menus: List[str] = []

    for role_id, dept_id, role_name in roles:
        sw = wc.switch_role(page, gateway, role_id, dept_id, frontend,
                            prev_menus=prev_menus or None)
        if not sw.get("ok"):
            print(f"\n  ⚠️  [{role_name} (role={role_id})] 换权未生效，"
                  f"本角色跳过（不计入功能异常）")
            print(f"       原因：{sw.get('detail')}")
            all_results.append({"role": role_name, "role_id": role_id,
                                "dept_id": dept_id, "switch_ok": False,
                                "detail": sw.get("detail"), "workstations": []})
            continue
        prev_menus = list(sw.get("menus") or [])

        # 侧边栏里渲染出来的，就是该角色能用的全部菜单功能
        names = wc.list_workstations(page, args.ws_keyword or "")
        if args.max_per_role:
            names = names[:args.max_per_role]
        scope = f"含「{args.ws_keyword}」" if args.ws_keyword else "全部菜单"
        print(f"\n  ── {role_name} (role={role_id}, dept={dept_id})："
              f"侧边栏 {len(sw.get('menus') or [])} 项，本次巡检 {len(names)} 项（{scope}）──")

        role_ws: List[Dict[str, Any]] = []
        if not names:
            print("     (该角色侧边栏没有可巡检的菜单项)")
        for name in names:
            r = wc.check_workstation(page, role_name, name,
                                     role_id=role_id,
                                     screenshot_dir=shots)
            total_pass += 1 if r.status == "PASSED" else 0
            total_fail += 1 if r.status == "FAILED" else 0
            mark = "✅" if r.status == "PASSED" else "❌"
            h = r.health or {}
            print(f"     {mark} {name}")
            print(f"        页面 {h.get('hash')} | 内容 {h.get('contentTextLen')} 字 | "
                  f"表格 {h.get('tables')} 个/{h.get('rows')} 行 | 表单 {h.get('forms')} | "
                  f"接口调用 {r.requests_seen} 次，失败 {len(r.failed_requests)}")
            for reason in r.reasons[:3]:
                print(f"        ↳ {reason[:170]}")
            for note in r.notes[:1]:
                print(f"        · {note[:140]}")
            role_ws.append({"name": name, "status": r.status, "reasons": r.reasons,
                            "notes": r.notes, "health": r.health,
                            "requests_seen": r.requests_seen,
                            "failed_requests": r.failed_requests[:10],
                            "exceptions": r.exceptions[:5],
                            "screenshot": r.screenshot})
        all_results.append({"role": role_name, "role_id": role_id, "dept_id": dept_id,
                            "switch_ok": True, "workstations": role_ws})

    page.close()

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(REPORTS_DIR) / "verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"meta": {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "frontend": frontend, "gateway": gateway},
               "summary": {"passed": total_pass, "failed": total_fail},
               "roles": all_results}
    for p in (out_dir / f"workstation_{ts}.json", out_dir / "workstation_latest.json"):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"\n  ── 工作站巡检结果 ──")
    print(f"  ✅ 正常 {total_pass} 个   ❌ 异常 {total_fail} 个"
          )
    print(f"  详细报告 : {out_dir / f'workstation_{ts}.json'}")
    try:
        rp = _write_report()
        print(f"  体检报告 : {rp}")
    except Exception as e:
        print(f"  [提示] 报告生成失败: {e}")
    return 0


def _run_closed_loop(args, gateway: str) -> int:
    """P0 关键业务闭环真校验（写入→回读→数据库比对）。"""
    from fs_web_testrunner.verify import closed_loop as cl

    print(f"\n{'─' * 66}")
    print("  P0 关键业务闭环真校验（真实造数 → 操作 → 回读 → 数据库比对）")
    print(f"{'─' * 66}")

    try:
        token = api_surface.login(gateway)
    except Exception as e:
        print(f"  [致命] 无法登录网关：{e}")
        return 2

    cases = [c.strip() for c in (args.cases or "").split(",") if c.strip()] \
        or cl.supported_cases()
    print(f"  本次校验 {len(cases)} 条：{', '.join(cases)}")
    print(f"  已实现闭环的用例：{', '.join(cl.supported_cases())}")
    print()

    def _progress(i, n, r):
        mark = {"通过": "✅", "失败": "❌", "未执行": "⚪"}.get(r.status, "?")
        print(f"  {mark} [{i}/{n}] {r.case_id} {r.title}  —— {r.status}")
        if r.note:
            print(f"        {r.note[:230]}")
        if r.evidence:
            print(f"        证据: {json.dumps(r.evidence, ensure_ascii=False)[:260]}")

    results = cl.run(cases, gateway, token, progress=_progress)

    out_dir = Path(REPORTS_DIR) / "verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    payload = {
        "meta": {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "gateway": gateway},
        "summary": {
            "通过": sum(1 for r in results if r.status == "通过"),
            "失败": sum(1 for r in results if r.status == "失败"),
            "未执行": sum(1 for r in results if r.status == "未执行"),
        },
        "results": [{"case_id": r.case_id, "title": r.title, "status": r.status,
                     "note": r.note, "evidence": r.evidence,
                     "duration_ms": r.duration_ms} for r in results],
    }
    with open(out_dir / f"closed_loop_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # ⚠️ **只有「全量运行」才更新 latest**。
    # 单跑几条（如 `--cases L6-038`）如果也覆盖 latest，下游 update_tracking_excel.py 就会
    # 只读到这一条结果、把其余用例当成"没有结果"，整张表的状态会塌回源表原值
    # —— 2026-10-09 19:29 真发生过一次（通过数从 175 掉到 119）。所以这里加门禁。
    if len(cases) >= len(cl.supported_cases()):
        with open(out_dir / "closed_loop_latest.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    else:
        print(f"  [提示] 本次是部分运行（{len(cases)}/{len(cl.supported_cases())} 条），"
              f"**不覆盖 closed_loop_latest.json**（避免把没跑的用例当成没结果）")

    s = payload["summary"]
    print(f"\n  ── 闭环校验结果 ──")
    print(f"  ✅ 通过 {s['通过']}   ❌ 失败 {s['失败']}   ⚪ 未执行 {s['未执行']}")
    print(f"  详细报告 : {out_dir / f'closed_loop_{ts}.json'}")
    return 0


def _write_report() -> str:
    """把最近一次 L1 / L2 / L3 的结果合成中文 HTML 报告。"""
    from fs_web_testrunner.verify import report as report_mod
    vdir = Path(REPORTS_DIR) / "verify"

    def _load(name):
        try:
            with open(vdir / name, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    return report_mod.build(_load("api_smoke_latest.json"),
                            _load("ui_walk_latest.json"),
                            str(vdir / "体检报告.html"),
                            ws_payload=_load("workstation_latest.json"))


def main() -> int:
    ap = argparse.ArgumentParser(description="HIS 真实验证体检")
    ap.add_argument("--limit", type=int, default=0, help="只探前 N 条（试跑用）")
    ap.add_argument("--workers", type=int, default=12, help="并发数")
    ap.add_argument("--no-oracle", action="store_true", help="不连数据库")
    ap.add_argument("--gateway", default=None, help="覆盖网关地址")
    ap.add_argument("--denylist", default=None, help="JSON 文件：需排除的接口列表")
    ap.add_argument("--ui", action="store_true",
                    help="L2 真实用户操作模拟：像真人一样点菜单逐页巡检")
    ap.add_argument("--workstations", action="store_true",
                    help="L3 工作站功能巡检：逐角色换权，实测菜单里每个工作站")
    ap.add_argument("--role-ids", default="",
                    help="限定角色ID，逗号分隔（如 35,36,37）；默认全部")
    ap.add_argument("--closed-loop", action="store_true",
                    help="P0 关键业务闭环真校验：造数→操作→回读→数据库比对")
    ap.add_argument("--cases", default="", help="指定闭环用例ID，逗号分隔（如 L6-001,L6-039）")
    ap.add_argument("--ws-keyword", default="", help="只测菜单名含该关键词的页面")
    ap.add_argument("--max-per-role", type=int, default=0,
                    help="每个角色最多巡检几个菜单项（默认全部）")
    ap.add_argument("--api", action="store_true", help="只跑 L1 后端接口体检")
    ap.add_argument("--role-label", default="", help="本次巡检的角色名（仅用于报告标注）")
    ap.add_argument("--username", default="admin", help="登录账号")
    ap.add_argument("--password", default="admin123", help="登录口令")
    ap.add_argument("--max-pages", type=int, default=0, help="UI 巡检最多点几项菜单")
    args = ap.parse_args()

    gateway = (args.gateway or EMR_API_URL).rstrip("/")
    frontend = env_config.get_frontend_url()

    # P0 关键业务闭环真校验
    if args.closed_loop:
        return _run_closed_loop(args, gateway)

    # L3 工作站功能巡检（用户最关心的：菜单里的工作站是否正常）
    if args.workstations:
        return _run_workstations(args, gateway, frontend)

    # L2 真实用户操作模拟
    if args.ui:
        return _run_ui_walk(args, gateway, frontend)

    print("=" * 66)
    print("  HIS 真实验证体检 · L1 后端接口层")
    print("=" * 66)
    print(f"  网关      : {gateway}")
    print(f"  前端      : {env_config.get_frontend_url()}")

    # 0. 数据库凭据
    oracle_cfg, oracle_note = _resolve_oracle_cfg(not args.no_oracle)
    print(f"  数据库    : {oracle_note}")

    # 1. 登录（失败即终止，不做任何静默降级）
    try:
        token = api_surface.login(gateway)
        print(f"  鉴权      : 登录成功，已获取 JWT")
    except Exception as e:
        print(f"\n[致命] 无法登录网关：{e}")
        print("       后端不可达或凭据失效，本次体检无法进行。")
        return 2

    # 2. 接口清单
    try:
        spec = api_surface.fetch_spec(gateway, token, cache_path=str(SPEC_CACHE))
        src = spec.get("_source", "?")
        cache_tag = "缓存" if spec.get("_cache_hit") else "新拉取"
        paths = spec.get("paths") or {}
        print(f"  接口清单  : {len(paths)} 条路径 ({src}, {cache_tag})")
    except Exception as e:
        print(f"\n[致命] 无法获取接口清单：{e}")
        return 2

    eps = api_surface.iter_endpoints(spec)
    ro = [e for e in eps if e.kind == "READ_ONLY"]
    mut = [e for e in eps if e.kind == "MUTATING"]
    print(f"  探针范围  : 只读 {len(ro)} 条（盲调） | 写操作 {len(mut)} 条（不盲调，留给 L3 闭环）")

    # 3. fixture 池
    pool = {}
    if oracle_cfg:
        pool = fixtures.build_fixtures(oracle_cfg)
        fixtures.dump(pool, str(VERIFY_DIR / "fixtures.json"))
        print(f"  探针夹具  : 从数据库取到 {len(pool)} 个真实入参")
    else:
        print(f"  探针夹具  : 无（缺参数接口将归入'需参数'，不计为异常）")

    denylist = set()
    if args.denylist and os.path.exists(args.denylist):
        with open(args.denylist, "r", encoding="utf-8") as f:
            denylist = set(json.load(f))

    # 4. 探测
    print(f"\n  正在对 {len(ro) if not args.limit else min(args.limit, len(ro))} 条只读接口发起真实调用"
          f"（两轮探针，并发 {args.workers}）...")
    t0 = time.time()

    def _progress(done, total):
        sys.stdout.write(f"\r    进度 {done}/{total} ...")
        sys.stdout.flush()

    results = smoke_api.run(
        gateway, token, spec, pool,
        workers=args.workers,
        denylist=denylist,
        limit=args.limit or None,
        progress=_progress,
    )
    elapsed = round(time.time() - t0, 1)
    sys.stdout.write("\r" + " " * 40 + "\r")

    summary = smoke_api.summarize(results)
    meta = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gateway": gateway,
        "frontend": env_config.get_frontend_url(),
        "oracle": oracle_note,
        "spec_source": spec.get("_source"),
        "spec_fingerprint": api_surface.spec_fingerprint(spec),
        "readonly_total": len(ro),
        "mutating_total": len(mut),
        "duration_sec": elapsed,
        "fingerprint_ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    paths_out = smoke_api.save(results, summary, str(VERIFY_DIR), meta)

    # 5. 中文结论
    c = summary["counts"]
    print("─" * 66)
    print(f"  后端接口体检完成（耗时 {elapsed}s，共探 {summary['total_probed']} 条只读接口）")
    print("─" * 66)
    print(f"  ✅ 正常        {c.get('OK', 0):>5} 条")
    print(f"  ❌ 异常        {c.get('DEFECT', 0):>5} 条   <- 需要处理的功能故障")
    print(f"  ❔ 无法判定    {c.get('CANNOT_VERIFY', 0):>5} 条   探针入参不合法或响应不可解析")
    print(f"  ⚠️  需参数      {c.get('NEEDS_PARAM', 0):>5} 条   缺少必填入参，无法判定（非故障）")
    print(f"  ⚪ 查无数据    {c.get('NO_DATA', 0):>5} 条   探针ID无对应记录，无法判定")
    print(f"  🧩 配置缺失    {c.get('CONFIG_GAP', 0):>5} 条   账号/科室/病区关系未配置（非代码缺陷）")
    print(f"  🔒 权限不足    {c.get('AUTH', 0):>5} 条   当前角色无权限（非故障）")
    unverified = (c.get('CANNOT_VERIFY', 0) + c.get('NEEDS_PARAM', 0) +
                  c.get('NO_DATA', 0) + c.get('CONFIG_GAP', 0) + c.get('AUTH', 0))
    print(f"\n  判定覆盖率：{c.get('OK', 0) + c.get('DEFECT', 0)}/{summary['total_probed']} 条给出了明确结论"
          f"（其余 {unverified} 条需补真实入参或换角色才能判定）")

    if summary["defect_count"]:
        print("\n  ── 异常接口清单（按模块） ──")
        shown = 0
        for d in summary["defects"]:
            if shown >= 30:
                print(f"     ... 其余 {summary['defect_count'] - shown} 条见报告")
                break
            http = d.get("http")
            code = d.get("code")
            print(f"  ❌ [{d.get('tag') or '未分类'}] {d['method']} {d['path']}")
            print(f"       {d['detail']}  (HTTP {http} / code {code})")
            shown += 1
    else:
        print("\n  ✅ 未发现后端接口层面的真实故障。")

    print(f"\n  详细报告 : {paths_out['ts']}")
    print(f"  最新快照 : {paths_out['latest']}")
    print(f"  接口指纹 : {meta['spec_fingerprint']}（下次比对可发现接口增减）")
    try:
        rp = _write_report()
        print(f"  体检报告 : {rp}")
    except Exception as e:
        print(f"  [提示] 报告生成失败: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
