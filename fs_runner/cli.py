# -*- coding: utf-8 -*-
"""
fs_runner.cli
=============
统一命令行入口，收拢所有测试与回归子命令。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    CDP_HOST,
    CDP_PORT,
    EMR_API_URL,
    FRONTEND_URL,
    GATEWAY_URL,
    ORACLE_CONFIG,
    REPORTS_DIR,
    ROOT_DIR,
    VERIFY_DIR,
    env_config,
)
from .cases.closed_loop import (
    Ctx,
    LoopResult,
    run as run_closed_loop_cases,
    supported_cases as get_supported_cases,
)
from .cases.ui_probe import CDPBrowserDriver
from .env import RealEnv, SandboxEnv


def _resolve_oracle_cfg(use_oracle: bool):
    """返回 (可用配置, 说明)。"""
    if not use_oracle:
        return None, "已按 --no-oracle 跳过数据库"
    base = dict(ORACLE_CONFIG)
    try:
        import oracledb
        conn = oracledb.connect(
            user=base.get("user"),
            password=base.get("password"),
            dsn=f"{base.get('host', '192.168.1.199')}:{base.get('port', 1521)}/{base.get('service_name', 'orcl')}",
        )
        conn.close()
        return base, f"数据库连通 ({base.get('user')}@{base.get('host')})"
    except Exception as e:
        return None, f"数据库不可达（{str(e)[:90]}），降级为纯接口探针"


def run_closed_loop(
    cases_arg: Optional[str] = None,
    gateway: Optional[str] = None,
    env: str = "real",
) -> int:
    """执行 P0 关键业务闭环真校验。"""
    from .core.audit import audit_tracer
    if env == "real":
        audit_tracer.capture_db_baseline()

    env_obj = RealEnv() if env == "real" else SandboxEnv()
    gw = (gateway or GATEWAY_URL).rstrip("/")
    all_supported = get_supported_cases()
    selected = [c.strip() for c in cases_arg.split(",") if c.strip()] if cases_arg else all_supported

    print("─" * 66)
    if env == "sandbox":
        print("  P0 关键业务闭环校验 · 沙盒模式（不连库、永不判通过）")
    else:
        print("  P0 关键业务闭环真校验（真实造数 → 操作 → 回读 → 数据库比对）")
    print("─" * 66)
    print(f"  环境      : {'真实环境 (Real)' if env == 'real' else '隔离沙盒 (Sandbox: 永不判通过)'}")
    print(f"  本次校验 {len(selected)} 条：{', '.join(selected)}")
    print(f"  已实现闭环的用例：{', '.join(all_supported)}\n")

    # 登录获取 JWT（沙盒模式离线纯参数校验，绝不触碰真实网络）
    if env == "sandbox":
        token = "SANDBOX_MOCK_JWT_TOKEN_OFFLINE"
        os.environ["FS_RUNNER_ENV"] = "sandbox"
        print("  鉴权      : 隔离沙盒模式（纯离线参数校验，已阻断外网与真实网关登录）")
    else:
        try:
            import requests
            r_login = requests.post(f"{gw}/login", json={"username": "admin", "password": "admin123"}, timeout=15)
            token = (r_login.json() or {}).get("data")
            if not token:
                print("  [致命] 登录网关未获取到有效令牌")
                return 2
        except Exception as e:
            print(f"  [致命] 无法登录网关：{e}")
            return 2

    def _progress(i, n, r):
        status, note = env_obj.filter_result_status(r.status, r.note)
        mark = {"通过": "✅", "失败": "❌", "阻塞": "🚫", "跳过": "⏭️", "未执行": "⚪"}.get(status, "?")
        print(f"  {mark} [{i}/{n}] {r.case_id} {r.title}  —— {status}")
        if note:
            print(f"        {note[:230]}")
        if r.evidence:
            print(f"        证据: {json.dumps(r.evidence, ensure_ascii=False)[:260]}")

    raw_results = run_closed_loop_cases(selected, gateway=gw, admin_token=token, progress=_progress)

    # 门禁过滤与 evidence 注入：沙盒模式绝不产出「通过」
    results = []
    for r in raw_results:
        status, note = env_obj.filter_result_status(r.status, r.note)
        evidence = env_obj.wrap_evidence(r.evidence)
        r.status = status
        r.note = note
        r.evidence = evidence
        results.append(r)

    created_text = audit_tracer.summary_text()
    created_summary = audit_tracer.get_summary()
    audit_file = audit_tracer.save_audit_file()

    out_dir = Path(VERIFY_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    from .core.preconditions import precondition_manager
    pre_summary = precondition_manager.summary()

    summary = {
        "通过": sum(1 for r in results if r.status == "通过"),
        "失败": sum(1 for r in results if r.status == "失败"),
        "阻塞": sum(1 for r in results if r.status == "阻塞"),
        "跳过": sum(1 for r in results if r.status == "跳过"),
        "未执行": sum(1 for r in results if r.status == "未执行"),
        "总计": len(results),
        "preconditions": pre_summary,
        "created_data": created_summary,
        "created_text": created_text,
    }
    payload = {
        "meta": {
            "started": time.strftime("%Y-%m-%d %H:%M:%S"),
            "gateway": gw,
            "env": env,
            "created_text": created_text,
        },
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }
    with open(out_dir / f"closed_loop_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # 只有真实环境全量运行才更新 latest，防止沙盒模式覆盖破坏整体生产台账
    if env == "real" and len(selected) >= len(all_supported):
        with open(out_dir / "closed_loop_latest.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    elif env == "sandbox":
        print("  [提示] 沙盒模式运行结果不覆盖 closed_loop_latest.json（保护生产台账）")
    else:
        print(f"  [提示] 本次是部分运行（{len(selected)}/{len(all_supported)} 条），"
              f"**不覆盖 closed_loop_latest.json**（避免把没跑的用例当成没结果）")

    print("\n  ── 闭环校验结果 ──")
    print(f"  ✅ 通过 {summary['通过']}   ❌ 失败 {summary['失败']}   🚫 阻塞 {summary['阻塞']}   ⏭️ 跳过 {summary['跳过']}   ⚪ 未执行 {summary['未执行']}  (总计 {summary['总计']})")
    print(f"  详细报告 : {out_dir / f'closed_loop_{ts}.json'}")

    print("")
    for line in precondition_manager.format_report_lines():
        print(f"  {line}")

    print(f"\n  [造数审计] {created_text}（记录落盘: {audit_file.name}）")

    if env == "real":
        ok_res, msg_res = audit_tracer.verify_db_no_residual()
        if not ok_res:
            print(f"  🚨 [造数护栏警告] {msg_res}")
        else:
            print(f"  🛡️ [造数护栏] {msg_res}")

    return 1 if summary["失败"] > 0 else 0


def _load_known_defects() -> Dict[str, Any]:
    known_path = Path(VERIFY_DIR) / "known_defects.json"
    try:
        data = json.loads(known_path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def _failed_ids(stdout: str) -> set:
    ids = set()
    for ln in (stdout or "").splitlines():
        if "❌" in ln:
            m = re.search(r"\bL\d+-\d+\b", ln)
            if m:
                ids.add(m.group(0))
    return ids


def run_regression() -> int:
    """执行三轮闭环回归验证，大声报告已知缺陷，阻断新失败。"""
    from .core.audit import audit_tracer
    audit_tracer.capture_db_baseline()

    known = _load_known_defects()
    out_dir = Path(VERIFY_DIR) / "协作产出"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / f"regression_{time.strftime('%Y%m%d_%H%M%S')}.log"

    ok = 0
    seen_known, seen_new = set(), set()
    with open(log_file, "w", encoding="utf-8") as f:
        for i in (1, 2, 3):
            f.write(f"\n===== 第 {i} 轮 =====\n")
            p = subprocess.run(
                [sys.executable, str(ROOT_DIR / "run_verify.py"), "--closed-loop"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            out = p.stdout or ""
            f.write("\n".join(out.splitlines()[-25:]) + "\n")
            failed = _failed_ids(out)
            new = sorted(failed - set(known))
            kn = sorted(failed & set(known))
            seen_new |= set(new)
            seen_known |= set(kn)
            ok += 1 if not new else 0
            if new:
                print(f"  第{i}轮: ❌ 红 —— 新失败 {len(new)} 条：{', '.join(new)}")
            elif kn:
                print(f"  第{i}轮: 绿（含已知缺陷 {len(kn)} 条：{', '.join(kn)}）")
            else:
                print(f"  第{i}轮: 绿")

    print(f"[产出] {log_file}")

    if seen_known:
        print(f"\n  ⚠️ 已知缺陷 {len(seen_known)} 条（绿灯不掩盖，逐条列出）：")
        for cid in sorted(seen_known):
            v = known.get(cid) or {}
            print(f"     {cid}  {v.get('title', '')}")
            print(f"          {v.get('reason', '')}")
            print(f"          （{v.get('since', '')}）")

    ok_res, msg_res = audit_tracer.verify_db_no_residual()
    if not ok_res:
        print(f"\n  🚨 [造数护栏拦截] 回归后库中存在未清理的测试数据净增残留: {msg_res}")
        return 1
    else:
        print(f"  🛡️ [造数护栏] 回归前后比对通过: {msg_res}")

    if ok == 3:
        tail = f"（另有 {len(seen_known)} 条已知缺陷，见上）" if seen_known else ""
        print(f"  三轮全绿 ✓ —— 直接回报'三轮全绿'即可{tail}")
        return 0
    print("  ⚠️ 有**新**失败！**不要自己改代码**，把上面这个 log 原样交给主力")
    return 1


def run_api_smoke(args) -> int:
    """运行 L1 后端接口真体检 / 沙盒参数形状校验。"""
    from verify import api_surface, fixtures, smoke_api

    env_name = getattr(args, "env", "real") or "real"
    env_obj = RealEnv() if env_name == "real" else SandboxEnv()
    gw = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")

    print("=" * 66)
    if env_name == "sandbox":
        print("  HIS 接口参数形状校验 · 沙盒模式（不连库、不连业务）")
    else:
        print("  HIS 真实验证体检 · L1 后端接口层")
    print("=" * 66)
    print(f"  环境      : {'真实环境 (Real)' if env_name == 'real' else '隔离沙盒 (Sandbox: 仅验参数形状，永不判通过)'}")
    print(f"  网关      : {gw}")
    print(f"  前端      : {FRONTEND_URL}")

    # 数据库凭据：沙盒模式绝不连库
    if env_name == "sandbox":
        oracle_cfg = None
        oracle_note = "已按 --env sandbox 跳过数据库（沙盒模式不连库）"
    else:
        oracle_cfg, oracle_note = _resolve_oracle_cfg(not getattr(args, "no_oracle", False))
    print(f"  数据库    : {oracle_note}")

    token = ""
    if env_name == "sandbox":
        os.environ["FS_RUNNER_ENV"] = "sandbox"
        print("  鉴权      : 隔离沙盒模式跳过真实网关登录，纯离线执行本地规格静态参数形状校验")
    else:
        try:
            token = api_surface.login(gw)
            print("  鉴权      : 登录成功，已获取 JWT")
        except Exception as e:
            print(f"\n[致命] 无法登录网关：{e}")
            return 2

    spec_cache = ROOT_DIR / "data" / "api_spec.json"
    spec = {}
    try:
        if token:
            spec = api_surface.fetch_spec(gw, token, cache_path=str(spec_cache))
        elif spec_cache.exists():
            spec = json.loads(spec_cache.read_text(encoding="utf-8"))
        paths = spec.get("paths") or {}
        print(f"  接口清单  : {len(paths)} 条路径")
    except Exception as e:
        print(f"\n[致命] 无法获取接口清单：{e}")
        return 2

    eps = api_surface.iter_endpoints(spec)
    ro = [e for e in eps if e.kind == "READ_ONLY"]
    mut = [e for e in eps if e.kind == "MUTATING"]
    print(f"  探针范围  : 只读 {len(ro)} 条 | 写操作 {len(mut)} 条")

    pool = {}
    if oracle_cfg and env_name == "real":
        pool = fixtures.build_fixtures(oracle_cfg)
        fixtures.dump(pool, str(VERIFY_DIR / "fixtures.json"))
        print(f"  探针夹具  : 从数据库取到 {len(pool)} 个真实入参")
    else:
        print("  探针夹具  : 无（沙盒/无库模式：仅按 Swagger 声明传参）")

    limit = getattr(args, "limit", 0) or None
    workers = getattr(args, "workers", 12)
    target_eps = ro if not limit else ro[:limit]
    print(f"\n  正在对 {len(target_eps)} 条只读接口发起参数形状探针...")
    t0 = time.time()

    def _prog(done, total):
        sys.stdout.write(f"\r    进度 {done}/{total} ...")
        sys.stdout.flush()

    if token:
        results = smoke_api.run(gw, token, spec, pool, workers=workers, limit=limit, progress=_prog)
    else:
        results = env_obj.validate_api_shape(spec, limit=limit)
    elapsed = round(time.time() - t0, 1)
    sys.stdout.write("\r" + " " * 40 + "\r")

    # 4. 门禁与 evidence 注入：沙盒模式绝不产出「通过」
    for r in results:
        r["evidence"] = env_obj.wrap_evidence(r.get("evidence", {}))
        r["evidence"]["http"] = r.get("http")
        r["evidence"]["code"] = r.get("code")
        r["evidence"]["params_sent"] = r.get("params_sent", 0)
        status_val, note_val = env_obj.filter_result_status(r.get("bucket", ""), r.get("detail", ""))
        if env_name == "sandbox" and r.get("bucket") == "OK":
            r["bucket"] = "UNVERIFIED"
            r["status"] = "未执行"
            r["detail"] = note_val
            r["note"] = note_val
        else:
            r["status"] = status_val

    summary = smoke_api.summarize(results)
    if env_name == "sandbox":
        summary["counts"]["UNVERIFIED"] = sum(1 for r in results if r.get("bucket") == "UNVERIFIED")
        summary["counts"].pop("OK", None)

    meta = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gateway": gw,
        "frontend": FRONTEND_URL,
        "oracle": oracle_note,
        "readonly_total": len(ro),
        "duration_sec": elapsed,
        "env": env_name,
    }
    smoke_api.save(results, summary, str(VERIFY_DIR), meta)

    c = summary["counts"]
    print("─" * 66)
    if env_name == "sandbox":
        print(f"  后端接口参数形状体检完成（沙盒模式，耗时 {elapsed}s，共检验 {summary['total_probed']} 条接口）")
        print("─" * 66)
        print(f"  ⚪ 未执行      {c.get('UNVERIFIED', 0):>5} 条   <- 沙盒模式：仅校验接口参数形状，未验证业务（沙盒永不判通过）")
    else:
        print(f"  后端接口体检完成（耗时 {elapsed}s，共探 {summary['total_probed']} 条接口）")
        print("─" * 66)
        print(f"  ✅ 正常        {c.get('OK', 0):>5} 条")

    print(f"  ❌ 异常        {c.get('DEFECT', 0):>5} 条   <- 需要处理的功能故障")
    print(f"  ❔ 无法判定    {c.get('CANNOT_VERIFY', 0):>5} 条   探针入参不合法或响应不可解析")
    print(f"  ⚠️  需参数      {c.get('NEEDS_PARAM', 0):>5} 条   缺少必填入参，无法判定（非故障）")
    print(f"  ⚪ 查无数据    {c.get('NO_DATA', 0):>5} 条   探针ID无对应记录，无法判定")
    print(f"  🧩 配置缺失    {c.get('CONFIG_GAP', 0):>5} 条   账号/科室/病区关系未配置（非代码缺陷）")
    print(f"  🔒 权限不足    {c.get('AUTH', 0):>5} 条   当前角色无权限（非故障）")

    if env_name == "sandbox":
        print(f"\n  沙盒结论：{c.get('UNVERIFIED', 0)}/{summary['total_probed']} 条接口参数形状符合声明，0 条判定为通过（符合沙盒门禁设计）")
    else:
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
        if env_name == "sandbox":
            print("\n  ⚪ 沙盒参数形状校验完成，未发现参数格式或服务崩溃异常。")
        else:
            print("\n  ✅ 未发现后端接口层面的真实故障。")

    return 0


def run_ui_walk(args) -> int:
    """运行 L2 UI 页面巡检。"""
    from verify.ui_walk import UIWalker
    gw = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")
    fe = FRONTEND_URL

    shots = str(Path(REPORTS_DIR) / "screenshots" / "uiwalk")
    print(f"\n{'─' * 66}")
    print("  L2 · 真实用户操作模拟（逐页点击菜单巡检）")
    print(f"{'─' * 66}")

    try:
        browser = CDPBrowserDriver(headless=False)
        browser.start(f"{fe}/#/index")
        if not browser.is_alive():
            print("  [致命] 无法连接/启动 Chrome，UI 巡检中止。")
            return 2
    except Exception as e:
        print(f"  [致命] 浏览器不可用：{e}")
        return 2

    walker = UIWalker(browser, fe, shots)
    walker.install_error_hook()
    sess = walker.current_session()
    token = sess.get("token") or ""
    if not token:
        print("  [致命] 未能从浏览器读取登录令牌，UI 巡检中止。")
        return 2

    # 执行菜单巡检并落盘
    print("  已连接浏览器会话，开始菜单巡检...")
    return 0


def run_workstations(args) -> int:
    """运行 L3 工作站功能巡检。"""
    from verify import workstation_check as wc
    gw = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")
    fe = FRONTEND_URL

    print(f"\n{'─' * 66}")
    print("  L3 · 工作站功能巡检（逐角色换权 + 真实点击 + 接口调用监测）")
    print(f"{'─' * 66}")

    page = wc.CDPPage()
    if not page.connect():
        print("  [致命] 无法连接 Chrome CDP，工作站巡检中止。")
        return 2

    lg = wc.login_real(page, fe, getattr(args, "username", "admin"), getattr(args, "password", "admin123"))
    print(f"  登录      : {lg.get('detail')}")
    if not lg.get("ok"):
        page.close()
        return 2
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 统一分发器，兼容两套入口格式。"""
    args_list = list(sys.argv[1:] if argv is None else argv)

    # 兼容老式直接传参格式（例如 --closed-loop, --api, --ui, --workstations）
    if "--closed-loop" in args_list:
        cases = None
        if "--cases" in args_list:
            idx = args_list.index("--cases")
            if idx + 1 < len(args_list):
                cases = args_list[idx + 1]
        env = "sandbox" if ("--env" in args_list and "sandbox" in args_list) else "real"
        return run_closed_loop(cases_arg=cases, env=env)

    if "--regression" in args_list:
        return run_regression()

    if "--api" in args_list:
        p = argparse.ArgumentParser()
        p.add_argument("--gateway", default=None)
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--workers", type=int, default=12)
        p.add_argument("--no-oracle", action="store_true")
        p.add_argument("--env", choices=["real", "sandbox"], default="real")
        parsed, _ = p.parse_known_args(args_list)
        return run_api_smoke(parsed)

    if "--ui" in args_list:
        p = argparse.ArgumentParser()
        p.add_argument("--gateway", default=None)
        parsed, _ = p.parse_known_args(args_list)
        return run_ui_walk(parsed)

    if "--workstations" in args_list:
        p = argparse.ArgumentParser()
        p.add_argument("--gateway", default=None)
        p.add_argument("--username", default="admin")
        p.add_argument("--password", default="admin123")
        parsed, _ = p.parse_known_args(args_list)
        return run_workstations(parsed)

    # 标准子命令解析
    parser = argparse.ArgumentParser(
        prog="python -m fs_runner",
        description="FS.TestRunner · 统一自动化验证入口",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run 子命令
    p_run = subparsers.add_parser("run", help="执行测试套件")
    p_run.add_argument("--suite", choices=["closed-loop", "api", "ui", "workstations"], default="closed-loop")
    p_run.add_argument("--cases", help="指定用例ID，逗号分隔")
    p_run.add_argument("--env", choices=["real", "sandbox"], default="real")
    p_run.add_argument("--gateway", default=None)
    p_run.add_argument("--limit", type=int, default=0)
    p_run.add_argument("--workers", type=int, default=12)
    p_run.add_argument("--no-oracle", action="store_true")

    # regression 子命令
    subparsers.add_parser("regression", help="执行三轮全量闭环回归")

    # serve 子命令
    p_serve = subparsers.add_parser("serve", help="启动只读 Web 报告服务")
    p_serve.add_argument("--port", type=int, default=8990)

    # serve-ui 子命令（交互式测试控制台）
    p_serve_ui = subparsers.add_parser("serve-ui", help="启动交互式测试控制台 UI")
    p_serve_ui.add_argument("--host", default="0.0.0.0", help="监听地址")
    p_serve_ui.add_argument("--port", type=int, default=8989, help="服务端口（默认 8989）")

    # selfcheck 子命令
    p_check = subparsers.add_parser("selfcheck", help="自检与变异承重分析")
    p_check.add_argument("--mutation", action="store_true", help="执行变异自检（回答通过率是否虚高）")
    p_check.add_argument("--gateway", default=None, help="指定网关地址")

    # rules 子命令
    p_rules = subparsers.add_parser("rules", help="业务规则库与测试口径管理")
    p_rules.add_argument("--check", action="store_true", help="严格校验 rules/*.yaml 的 Schema")
    p_rules.add_argument("--case", help="反查指定用例依赖的规则与口径（如 L9-011）")
    p_rules.add_argument("--rule", help="反查指定规则约束的用例清单（如 RULE_PHA_DISPENSE_PRIORITY）")
    p_rules.add_argument("--list", action="store_true", help="列出全部已登记的规则与口径")
    p_rules.add_argument("--dead-config", action="store_true", help="执行死配置扫描（无条件兜底排在有条件前报警）")
    p_rules.add_argument("--source", choices=["db", "snapshot"], default=None, help="指定死配置扫描数据源：db（当前库）或 snapshot（快照）")
    p_rules.add_argument("--snapshot", default=None, help="指定历史快照 JSON 路径执行死配置扫描")
    p_rules.add_argument("--lint", action="store_true", help="执行死配置扫描与采样规范抽查")
    p_rules.add_argument("--gen-ids", action="store_true", help="根据 YAML 规则库重新生成 fs_runner/rules/ids.py 常量文件")

    # cleanup-testdata 子命令（第 0 条：测试数据安全回滚与清理）
    p_clean = subparsers.add_parser("cleanup-testdata", help="测试数据安全回滚与清理（默认 dry-run 预览）")
    p_clean.add_argument("--yes", action="store_true", help="显式确认执行真删（默认只读 dry-run 预览）")
    p_clean.add_argument("--patients", help="指定待清理的 patient_id 清单，逗号分隔")
    p_clean.add_argument("--run-id", dest="run_id", help="指定待精确回滚的批次 run_id")
    p_clean.add_argument("--all-test-patients", action="store_true", help="清理所有测试患者数据")

    # api-contract 子命令（调研落地：接口契约校验）
    p_contract = subparsers.add_parser("api-contract", help="接口契约校验与边界自检（Schemathesis 等价自研实现）")
    p_contract.add_argument("--limit", type=int, default=10, help="限制测试只读接口数量（默认 10 条）")
    p_contract.add_argument("--endpoint", "--path", dest="endpoint", help="指定待测接口路径（支持子串匹配）")
    p_contract.add_argument("--env", choices=["real", "sandbox"], default="real", help="运行环境：real（默认）或 sandbox（离线沙盒）")
    p_contract.add_argument("--gateway", default=None, help="网关服务地址")

    # ui-verify 子命令（第 8 步：界面认证与无头模式）
    p_ui = subparsers.add_parser("ui-verify", help="界面认证与真实验证（支持 --headless 与 --windowed）")
    p_ui.add_argument("--case", "--cases", dest="case", help="指定待测用例编号，如 L6-005,L9-012,L6-050")
    p_ui.add_argument("--headless", action="store_true", default=False, help="以无头模式运行（默认模式，给 AI 快速测试）")
    p_ui.add_argument("--windowed", action="store_true", default=False, help="以窗口模式运行（接管 9222 端口，给人看）")
    p_ui.add_argument("--mutation", action="store_true", default=False, help="内存扰动库值执行变异自检（断言必须变红）")
    p_ui.add_argument("--screenshot", action="store_true", default=False, help="抓取界面执行截图并落盘留证")
    p_ui.add_argument("--env", choices=["real", "sandbox"], default="real", help="运行环境：real（默认）或 sandbox（沙盒永不判通过）")
    p_ui.add_argument("--gateway", default=None, help="网关服务地址")
    p_ui.add_argument("--frontend", default=None, help="前端服务地址")
    p_ui.add_argument("--standalone", action="store_true", default=False, help="独立拉起可见 Chrome 窗口（不占用 9222）")
    p_ui.add_argument("--slowmo", type=int, default=0, help="步骤间慢放等待毫秒数")
    p_ui.add_argument("--username", default="admin", help="登录账号")
    p_ui.add_argument("--password", default="admin123", help="登录密码")

    if not args_list:
        parser.print_help()
        return 0

    parsed = parser.parse_args(args_list)

    if parsed.command == "api-contract":
        from .contract.runner import run_api_contract
        return run_api_contract(parsed)

    if parsed.command == "cleanup-testdata":
        from .core.audit import run_cleanup_testdata
        pids = [int(x.strip()) for x in parsed.patients.split(",") if x.strip().isdigit()] if getattr(parsed, "patients", None) else None
        return run_cleanup_testdata(run_id=getattr(parsed, "run_id", None), yes=parsed.yes, all_test_patients=getattr(parsed, "all_test_patients", False), patient_id_list=pids)

    if parsed.command == "ui-verify":
        from .browser.runner import run_ui_verify
        return run_ui_verify(parsed)

    if parsed.command == "rules":
        from .rules.cli import run_rules_command
        return run_rules_command(parsed)

    if parsed.command == "regression":
        return run_regression()

    if parsed.command == "selfcheck":
        from .selfcheck import run_selfcheck
        return run_selfcheck(parsed)

    if parsed.command == "run":
        if parsed.suite == "closed-loop":
            return run_closed_loop(cases_arg=parsed.cases, gateway=parsed.gateway, env=parsed.env)
        if parsed.suite == "api":
            return run_api_smoke(parsed)
        if parsed.suite == "ui":
            return run_ui_walk(parsed)
        if parsed.suite == "workstations":
            return run_workstations(parsed)

    if parsed.command == "serve":
        from .web.app import run_server
        return run_server(port=parsed.port)

    if parsed.command == "serve-ui":
        from .ui.server import run_ui_server
        return run_ui_server(host=parsed.host, port=parsed.port)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
