# -*- coding: utf-8 -*-
"""
fs_runner.config
================
环境、凭据与配置管理。
仅提供 real 与 sandbox 两种有效环境模式，不保留废弃的 AUTO/ADAPTIVE_MOCK。
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
VERIFY_DIR = REPORTS_DIR / "verify"

GATEWAY_URL = os.environ.get("FS_GATEWAY_URL", "http://192.168.1.198:8081")
FRONTEND_URL = os.environ.get("FS_FRONTEND_URL", "http://192.168.1.198:8088")
EMR_API_URL = os.environ.get("FS_EMR_API_URL", "http://192.168.1.198:8021")

CDP_HOST = os.environ.get("FS_CDP_HOST", "127.0.0.1")
CDP_PORT = int(os.environ.get("FS_CDP_PORT", "9222"))

ORACLE_CONFIG: Dict[str, Any] = {
    "user": "xchis",
    "password": "xchis",
    "host": "192.168.1.199",
    "port": 1521,
    "service_name": "orcl",
    "dsn": "192.168.1.199:1521/orcl",
}


class _EnvConfigCompat:
    """兼容原 core/env_config.py 常用读取接口，零副作用。"""

    def get_frontend_url(self) -> str:
        return FRONTEND_URL

    def get_api_gateway_url(self) -> str:
        return GATEWAY_URL

    def get_emr_designer_url(self) -> str:
        return f"{FRONTEND_URL}/#/emrDesigner"

    def get_config(self) -> Dict[str, Any]:
        return {
            "gateway_url": GATEWAY_URL,
            "frontend_url": FRONTEND_URL,
            "emr_api_url": EMR_API_URL,
            "oracle": ORACLE_CONFIG,
        }


env_config = _EnvConfigCompat()
