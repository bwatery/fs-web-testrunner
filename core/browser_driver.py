"""
Browser Driver based on Chrome DevTools Protocol (CDP) over WebSocket.
Requires no external selenium/chromedriver binaries, 100% reliable in LAN/intranet.
"""

import json
import os
import subprocess
import time
import base64
import requests
import websocket
from typing import Any, Dict, Optional, List
from pathlib import Path
from fs_web_testrunner.config import (
    BROWSER_EXECUTABLE,
    CDP_PORT,
    CDP_HOST,
    SCREENSHOTS_DIR
)

NO_PROXY = {"http": None, "https": None}

class DesktopProcess:
    def __init__(self, pid: int, h_process=None, h_thread=None):
        self.pid = pid
        self.h_process = h_process
        self.h_thread = h_thread

    def poll(self) -> Optional[int]:
        if not self.h_process:
            return None
        import ctypes
        from ctypes import wintypes
        exit_code = wintypes.DWORD()
        if ctypes.windll.kernel32.GetExitCodeProcess(self.h_process, ctypes.byref(exit_code)):
            if exit_code.value == 259:  # STILL_ACTIVE
                return None
            return exit_code.value
        return 0

    def terminate(self):
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.pid)], capture_output=True, timeout=3)
        except Exception:
            pass

    def wait(self, timeout=2):
        if self.h_process:
            import ctypes
            ms = int(timeout * 1000)
            ctypes.windll.kernel32.WaitForSingleObject(self.h_process, ms)

def _spawn_process_interactive(cmd_list: List[str]) -> Any:
    """Launch process explicitly on Windows interactive user desktop (WinSta0\\default)."""
    try:
        import ctypes
        from ctypes import wintypes

        class STARTUPINFO(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR),
                ('dwX', wintypes.DWORD),
                ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD),
                ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD),
                ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_char_p),
                ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE),
                ('hStdError', wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('hProcess', wintypes.HANDLE),
                ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD),
            ]

        si = STARTUPINFO()
        si.cb = ctypes.sizeof(STARTUPINFO)
        si.lpDesktop = 'WinSta0\\default'
        si.dwFlags = 1  # STARTF_USESHOWWINDOW
        si.wShowWindow = 3  # SW_SHOWMAXIMIZED
        pi = PROCESS_INFORMATION()

        cmd_str = subprocess.list2cmdline(cmd_list)
        success = ctypes.windll.kernel32.CreateProcessW(
            None, cmd_str, None, None, False, 0, None, None,
            ctypes.byref(si), ctypes.byref(pi)
        )
        if success:
            return DesktopProcess(pi.dwProcessId, pi.hProcess, pi.hThread)
    except Exception:
        pass
    return subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class BrowserDriver:
    def __init__(self, headless: bool = False, user_data_dir: Optional[str] = None):
        self.headless = headless
        self.user_data_dir = user_data_dir or str(Path.home() / ".fs_web_testrunner_profile")
        self.proc: Optional[subprocess.Popen] = None
        self.ws: Optional[websocket.WebSocket] = None
        self._msg_id = 0
        self.target_url: Optional[str] = None
        self.ws_url: Optional[str] = None

    def _kill_existing_cdp(self):
        """Cleanly terminate any existing background processes holding CDP_PORT or testrunner profile."""
        try:
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -like '*fs_web_testrunner_profile*' -or $_.CommandLine -like '*remote-debugging-port={CDP_PORT}*' }} | "
                f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=5)
            time.sleep(0.5)
        except Exception:
            pass

    def _is_existing_headless(self) -> bool:
        try:
            resp = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/version", timeout=1.5, proxies=NO_PROXY)
            if resp.status_code == 200:
                data = resp.json()
                ua = data.get("User-Agent", "").lower()
                b = data.get("Browser", "").lower()
                return "headless" in ua or "headless" in b
        except Exception:
            pass
        return False

    def is_alive(self) -> bool:
        """Check if browser process and CDP connection are still functioning."""
        if not self._check_cdp_alive():
            return False
        if self.proc and self.proc.poll() is not None:
            return False
        if self.ws and not self.ws.connected:
            return False
        return True

    def bring_to_front(self):
        """Bring Chrome window to the absolute front on Windows."""
        try:
            self.send_cdp_command("Page.bringToFront")
        except Exception:
            pass
        try:
            ps_script = """
            $p = Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
            if ($p) {
                $sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'
                Add-Type -MemberDefinition $sig -Name Win32SetFore -Namespace Win32Utils -ErrorAction SilentlyContinue
                [Win32Utils.Win32SetFore]::ShowWindow($p.MainWindowHandle, 3)
                [Win32Utils.Win32SetFore]::SetForegroundWindow($p.MainWindowHandle)
            }
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=2)
        except Exception:
            pass

    def start(self, initial_url: Optional[str] = None) -> bool:
        """Start or connect to Chromium instance."""
        url = initial_url or "about:blank"
        alive = self._check_cdp_alive()

        if alive:
            # Check if current mode (visible vs headless) matches existing instance
            is_headless = self._is_existing_headless()
            if self.headless != is_headless:
                # Mode mismatch: recreate with correct visibility
                self._kill_existing_cdp()
                self._launch_browser(url)
            else:
                # Mode matches: reuse existing running browser window!
                if initial_url:
                    try:
                        self._connect_to_tab()
                        self.navigate(initial_url)
                    except Exception:
                        pass
        else:
            self._kill_existing_cdp()
            self._launch_browser(url)
        
        # Connect to the target tab
        ok = self._connect_to_tab(initial_url)
        if ok and not self.headless:
            self.bring_to_front()
        return ok

    def _check_cdp_alive(self) -> bool:
        try:
            resp = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/version", timeout=1.5, proxies=NO_PROXY)
            return resp.status_code == 200
        except Exception:
            return False

    def _ensure_profile_prefs(self):
        """Disable all Google sign-in prompts, sync promos, and welcome screens."""
        try:
            p = Path(self.user_data_dir)
            d = p / "Default"
            d.mkdir(parents=True, exist_ok=True)
            pref_path = d / "Preferences"
            prefs = {}
            if pref_path.exists():
                try:
                    prefs = json.loads(pref_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            prefs.setdefault("signin", {})["allowed"] = False
            prefs.setdefault("sync_promo", {})["user_skipped"] = True
            prefs.setdefault("sync_promo", {})["show_on_first_run_allowed"] = False
            prefs.setdefault("browser", {})["has_seen_welcome_page"] = True
            pref_path.write_text(json.dumps(prefs), encoding="utf-8")

            ls_path = p / "Local State"
            ls = {}
            if ls_path.exists():
                try:
                    ls = json.loads(ls_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            ls.setdefault("browser", {})["has_seen_welcome_page"] = True
            ls.setdefault("signin", {})["allowed"] = False
            ls_path.write_text(json.dumps(ls), encoding="utf-8")
        except Exception:
            pass

    def _launch_browser(self, initial_url: Optional[str] = None):
        self._ensure_profile_prefs()
        url = initial_url or "http://192.168.1.198:8088/#/login"
        cmd = [
            BROWSER_EXECUTABLE,
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-signin-promo",
            "--disable-features=Translate,OptimizationHints,MediaRouter,DialMediaRouteProvider,ChromeWhatsNewUI,SignInProfileCreationPolicy,IdentityConsistency",
            "--password-store=basic",
            "--new-window",
            "--start-maximized",
            "--window-size=1440,900",
        ]
        if self.headless:
            cmd.extend(["--headless=new", "--disable-gpu"])
        cmd.append(url)

        if not self.headless:
            # Explicitly launch onto user's physical interactive desktop!
            self.proc = _spawn_process_interactive(cmd)
        else:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for CDP endpoint to become ready
        for _ in range(35):
            time.sleep(0.3)
            if self._check_cdp_alive():
                return
        raise RuntimeError(f"Browser failed to start CDP service on port {CDP_PORT}")

    def _connect_to_tab(self, target_url_match: Optional[str] = None) -> bool:
        tabs_resp = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json", timeout=3, proxies=NO_PROXY)
        tabs = tabs_resp.json()
        
        selected_tab = None
        for tab in tabs:
            if tab.get("type") == "page":
                if target_url_match and target_url_match in tab.get("url", ""):
                    selected_tab = tab
                    break
                if not selected_tab:
                    selected_tab = tab

        if not selected_tab:
            # Create a new tab
            new_tab = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/new?{target_url_match or 'about:blank'}", timeout=3, proxies=NO_PROXY).json()
            selected_tab = new_tab

        self.ws_url = selected_tab["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(self.ws_url, timeout=15)
        
        # Enable runtime & page events
        self.send_cdp_command("Runtime.enable")
        self.send_cdp_command("Page.enable")
        return True

    def send_cdp_command(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send command over CDP WebSocket and return result."""
        if not self.ws or not self.ws.connected:
            raise RuntimeError(f"CDP WebSocket 未连接，无法执行 [{method}]")
        self._msg_id += 1
        current_id = self._msg_id
        payload = {
            "id": current_id,
            "method": method,
            "params": params or {}
        }
        try:
            self.ws.send(json.dumps(payload))
        except Exception as e:
            raise RuntimeError(f"CDP WebSocket 发送异常 [{method}]: {e}")
        
        # Receive until matching response ID
        start_time = time.time()
        while time.time() - start_time < 20:
            try:
                raw = self.ws.recv()
            except Exception as e:
                raise RuntimeError(f"CDP WebSocket 接收异常 [{method}]: {e}")
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if data.get("id") == current_id:
                if "error" in data:
                    raise RuntimeError(f"CDP Error [{method}]: {data['error'].get('message')}")
                return data.get("result", {})
        raise TimeoutError(f"CDP Command {method} timed out waiting for reply")

    def navigate(self, url: str):
        """Navigate to URL and wait briefly."""
        self.send_cdp_command("Page.navigate", {"url": url})
        time.sleep(2.0)

    def evaluate(self, js_expression: str) -> Any:
        """Evaluate JS in page context and return parsed value."""
        result = self.send_cdp_command("Runtime.evaluate", {
            "expression": js_expression,
            "awaitPromise": True,
            "returnByValue": True
        })
        val = result.get("result", {})
        if "value" in val:
            return val["value"]
        if val.get("type") == "undefined":
            return None
        return val

    def get_current_url(self) -> str:
        return self.evaluate("window.location.href") or ""

    def take_screenshot(self, filename_prefix: str = "shot") -> str:
        """Capture screenshot and save to disk, returns file path."""
        res = self.send_cdp_command("Page.captureScreenshot", {"format": "png"})
        img_b64 = res.get("data", "")
        file_path = SCREENSHOTS_DIR / f"{filename_prefix}_{int(time.time()*1000)}.png"
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        return str(file_path)

    def get_screenshot_base64(self) -> str:
        """Capture screenshot and return base64 string directly for web streaming."""
        res = self.send_cdp_command("Page.captureScreenshot", {"format": "jpeg", "quality": 75})
        return res.get("data", "")

    def close(self):
        """Clean up connection and browser process tree."""
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.ws = None

        if self.proc:
            try:
                # Forcefully terminate entire process tree on Windows
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True, timeout=3)
            except Exception:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
            self.proc = None
