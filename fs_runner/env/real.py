# -*- coding: utf-8 -*-
"""
fs_runner.env.real
==================
内网真实环境：直连网关与 Oracle，全套件唯一能产出「通过」的环境。
"""
from typing import Any, Dict, Tuple
from .base import BaseEnv
from ..config import GATEWAY_URL, ORACLE_CONFIG


class RealEnv(BaseEnv):
    """真实内网环境。"""

    name: str = "real"

    def is_real(self) -> bool:
        return True

    def can_connect_oracle(self) -> bool:
        try:
            import oracledb
            conn = oracledb.connect(
                user=ORACLE_CONFIG["user"],
                password=ORACLE_CONFIG["password"],
                dsn=ORACLE_CONFIG["dsn"],
            )
            conn.close()
            return True
        except Exception:
            return False

    def can_connect_gateway(self) -> bool:
        try:
            import requests
            r = requests.get(f"{GATEWAY_URL}/login", timeout=5, proxies={"http": None, "https": None})
            return r.status_code in (200, 400, 401, 405)
        except Exception:
            return False

    def filter_result_status(self, raw_status: str, note: str = "") -> Tuple[str, str]:
        """真实环境保留原样状态与说明。"""
        return raw_status, note

    def wrap_evidence(self, evidence: Any) -> Dict[str, Any]:
        """在 evidence 中注入 env='real'。"""
        if isinstance(evidence, dict):
            res = dict(evidence)
        elif evidence is None:
            res = {}
        else:
            res = {"data": evidence}
        res["env"] = "real"
        return res
