# -*- coding: utf-8 -*-
"""
fs_runner.env.sandbox
=====================
隔离沙盒环境：只验接口参数形状（不连库、不连业务）。
⚠️ 强制约束：沙盒环境永远不能产出「通过」，只能产出「未执行」，
备注写明"沙盒模式：仅校验接口参数形状，未验证业务"。
绝不采用替换 requests/oracledb 等全局 monkey-patch 手段。
"""
from typing import Any, Dict, List, Optional, Tuple
from .base import BaseEnv


class SandboxEnv(BaseEnv):
    """
    隔离沙盒环境（只验参数形状，永不产出「通过」）。
    - 绝不连库（can_connect_oracle 恒为 False）
    - 显式声明模式，不进行任何全局 monkey-patch
    - 强制门禁：沙盒模式绝不产出「通过」，全部映射为「未执行」
    """

    name: str = "sandbox"

    def is_real(self) -> bool:
        return False

    def can_connect_oracle(self) -> bool:
        # 显式拒绝数据库连接，沙盒不连库
        return False

    def can_connect_gateway(self) -> bool:
        # 沙盒不依赖内网环境
        return False

    def filter_result_status(self, raw_status: str, note: str = "") -> Tuple[str, str]:
        """
        强制门禁：沙盒环境永远不能产出「通过」、「失败」或「阻塞」。
        沙盒环境下允许出现的状态只有两个：「跳过」与「未执行」。
        除了「跳过」保留原状态与原因外，其余所有状态一律映射为「未执行」，并注明沙盒说明。
        """
        if raw_status in ("跳过", "SKIPPED"):
            return "跳过", note
        fallback_note = note if ("沙盒模式" in note) else f"沙盒模式：未连接数据库，无法验证业务 (原状态: {raw_status})"
        return "未执行", fallback_note

    def wrap_evidence(self, evidence: Any) -> Dict[str, Any]:
        """在 evidence 中注入 env='sandbox'。"""
        if isinstance(evidence, dict):
            res = dict(evidence)
        elif evidence is None:
            res = {}
        else:
            res = {"data": evidence}
        res["env"] = "sandbox"
        res["sandbox_mode"] = "param_shape_only"
        return res

    def validate_api_shape(
        self,
        spec: Dict[str, Any],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        仅按 Swagger / OpenAPI 规格进行接口参数形状校验（不连库、不连业务）。
        每条记录返回参数形状合法性判定，绝不产出「通过」。
        """
        results: List[Dict[str, Any]] = []
        paths = spec.get("paths", {})
        count = 0
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch"):
                    continue
                if not isinstance(op, dict):
                    continue

                count += 1
                if limit and count > limit:
                    break

                tag = (op.get("tags") or ["未分类"])[0]
                summary = (op.get("summary") or "").replace("\n", " ").strip()
                params = op.get("parameters") or []

                param_defects = []
                for p in params:
                    if not isinstance(p, dict):
                        param_defects.append("参数声明非合法对象")
                        continue
                    if "name" not in p:
                        param_defects.append("缺少参数名 name")
                    if "in" not in p:
                        param_defects.append(f"参数 {p.get('name')} 缺少 in 位置声明")

                if param_defects:
                    bucket = "DEFECT"
                    status = "异常"
                    detail = f"参数规格不合规: {'; '.join(param_defects)}"
                else:
                    bucket = "UNVERIFIED"
                    status = "未执行"
                    detail = "沙盒模式：仅校验接口参数形状，未验证业务"

                results.append({
                    "method": method.upper(),
                    "path": path,
                    "tag": tag,
                    "summary": summary,
                    "kind": "READ_ONLY" if method.lower() == "get" else "MUTATING",
                    "bucket": bucket,
                    "status": status,
                    "detail": detail,
                    "note": detail,
                    "duration_ms": 0.1,
                    "evidence": {
                        "env": "sandbox",
                        "params_count": len(params),
                        "has_body": bool(op.get("requestBody") or any(p.get("in") == "body" for p in params if isinstance(p, dict))),
                        "schema_checked": True,
                        "sandbox_mode": "schema_shape_only",
                    },
                })
            if limit and count > limit:
                break
        return results
