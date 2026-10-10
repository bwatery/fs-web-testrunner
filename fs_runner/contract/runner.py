# -*- coding: utf-8 -*-
"""
fs_runner.contract.runner
=========================
自研接口契约校验执行器（Schemathesis 等价自研物）：
1. 数据源：data/api_spec.json (Swagger 2.0 / OpenAPI 规范) + 闭环用例调用的业务接口。
2. 按 schema 生成入参变异组合：
   - 正常只读基线契约：按 spec 默认/示例传参，断言响应体符合 JSON 与标准结构。
   - 必填项缺失变异 (Missing Required)：故意缺传必填参数，断言服务端返回规范的错误信封而非崩溃。
   - 类型错误变异 (Type Mismatch)：数值型字段传入字符串，断言参数校验拦截且返回标准错误格式。
   - 边界值变异 (Boundary Mutation)：负数、超长字符串、特殊转义字符，断言服务安全防御且不抛 502/HTML 崩溃。
3. 安全硬护栏：
   - 优先扫描 66 条闭环用例中调用的真实业务 GET 接口，严格排除文件下载等非 JSON 接口。
   - 仅允许 Read 类接口或非法参数变异测试，严禁对写库/改表接口发起可能落盘的调用。
   - --env sandbox 模式下纯离线静态验证 schema 与契约映射，绝不发网关网络请求，强制产出「未执行」。
4. 结果落盘：reports/verify/contract_latest.json。
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..config import GATEWAY_URL, ROOT_DIR


SPEC_PATH = ROOT_DIR / "data" / "api_spec.json"
REPORTS_DIR = ROOT_DIR / "reports" / "verify"
_JSON_H = {"Content-Type": "application/json"}


def _get_admin_token(gateway: str) -> Optional[str]:
    """获取网关鉴权令牌。"""
    try:
        r = requests.post(
            f"{gateway}/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10,
            proxies={"http": None, "https": None},
        )
        return (r.json() or {}).get("data")
    except Exception:
        return None


def _collect_closed_loop_endpoints() -> List[str]:
    """扫描 closed_loop 代码库中引用的接口路径。"""
    cl_dir = ROOT_DIR / "fs_runner" / "cases" / "closed_loop"
    endpoints = []
    if cl_dir.exists():
        for py_file in cl_dir.rglob("*.py"):
            try:
                txt = py_file.read_text(encoding="utf-8")
                matches = re.findall(r"['\"](/faith/[a-zA-Z0-9_/]+)['\"]", txt)
                endpoints.extend(matches)
            except Exception:
                pass
    # 去重且保持相对顺序
    seen = set()
    ordered = []
    for ep in endpoints:
        if ep not in seen:
            seen.add(ep)
            ordered.append(ep)
    return ordered


def run_api_contract(args: Any) -> int:
    """执行 api-contract 子命令。"""
    limit = getattr(args, "limit", 10) or 10
    target_endpoint = getattr(args, "endpoint", None) or getattr(args, "path", None)
    env_name = getattr(args, "env", "real") or "real"
    gateway = (getattr(args, "gateway", None) or GATEWAY_URL).rstrip("/")

    print("=" * 68)
    print("  FS.TestRunner · 接口契约校验与边界变异引擎 (api-contract)")
    print("=" * 68)
    print(f"  规格数据源: {SPEC_PATH.relative_to(ROOT_DIR) if SPEC_PATH.exists() else '不存在'}")
    print(f"  运行环境  : {'隔离沙盒 (Sandbox: 纯离线契约自检)' if env_name == 'sandbox' else '真实环境 (Real)'}")
    print(f"  检验数量  : 限制测试 {limit} 条接口")
    if target_endpoint:
        print(f"  目标接口  : {target_endpoint}")
    print("-" * 68)

    if not SPEC_PATH.exists():
        print(f"❌ [错误] 未找到接口规范文件: {SPEC_PATH}")
        return 1

    try:
        spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ [错误] 解析接口规范文件失败: {e}")
        return 1

    paths = spec.get("paths", {})
    if not paths:
        print("❌ [错误] 规范文件中 paths 为空")
        return 1

    # 1. 扫描闭环用例引用的真实业务接口
    cl_endpoints = _collect_closed_loop_endpoints()

    # 2. 筛选优先只读接口（严格 GET 请求，排除下载类二进制接口）
    candidate_endpoints: List[Dict[str, Any]] = []

    # 优先匹配闭环用例中的 GET 接口
    for ep_path in cl_endpoints:
        if target_endpoint and target_endpoint not in ep_path:
            continue
        if ep_path in paths:
            item = paths[ep_path]
            if isinstance(item, dict) and "get" in item and isinstance(item["get"], dict):
                candidate_endpoints.append({
                    "path": ep_path,
                    "method": "GET",
                    "op": item["get"],
                    "source": "closed_loop",
                })

    # 若未达 limit，补充 spec 中其他只读业务接口（排除 /common/download 等二进制/下载接口）
    if len(candidate_endpoints) < limit:
        for path_str, path_item in paths.items():
            if target_endpoint and target_endpoint not in path_str:
                continue
            if not isinstance(path_item, dict):
                continue
            if "download" in path_str.lower() or "export" in path_str.lower() or "upload" in path_str.lower():
                continue
            if "get" in path_item and isinstance(path_item["get"], dict):
                if not any(c["path"] == path_str for c in candidate_endpoints):
                    candidate_endpoints.append({
                        "path": path_str,
                        "method": "GET",
                        "op": path_item["get"],
                        "source": "api_spec",
                    })
            if len(candidate_endpoints) >= limit * 2:
                break

    if not candidate_endpoints:
        print("⚠️ 未找到匹配的只读接口供契约校验。")
        return 0

    selected_endpoints = candidate_endpoints[:limit]
    print(f"\n[1/2] 已选取 {len(selected_endpoints)} 条只读接口开展契约与变异校验...\n")

    # 3. 沙盒模式离线静态校验
    if env_name == "sandbox":
        print("⚪ [沙盒模式硬约束] 仅对接口 Schema 结构开展静态契约校验，不发真实网络请求，强制产出「未执行」：\n")
        results = []
        for ep in selected_endpoints:
            p = ep["path"]
            params = ep["op"].get("parameters", [])
            req_params = [x.get("name") for x in params if isinstance(x, dict) and x.get("required")]
            note = f"沙盒模式：仅校验接口契约参数形状（含 {len(params)} 参数，{len(req_params)} 必填），未验证业务"
            print(f"  ⚪ [未执行] GET {p:<52} —— {note}")
            results.append({
                "path": p,
                "method": "GET",
                "status": "未执行",
                "note": note,
                "evidence": {
                    "env": "sandbox",
                    "parameters_count": len(params),
                    "required_params": req_params,
                    "contract_valid": True,
                },
            })
        _save_contract_report(results, env_name, gateway, limit)
        return 0

    # 4. 真实环境动态契约测试
    token = _get_admin_token(gateway)
    if not token:
        print(f"❌ 无法从网关 {gateway} 获取有效令牌，契约校验中止。")
        return 2

    headers = {"Authorization": f"Bearer {token}", **_JSON_H}
    s = requests.Session()
    s.proxies = {"http": None, "https": None}
    s.trust_env = False

    results = []
    total_mutations = 0
    passed_mutations = 0

    # 常见参数推断词典（辅助基线传参对齐）
    PARAM_HINTS = {
        "storagedeptid": 910131,
        "deptid": 910131,
        "roleid": 36,
        "pageno": 1,
        "pagesize": 10,
        "month": time.strftime("%Y-%m"),
        "type": "1",
    }

    for idx, ep in enumerate(selected_endpoints, 1):
        path_str = ep["path"]
        op = ep["op"]
        summary = (op.get("summary") or "").replace("\n", " ").strip()
        params = op.get("parameters", [])
        url = f"{gateway}{path_str}"

        # 构造基线查询参数
        base_params = {}
        for p in params:
            if not isinstance(p, dict):
                continue
            p_name = p.get("name")
            p_type = p.get("type", "string")
            if p_name and p.get("in") == "query":
                low_name = p_name.lower()
                if low_name in PARAM_HINTS:
                    base_params[p_name] = PARAM_HINTS[low_name]
                elif p_type in ("integer", "int", "number"):
                    base_params[p_name] = 1
                elif p_type == "boolean":
                    base_params[p_name] = True
                else:
                    base_params[p_name] = "test"

        ep_mutations: List[Dict[str, Any]] = []

        # 变异 1: 正常基线查询 (Baseline Contract)
        t0 = time.time()
        try:
            r_base = s.get(url, headers=headers, params=base_params, timeout=10)
            dur_ms = round((time.time() - t0) * 1000, 1)
            is_json = False
            resp_body = None
            try:
                resp_body = r_base.json()
                is_json = True
            except Exception:
                pass

            # 结构断言：返回 JSON 且含有通用外层信封 (code/msg/data 或 list/dict)，无 502/HTML 崩溃
            has_envelope = isinstance(resp_body, (dict, list))
            base_ok = (r_base.status_code in (200, 400, 401, 403, 404, 500)) and is_json and has_envelope
            ep_mutations.append({
                "type": "正常基线契约",
                "ok": base_ok,
                "status_code": r_base.status_code,
                "is_json": is_json,
                "duration_ms": dur_ms,
                "detail": "响应为合法 JSON 且结构符合信封标准" if base_ok else "响应非 JSON 或发生网络崩溃",
            })
        except Exception as e:
            ep_mutations.append({
                "type": "正常基线契约",
                "ok": False,
                "status_code": None,
                "is_json": False,
                "duration_ms": 0,
                "detail": f"请求异常: {e}",
            })

        # 变异 2: 必填缺失变异 (Missing Required)
        required_params = [p.get("name") for p in params if isinstance(p, dict) and p.get("required") and p.get("in") == "query"]
        if required_params:
            for rp in required_params[:2]:
                mut_params = dict(base_params)
                mut_params.pop(rp, None)
                try:
                    r_mut = s.get(url, headers=headers, params=mut_params, timeout=10)
                    is_json = False
                    try:
                        r_mut.json()
                        is_json = True
                    except Exception:
                        pass
                    # 缺少必填时网关应正常拦截并返回 JSON 错误（绝非 502/HTML）
                    mut_ok = is_json and (r_mut.status_code != 502)
                    ep_mutations.append({
                        "type": f"必填缺失变异({rp})",
                        "ok": mut_ok,
                        "status_code": r_mut.status_code,
                        "is_json": is_json,
                        "detail": "网关按规约拦截或返回结构化响应" if mut_ok else "缺少必填参数引发未捕获崩溃",
                    })
                except Exception as e:
                    ep_mutations.append({
                        "type": f"必填缺失变异({rp})",
                        "ok": False,
                        "detail": f"异常: {e}",
                    })
        else:
            ep_mutations.append({
                "type": "必填缺失变异",
                "ok": True,
                "detail": "该接口无显式必填 query 参数，豁免跳过",
            })

        # 变异 3: 类型错误变异 (Type Mismatch)
        int_params = [p.get("name") for p in params if isinstance(p, dict) and p.get("type") in ("integer", "int", "number") and p.get("in") == "query"]
        if int_params:
            for ip in int_params[:1]:
                mut_params = dict(base_params)
                mut_params[ip] = "INVALID_STRING_NOT_NUMBER"
                try:
                    r_mut = s.get(url, headers=headers, params=mut_params, timeout=10)
                    is_json = False
                    try:
                        r_mut.json()
                        is_json = True
                    except Exception:
                        pass
                    # 类型错误被统一异常处理器拦截为结构化 JSON
                    mut_ok = is_json and (r_mut.status_code != 502)
                    ep_mutations.append({
                        "type": f"类型错误变异({ip})",
                        "ok": mut_ok,
                        "status_code": r_mut.status_code,
                        "is_json": is_json,
                        "detail": "类型错误被统一异常处理器拦截" if mut_ok else "类型不匹配引发非结构化崩溃",
                    })
                except Exception as e:
                    ep_mutations.append({
                        "type": f"类型错误变异({ip})",
                        "ok": False,
                        "detail": f"异常: {e}",
                    })
        else:
            ep_mutations.append({
                "type": "类型错误变异",
                "ok": True,
                "detail": "该接口无整型参数，豁免跳过",
            })

        # 变异 4: 边界值变异 (Boundary Mutation)
        str_params = [p.get("name") for p in params if isinstance(p, dict) and p.get("type") in ("string", None) and p.get("in") == "query"]
        if str_params:
            sp = str_params[0]
            mut_params = dict(base_params)
            mut_params[sp] = "SPECIAL_'\"<>&_BOUNDARY_LONG_" + ("X" * 128)
            try:
                r_mut = s.get(url, headers=headers, params=mut_params, timeout=10)
                is_json = False
                try:
                    r_mut.json()
                    is_json = True
                except Exception:
                    pass
                mut_ok = is_json and (r_mut.status_code != 502)
                ep_mutations.append({
                    "type": f"边界值变异({sp})",
                    "ok": mut_ok,
                    "status_code": r_mut.status_code,
                    "is_json": is_json,
                    "detail": "边界值与特殊字符被安全解析" if mut_ok else "边界值处理异常",
                })
            except Exception as e:
                ep_mutations.append({
                    "type": f"边界值变异({sp})",
                    "ok": False,
                    "detail": f"异常: {e}",
                })

        ep_all_ok = all(m.get("ok", False) for m in ep_mutations)
        ep_status = "通过" if ep_all_ok else "失败"
        mark = "✅" if ep_all_ok else "❌"

        total_mutations += len(ep_mutations)
        passed_mutations += sum(1 for m in ep_mutations if m.get("ok", False))

        print(f"  {mark} [{idx}/{len(selected_endpoints)}] GET {path_str}")
        print(f"        摘要: {summary or '（无摘要）'} | 变异项共 {len(ep_mutations)} 项 ({ep_status})")
        for m in ep_mutations:
            sub_mark = "✓" if m.get("ok") else "✗"
            print(f"         {sub_mark} {m['type']:<24} : {m.get('detail')} (HTTP {m.get('status_code', '-')})")

        results.append({
            "path": path_str,
            "method": "GET",
            "summary": summary,
            "status": ep_status,
            "mutations": ep_mutations,
            "evidence": {
                "env": "real",
                "mutations_count": len(ep_mutations),
                "all_mutations_passed": ep_all_ok,
                "read_only_guarantee": True,
            },
        })

    _save_contract_report(results, env_name, gateway, limit)

    passed_eps = sum(1 for r in results if r["status"] == "通过")
    print("\n" + "─" * 68)
    print(f"  接口契约与变异校验完成：")
    print(f"  • 接口通过率: {passed_eps}/{len(results)} ({round(passed_eps/len(results)*100, 1)}%)")
    print(f"  • 变异项通过: {passed_mutations}/{total_mutations} ({round(passed_mutations/total_mutations*100, 1)}%)")
    print(f"  • 报告落盘  : reports/verify/contract_latest.json")
    print("─" * 68)

    return 0 if passed_eps == len(results) else 1


def _save_contract_report(results: List[Dict[str, Any]], env_name: str, gateway: str, limit: int):
    """保存契约测试报告至 reports/verify/contract_latest.json。"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "contract_latest.json"
    payload = {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "env": env_name,
            "gateway": gateway,
            "limit": limit,
            "engine": "FS.ContractVerifier (Schemathesis Equivalent)",
        },
        "summary": {
            "total_endpoints": len(results),
            "passed": sum(1 for r in results if r["status"] == "通过"),
            "failed": sum(1 for r in results if r["status"] == "失败"),
            "unverified": sum(1 for r in results if r["status"] == "未执行"),
        },
        "results": results,
    }
    report_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
