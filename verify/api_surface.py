"""
L1 · 接口面发现与分类（API Surface）

职责：
1. 从网关拉取权威接口清单（Swagger 2.0 /v2/api-docs，回退 OpenAPI 3 /v3/api-docs）
2. 把 1590 条接口分成"可安全盲调"与"会改数据、绝不盲调"两类
3. 依据 Swagger 声明 + 运行时 fixture，为只读接口构造尽可能真实的探针入参

分类原则（宁可漏调，不可误改）：
- GET 一律视为只读
- POST 只有在"路径/摘要都像查询"且"Swagger 未声明必填 body"时才视为只读
- 任何命中写操作词表的（保存/新增/修改/删除/作废/收费/退费/结算/发药/执行/确认/提交/审核…）
  一律判为 MUTATING，交给 L3 在受控闭环里使用
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

# 写操作词表：命中即视为会改数据，绝不盲调
MUTATING_TOKENS = [
    "save", "add", "insert", "create", "update", "edit", "modify", "delete",
    "remove", "cancel", "refund", "charge", "pay", "settle", "audit", "submit",
    "confirm", "dispatch", "exec", "import", "upload", "rollback", "void",
    "disable", "enable", "reset", "login", "logout", "exchange", "send",
    "push", "receive", "register", "triage", "diagnosis", "print", "back",
    "del", "set", "handle", "approve", "reject", "stop", "start", "finish",
    "bind", "unbind", "merge", "split", "move", "copy", "renew", "apply",
]

MUTATING_CN = [
    "保存", "新增", "修改", "删除", "作废", "退费", "收费", "结算", "发药", "退药",
    "执行", "确认", "提交", "审核", "登记", "挂号", "退号", "开立", "下达", "撤销",
    "重置", "停用", "启用", "上传", "导入", "打印", "扣减", "冲正", "支付", "收费",
]

# 只读词表：路径末段命中即视为查询类
READ_TOKENS = [
    "list", "query", "page", "pages", "info", "detail", "tree", "select",
    "find", "search", "count", "dict", "dictionary", "check", "view", "history",
    "record", "records", "statistic", "statistics", "report", "options", "all",
    "get", "querybyid", "querybycode", "getbyid", "getbycode", "listbypage",
    "barinfo", "index", "summary", "overview", "config", "params", "status",
]

# Swagger 里常见的"成功"业务码
SUCCESS_CODES = {200, 0, "200", "0"}

_SESSION_PROXIES = {"http": None, "https": None}


def _clean_path(path: str) -> str:
    """仅取路径部分，去掉 query 与尾部斜杠。"""
    return (path or "").split("?")[0].rstrip("/") or "/"


def _last_segment(path: str) -> str:
    segs = [s for s in _clean_path(path).split("/") if s]
    return segs[-1].lower() if segs else ""


def _segments(path: str) -> List[str]:
    return [s.lower() for s in _clean_path(path).split("/") if s]


@dataclass
class Endpoint:
    method: str            # 大写：GET / POST
    path: str
    operation_id: str = ""
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    params: List[Dict[str, Any]] = field(default_factory=list)
    kind: str = "READ_ONLY"   # READ_ONLY | MUTATING
    classify_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


def login(base_url: str, username: str = "admin", password: str = "admin123",
          timeout: int = 15) -> str:
    """登录网关，返回 JWT。失败直接抛错——不做任何静默降级。"""
    r = requests.post(
        f"{base_url.rstrip('/')}/login",
        json={"username": username, "password": password},
        timeout=timeout,
        proxies=_SESSION_PROXIES,
    )
    if r.status_code != 200:
        raise ConnectionError(f"后端登录失败: HTTP {r.status_code} {r.text[:200]}")
    body = r.json()
    if body.get("code") != 200 or not body.get("data"):
        raise ConnectionError(f"后端登录被拒绝: {body}")
    return body["data"]


def fetch_spec(base_url: str, token: str, cache_path: Optional[str] = None,
               max_age_sec: int = 3600, timeout: int = 90) -> Dict[str, Any]:
    """
    拉取接口清单。优先 /v2/api-docs（1526+ 路径的权威版本），失败回退 /v3/api-docs。
    结果按文件缓存，避免每次体检都传输 2.9MB。
    """
    if cache_path and os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < max_age_sec:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("paths"):
                    cached["_source"] = cached.get("spec_source", "缓存")
                    cached["_cache_hit"] = True
                    return cached
            except Exception:
                pass

    headers = {"Authorization": f"Bearer {token}"}
    last_err: Optional[Exception] = None
    for doc_path in ("/v2/api-docs", "/v3/api-docs"):
        try:
            r = requests.get(f"{base_url.rstrip('/')}{doc_path}", headers=headers,
                             timeout=timeout, proxies=_SESSION_PROXIES)
            if r.status_code != 200:
                last_err = ConnectionError(f"{doc_path} -> HTTP {r.status_code}")
                continue
            spec = r.json()
            if not spec.get("paths"):
                last_err = ConnectionError(f"{doc_path} 未返回 paths")
                continue
            spec["_source"] = doc_path
            spec["_cache_hit"] = False
            if cache_path:
                try:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    tmp = {k: v for k, v in spec.items() if not k.startswith("_")}
                    tmp["spec_source"] = doc_path
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(tmp, f, ensure_ascii=False)
                except Exception:
                    pass
            return spec
        except Exception as e:  # 网络类异常，换下一个文档地址
            last_err = e
    raise ConnectionError(f"无法获取接口清单: {last_err}")


def spec_fingerprint(spec: Dict[str, Any]) -> str:
    """接口清单指纹：用于跨次比对，新增/消失的接口即回归信号。"""
    paths = sorted(spec.get("paths", {}).keys())
    return hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()[:16]


def classify(method: str, path: str, summary: str = "",
             params: Optional[List[Dict[str, Any]]] = None) -> tuple:
    """
    判定接口是否可安全盲调。返回 (kind, reason)。

    保守策略：只有同时满足"方法安全 + 语义读 + 无必填 body"才算只读。
    """
    method = (method or "GET").upper()
    params = params or []
    blob = f"{path} {summary}".lower()
    segs = _segments(path)
    last = _last_segment(path)

    # 1. 方法层面：非 GET/POST 一律不碰
    if method not in ("GET", "POST"):
        return "MUTATING", f"非 GET/POST 方法({method})，需人工确认"

    # 2. 显式写操作词表优先（路径或摘要命中）
    for tok in MUTATING_TOKENS:
        if re.search(rf"(^|[^a-z]){re.escape(tok)}([^a-z]|$)", blob):
            return "MUTATING", f"命中写操作词 '{tok}'"
    for cn in MUTATING_CN:
        if cn in f"{path} {summary}":
            return "MUTATING", f"命中写操作词 '{cn}'"

    # 3. GET 且未命中写词 → 只读
    if method == "GET":
        return "READ_ONLY", "GET 且非写操作"

    # 4. POST：必须是查询语义，且不能有必填 body
    if last not in READ_TOKENS:
        return "MUTATING", f"POST 末段 '{last}' 非查询语义，保守归为写操作"

    for p in params:
        if p.get("in") == "body" and p.get("required"):
            return "MUTATING", "POST 声明了必填 body，保守归为写操作"

    return "READ_ONLY", f"POST 查询语义 '{last}' 且无必填 body"


def iter_endpoints(spec: Dict[str, Any]) -> List[Endpoint]:
    """把 Swagger paths 展开为 Endpoint 列表（含分类结果）。"""
    out: List[Endpoint] = []
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                continue
            if not isinstance(op, dict):
                continue
            summary = op.get("summary") or op.get("description") or ""
            params = op.get("parameters") or []
            kind, reason = classify(method, path, summary, params)
            out.append(Endpoint(
                method=method.upper(),
                path=path,
                operation_id=op.get("operationId", "") or "",
                summary=summary,
                tags=op.get("tags") or [],
                params=params,
                kind=kind,
                classify_reason=reason,
            ))
    out.sort(key=lambda e: (e.kind, e.path, e.method))
    return out


# ---------------------------------------------------------------------------
# 入参构造
# ---------------------------------------------------------------------------

def _dummy_for_type(t: str, name: str = "", fixtures: Optional[Dict[str, Any]] = None) -> Any:
    """
    按 Swagger 类型给一个尽量合法的占位值。
    注意：这里返回的都是**编造值**，调用方必须据此把失败降级为"无法判定"。
    """
    fixtures = fixtures or {}
    key = (name or "").lower()
    if key in fixtures:
        return fixtures[key]
    for fk, fv in fixtures.items():
        if len(fk) >= 4 and (fk in key or key in fk):
            return fv
    if t in ("integer", "int32", "int64", "long", "number"):
        return 1
    if t in ("boolean", "bool"):
        return False
    if t in ("array",):
        return []
    if t == "string":
        # 空字符串会被后端判为"参数存在但非法"，给一个按语义猜测的非空值
        if any(k in key for k in ("date", "time", "begin", "end", "start", "stop")):
            return "2026-01-01"
        return "1"
    return ""


def fill_schema(schema: Dict[str, Any], spec: Dict[str, Any],
                fixtures: Optional[Dict[str, Any]] = None, depth: int = 0) -> Any:
    """
    依据 Swagger schema 浅层构造一个请求体。
    只填一层对象属性，避免无限展开；$ref 解析有限深度。
    """
    if not isinstance(schema, dict) or depth > 3:
        return {}
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        target = (spec.get("definitions") or {}).get(ref) or \
                 (spec.get("components", {}).get("schemas") or {}).get(ref)
        if isinstance(target, dict):
            return fill_schema(target, spec, fixtures, depth + 1)
        return {}

    stype = schema.get("type")
    if stype == "array":
        item = fill_schema(schema.get("items") or {}, spec, fixtures, depth + 1)
        return [item] if item not in ({}, None) else []
    if stype != "object" and "properties" not in schema:
        return _dummy_for_type(stype or "string", "", fixtures)

    body: Dict[str, Any] = {}
    for prop, pschema in (schema.get("properties") or {}).items():
        body[prop] = fill_schema(pschema if isinstance(pschema, dict) else {},
                                 spec, fixtures, depth + 1)
    return body


def build_request(ep: Endpoint, spec: Dict[str, Any],
                  fixtures: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    为一条接口构造探针请求。返回
    {query, body, path, unresolved, placeholder_used}

    关键约定 —— placeholder_used：
      只要请求里有任何一个值是"我们编的"（不是 fixture 池里的真实数据），
      就置 True。执行器据此把失败降级为"无法判定"而不是"缺陷"，
      避免把探针自身编造的入参造成的报错算成系统故障。

    另外：可选参数默认**不发送**。空字符串会被后端当成"参数存在但非法"而报错，
    这是纯粹的探针噪声。
    """
    fixtures = fixtures or {}
    query: Dict[str, Any] = {}
    body: Any = None
    resolved_path = ep.path
    unresolved: List[str] = []
    placeholder_used = False

    for p in ep.params:
        loc = p.get("in")
        name = p.get("name") or ""
        required = bool(p.get("required"))
        ptype = p.get("type") or "string"

        if loc == "path":
            val, is_ph = _pick_value(ptype, name, fixtures)
            placeholder_used = placeholder_used or is_ph
            resolved_path = resolved_path.replace("{" + name + "}", str(val))

        elif loc == "query":
            val, is_ph = _pick_value(ptype, name, fixtures)
            if is_ph and not required:
                continue          # 可选参数没有真实值时干脆不发，避免"存在但非法"
            query[name] = val
            placeholder_used = placeholder_used or is_ph

        elif loc == "body":
            schema = p.get("schema") or {}
            body, body_ph = _fill_schema_tracked(schema, spec, fixtures)
            placeholder_used = placeholder_used or body_ph
            if body in ({}, [], None) and required:
                unresolved.append("body")

    if body is None and ep.method == "POST":
        body = {}   # 大量 @RequestBody 接口未在 Swagger 声明体，空对象是最小侵入探针

    return {"query": query, "body": body, "path": resolved_path,
            "unresolved": unresolved, "placeholder_used": placeholder_used}


def _pick_value(ptype: str, name: str, fixtures: Dict[str, Any]) -> tuple:
    """取参数值。命中 fixture 池返回真实值(is_ph=False)，否则编一个(is_ph=True)。"""
    key = (name or "").lower()
    if key in fixtures:
        return fixtures[key], False
    for fk, fv in fixtures.items():
        if len(fk) >= 4 and (fk in key or key in fk):
            return fv, False
    return _dummy_for_type(ptype, name, fixtures), True


def _fill_schema_tracked(schema: Dict[str, Any], spec: Dict[str, Any],
                         fixtures: Dict[str, Any], depth: int = 0) -> tuple:
    """fill_schema 的带标记版本：返回 (值, 是否使用了编造值)。"""
    if not isinstance(schema, dict) or depth > 3:
        return {}, False
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        target = (spec.get("definitions") or {}).get(ref) or \
                 (spec.get("components", {}).get("schemas") or {}).get(ref)
        if isinstance(target, dict):
            return _fill_schema_tracked(target, spec, fixtures, depth + 1)
        return {}, False

    stype = schema.get("type")
    if stype == "array":
        item, ph = _fill_schema_tracked(schema.get("items") or {}, spec, fixtures, depth + 1)
        return ([item] if item not in ({}, [], None) else []), ph
    if stype != "object" and "properties" not in schema:
        return _dummy_for_type(stype or "string", "", fixtures), True

    out: Dict[str, Any] = {}
    ph_any = False
    for prop, pschema in (schema.get("properties") or {}).items():
        val, ph = _fill_schema_tracked(pschema if isinstance(pschema, dict) else {},
                                       spec, fixtures, depth + 1)
        key = (prop or "").lower()
        if key in fixtures:
            out[prop] = fixtures[key]
        else:
            out[prop] = val
            ph_any = ph_any or ph
    return out, ph_any
