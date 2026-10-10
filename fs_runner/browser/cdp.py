# -*- coding: utf-8 -*-
"""
fs_runner.browser.cdp
=====================
自建 CDP 客户端实现（无第三方 Selenium/Playwright 依赖）：
1. 窗口模式 (--windowed): 直连 9222 端口运行中的 Chrome，点菜单时屏幕可见。
2. 无头模式 (--headless): 自动寻找系统 Chrome 并拉起带 --headless=new 的独立实例。
3. 严格遵循门禁要求：起不来/连不上立即抛出明确异常，绝不静默降级为冒烟或伪通过。
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import websocket

_CHROME_CANDIDATE_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome_executable() -> Optional[str]:
    """寻找本地 Chrome/Edge 浏览器可执行文件。"""
    env_p = os.environ.get("CHROME_PATH")
    if env_p and Path(env_p).is_file():
        return env_p
    for p in _CHROME_CANDIDATE_PATHS:
        if Path(p).is_file():
            return p
    for cmd in ("chrome.exe", "chrome", "google-chrome", "msedge.exe"):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def get_free_tcp_port() -> int:
    """获取一个空闲的 TCP 端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class BrowserSession:
    """自建 CDP 客户端会话，管理通信协议与浏览器生命周期。"""

    def __init__(
        self,
        headless: bool = True,
        port: int = 9222,
        host: str = "127.0.0.1",
        timeout: float = 20.0,
        standalone: bool = False,
    ):
        self.headless = headless
        self.standalone = standalone
        self.port = port
        self.host = host
        self.default_timeout = timeout

        self.proc: Optional[subprocess.Popen] = None
        self.temp_user_data_dir: Optional[str] = None
        self.ws: Optional[websocket.WebSocket] = None
        self._id = 0
        self.events: List[Dict[str, Any]] = []
        self.history_events: List[Dict[str, Any]] = []
        self._connected = False

    def start(self) -> "BrowserSession":
        """启动浏览器或连接到已有实例。"""
        if self._connected:
            return self

        if self.headless or self.standalone:
            # 1. 独立新实例：无头模式 或 独立可见窗口模式（不占用用户自己的 9222 端口）
            chrome_bin = find_chrome_executable()
            if not chrome_bin:
                raise RuntimeError(
                    "【浏览器启动失败】未在系统中找到 Chrome/Edge 可执行文件，"
                    "请安装 Chrome 或设置环境变量 CHROME_PATH。"
                )

            self.port = get_free_tcp_port()
            pfx = "fs_chrome_headless_" if self.headless else "fs_chrome_visible_"
            self.temp_user_data_dir = tempfile.mkdtemp(prefix=pfx)

            args = [
                chrome_bin,
                f"--remote-debugging-port={self.port}",
                "--remote-allow-origins=*",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={self.temp_user_data_dir}",
                "--window-size=1600,1050",
                "--disable-background-networking",
                "about:blank",
            ]
            if self.headless:
                args.append("--headless=new")
            else:
                args.append("--window-position=60,60")

            try:
                self.proc = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                self.close()
                mode_str = "Headless Chrome" if self.headless else "独立可见 Chrome"
                raise RuntimeError(f"【浏览器启动失败】拉起 {mode_str} 进程失败: {e}")

            # 等待调试端口就绪（最多等待 8 秒）
            ready = False
            deadline = time.time() + 8.0
            while time.time() < deadline:
                try:
                    r = requests.get(
                        f"http://{self.host}:{self.port}/json/version",
                        timeout=1.0,
                        proxies={"http": None, "https": None},
                    )
                    if r.status_code == 200:
                        ready = True
                        break
                except Exception:
                    time.sleep(0.3)

            if not ready:
                self.close()
                mode_str = "Headless Chrome" if self.headless else "独立可见 Chrome"
                raise RuntimeError(
                    f"【浏览器启动失败】{mode_str} 未能在 8 秒内开启 CDP 端口 {self.port}。"
                )

        else:
            # 2. 窗口模式：连接正开着的 Chrome(9222)
            try:
                r = requests.get(
                    f"http://{self.host}:{self.port}/json/version",
                    timeout=2.0,
                    proxies={"http": None, "https": None},
                )
                if r.status_code != 200:
                    raise RuntimeError("状态码异常")
            except Exception as e:
                raise RuntimeError(
                    f"【浏览器连接失败】无法连接到运行中的 Chrome 窗口 (http://{self.host}:{self.port})。\n"
                    f"请确认 Chrome 已携带 `--remote-debugging-port={self.port}` 参数启动。\n"
                    f"（硬约束：绝不静默降级为无头或伪通过）"
                )

        # 3. 建立 WebSocket CDP 连接
        try:
            tabs_url = f"http://{self.host}:{self.port}/json"
            tabs = requests.get(tabs_url, timeout=4, proxies={"http": None, "https": None}).json()
            page = next((t for t in tabs if t.get("type") == "page"), None)
            if not page:
                # 若无 page 标签页，创建一个
                new_tab = requests.put(
                    f"http://{self.host}:{self.port}/json/new",
                    timeout=4,
                    proxies={"http": None, "https": None},
                ).json()
                ws_url = new_tab.get("webSocketDebuggerUrl")
            else:
                ws_url = page.get("webSocketDebuggerUrl")

            if not ws_url:
                raise RuntimeError("未能从 Chrome 获取有效 webSocketDebuggerUrl")

            self.ws = websocket.create_connection(ws_url, timeout=self.default_timeout)
            self._connected = True

            # 激活必备 CDP 域
            self.cmd("Runtime.enable")
            self.cmd("Page.enable")
            self.cmd("Network.enable")
            self.cmd("DOM.enable")
            try:
                self.cmd("Log.enable")
            except Exception:
                pass

        except Exception as e:
            self.close()
            mode_desc = "Headless 实例" if self.headless else "Windowed 窗口"
            raise RuntimeError(f"【CDP 连接建立失败】连接 {mode_desc} 失败: {e}")

        return self

    def cmd(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """向 CDP 发送命令并阻塞等待对应的结果（同时缓冲异步事件）。"""
        if not self.ws:
            raise RuntimeError("浏览器 WebSocket 尚未建立连接")

        self._id += 1
        mid = self._id
        payload = {"id": mid, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))

        wait_limit = timeout or self.default_timeout
        deadline = time.time() + wait_limit

        while time.time() < deadline:
            raw = self.ws.recv()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            # 匹配到当前命令返回
            if msg.get("id") == mid:
                if "error" in msg:
                    err_msg = msg["error"].get("message", "未知错误")
                    raise RuntimeError(f"CDP 命令 [{method}] 执行失败: {err_msg}")
                return msg.get("result", {})

            # 异步事件入缓冲池
            if "method" in msg:
                self.events.append(msg)
                self.history_events.append(msg)

        raise TimeoutError(f"CDP 命令 [{method}] 在 {wait_limit} 秒内超时未响应")

    def drain(self, timeout: float = 0.8) -> List[Dict[str, Any]]:
        """消费当前缓冲池中的全部异步事件，并持续吸收后续事件。"""
        if not self.ws:
            return []
        end = time.time() + timeout
        self.ws.settimeout(0.2)
        try:
            while time.time() < end:
                try:
                    raw = self.ws.recv()
                    if raw:
                        msg = json.loads(raw)
                        if "method" in msg:
                            self.events.append(msg)
                            self.history_events.append(msg)
                except Exception:
                    continue
        finally:
            self.ws.settimeout(self.default_timeout)

        out, self.events = list(self.events), []
        return out

    def eval(self, expr: str, timeout: float = 15.0) -> Any:
        """在页面环境中执行 JS 表达式并返回求值结果。"""
        res = self.cmd(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout,
        )
        val_obj = res.get("result", {})
        if "value" in val_obj:
            return val_obj["value"]
        if "description" in val_obj:
            return val_obj["description"]
        return None

    def navigate(self, url: str, wait_sec: float = 2.0):
        """控制浏览器导航到目标 URL，并等待初始加载。"""
        self.cmd("Page.navigate", {"url": url})
        time.sleep(wait_sec)
        self.drain(0.4)

    def reload(self, ignore_cache: bool = True, wait_sec: float = 2.0):
        """强制重载当前页面（解决 Vue 3 hash 跳转不重新挂载组件的坑）。"""
        self.cmd("Page.reload", {"ignoreCache": ignore_cache})
        time.sleep(wait_sec)
        self.drain(0.4)

    def screenshot(self, save_path: Union[str, Path]) -> str:
        """抓取当前视口截图并落盘为 PNG 文件，返回绝对路径。"""
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        res = self.cmd("Page.captureScreenshot", {"format": "png"})
        b64_data = res.get("data")
        if not b64_data:
            raise RuntimeError("CDP Page.captureScreenshot 返回空数据")
        raw_bytes = base64.b64decode(b64_data)
        p.write_bytes(raw_bytes)
        return str(p.resolve())

    def is_alive(self) -> bool:
        """检查浏览器会话是否健康存活。"""
        if not self._connected or not self.ws:
            return False
        try:
            v = self.eval("1 + 1", timeout=2.0)
            return v == 2
        except Exception:
            return False

    def close(self):
        """安全释放 CDP 客户端与浏览器进程。"""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

        self._connected = False

        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

        if self.temp_user_data_dir and Path(self.temp_user_data_dir).exists():
            try:
                shutil.rmtree(self.temp_user_data_dir, ignore_errors=True)
            except Exception:
                pass
            self.temp_user_data_dir = None

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def launch_browser(
    headless: bool = True,
    port: int = 9222,
    host: str = "127.0.0.1",
    standalone: bool = False,
) -> BrowserSession:
    """便捷工厂函数：创建并启动 BrowserSession。"""
    session = BrowserSession(headless=headless, port=port, host=host, standalone=standalone)
    return session.start()
