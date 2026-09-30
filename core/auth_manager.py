"""
Authentication Manager supporting both:
- Option A: Fully automatic login via configured username & password.
- Option B: Manual login by the user in the interactive Chrome window with auto-detection.
"""

import time
from typing import Optional
from fs_web_testrunner.config import DEFAULT_USERNAME, DEFAULT_PASSWORD

class AuthManager:
    def __init__(self, browser_driver, engine=None):
        self.browser = browser_driver
        self.engine = engine

    def _log(self, message: str, level: str = "INFO"):
        if self.engine:
            self.engine.log(None, message, level)
        else:
            print(f"[{level}] {message}")

    def is_logged_in(self) -> bool:
        """Check whether current browser session is already authenticated."""
        js = """
        (() => {
            const url = window.location.href;
            if (url.includes('/login')) return false;
            
            // Check sessionStorage (e.g. shop-vite-token)
            const sToken = sessionStorage.getItem('shop-vite-token') || sessionStorage.getItem('token');
            if (sToken && sToken.length > 10) return true;

            // Check common token storage keys in localStorage
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i).toLowerCase();
                if (key.includes('token') || key.includes('user') || key.includes('auth')) {
                    const val = localStorage.getItem(localStorage.key(i));
                    if (val && val.length > 10) return true;
                }
            }
            return !url.includes('/login') && document.querySelectorAll('.el-table, .el-menu, .el-header').length > 0;
        })()
        """
        return bool(self.browser.evaluate(js))

    def ensure_authenticated(
        self,
        mode: str = "B",
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        timeout_sec: int = 180
    ) -> bool:
        """
        Ensure user is authenticated before running tests.
        mode: 'A' (Auto login) or 'B' (Manual login).
        """
        if self.is_logged_in():
            self._log("✓ 检测到浏览器已有有效登录凭证，直接复用当前会话！", "SUCCESS")
            return True

        from fs_web_testrunner.core.offline_sandbox import get_environment_status
        env_status = get_environment_status()
        if env_status.get("is_mock"):
            self._log("💻 [离线沙盒模式] 检测到处于离线免库沙盒环境，自动注入仿真登录凭据，跳过内网网络等待！", "SUCCESS")
            mock_tok = "eyJhbGciOiJIUzUxMiJ9.mock_sandbox_token.sign"
            try:
                self.browser.evaluate(f"sessionStorage.setItem('shop-vite-token', '{mock_tok}');")
            except Exception:
                pass
            return True

        curr_url = self.browser.get_current_url()
        if "/login" not in curr_url:
            self.browser.navigate("http://192.168.1.198:8088/#/login")
            time.sleep(1.5)

        # Smart token injection fallback (instantly logs in using admin/admin123 without 180s wait)
        try:
            import requests
            from fs_web_testrunner.config import EMR_API_URL
            r = requests.post(
                f"{EMR_API_URL}/login",
                json={"username": username, "password": password},
                timeout=2
            )
            if r.status_code == 200:
                tok = r.json().get("data")
                if tok:
                    self.browser.evaluate(f"sessionStorage.setItem('shop-vite-token', '{tok}'); window.location.reload();")
                    time.sleep(2.0)
                    if self.is_logged_in():
                        self._log("✓ 已通过后端凭证快速同步登录态至浏览器！", "SUCCESS")
                        return True
        except Exception:
            pass

        if mode.upper() == "A":
            return self._auto_login_option_a(username, password)
        else:
            return self._wait_manual_login_option_b(timeout_sec)

    def _auto_login_option_a(self, username: str, password: str) -> bool:
        """[方案 A] 自动代登模式"""
        self._log(f"[方案 A: 自动代登] 正在为工号 [{username}] 执行自动表单录入与登录...")
        
        js_fill = f"""
        (() => {{
            const inputs = document.querySelectorAll('input.el-input__inner');
            if (inputs.length >= 2) {{
                // Set username
                inputs[0].value = '{username}';
                inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                // Set password
                inputs[1].value = '{password}';
                inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                // Trigger button
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('登录'));
                if (btn) {{
                    btn.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
        triggered = self.browser.evaluate(js_fill)
        if not triggered:
            self._log("未能定位登录表单按钮，请检查界面", "ERROR")
            return False

        # Wait for redirect or department choice dialog
        start_t = time.time()
        while time.time() - start_t < 15:
            time.sleep(1.0)
            if self.is_logged_in():
                self._log("✓ [方案 A] 自动登录成功！", "SUCCESS")
                return True
            
            # Check if department selection dialog popped up
            js_dept = """
            (() => {
                const dialog = document.querySelector('.el-dialog');
                if (dialog && (dialog.innerText.includes('科室') || dialog.innerText.includes('角色'))) {
                    const firstOption = dialog.querySelector('.el-radio, .el-button--primary, li');
                    if (firstOption) {
                        firstOption.click();
                        const confirmBtn = dialog.querySelector('.el-button--primary');
                        if (confirmBtn) confirmBtn.click();
                        return true;
                    }
                }
                return false;
            })()
            """
            self.browser.evaluate(js_dept)

        self._log("自动登录等待超时，请确认账号密码是否正确", "WARN")
        return False

    def _wait_manual_login_option_b(self, timeout_sec: int) -> bool:
        """[方案 B] 手动登录模式"""
        self._log("==================================================================", "INFO")
        self._log("【方案 B: 手动登录模式已就绪】", "INFO")
        self._log("👉 请在弹出的 Chrome 浏览器窗口中输入您的 HIS 工号与密码并登录...", "WARN")
        self._log(f"系统将自动检测登录状态（最长等待 {timeout_sec} 秒）...", "INFO")
        self._log("==================================================================", "INFO")

        start_t = time.time()
        last_prompt_t = start_t
        while time.time() - start_t < timeout_sec:
            # Check if user clicked STOP button!
            if self.engine and not self.engine._is_running:
                self._log("已接收到用户【停止执行】指令，立即终止等待。", "WARN")
                return False

            # Check if browser was closed by user
            if not self.browser.is_alive():
                self._log("检测到 Chrome 浏览器窗口已关闭，自动终止登录等待。", "WARN")
                return False

            try:
                if self.is_logged_in():
                    self._log("🎉 检测到您已在浏览器中成功登录！自动化测试将自动继续执行...", "SUCCESS")
                    if self.engine:
                        self.engine._broadcast("LOGIN_SUCCESS", {})
                    time.sleep(1.0)
                    return True
            except Exception as e:
                if self.engine and not self.engine._is_running:
                    return False
                if not self.browser.is_alive():
                    self._log(f"浏览器连接已断开: {e}，终止等待。", "WARN")
                    return False

            # Broadcast countdown event to UI
            elapsed = int(time.time() - start_t)
            remaining = timeout_sec - elapsed
            if self.engine:
                self.engine._broadcast("LOGIN_WAITING", {
                    "remaining": remaining,
                    "elapsed": elapsed,
                    "timeout": timeout_sec
                })

            time.sleep(1.0)

            # Reminder every 20 seconds in log
            if time.time() - last_prompt_t > 20:
                self._log(f"[等待手动登录中...] 已等待 {elapsed} 秒，剩余 {remaining} 秒 (若已输入请点击登录按钮)", "INFO")
                last_prompt_t = time.time()

        self._log("等待手动登录超时，请重试", "ERROR")
        return False
