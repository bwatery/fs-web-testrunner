"""
L1 · 后端接口真体检执行器

对全站只读接口发起真实调用，把响应分成六个桶，只有 DEFECT 才是"功能异常"。
关键设计：**两轮探针**。第一轮只按 Swagger 声明传参；对报参数缺失的接口，
第二轮补上真实 fixture 再打一次。只有两轮都失败的才可能是缺陷，
以此把"接口没给参数"的噪声和"接口真的坏了"分开。
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests

from . import api_surface, fixtures

# 参数校验类错误词表 → 归入 NEEDS_PARAM（噪声，不是缺陷）
_PARAM_VOCAB = [
    "不能为空", "不可为空", "必填", "请传入", "未传", "参数错误", "参数异常",
    "参数不合法", "参数不完整", "参数缺失", "缺少参数", "格式错误", "格式不正确",
    "类型错误", "转换失败", "非法参数", "无效参数", "不能为null", "不能为 null",
    "required", "parameter", "missing", "invalid",
]

# 查无数据类 → 归入 NO_DATA（探针用的 ID 在该接口域内无对应记录，无法判定）
_NODATA_VOCAB = [
    "记录不存在", "数据不存在", "查无数据", "未找到", "不存在该", "无此条",
    "没有查询到", "暂无数据", "该记录", "已被删除", "项目不存在", "药品不存在",
    "信息不存在", "单号不存在", "不存在", "已被删除", "已停用",
]

# 环境/配置缺失类 → 归入 CONFIG_GAP（账号、科室、病区关系没配好，不是代码缺陷）
_CONFIG_GAP_VOCAB = [
    "未维护", "未关联", "未配置", "未绑定", "未设置", "无对应关系", "未建立",
    "没有关联", "未授权该科室", "科室未", "未开通",
]

# 代码级故障特征 → 与入参取值基本无关，可直接判为高置信缺陷
_CODE_FAULT_VOCAB = [
    "ora-", "sqlsyntaxerror", "nullpointerexception", "空指针", "classcastexception",
    "badgrammar", "badsqlgrammar", "dataintegrityviolation", "mybatis", "sqlexception",
    "indexoutofbounds", "stackoverflow", "unsupportedoperation", "no such method",
    "cannot be cast", "syntax error", "语法错误",
]

_TIMEOUT = 8
_RETRY = 1

_local = threading.local()


def _session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.proxies = {"http": None, "https": None}
        s.trust_env = False
        _local.s = s
    return s


def bucket_response(http_status: Optional[int], text: str,
                    elapsed_ms: float, exc: Optional[str] = None,
                    placeholder_used: bool = False, params_sent: int = 0) -> tuple:
    """
    把一次探针响应归类。返回 (bucket, code, msg, detail)。

    桶含义：
      OK             —— 真实成功
      NEEDS_PARAM    —— 缺参数，无法判定（噪声）
      NO_DATA        —— 查无数据，无法判定
      CONFIG_GAP     —— 账号/科室等环境配置缺失，非代码缺陷
      AUTH           —— 权限不足（角色门禁，非缺陷）
      CANNOT_VERIFY  —— 响应不可解析，或业务拒绝但探针入参可能不对 → 不许下结论
      DEFECT         —— 真实缺陷（这次体检要报的东西）

    判定纪律（宁漏报，不误报）：
      1. **5xx / 传输失败 一律不算入参问题**：服务端抛出未捕获异常或被下游拖垮，
         无论入参对错都是缺陷，不因探针带了参数而降级。
      2. **4xx 级业务拒绝**在探针带了入参时一律不下"缺陷"结论 ——
         真实 fixture ID 也只是"真实"，未必是该接口域内的合法值。
      3. 只有"没带任何入参却仍然被 4xx 拒绝"的接口，才把业务拒绝算作缺陷。
      4. HTTP 200 且返回裸数组/裸对象（无 code 信封）视为成功，本项目确实有这类接口。
    """
    def _soft(bucket, code, msg, detail):
        """4xx 级：探针带了参数就不许定性为缺陷。"""
        if bucket == "DEFECT" and params_sent > 0:
            return "CANNOT_VERIFY", code, msg, \
                   f"已传参但请求被拒，无法区分是入参不合法还是系统异常: {detail}"
        return bucket, code, msg, detail

    if exc:
        # 传输层失败与入参无关
        return "DEFECT", None, None, f"传输失败: {exc}"
    if http_status is None:
        return "DEFECT", None, None, "无响应"

    # 空响应体：不是错误，只是没内容可判
    if not (text or "").strip():
        if http_status == 200:
            return "CANNOT_VERIFY", None, None, "HTTP 200 空响应，无可判定内容"
        return "DEFECT", None, None, f"HTTP {http_status} 空响应"

    # 解析响应体
    try:
        body = json.loads(text)
    except Exception:
        if http_status == 200:
            return "OK", None, None, "HTTP 200 非 JSON（文件流/二进制，视为成功）"
        if http_status >= 500:
            return "DEFECT", None, None, f"HTTP {http_status} 非 JSON 响应页"
        return _soft("DEFECT", None, None, f"HTTP {http_status} 非 JSON: {text[:160]}")

    # 裸数组 / 无信封对象：本项目部分接口直接返回数据体，HTTP 200 即成功
    if isinstance(body, list):
        if http_status == 200:
            return "OK", None, None, f"HTTP 200 裸数组响应（{len(body)} 条），视为成功"
        return "DEFECT", None, None, f"HTTP {http_status} 裸数组响应"
    if not isinstance(body, dict):
        return ("OK", None, None, "HTTP 200 标量响应") if http_status == 200 else \
               ("DEFECT", None, None, f"HTTP {http_status} 标量响应")
    if "code" not in body and "msg" not in body:
        if http_status == 200:
            return "OK", None, None, "HTTP 200 无信封对象响应，视为成功"
        return "DEFECT", None, None, f"HTTP {http_status} 无信封对象响应"

    code = body.get("code")
    msg = body.get("msg") or body.get("message") or ""
    msg_s = str(msg)
    low = msg_s.lower()

    # ---- 业务码优先：本项目绝大多数错误用 HTTP 200 + 业务码表达 ----
    if code in api_surface.SUCCESS_CODES:
        return "OK", code, msg_s, ""
    if code == 500:
        # 500 是硬信号：服务端异常，不因入参而降级
        if any(v in msg_s for v in _NODATA_VOCAB):
            return "NO_DATA", code, msg_s, msg_s
        if any(v in msg_s for v in _CONFIG_GAP_VOCAB):
            return "CONFIG_GAP", code, msg_s, msg_s
        return "DEFECT", code, msg_s, \
               f"业务码 500 服务端异常: {msg_s[:160] or '(无错误信息，典型未捕获异常)'}"
    if code in (401, 403):
        return "AUTH", code, msg_s, f"权限不足({code}): {msg_s[:120]}"
    if code in (400, 404, 422):
        if any(v in msg_s or v in low for v in _PARAM_VOCAB):
            return "NEEDS_PARAM", code, msg_s, msg_s
        if any(v in msg_s for v in _CONFIG_GAP_VOCAB):
            return "CONFIG_GAP", code, msg_s, msg_s
        if any(v in msg_s for v in _NODATA_VOCAB):
            return "NO_DATA", code, msg_s, msg_s
        return _soft("DEFECT", code, msg_s, f"业务码 {code}: {msg_s[:160]}")

    # ---- 再按 HTTP 状态兜底 ----
    if http_status >= 500:
        return "DEFECT", code, msg_s, f"HTTP {http_status}: {msg_s[:160] or '服务端错误'}"
    if http_status == 404:
        if any(v in msg_s for v in _NODATA_VOCAB):
            return "NO_DATA", code, msg_s, msg_s
        if any(v in msg_s for v in _CONFIG_GAP_VOCAB):
            return "CONFIG_GAP", code, msg_s, msg_s
        return _soft("DEFECT", code, msg_s, f"HTTP 404 接口不存在/网关未注册: {msg_s[:120]}")
    if http_status in (400, 422):
        if any(v in msg_s or v in low for v in _PARAM_VOCAB):
            return "NEEDS_PARAM", code, msg_s, msg_s
        if any(v in msg_s for v in _CONFIG_GAP_VOCAB):
            return "CONFIG_GAP", code, msg_s, msg_s
        if any(v in msg_s for v in _NODATA_VOCAB):
            return "NO_DATA", code, msg_s, msg_s
        return _soft("DEFECT", code, msg_s, f"HTTP {http_status}: {msg_s[:160]}")
    if http_status != 200:
        return _soft("DEFECT", code, msg_s, f"HTTP {http_status} 非预期状态码")

    if code is None:
        return _soft("DEFECT", code, msg_s, f"响应无业务码: {text[:160]}")

    return _soft("DEFECT", code, msg_s, f"未知业务码 {code}: {msg_s[:160]}")


def probe_one(base_url: str, token: str, ep: api_surface.Endpoint,
              spec: Dict[str, Any], fixture_pool: Dict[str, Any],
              extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """对单条接口发起一次真实调用。"""
    req = api_surface.build_request(ep, spec, fixture_pool)
    query = dict(req["query"])
    if extra_params:
        query.update(extra_params)
    url = f"{base_url.rstrip('/')}{req['path']}"
    headers = {"Authorization": f"Bearer {token}"}
    kwargs: Dict[str, Any] = {"timeout": _TIMEOUT, "proxies": {"http": None, "https": None}}
    body = req["body"]
    params_sent = len(query) + (1 if body not in (None, {}, []) else 0)

    t0 = time.time()
    exc_msg = None
    status = None
    text = ""
    for attempt in range(_RETRY + 1):
        try:
            if ep.method == "GET":
                r = _session().get(url, params=query, headers=headers, **kwargs)
            else:
                headers["Content-Type"] = "application/json"
                r = _session().post(url, params=query, json=body, headers=headers, **kwargs)
            status = r.status_code
            text = r.text or ""
            exc_msg = None
            break
        except Exception as e:
            exc_msg = f"{type(e).__name__}: {e}"
            status, text = None, ""
            if attempt < _RETRY:
                time.sleep(0.4)
    elapsed = round((time.time() - t0) * 1000, 1)

    bucket, code, msg, detail = bucket_response(
        status, text, elapsed, exc_msg,
        placeholder_used=req["placeholder_used"], params_sent=params_sent)

    # 置信度：高 = 与探针入参无关（无编造入参，或命中代码级故障特征）；低 = 可能是我们传参不当
    confidence = "high"
    if bucket == "DEFECT":
        blob = f"{msg or ''} {detail or ''}".lower()
        if any(v in blob for v in _CODE_FAULT_VOCAB):
            confidence = "high"
        elif req["placeholder_used"]:
            confidence = "low"

    return {
        "method": ep.method,
        "path": ep.path,
        "tag": (ep.tags or [""])[0],
        "summary": ep.summary,
        "kind": ep.kind,
        "http": status,
        "code": code,
        "msg": msg,
        "bucket": bucket,
        "confidence": confidence,
        "detail": detail,
        "duration_ms": elapsed,
        "placeholder_used": req["placeholder_used"],
        "params_sent": params_sent,
        "probe_query": {k: str(v) for k, v in query.items()},
        "probe_body": json.dumps(body, ensure_ascii=False)[:300] if body else "",
        "response_head": text[:400],
    }


def run(base_url: str, token: str, spec: Dict[str, Any],
        fixture_pool: Dict[str, Any], workers: int = 12,
        denylist: Optional[set] = None, limit: Optional[int] = None,
        progress=None) -> List[Dict[str, Any]]:
    """对全部只读接口跑两轮探针。"""
    denylist = denylist or set()
    eps = [e for e in api_surface.iter_endpoints(spec) if e.kind == "READ_ONLY"]
    eps = [e for e in eps if e.key not in denylist and e.path not in denylist]
    if limit:
        eps = eps[:limit]

    results: List[Dict[str, Any]] = []
    total = len(eps)
    done = 0

    def _work(ep):
        return probe_one(base_url, token, ep, spec, fixture_pool)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_work, ep): ep for ep in eps}
        for fut in as_completed(futs):
            ep = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {
                    "method": ep.method, "path": ep.path, "tag": (ep.tags or [""])[0],
                    "summary": ep.summary, "kind": ep.kind, "http": None, "code": None,
                    "msg": None, "bucket": "DEFECT",
                    "detail": f"执行器异常: {type(e).__name__}: {e}",
                    "duration_ms": 0, "placeholder_used": False,
                    "probe_query": {}, "response_head": "",
                }
            results.append(res)
            done += 1
            if progress and done % 25 == 0:
                progress(done, total)

    # ---- 第二轮：对缺参数的接口补 fixture 再打一次 ----
    retry_eps = {e.key: e for e in eps}
    pending = [r for r in results if r["bucket"] == "NEEDS_PARAM"]
    if pending and fixture_pool:
        def _work2(r):
            ep = retry_eps.get(f"{r['method']} {r['path']}")
            # 从报错里提取缺失字段名，补最贴切的 fixture
            extra = _guess_missing_params(r.get("msg") or "", fixture_pool)
            return probe_one(base_url, token, ep, spec, fixture_pool, extra_params=extra)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_work2, r): r for r in pending}
            for fut in as_completed(futs):
                old = futs[fut]
                try:
                    new = fut.result()
                except Exception:
                    continue
                # 只有当第二轮真的改善时才覆盖（避免把可复现结论覆盖成噪声）
                if new["bucket"] in ("OK", "NO_DATA", "AUTH", "DEFECT"):
                    new["pass2"] = True
                    results[results.index(old)] = new

    results.sort(key=lambda r: ({"DEFECT": 0, "CANNOT_VERIFY": 1, "NEEDS_PARAM": 2,
                                 "NO_DATA": 3, "CONFIG_GAP": 4, "AUTH": 5,
                                 "OK": 6}.get(r["bucket"], 7),
                                r["path"]))
    return results


def _guess_missing_params(msg: str, fixture_pool: Dict[str, Any]) -> Dict[str, Any]:
    """
    从"XX不能为空"这类报错里猜出缺失字段，并从 fixture 池取最贴近的真实值。
    猜不出就返回空（第二轮与第一轮等价，不会污染结论）。
    """
    extra: Dict[str, Any] = {}
    if not msg:
        return extra
    for key, val in fixture_pool.items():
        # 用 fixture 键的中英文线索去匹配报错文本
        if len(key) < 4:
            continue
        if key.lower() in msg.lower():
            extra[key] = val
    return extra


# ---------------------------------------------------------------------------
# 汇总与落盘
# ---------------------------------------------------------------------------

def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
    defects = [r for r in results if r["bucket"] == "DEFECT"]
    high = [r for r in defects if r.get("confidence") == "high"]
    low = [r for r in defects if r.get("confidence") != "high"]
    # 按模块（tag）聚合缺陷，便于直接看出哪个业务域坏了
    by_tag: Dict[str, Dict[str, int]] = {}
    for r in results:
        tag = r.get("tag") or "未分类"
        slot = by_tag.setdefault(tag, {"total": 0, "DEFECT": 0, "HIGH": 0})
        slot["total"] += 1
        if r["bucket"] == "DEFECT":
            slot["DEFECT"] += 1
            if r.get("confidence") == "high":
                slot["HIGH"] += 1
    return {
        "total_probed": len(results),
        "counts": counts,
        "defect_count": len(defects),
        "high_confidence_count": len(high),
        "low_confidence_count": len(low),
        "high_confidence_defects": high,
        "low_confidence_defects": low,
        "defects": defects,
        "by_tag": dict(sorted(by_tag.items(),
                              key=lambda kv: (-kv[1]["DEFECT"], -kv[1]["HIGH"]))),
    }


def save(results: List[Dict[str, Any]], summary: Dict[str, Any],
         out_dir: str, meta: Dict[str, Any]) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    payload = {"meta": meta, "summary": summary, "results": results}
    paths = {
        "ts": os.path.join(out_dir, f"api_smoke_{ts}.json"),
        "latest": os.path.join(out_dir, "api_smoke_latest.json"),
    }
    for p in paths.values():
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return paths
