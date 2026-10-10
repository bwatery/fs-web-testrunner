# -*- coding: utf-8 -*-
"""
fs_runner.cases.ui_probe
========================
界面巡检探测与自建 CDP 浏览器驱动。
完全独立于旧 core/browser_driver.py，不引入任何旧引擎副作用。
"""
import base64
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import websocket

from ..config import CDP_HOST, CDP_PORT, REPORTS_DIR

_NO_PROXY = {"http": None, "https": None}


class CDPBrowserDriver:
    """自建带 CDP 协议的浏览器驱动（针对 Chrome/Edge DevTools 协议）。"""

    def __init__(self, headless: bool = False, host: str = CDP_HOST, port: int = CDP_PORT):
        self.headless = headless
        self.host = host
        self.port = port
        self.ws: Optional[websocket.WebSocket] = None
        self._msg_id = 0
        self.proc: Optional[subprocess.Popen] = None

    def _check_alive(self) -> bool:
        try:
            r = requests.get(f"http://{self.host}:{self.port}/json/version", timeout=1.5, proxies=_NO_PROXY)
            return r.status_code == 200
        except Exception:
            return False

    def is_alive(self) -> bool:
        return self._check_alive() and (self.ws is not None and self.ws.connected)

    def _find_browser_exe(self) -> str:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "chrome"

    def _launch_browser(self, url: str) -> None:
        exe = self._find_browser_exe()
        user_data = os.path.expandvars(r"%USERPROFILE%\.fs_web_testrunner_profile")
        cmd = [
            exe,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--start-maximized",
        ]
        if self.headless:
            cmd.extend(["--headless=new", "--disable-gpu"])
        cmd.append(url)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            time.sleep(0.3)
            if self._check_alive():
                return
        raise RuntimeError(f"无法在端口 {self.port} 启动 Chrome 调试服务")

    def _connect_tab(self, target_url: Optional[str] = None) -> bool:
        resp = requests.get(f"http://{self.host}:{self.port}/json", timeout=3, proxies=_NO_PROXY)
        tabs = resp.json()
        selected = next((t for t in tabs if t.get("type") == "page"), None)
        if not selected:
            new_tab = requests.get(f"http://{self.host}:{self.port}/json/new?{target_url or 'about:blank'}", timeout=3, proxies=_NO_PROXY).json()
            selected = new_tab

        ws_url = selected["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.send_cdp_command("Runtime.enable")
        self.send_cdp_command("Page.enable")
        self.send_cdp_command("Network.enable")
        return True

    def start(self, initial_url: Optional[str] = None) -> bool:
        url = initial_url or "about:blank"
        if not self._check_alive():
            self._launch_browser(url)
        ok = self._connect_tab(url)
        if ok and initial_url:
            self.send_cdp_command("Page.navigate", {"url": initial_url})
        return ok

    def send_cdp_command(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 20.0) -> Dict[str, Any]:
        if not self.ws:
            raise RuntimeError("CDP WebSocket 未连接")
        self._msg_id += 1
        mid = self._msg_id
        payload = {"id": mid, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method} error: {msg['error'].get('message')}")
                return msg.get("result", {})
        raise TimeoutError(f"CDP {method} 超时")

    def evaluate(self, expr: str) -> Any:
        res = self.send_cdp_command("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val_obj = res.get("result", {})
        return val_obj.get("value")

    def take_screenshot(self, prefix: str = "shot") -> Optional[str]:
        try:
            res = self.send_cdp_command("Page.captureScreenshot", {"format": "png"})
            b64_data = res.get("data")
            if not b64_data:
                return None
            shots_dir = Path(REPORTS_DIR) / "screenshots" / "uiwalk"
            shots_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prefix}_{int(time.time() * 1000)}.png"
            out_file = shots_dir / filename
            out_file.write_bytes(base64.b64decode(b64_data))
            return str(out_file)
        except Exception:
            return None


def run_ui_probe() -> List[Dict[str, Any]]:
    """执行 UI 页面巡检。"""
    return []
