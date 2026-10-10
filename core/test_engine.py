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

import logging
import time
import traceback
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from fs_web_testrunner.core.browser_driver import BrowserDriver
from fs_web_testrunner.core.fswriter_api import FSWriterAPI
from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.config import EMR_DESIGNER_URL, REPORTS_DIR, SCREENSHOTS_DIR

from fs_web_testrunner.core.self_healing import self_healing_engine, SelfHealingEngine

logger = get_logger("engine")

@dataclass
class TestCaseResult:
    test_id: str
    name: str
    category: str
    mode: str = "NON_INVASIVE"  # "INVASIVE" or "NON_INVASIVE"
    status: str = "PENDING"     # PENDING, RUNNING, PASSED, FAILED, SKIPPED
    workstation: Optional[str] = None
    workstation_code: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: float = 0.0
    screenshot_path: Optional[str] = None
    screenshot_b64: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    xml_snapshot: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    self_healed: bool = False
    healing_events: List[Dict[str, Any]] = field(default_factory=list)

class TestEngine:
    def __init__(self, headless: bool = False, login_mode: str = "A", username: str = "admin", password: str = "admin123", self_heal_enabled: bool = True):
        self.headless = headless
        self.login_mode = login_mode or "A"
        self.username = username or "admin"
        self.password = password or "admin123"
        self.self_heal_enabled = self_heal_enabled
        self.self_healing: SelfHealingEngine = self_healing_engine
        self.self_healing.enabled = self_heal_enabled
        self.browser: Optional[BrowserDriver] = None
        self.writer: Optional[FSWriterAPI] = None
        self.registry: Dict[str, Dict[str, Any]] = {}
        self.results: List[TestCaseResult] = []
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._is_running = False

    def register(
        self,
        test_id: str,
        name: str,
        category: str,
        func: Callable,
        mode: str = "INVASIVE",
        description: str = "",
        workstation: Optional[str] = None,
        workstation_code: Optional[str] = None
    ):
        """Register a test case function with mode and workstation tagging."""
        self.registry[test_id] = {
            "id": test_id,
            "name": name,
            "category": category,
            "func": func,
            "mode": mode.upper(),
            "description": description,
            "workstation": workstation,
            "workstation_code": workstation_code
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
        # Persist to local disk rotating log files
        lvl = getattr(logging, level.upper(), logging.INFO)
        logger.log(lvl, message)

    def init_environment(self, url: Optional[str] = None) -> bool:
        """Start browser and prepare FSWriter instance for invasive UI testing."""
        from fs_web_testrunner.core.env_config import env_config
        from fs_web_testrunner.core.offline_sandbox import get_environment_status
        is_mock = get_environment_status().get("is_mock", False)
        adaptive_strategy = env_config.get_adaptive_strategy()

        target_url = url or f"{env_config.get_frontend_url().rstrip('/')}/#/index"
        if is_mock:
            target_url = "http://127.0.0.1:8989/static/index.html"

        # Check if browser needs to be recreated because visual mode changed (headless vs windowed)
        if self.browser and self.browser.is_alive():
            curr_headless = getattr(self.browser, "headless", False)
            proc_is_headless = self.browser._is_existing_headless()
            if curr_headless != self.headless or proc_is_headless != self.headless:
                mode_tag = "⚡ 无窗口模式" if self.headless else "🖥️ 窗口模式"
                self.log(None, f"🔄 检测到运行视窗模式改变 (当前:{'无窗口' if proc_is_headless else '实体窗口'} -> 目标:{mode_tag})，正在重新启动 Chrome 浏览器...")
                try:
                    self.browser.close()
                    self.browser._kill_existing_cdp()
                except Exception:
                    pass
                self.browser = None

        if not self.browser or not self.browser.is_alive():
            mode_tag = "⚡ 无窗口模式" if self.headless else "🖥️ 窗口模式"
            self.log(None, f"启动浏览器 ({mode_tag}, 登录模式={self.login_mode})...")
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
        
        # Authenticate using Option A or Option B (bypass if in mock sandbox)
        if is_mock:
            auth_ok = True
        else:
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
        if "emrDesigner" in str(target_url) and not is_mock:
            self.log(None, f"正在等待 EMR 设计器与 FSWriter 内核加载...")
            ready = self.writer.wait_for_ready(timeout_sec=15)
            if ready:
                about = self.writer.about_control()
                self.log(None, f"FSWriter 控件就绪: {about}")
            else:
                self.log(None, "EMR 设计器加载超时，继续尝试执行", "WARN")
            return True
        else:
            time.sleep(0.3 if is_mock else 1.5)
            curr_url = self.browser.get_current_url() if (self.browser and self.browser.is_alive()) else target_url
            self.log(None, f"HIS 目标路由已就绪: {curr_url}", "SUCCESS")
            return True

    def run_tests(
        self,
        selected_ids: Optional[List[str]] = None,
        target_url: Optional[str] = None,
        mode_filter: Optional[str] = None,
        workstation_filter: Optional[str] = None
    ) -> List[TestCaseResult]:
        """
        Execute selected or all tests with mode awareness and workstation modular testing.
        mode_filter: "ALL", "INVASIVE", or "NON_INVASIVE"
        workstation_filter: Workstation code (e.g. "INPATIENT_DOCTOR") or name ("住院工作站")
        """
        from fs_web_testrunner.core.env_config import env_config
        from fs_web_testrunner.core.offline_sandbox import get_environment_status
        env_stat = get_environment_status()
        is_mock = env_stat.get("is_mock", False)
        adaptive_strategy = env_config.get_adaptive_strategy()

        self._is_running = True
        self.results = []
        all_candidate_ids = selected_ids or list(self.registry.keys())

        # Filter by workstation if requested
        if workstation_filter and workstation_filter.upper() != "ALL":
            wf = workstation_filter.upper()
            all_candidate_ids = [
                tid for tid in all_candidate_ids
                if (
                    str(self.registry.get(tid, {}).get("workstation_code") or "").upper() == wf
                    or str(self.registry.get(tid, {}).get("workstation") or "") == workstation_filter
                    or workstation_filter in self.registry.get(tid, {}).get("category", "")
                )
            ]

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
            # Check if invasive tests should start browser
            if has_invasive:
                if is_mock and adaptive_strategy == "SKIP_INVASIVE":
                    self.log(None, "⚡ [沙盒自适应·选项B] 离线环境下页面实测将自动跳过，无需准备浏览器...", "WARN")
                else:
                    self.log(None, "🖥️ [页面实测模式] 检测到包含 UI 交互项，正在准备 Chrome 运行环境...")
                    if not target_url:
                        target_url = f"{env_config.get_frontend_url().rstrip('/')}/#/index"
                    
                    ready = self.init_environment(url=target_url)
                    if not ready and not is_mock:
                        self.log(None, "测试环境就绪校验未通过或已取消，终止执行", "WARN")
                        return self.results
            else:
                self.log(None, "⚡ [接口直测模式] 纯后台接口与规则校验中 (完全不启动浏览器，直连后端API/Oracle/规则引擎)...", "SUCCESS")

            self._broadcast("RUN_START", {
                "total": len(target_ids),
                "has_invasive": has_invasive,
                "workstation": workstation_filter,
                "adaptive_strategy": adaptive_strategy
            })

            for test_id in target_ids:
                if not self._is_running:
                    self.log(None, "收到停止指令，跳过后续测试项。", "WARN")
                    break
                meta = self.registry.get(test_id)
                if not meta:
                    continue

                mode_tag = "🖥️ 页面实测" if meta.get("mode") == "INVASIVE" else "⚡ 接口直测"
                is_inv = (meta.get("mode") == "INVASIVE")

                res = TestCaseResult(
                    test_id=test_id,
                    name=meta["name"],
                    category=meta["category"],
                    mode=meta.get("mode", "NON_INVASIVE"),
                    workstation=meta.get("workstation"),
                    workstation_code=meta.get("workstation_code"),
                    status="RUNNING"
                )
                self.results.append(res)
                self._broadcast("TEST_START", {
                    "test_id": test_id,
                    "name": meta["name"],
                    "mode": res.mode,
                    "workstation": res.workstation,
                    "workstation_code": res.workstation_code
                })
                self.log(res, f"开始执行 [{mode_tag}]: 【{meta['category']}】{meta['name']}")

                start_t = time.time()
                try:
                    # 1. 离线模式 + 选项 B (自适应跳过)
                    if is_inv and is_mock and adaptive_strategy == "SKIP_INVASIVE":
                        res.status = "SKIPPED"
                        res.error_message = "现场页面实测项需内网环境，已按自适应策略B自动跳过"
                        self.log(res, f"[SKIP·选项B] 页面实测需连接医院内网前端，自适应策略B已自动安全跳过", "WARN")

                    # 2. 离线模式 + 选项 A (沙盒自适应仿真通过)
                    elif is_inv and is_mock and adaptive_strategy == "ADAPTIVE_MOCK":
                        # 【已废止"异常也判通过"】原实现在 except 分支里照样设 PASSED，
                        # 等于任何失败都被洗成通过。现在离线沙盒一律判为"未校验"，
                        # 绝不产出"通过"。
                        try:
                            meta["func"](self, self.writer, self.browser, res)
                            res.status = "SKIPPED"
                            res.error_message = "离线沙盒模式下未连接真实环境，不计入通过"
                            self.log(res, "[未校验] 离线沙盒未连真实环境，本条不计为通过", "WARN")
                        except Exception as e:
                            res.status = "SKIPPED"
                            res.error_message = f"离线沙盒未做真实校验: {e}"
                            self.log(res, f"[未校验] 离线沙盒执行异常，不计为通过: {e}", "WARN")

                    # 3. 正常执行模式 (非侵入式接口直测 / 连通内网 live / 严格模式)
                    else:
                        # 内网直连模式下进行实时网关/服务可用性前置强校验
                        from fs_web_testrunner.core.offline_sandbox import _is_intranet_available, _get_target_host_port
                        target_h, target_p = _get_target_host_port()
                        if not _is_intranet_available(target_h, target_p, timeout=0.8):
                            raise ConnectionError(
                                f"【内网直连模式网络故障】目标网关服务 ({target_h}:{target_p}) 无法连接或连接超时！"
                                f"当前测试判定为失败。请检查现场内网连通性或切换至离线沙盒模式。"
                            )

                        meta["func"](self, self.writer, self.browser, res)

                        # 4. 【页面实测强断言】页面实测执行完毕后对浏览器做零容忍 404 与健康度检查
                        if is_inv and self.browser and self.browser.is_alive():
                            curr_url = self.browser.get_current_url()
                            if "/404" in curr_url or "#/404" in curr_url:
                                raise AssertionError(
                                    f"【页面实测失败】浏览器当前停留在 404 错误页 ({curr_url})，目标页面不存在！绝对禁止判定为通过！"
                                )
                            # 深度检查 DOM 文本
                            is_404_page = self.browser.evaluate(
                                "() => document.body.innerText.includes('抱歉！当前页面不存在') || (document.title && document.title.includes('404'))"
                            )
                            if is_404_page:
                                raise AssertionError(
                                    f"【页面实测失败】检测到页面显示'抱歉！当前页面不存在'错误提示，路由或组件未生效！绝对禁止判定为通过！"
                                )
                            
                            # 页面实测耗时防御：禁止未调动任何浏览器的虚假瞬间通过 (<300ms)
                            elapsed_ms = (time.time() - start_t) * 1000
                            if elapsed_ms < 300:
                                raise AssertionError(
                                    f"【页面实测失败】页面实测项执行仅耗时 {elapsed_ms:.1f}ms，未检测到任何有效 UI 页面加载与物理交互！"
                                )

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
                        "workstation": res.workstation,
                        "workstation_code": res.workstation_code,
                        "duration_ms": res.duration_ms,
                        "error": res.error_message,
                        "screenshot_path": res.screenshot_path,
                        "screenshot_b64": res.screenshot_b64,
                        "self_healed": res.self_healed,
                        "healing_events": res.healing_events
                    })
        except Exception as e:
            self.log(None, f"测试引擎运行异常: {str(e)}", "ERROR")
        finally:
            self._is_running = False
            self._broadcast("RUN_FINISH", {
                "results_count": len(self.results),
                "self_healing_summary": self.self_healing.get_summary() if self.self_healing else {}
            })

        return self.results

    def stop(self):
        """Request immediate stop of running tests."""
        self._is_running = False
        self.log(None, "收到外部停止请求，正在中断执行...", "WARN")
