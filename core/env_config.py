"""
FS Web TestRunner - Target Environment & Dynamic Configuration Manager
Provides persistent, manually editable target environment settings (Frontend, Gateway, Oracle, Workstations)
and configurable Offline Sandbox Adaptive Strategies (Option A: MOCK_PASS vs Option B: SKIP_INVASIVE).
"""

import json
import os
import socket
import time
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import requests

from fs_web_testrunner.core.logger import get_logger

logger = get_logger("env_config")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_FILE = DATA_DIR / "environment_config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "active_preset": "hospital_live",
    "mode": "AUTO",  # "AUTO", "LIVE", "MOCK"
    # Adaptive strategy for invasive (UI) tests when running offline/sandbox:
    # "ADAPTIVE_MOCK" = Option A (沙盒自适应通过: 模拟DOM与规范契约校验, 标记为 PASSED)
    # "SKIP_INVASIVE" = Option B (沙盒自适应跳过: 自动安全跳过现场实测项, 标记为 SKIPPED)
    # "STRICT"        = 严格模式 (报错并截屏)
    "offline_adaptive_strategy": "ADAPTIVE_MOCK",
    "frontend_base_url": "http://192.168.1.198:8088",
    "api_gateway_url": "http://192.168.1.198:8081",
    "emr_designer_url": "http://192.168.1.198:8088/#/emr/templatesrecords/emrDesigner",
    "oracle": {
        "host": "192.168.1.199",
        "port": 1521,
        "service_name": "orcl",
        "user": "his_test",
        "password": "his_test123"
    },
    "workstations": {
        "inpatient_doctor": {
            "name": "住院工作站",
            "code": "INPATIENT_DOCTOR",
            "url": "http://192.168.1.198:8088/#/inpatient/doctor/workstation",
            "route": "/#/inpatient/doctor/workstation",
            "desc": "在院患者管理、开立长临医嘱、诊断下达、电子病历书写与出院带药"
        },
        "outpatient_doctor": {
            "name": "门诊工作站",
            "code": "OUTPATIENT_DOCTOR",
            "url": "http://192.168.1.198:8088/#/outpatient/doctor",
            "route": "/#/outpatient/doctor",
            "desc": "门诊接诊排队、门诊电子病历、西药草药处方开立与检验检查申请"
        },
        "pharmacy": {
            "name": "药房工作站",
            "code": "PHARMACY",
            "url": "http://192.168.1.198:8088/#/pharmacy/inpatient",
            "route": "/#/pharmacy/inpatient",
            "desc": "处方合理用药审核、门诊窗口发药、病区自动摆药、退药冲正与库存盘点"
        },
        "outpatient_billing": {
            "name": "门诊收费工作站",
            "code": "OUTPATIENT_BILLING",
            "url": "http://192.168.1.198:8088/#/outpatient/charge",
            "route": "/#/outpatient/charge",
            "desc": "门诊建档挂号、处方划价预结算、医保统筹自费拆分、门诊退费与日结"
        },
        "inpatient_billing": {
            "name": "住院收费工作站",
            "code": "INPATIENT_BILLING",
            "url": "http://192.168.1.198:8088/#/inpatient/settlement",
            "route": "/#/inpatient/settlement",
            "desc": "入院登记押金、住院一日清单穿透、欠费催缴预警、出院多渠道结算分解"
        },
        "inpatient_nurse": {
            "name": "住院护士工作站",
            "code": "INPATIENT_NURSE",
            "url": "http://192.168.1.198:8088/#/inpatient/nurse",
            "route": "/#/inpatient/nurse",
            "desc": "床位分配腕带打印、医嘱校对与执行、体温三测单批量录入、护理评估单"
        }
    },
    "presets": {
        "hospital_live": {
            "label": "医院现场正式环境 (192.168.1.198)",
            "frontend_base_url": "http://192.168.1.198:8088",
            "api_gateway_url": "http://192.168.1.198:8081",
            "emr_designer_url": "http://192.168.1.198:8088/#/emr/templatesrecords/emrDesigner",
            "oracle_host": "192.168.1.199",
            "oracle_port": 1521,
            "oracle_service": "orcl",
            "mode": "AUTO"
        },
        "local_mock": {
            "label": "本地离线沙盒环境 (127.0.0.1)",
            "frontend_base_url": "http://127.0.0.1:8989",
            "api_gateway_url": "http://127.0.0.1:8989/mock-api",
            "emr_designer_url": "http://127.0.0.1:8989/static/index.html",
            "oracle_host": "127.0.0.1",
            "oracle_port": 1521,
            "oracle_service": "mock_orcl",
            "mode": "MOCK"
        },
        "custom": {
            "label": "自定义手动配置环境",
            "frontend_base_url": "http://127.0.0.1:8088",
            "api_gateway_url": "http://127.0.0.1:8081",
            "emr_designer_url": "http://127.0.0.1:8088/#/emr/templatesrecords/emrDesigner",
            "oracle_host": "127.0.0.1",
            "oracle_port": 1521,
            "oracle_service": "orcl",
            "mode": "AUTO"
        }
    }
}

class EnvironmentConfigManager:
    """Singleton manager for target environment configuration."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EnvironmentConfigManager, cls).__new__(cls)
            cls._instance._config = cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> Dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            self._save_config_file(DEFAULT_CONFIG)
            return json.loads(json.dumps(DEFAULT_CONFIG))
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # Merge saved onto default so new fields won't be lost
                merged = json.loads(json.dumps(DEFAULT_CONFIG))
                merged.update(saved)
                return merged
        except Exception as e:
            logger.error(f"Failed to load environment config from {CONFIG_FILE}: {e}")
            return json.loads(json.dumps(DEFAULT_CONFIG))

    def _save_config_file(self, conf: Dict[str, Any]):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(conf, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save environment config to {CONFIG_FILE}: {e}")

    def get_config(self) -> Dict[str, Any]:
        return self._config

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configurations, persist, and refresh dynamic workstation paths."""
        for k, v in updates.items():
            if k in self._config:
                if isinstance(v, dict) and isinstance(self._config[k], dict):
                    self._config[k].update(v)
                else:
                    self._config[k] = v
            else:
                self._config[k] = v

        # Re-derive workstation URLs if frontend_base_url changed
        frontend = self._config.get("frontend_base_url", "http://192.168.1.198:8088").rstrip("/")
        workstations = self._config.get("workstations", {})
        for wk, wdata in workstations.items():
            route = wdata.get("route", "")
            if route and not wdata.get("custom_override", False):
                wdata["url"] = f"{frontend}{route}"

        self._save_config_file(self._config)
        logger.info(f"Target environment config updated: strategy={self._config.get('offline_adaptive_strategy')}, frontend={frontend}")
        return self._config

    def set_adaptive_strategy(self, strategy: str) -> str:
        """Set offline adaptive strategy: 'ADAPTIVE_MOCK' (Option A), 'SKIP_INVASIVE' (Option B), 'STRICT'."""
        if strategy not in ("ADAPTIVE_MOCK", "SKIP_INVASIVE", "STRICT"):
            strategy = "ADAPTIVE_MOCK"
        self._config["offline_adaptive_strategy"] = strategy
        self._save_config_file(self._config)
        logger.info(f"Offline adaptive strategy switched to: {strategy}")
        return strategy

    def get_adaptive_strategy(self) -> str:
        return self._config.get("offline_adaptive_strategy", "ADAPTIVE_MOCK")

    def get_frontend_url(self) -> str:
        return self._config.get("frontend_base_url", "http://192.168.1.198:8088")

    def get_api_gateway_url(self) -> str:
        return self._config.get("api_gateway_url", "http://192.168.1.198:8081")

    def get_emr_designer_url(self) -> str:
        return self._config.get("emr_designer_url", "http://192.168.1.198:8088/#/emr/templatesrecords/emrDesigner")

    def get_workstation_url(self, code_or_key: str) -> str:
        ws = self._config.get("workstations", {})
        # by key
        if code_or_key in ws:
            return ws[code_or_key].get("url", self.get_frontend_url())
        # by code
        for k, v in ws.items():
            if v.get("code") == code_or_key or v.get("name") == code_or_key:
                return v.get("url", self.get_frontend_url())
        return self.get_frontend_url()

    def test_connectivity(self, target_type: str = "api_gateway", custom_target: Optional[str] = None) -> Dict[str, Any]:
        """Test network reachability and HTTP latency of target."""
        start_t = time.time()
        url_to_test = custom_target
        if not url_to_test:
            if target_type == "frontend":
                url_to_test = self.get_frontend_url()
            elif target_type == "api_gateway":
                url_to_test = self.get_api_gateway_url()
            elif target_type == "oracle":
                host = self._config.get("oracle", {}).get("host", "192.168.1.199")
                port = int(self._config.get("oracle", {}).get("port", 1521))
                try:
                    s = socket.create_connection((host, port), timeout=1.0)
                    s.close()
                    elapsed = round((time.time() - start_t) * 1000, 1)
                    return {"target": f"{host}:{port}", "reachable": True, "latency_ms": elapsed, "status": "CONNECTED"}
                except Exception as e:
                    elapsed = round((time.time() - start_t) * 1000, 1)
                    return {"target": f"{host}:{port}", "reachable": False, "latency_ms": elapsed, "error": str(e), "status": "UNREACHABLE"}

        if not url_to_test:
            url_to_test = self.get_api_gateway_url()

        parsed = urlparse(url_to_test)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # 1. Socket check
        socket_ok = False
        try:
            s = socket.create_connection((host, port), timeout=1.0)
            s.close()
            socket_ok = True
        except Exception as e:
            socket_ok = False

        if not socket_ok:
            elapsed = round((time.time() - start_t) * 1000, 1)
            return {"target": url_to_test, "host": host, "port": port, "reachable": False, "latency_ms": elapsed, "status": "UNREACHABLE"}

        # 2. HTTP check
        try:
            r = requests.get(url_to_test, timeout=1.5)
            elapsed = round((time.time() - start_t) * 1000, 1)
            return {"target": url_to_test, "reachable": True, "http_status": r.status_code, "latency_ms": elapsed, "status": "ONLINE"}
        except Exception as e:
            elapsed = round((time.time() - start_t) * 1000, 1)
            return {"target": url_to_test, "reachable": True, "http_status": None, "latency_ms": elapsed, "status": "PORT_OPEN"}

env_config = EnvironmentConfigManager()
