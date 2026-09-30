"""
Test Engine & Runner.
Supports dual-mode test execution:
1. INVASIVE (侵入式·视觉观察):
   - Designed for human user inspection.
   - Operates visible Chrome browser, clicks UI buttons, navigates routes, triggers dialogs, takes live screenshots.
2. NON_INVASIVE (非侵入式·AI静默验证):
   - Designed for AI rapid automated verification of newly written or refactored code.
   - Zero frontend interference, zero window focus disruption.
   - Tests backend REST APIs, Oracle DB persistence, mathematical rules, XML schema, and data models.
"""

import time
import traceback
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from fs_web_testrunner.core.browser_driver import BrowserDriver
from fs_web_testrunner.core.fswriter_api import FSWriterAPI
from fs_web_testrunner.config import EMR_DESIGNER_URL, REPORTS_DIR, SCREENSHOTS_DIR

@dataclass
class TestCaseResult:
    test_id: str
    name: str
    category: str
    mode: str = "NON_INVASIVE"  # "INVASIVE" or "NON_INVASIVE"
    status: str = "PENDING"     # PENDING, RUNNING, PASSED, FAILED, SKIPPED
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: float = 0.0
    screenshot_path: Optional[str] = None
    screenshot_b64: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    xml_snapshot: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

class TestEngine:
    def __init__(self, headless: bool = False, login_mode: str = "B", username: str = "", password: str = ""):
        self.headless = headless
        self.login_mode = login_mode  # "A" (Auto) or "B" (Manual)
        self.username = username
        self.password = password
        self.browser: Optional[BrowserDriver] = None
        self.writer: Optional[FSWriterAPI] = None
        self.registry: Dict[str, Dict[str, Any]] = {}
        self.results: List[TestCaseResult] = []
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._is_running = False

    def register(self, test_id: str, name: str, category: str, func: Callable, mode: str = "INVASIVE", description: str = ""):
        """Register a test case function with explicit mode (INVASIVE / NON_INVASIVE). Default is INVASIVE."""
        self.registry[test_id] = {
            "id": test_id,
            "name": name,
            "category": category,
            "func": func,
            "mode": mode.upper(),
            "description": description
        }

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to real-time events (for Web Dashboard / WebSocket)."""
        self.listeners.append(callback)

    def _broadcast(self, event_type: str, data: Dict[str, Any]):
        msg = {"type": event_type, "timestamp": time.time(), "data": data}
        for listener in self.listeners:
            try:
                listener(msg)
            except Exception:
                pass

    def log(self, current_result: Optional[TestCaseResult], message: str, level: str = "INFO"):
        formatted = f"[{time.strftime('%H:%M:%S')}] [{level}] {message}"
        if current_result:
            current_result.logs.append(formatted)
        self._broadcast("LOG", {"level": level, "message": formatted})
        print(formatted)

    def init_environment(self, url: Optional[str] = None) -> bool:
        """Start browser and prepare FSWriter instance for invasive UI testing."""
        from fs_web_testrunner.core.offline_sandbox import get_environment_status
        is_mock = get_environment_status().get("is_mock", False)

        target_url = url or EMR_DESIGNER_URL
        if is_mock and ("192.168.1.198" in str(target_url)):
            target_url = "http://127.0.0.1:8989/static/index.html"

        if not self.browser or not self.browser.is_alive():
            self.log(None, f"启动浏览器 (Headless={self.headless}, 登录模式={self.login_mode})...")
            self.browser = BrowserDriver(headless=self.headless)
            self.browser.start(target_url)
        else:
            self.log(None, "复用当前活跃浏览器会话...")
            if not self.headless:
                self.browser.bring_to_front()
            if target_url:
                try:
                    self.browser.navigate(target_url)
                except Exception:
                    pass

        self.writer = FSWriterAPI(self.browser)
        
        # Authenticate using Option A or Option B
        from fs_web_testrunner.core.auth_manager import AuthManager
        from fs_web_testrunner.config import DEFAULT_USERNAME, DEFAULT_PASSWORD
        auth = AuthManager(self.browser, self)
        auth_ok = auth.ensure_authenticated(
            mode=self.login_mode,
            username=self.username or DEFAULT_USERNAME,
            password=self.password or DEFAULT_PASSWORD
        )
        if not auth_ok or not self._is_running:
            return False
        
        # If testing EMR Designer, wait for FSWriter WebAssembly kernel
        if "emrDesigner" in target_url:
            self.log(None, f"正在等待 EMR 设计器与 FSWriter 内核加载...")
            ready = self.writer.wait_for_ready(timeout_sec=15)
            if ready:
                about = self.writer.about_control()
                self.log(None, f"FSWriter 控件就绪: {about}")
            else:
                self.log(None, "EMR 设计器加载超时，继续尝试执行", "WARN")
            return True
        else:
            time.sleep(1.5)
            curr_url = self.browser.get_current_url()
            self.log(None, f"HIS 目标路由已就绪: {curr_url}", "SUCCESS")
            return True

    def run_tests(
        self,
        selected_ids: Optional[List[str]] = None,
        target_url: Optional[str] = None,
        mode_filter: Optional[str] = None
    ) -> List[TestCaseResult]:
        """
        Execute selected or all tests with mode awareness.
        mode_filter: "ALL", "INVASIVE", or "NON_INVASIVE"
        """
        self._is_running = True
        self.results = []
        all_candidate_ids = selected_ids or list(self.registry.keys())

        # Filter by mode if requested
        if mode_filter and mode_filter.upper() in ["INVASIVE", "NON_INVASIVE"]:
            target_ids = [
                tid for tid in all_candidate_ids
                if self.registry.get(tid, {}).get("mode", "NON_INVASIVE") == mode_filter.upper()
            ]
        else:
            target_ids = all_candidate_ids

        has_invasive = any(
            self.registry.get(tid, {}).get("mode") == "INVASIVE"
            for tid in target_ids
        )

        try:
            if has_invasive:
                self.log(None, "👀 [侵入式模式] 检测到包含 UI 交互项，正在准备 Chrome 实体窗口供视觉核验...")
                if not target_url:
                    has_emr = any("emr" in tid.lower() or "病历" in self.registry.get(tid, {}).get("category", "") for tid in target_ids)
                    target_url = EMR_DESIGNER_URL if has_emr else "http://192.168.1.198:8088/#/inpatient/doctor/workstation"
                
                ready = self.init_environment(url=target_url)
                if not ready or not self._is_running:
                    self.log(None, "测试环境就绪校验未通过或已取消，终止执行", "WARN")
                    return self.results
            else:
                self.log(None, "🤖 [非侵入式模式] 纯后台静默运行中 (零前端页面干扰，直连后端API/Oracle/规则引擎)...", "SUCCESS")

            self._broadcast("RUN_START", {"total": len(target_ids), "has_invasive": has_invasive})

            for test_id in target_ids:
                if not self._is_running:
                    self.log(None, "收到停止指令，跳过后续测试项。", "WARN")
                    break
                meta = self.registry.get(test_id)
                if not meta:
                    continue

                mode_tag = "👀 侵入式" if meta.get("mode") == "INVASIVE" else "🤖 非侵入式"
                res = TestCaseResult(
                    test_id=test_id,
                    name=meta["name"],
                    category=meta["category"],
                    mode=meta.get("mode", "NON_INVASIVE"),
                    status="RUNNING"
                )
                self.results.append(res)
                self._broadcast("TEST_START", {"test_id": test_id, "name": meta["name"], "mode": res.mode})
                self.log(res, f"开始执行 [{mode_tag}]: 【{meta['category']}】{meta['name']}")

                start_t = time.time()
                try:
                    # Execute test function passing engine, writer, browser, result
                    meta["func"](self, self.writer, self.browser, res)
                    res.status = "PASSED"
                    self.log(res, f"[PASS] 测试通过: {meta['name']}", "SUCCESS")
                except Exception as e:
                    res.status = "FAILED"
                    res.error_message = str(e)
                    res.stack_trace = traceback.format_exc()
                    self.log(res, f"[FAIL] 测试失败: {str(e)}", "ERROR")
                    
                    # Capture screenshot on failure if browser available
                    if self.browser and self.browser.is_alive():
                        try:
                            shot_path = self.browser.take_screenshot(f"fail_{test_id}")
                            res.screenshot_path = shot_path
                            res.screenshot_b64 = self.browser.get_screenshot_base64()
                        except Exception:
                            pass
                finally:
                    res.duration_ms = round((time.time() - start_t) * 1000, 2)
                    if self.writer:
                        try:
                            res.xml_snapshot = self.writer.get_document_xml()
                        except Exception:
                            pass
                    
                    self._broadcast("TEST_END", {
                        "test_id": test_id,
                        "name": res.name,
                        "status": res.status,
                        "mode": res.mode,
                        "duration_ms": res.duration_ms,
                        "error": res.error_message,
                        "screenshot_path": res.screenshot_path,
                        "screenshot_b64": res.screenshot_b64
                    })
        except Exception as e:
            self.log(None, f"测试引擎运行异常: {str(e)}", "ERROR")
        finally:
            self._is_running = False
            self._broadcast("RUN_END", {"results_count": len(self.results)})
            self._broadcast("RUN_FINISH", {"results_count": len(self.results)})

        return self.results

    def stop(self):
        """Request immediate stop of running tests."""
        self._is_running = False
        self.log(None, "收到外部停止请求，正在中断执行...", "WARN")
