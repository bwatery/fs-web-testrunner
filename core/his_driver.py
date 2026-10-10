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
from fs_web_testrunner.core.self_healing import self_healing_engine, SelfHealingEngine

class HISDriver:
    def __init__(self, browser_driver, self_healing: Optional[SelfHealingEngine] = None):
        self.browser = browser_driver
        self.self_healing = self_healing or self_healing_engine

    def heal_usage_dept(self, usage: str = "口服", default_dept: str = "西药房 (910125)", test_result: Optional[Any] = None) -> bool:
        """自愈补偿：解决开西药选择用法后清空默认执行科室的前端问题。"""
        return self.self_healing.heal_usage_dept_wipeout(
            self.browser, test_result=test_result, usage_name=usage, default_dept=default_dept
        )

    def close_active_dialog(self, test_result: Optional[Any] = None) -> bool:
        """自愈补偿：关闭阻挡点击的全局浮层、Popper与历史遮罩。"""
        return self.self_healing.heal_dangling_poppers_and_overlays(
            self.browser, test_result=test_result
        )

    def heal_patient_context(self, context_name: str = "住院工作站", test_result: Optional[Any] = None) -> bool:
        """自愈补偿：工作站就诊上下文缺失时自动补选就诊患者。"""
        return self.self_healing.heal_patient_context(
            self.browser, test_result=test_result, context_name=context_name
        )

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

    def click_menu(self, menu_title: str, parent_menu_title: Optional[str] = None) -> Dict[str, Any]:
        """
        真实模拟用户在顶部导航栏/侧边栏寻找并点击菜单项进入页面。
        1. 优先检测顶部横向菜单 (.el-menu--horizontal)，若指定 parent_menu_title 或 menu_title 匹配顶级项，
           自动触发 mouseenter 和 click 唤起弹出子菜单 (.el-menu--popup)，并在弹出层内精确定位点击子菜单项。
        2. 兼容侧边栏折叠手风琴展开与子菜单定位。
        3. 兼容已打开标签页 (.el-tabs__item / .tags-view-item) 切换。
        4. 点击时为元素注入发光视觉外框，并在点击后自然等待。
        """
        js_click = f"""(() => {{
            const targetTitle = '{menu_title}';
            const parentTitle = '{parent_menu_title or ""}';
            
            function highlight(el, color = '#409EFF') {{
                if (!el) return;
                el.style.outline = '3px solid ' + color;
                el.style.boxShadow = '0 0 12px ' + color;
                el.style.transition = 'all 0.3s ease';
            }}
            
            // 1. 尝试匹配顶部水平导航栏 (.el-menu--horizontal)
            const topItems = Array.from(document.querySelectorAll(
                '.el-menu--horizontal > .el-sub-menu, .el-menu--horizontal > .el-menu-item, .vab-top-bar-item'
            ));
            
            let matchedParent = null;
            if (parentTitle) {{
                matchedParent = topItems.find(el => el.innerText && el.innerText.trim().includes(parentTitle));
            }} else {{
                matchedParent = topItems.find(el => el.innerText && el.innerText.trim().includes(targetTitle));
            }}
            
            if (matchedParent) {{
                highlight(matchedParent, '#409EFF');
                matchedParent.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                matchedParent.click();
                
                // 查找弹出子菜单 (.el-menu--popup) 内的目标项
                const popupItems = Array.from(document.querySelectorAll('.el-menu--popup .el-menu-item, .el-menu--popup [role="menuitem"]'));
                const childTarget = popupItems.find(el => el.innerText && el.innerText.trim().includes(targetTitle));
                if (childTarget) {{
                    highlight(childTarget, '#67C23A');
                    childTarget.click();
                    return {{
                        success: true,
                        method: 'top_menu_popup_click',
                        parent: matchedParent.innerText.trim(),
                        title: childTarget.innerText.trim()
                    }};
                }}
                
                // 若顶级项本身即为目标项（无单独二级项）
                if (!parentTitle || matchedParent.innerText.trim().includes(targetTitle)) {{
                    return {{
                        success: true,
                        method: 'top_menu_direct_click',
                        title: matchedParent.innerText.trim()
                    }};
                }}
            }}
            
            // 2. 尝试侧边栏折叠项与菜单
            if (parentTitle) {{
                const subMenus = Array.from(document.querySelectorAll('.el-sub-menu, .el-submenu'));
                for (const sm of subMenus) {{
                    const titleEl = sm.querySelector('.el-sub-menu__title, .el-submenu__title');
                    if (titleEl && titleEl.innerText.trim().includes(parentTitle)) {{
                        const isOpened = sm.classList.contains('is-opened') || sm.getAttribute('aria-expanded') === 'true';
                        if (!isOpened) {{
                            titleEl.click();
                        }}
                        break;
                    }}
                }}
            }} else {{
                const subMenus = Array.from(document.querySelectorAll('.el-sub-menu, .el-submenu'));
                for (const sm of subMenus) {{
                    if (sm.innerText && sm.innerText.includes(targetTitle)) {{
                        const titleEl = sm.querySelector('.el-sub-menu__title, .el-submenu__title');
                        const isOpened = sm.classList.contains('is-opened');
                        if (!isOpened && titleEl) {{
                            titleEl.click();
                        }}
                    }}
                }}
            }}
            
            const menuItems = Array.from(document.querySelectorAll('.el-menu-item, [role="menuitem"], .vab-side-bar-item'));
            const targetItem = menuItems.find(el => {{
                const txt = el.innerText ? el.innerText.trim() : '';
                return txt === targetTitle || txt.includes(targetTitle);
            }});
            
            if (targetItem) {{
                highlight(targetItem, '#67C23A');
                targetItem.scrollIntoView({{ block: 'nearest' }});
                targetItem.click();
                return {{
                    success: true,
                    method: 'menu_click',
                    title: targetItem.innerText.trim(),
                    classes: targetItem.className
                }};
            }}
            
            // 3. 检查顶部活跃页签/历史标签
            const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .tags-view-item, [role="tab"]'));
            const targetTab = tabs.find(t => t.innerText && t.innerText.trim().includes(targetTitle));
            if (targetTab) {{
                highlight(targetTab, '#E6A23C');
                targetTab.click();
                return {{ success: true, method: 'tab_click', title: targetTab.innerText.trim() }};
            }}
            
            return {{ success: false, reason: 'menu_not_found', target: targetTitle }};
        }})()"""
        try:
            res = self.browser.evaluate(js_click) or {}
            time.sleep(1.2)
            return res
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def click_button(
        self,
        button_text: str,
        parent_selector: Optional[str] = None,
        highlight_color: str = "#409EFF",
        wait_sec: float = 1.0,
        timeout: float = 5.0
    ) -> Dict[str, Any]:
        """
        在页面或指定容器内寻找按钮，进行可见性发光描边后触发真实实体点击。
        支持动态等待渲染（最多等待 timeout 秒）。
        """
        js = f"""(() => {{
            const root = '{parent_selector or ""}' ? document.querySelector('{parent_selector or ""}') : document;
            if (!root) return {{ found: false, error: 'Parent selector not found' }};

            const btns = Array.from(root.querySelectorAll('button, .el-button, [role="button"]'));
            const isVisible = b => b.offsetWidth > 0 && b.offsetHeight > 0 && b.offsetParent !== null;
            const isMatch = b => {{
                const t = (b.innerText || '').trim();
                return t === '{button_text}' || t.includes('{button_text}');
            }};
            const target = btns.find(b => isMatch(b) && isVisible(b)) || btns.find(isMatch);

            if (!target) {{
                const allTexts = btns.map(b => (b.innerText || '').trim()).filter(Boolean);
                return {{ found: false, availableButtons: allTexts.slice(0, 15) }};
            }}

            const disabled = target.disabled || target.classList.contains('is-disabled');
            target.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
            target.style.outline = '3px solid {highlight_color}';
            target.style.boxShadow = '0 0 12px {highlight_color}';
            target.style.transition = 'all 0.25s ease';

            if (!disabled) {{
                target.click();
            }}

            return {{
                found: true,
                text: (target.innerText || '').trim(),
                disabled: disabled,
                clicked: !disabled
            }};
        }})()"""
        start = time.time()
        last_res = {}
        while time.time() - start < timeout:
            res = self.browser.evaluate(js) or {}
            last_res = res
            if res.get("found"):
                time.sleep(wait_sec)
                return res
            time.sleep(0.4)
        return last_res

    def click_tab(self, tab_text: str, wait_sec: float = 1.0) -> Dict[str, Any]:
        """点击顶部页签栏或内联标签项 (例如 .el-tabs__item, .tab-item, .tags-view-item)"""
        js = f"""(() => {{
            const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .tags-view-item, .tab-item, [role="tab"]'));
            const target = tabs.find(t => (t.innerText || '').trim().includes('{tab_text}'));
            if (!target) return {{ success: false, reason: 'tab not found' }};
            target.style.outline = '3px solid #E6A23C';
            target.style.boxShadow = '0 0 10px #E6A23C';
            target.click();
            return {{ success: true, text: (target.innerText || '').trim() }};
        }})()"""
        res = self.browser.evaluate(js) or {}
        time.sleep(wait_sec)
        return res

    def has_button(self, button_text: str) -> bool:
        """检查当前界面是否存在指定文本的按钮。"""
        js = f"""(() => {{
            const btns = Array.from(document.querySelectorAll('button, .el-button'));
            return btns.some(b => (b.innerText || '').trim().includes('{button_text}'));
        }})()"""
        return bool(self.browser.evaluate(js))

    def assert_button_present(self, button_text: str):
        """断言当前界面存在指定操作按钮，否则抛出异常。"""
        if not self.has_button(button_text):
            raise AssertionError(f"【按钮断言失败】当前页面未检测到按钮【{button_text}】！")

    def wait_and_assert_dialog(
        self,
        title_keyword: str = "",
        timeout: float = 8.0
    ) -> Dict[str, Any]:
        """
        动态等待并断言页面弹出了 Element Plus 对话框/抽屉，返回其标题、行数据与按钮列表。
        """
        start = time.time()
        js = f"""(() => {{
            const dialogs = Array.from(document.querySelectorAll('.el-dialog, .el-drawer, [role="dialog"], .el-overlay-dialog')).filter(d => {{
                const style = window.getComputedStyle(d);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                const rect = d.getBoundingClientRect();
                return ((rect.width > 0 && rect.height > 0) || (d.offsetWidth > 0 && d.offsetHeight > 0)) && !d.classList.contains('is-closing');
            }});
            if (dialogs.length === 0) return {{ hasDialog: false }};

            const target = dialogs.find(d => {{
                const title = (d.querySelector('.el-dialog__title, .el-drawer__title, .el-drawer__header') || {{}}).innerText || d.innerText || '';
                return !'{title_keyword}' || title.includes('{title_keyword}');
            }}) || dialogs[0];

            const title = (target.querySelector('.el-dialog__title, .el-drawer__title, .el-drawer__header') || {{}}).innerText || '';
            const rows = Array.from(target.querySelectorAll('tbody tr, .vxe-body--row')).map(tr => tr.innerText.trim().replace(/\\t+/g, ' | '));
            const buttons = Array.from(target.querySelectorAll('button, .el-button')).map(b => (b.innerText || '').trim()).filter(Boolean);

            return {{
                hasDialog: true,
                title: title,
                rowCount: rows.length,
                rows: rows.slice(0, 5),
                buttons: buttons
            }};
        }})()"""
        while time.time() - start < timeout:
            res = self.browser.evaluate(js) or {}
            if res.get("hasDialog"):
                return res
            time.sleep(0.5)
        raise AssertionError(f"超时 ({timeout}s) 未能检测到弹出的【{title_keyword or '业务对话框'}】")

    def close_modal_dialog(self) -> bool:
        """关闭当前激活的最顶层对话框或浮层"""
        js = """(() => {
            const dialogs = Array.from(document.querySelectorAll('.el-dialog, .el-drawer')).filter(d => d.offsetHeight > 0);
            if (dialogs.length === 0) return false;
            const topDialog = dialogs[dialogs.length - 1];
            const closeBtn = topDialog.querySelector('.el-dialog__headerbtn, .el-drawer__close-btn') || 
                             Array.from(topDialog.querySelectorAll('.el-button')).find(b => {
                                 const t = (b.innerText || '').trim();
                                 return t === '关闭' || t === '取消' || t === '退出';
                             });
            if (closeBtn) {
                closeBtn.click();
                return true;
            }
            return false;
        })()"""
        res = self.browser.evaluate(js)
        time.sleep(0.8)
        return bool(res)

    def navigate_via_menu(
        self,
        menu_title: str,
        parent_menu_title: Optional[str] = None,
        fallback_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        优先通过真实顶部/左侧菜单点进去；若菜单未配置或离线降级，则使用备用路由。
        """
        click_res = self.click_menu(menu_title, parent_menu_title)
        time.sleep(1.2)
        
        # 验证是否成功跳转至目标路由；若未成功则使用备用路由确保页面就绪
        if fallback_hash:
            curr_url = self.browser.get_current_url()
            clean_target = fallback_hash.lstrip('#').strip('/')
            if clean_target not in curr_url:
                self.navigate_route(fallback_hash)
                return {"success": True, "method": "fallback_route_sync", "hash": fallback_hash, "menu_click": click_res}

        if click_res.get("success"):
            return click_res
        
        # 降级 Hash 路由直跳
        if fallback_hash:
            self.navigate_route(fallback_hash)
            return {"success": True, "method": "fallback_hash_nav", "hash": fallback_hash, "note": click_res.get("reason")}
        return click_res

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
                'dispense': '发药',
                'registration': '挂号',
                'charge': '收费'
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
        Inspect current page: detects Vue errors, blank screens, 404, or network exceptions.
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

            // 深度检测前端 UI 弹出的各种错误及网络故障提示
            const errorElements = Array.from(document.querySelectorAll(
                '.el-message--error, .el-notification--error, .el-alert--error, .el-result--error'
            )).map(el => el.innerText.trim()).filter(Boolean);

            const netKeywords = [
                '网络异常', '网络错误', '连接超时', '网络连接失败', '未能连接到服务器',
                'Network Error', 'timeout of', 'Failed to fetch', '502 Bad Gateway',
                '504 Gateway Time-out', '500 Internal Server Error', 'ERR_CONNECTION_REFUSED',
                '服务暂不可用', '请检查网络', '请求失败', 'net::ERR'
            ];

            let detectedNetError = '';
            for (const kw of netKeywords) {
                if (bodyText.includes(kw)) {
                    detectedNetError = kw;
                    break;
                }
                for (const em of errorElements) {
                    if (em.includes(kw)) {
                        detectedNetError = em;
                        break;
                    }
                }
                if (detectedNetError) break;
            }

            const isNetworkError = !!detectedNetError || (errorElements.length > 0 && errorElements.some(e => e.includes('失败') || e.includes('超时')));

            return {
                url: window.location.href,
                hash: window.location.hash,
                title: title,
                is404: is404,
                isLogin: isLogin,
                hasApp: hasApp,
                hasError: hasError,
                isNetworkError: isNetworkError,
                networkErrorMsg: detectedNetError || (errorElements.length > 0 ? errorElements[0] : ''),
                errorElements: errorElements,
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

    def assert_page_healthy(self, context_name: str = "页面") -> Dict[str, Any]:
        """
        严格页面健康与网络连通性断言。
        若出现 404、白屏、前端网络错误浮窗或微服务拒绝，立即抛出明确异常，杜绝直连模式下的假阳性！
        """
        health = self.check_page_health()
        if health.get("is404"):
            raise AssertionError(f"[{context_name}] 路由异常: 页面出现 404 (页面未找到)")
        if health.get("isNetworkError"):
            err_msg = health.get("networkErrorMsg") or "检测到前端网络通信错误"
            raise ConnectionError(f"[{context_name}] 现场网络通信异常: 『{err_msg}』")
        if health.get("isBlank"):
            raise AssertionError(f"[{context_name}] 页面白屏渲染失败: DOM 内容为空 (可能因网络阻塞未能拉取页面组件)")
        return health

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
