"""
HIS Web Frontend Driver.
Specialized for Element Plus + Vue 3 HIS application (ZJCK / HIOP).
Handles authentication, menu navigation, table verification, form fills,
dialog interactions, and white-screen/JS error detection.
"""

import time
import json
from typing import Any, Dict, List, Optional
from fs_web_testrunner.config import EMR_BASE_URL, DEFAULT_USERNAME, DEFAULT_PASSWORD

class HISDriver:
    def __init__(self, browser_driver):
        self.browser = browser_driver

    def ensure_logged_in(self, username: str = DEFAULT_USERNAME, password: str = DEFAULT_PASSWORD) -> bool:
        """
        Check if user is logged into HIS; if at /#/login, attempt login or check token.
        """
        curr_url = self.browser.get_current_url()
        if "#/login" not in curr_url:
            return True

        # Check if login form exists
        js_login = f"""
        (async () => {{
            const userInputs = document.querySelectorAll('input');
            let uInput = null, pInput = null;
            for (let input of userInputs) {{
                const ph = input.getAttribute('placeholder') || '';
                const type = input.getAttribute('type') || '';
                if (ph.includes('账号') || ph.includes('用户') || ph.includes('名')) uInput = input;
                if (type === 'password' || ph.includes('密')) pInput = input;
            }}
            if (uInput && pInput) {{
                uInput.value = '{username}';
                uInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                pInput.value = '{password}';
                pInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                // Click login button
                const btn = document.querySelector('button[type="button"]') || document.querySelector('.el-button--primary');
                if (btn) {{
                    btn.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
        res = self.browser.evaluate(js_login)
        time.sleep(2.0)
        return bool(res)

    def navigate_route(self, hash_path: str):
        """Navigate to specific HIS Vue route (e.g. #/inpatient/finance/syntheticfquery)."""
        clean_hash = hash_path.strip()
        if not clean_hash.startswith('#'):
            clean_hash = '#' + clean_hash

        nav_js = f"""(() => {{
            const targetHash = '{clean_hash}';
            const routeKeywords = {{
                'syntheticfquery': '费用综合查询',
                'leavehospitalcalculate': '出院结算',
                'prepaycharge': '预交金收费',
                'workstation': '医生工作站',
                'dispense': '发药'
            }};
            
            let keyword = '';
            for (let [k, w] of Object.entries(routeKeywords)) {{
                if (targetHash.includes(k)) {{
                    keyword = w;
                    break;
                }}
            }}
            
            if (keyword) {{
                // 1. Try open tabs first
                const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .tags-view-item, [role="tab"]')).filter(el => el.innerText && el.innerText.trim().includes(keyword));
                if (tabs.length > 0) {{
                    tabs[0].click();
                    return {{ success: true, method: 'tab_click', keyword: keyword }};
                }}
                
                // 2. Try sidebar menu item
                const menus = Array.from(document.querySelectorAll('.el-menu-item, span, a')).filter(el => el.innerText && el.innerText.trim() === keyword);
                if (menus.length > 0) {{
                    menus[0].click();
                    return {{ success: true, method: 'menu_click', keyword: keyword }};
                }}
            }}
            
            // 3. Fallback: hash navigation
            window.location.hash = targetHash;
            return {{ success: true, method: 'hash_nav' }};
        }})()"""
        try:
            self.browser.evaluate(nav_js)
        except Exception:
            target = f"{EMR_BASE_URL}/{hash_path.lstrip('/')}"
            self.browser.navigate(target)
        time.sleep(1.8)

    def check_page_health(self) -> Dict[str, Any]:
        """
        Inspect current page: detects Vue errors, blank screens, 404, or unhandled exceptions.
        """
        js = """
        (() => {
            const bodyText = document.body ? document.body.innerText.trim() : '';
            const is404 = window.location.hash.includes('/404') || bodyText.includes('404') || bodyText.includes('找不到页面');
            const isLogin = window.location.hash.includes('/login');
            const hasApp = !!document.getElementById('app');
            const hasError = !!document.querySelector('.el-result--error') || bodyText.includes('TypeError:') || bodyText.includes('Vue error');
            const tablesCount = document.querySelectorAll('.el-table').length;
            const buttonsCount = document.querySelectorAll('.el-button').length;
            const inputsCount = document.querySelectorAll('input').length;
            const title = document.title || '';

            return {
                url: window.location.href,
                hash: window.location.hash,
                title: title,
                is404: is404,
                isLogin: isLogin,
                hasApp: hasApp,
                hasError: hasError,
                elementStats: {
                    tables: tablesCount,
                    buttons: buttonsCount,
                    inputs: inputsCount
                },
                isBlank: bodyText.length < 5
            };
        })()
        """
        return self.browser.evaluate(js) or {}

    def get_table_data(self) -> List[Dict[str, Any]]:
        """Extract data from first Element Plus table on current page."""
        js = """
        (() => {
            const table = document.querySelector('.el-table');
            if (!table) return [];
            const headers = Array.from(table.querySelectorAll('th .cell')).map(th => th.innerText.trim());
            const rows = Array.from(table.querySelectorAll('.el-table__body-wrapper tbody tr'));
            const data = [];
            for (let row of rows) {
                const cells = Array.from(row.querySelectorAll('td .cell')).map(td => td.innerText.trim());
                const rowObj = {};
                headers.forEach((h, i) => {
                    if (h) rowObj[h] = cells[i] || '';
                });
                data.push(rowObj);
            }
            return data;
        })()
        """
        res = self.browser.evaluate(js)
        return res if isinstance(res, list) else []

    def get_el_message_text(self) -> Optional[str]:
        """Get text of active Element Plus toast/message."""
        js = """
        (() => {
            const msg = document.querySelector('.el-message__content');
            return msg ? msg.innerText.trim() : null;
        })()
        """
        return self.browser.evaluate(js)
