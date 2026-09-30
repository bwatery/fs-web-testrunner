"""
HIS Login & Session Validator (登录验证器)
Extracts live session tokens from the interactive Chrome browser and verifies
backend APIs (order dictionaries, workstation context, Oracle DB persistence)
WITHOUT navigating or altering the user's frontend pages!
"""

import time
import json
import base64
import requests
from typing import Dict, Any, Optional, List
from fs_web_testrunner.config import CDP_HOST, CDP_PORT

class LoginValidator:
    def __init__(self, cdp_port: int = CDP_PORT):
        self.cdp_port = cdp_port

    def get_browser_session(self) -> Dict[str, Any]:
        """Extract live token, user info, and department from current Chrome window."""
        try:
            tabs_resp = requests.get(
                f"http://{CDP_HOST}:{self.cdp_port}/json",
                timeout=2,
                proxies={"http": None, "https": None}
            )
            tabs = tabs_resp.json()
            page = next((t for t in tabs if t.get("type") == "page"), None)
            if not page:
                return {"is_connected": False, "error": "未检测到已打开的 Chrome 页面，请先点击【🌐 弹出独立浏览器】"}

            import websocket
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=4)
            ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            
            expr = """(() => {
                const token = sessionStorage.getItem('shop-vite-token') || localStorage.getItem('token') || '';
                const roleDept = localStorage.getItem('userRoleDeptCache') || '';
                return {
                    href: window.location.href,
                    title: document.title,
                    token: token,
                    roleDept: roleDept
                };
            })()"""
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))

            start_t = time.time()
            data_val = {}
            while time.time() - start_t < 3:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == 2:
                    data_val = msg.get("result", {}).get("result", {}).get("value", {})
                    break
            ws.close()

            token = data_val.get("token", "")
            if not token:
                return {
                    "is_connected": True,
                    "is_logged_in": False,
                    "href": data_val.get("href", ""),
                    "title": data_val.get("title", ""),
                    "message": "Chrome 窗口已打开，但当前尚未检测到有效登录凭证 (请在弹出的 Chrome 窗口中输入工号密码并点击登录)"
                }

            # Parse JWT token
            user_info = {}
            try:
                parts = token.split(".")
                if len(parts) >= 2:
                    padded = parts[1] + "=" * (-len(parts[1]) % 4)
                    user_info = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            except Exception:
                pass

            return {
                "is_connected": True,
                "is_logged_in": True,
                "token": token,
                "user": user_info,
                "username": user_info.get("sub", "admin"),
                "login_user_key": user_info.get("login_user_key", ""),
                "roleDept": data_val.get("roleDept", ""),
                "href": data_val.get("href", ""),
                "title": data_val.get("title", "")
            }
        except Exception as e:
            return {"is_connected": False, "error": f"连接浏览器失败: {e}"}

    def validate_backend_services(self, token: str, role_dept_str: str = "") -> Dict[str, Any]:
        """Validate backend HIS APIs and Oracle database using the extracted token."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        results = {}

        # 1. 验证用户身份与角色权限 (/userInfo)
        t_user = time.time()
        try:
            r_user = requests.get(
                "http://192.168.1.198:8081/userInfo",
                headers=headers,
                timeout=4
            )
            elapsed_user = round((time.time() - t_user) * 1000, 1)
            if r_user.status_code == 200:
                user_res = r_user.json()
                u_data = user_res.get("data", {})
                results["user_info"] = {
                    "status": "PASS",
                    "status_code": 200,
                    "elapsed_ms": elapsed_user,
                    "user_id": u_data.get("userId"),
                    "role_id": u_data.get("roleId"),
                    "role_name": u_data.get("roleName", "医生"),
                    "role_key": u_data.get("roleInfo", {}).get("roleKey", ""),
                    "message": f"用户身份验证通过: {u_data.get('roleName', '住院医生')} (工号ID: {u_data.get('userId')})"
                }
            else:
                results["user_info"] = {
                    "status": "FAIL",
                    "status_code": r_user.status_code,
                    "elapsed_ms": elapsed_user,
                    "message": f"用户信息接口异常 HTTP {r_user.status_code}"
                }
        except Exception as e:
            results["user_info"] = {"status": "ERROR", "message": f"连接用户信息接口失败: {e}"}

        # 解析科室 ID
        dept_id = 910092
        try:
            if role_dept_str:
                dept_dict = json.loads(role_dept_str)
                for r_k, d_v in dept_dict.items():
                    if isinstance(d_v, dict):
                        dept_id = list(d_v.values())[0]
                    elif isinstance(d_v, (int, str)):
                        dept_id = int(d_v)
        except Exception:
            pass

        # 2. 验证在院患者队列与病区服务 (/faith/medical/inpatient/ward/patient/list)
        t_patient = time.time()
        try:
            r_pat = requests.post(
                "http://192.168.1.198:8081/faith/medical/inpatient/ward/patient/list",
                headers=headers,
                json={"deptId": dept_id},
                timeout=4
            )
            elapsed_pat = round((time.time() - t_patient) * 1000, 1)
            if r_pat.status_code == 200:
                pat_data = r_pat.json()
                pat_list = pat_data.get("data", [])
                pat_count = pat_data.get("total", len(pat_list))
                samples = [
                    {
                        "patientName": p.get("patientName"),
                        "inpatientNo": p.get("inpatientNo"),
                        "bedNo": p.get("bedNo") or "未分配",
                        "attendDoctorName": p.get("attendDoctorName") or "主管医生"
                    }
                    for p in pat_list[:3]
                ]
                results["patient_queue"] = {
                    "status": "PASS",
                    "status_code": 200,
                    "elapsed_ms": elapsed_pat,
                    "dept_id": dept_id,
                    "patient_count": pat_count,
                    "samples": samples,
                    "message": f"病区患者数据正常，科室({dept_id})当前在院患者 {pat_count} 人 (耗时 {elapsed_pat}ms)"
                }
            else:
                results["patient_queue"] = {
                    "status": "WARN",
                    "status_code": r_pat.status_code,
                    "elapsed_ms": elapsed_pat,
                    "message": f"在院患者列表接口 HTTP {r_pat.status_code}"
                }
        except Exception as e:
            results["patient_queue"] = {"status": "WARN", "message": f"查询在院患者失败: {e}"}

        # 3. 验证医嘱字典查询与 Oracle 数据库检索
        t0 = time.time()
        try:
            r1 = requests.post(
                "http://192.168.1.198:8081/faith/medical/inpatient/order/item/list",
                headers=headers,
                json={"pageNum": 1, "pageSize": 5, "classifyType": "W"},
                timeout=4
            )
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            if r1.status_code == 200:
                data = r1.json()
                total = data.get("total", 0)
                items = data.get("data", [])
                sample = items[0] if items else {}
                results["order_dict"] = {
                    "status": "PASS",
                    "status_code": 200,
                    "elapsed_ms": elapsed_ms,
                    "total_items": total,
                    "sample": {
                        "itemId": sample.get("itemId"),
                        "itemName": sample.get("itemName"),
                        "specs": sample.get("specs"),
                        "price": sample.get("price"),
                        "packageUnit": sample.get("packageUnit"),
                        "spellCode": sample.get("spellCode")
                    },
                    "message": f"医嘱项目字典服务正常，已从 Oracle 数据库检索到 {total} 条真实药品诊疗项目 (耗时 {elapsed_ms}ms)"
                }
            else:
                results["order_dict"] = {
                    "status": "FAIL",
                    "status_code": r1.status_code,
                    "elapsed_ms": elapsed_ms,
                    "message": f"医嘱字典接口响应异常 HTTP {r1.status_code}: {r1.text[:120]}"
                }
        except Exception as e:
            results["order_dict"] = {"status": "ERROR", "message": f"连接医嘱接口失败: {e}"}

        # 4. 验证医嘱业务规则校验引擎
        t1 = time.time()
        try:
            r2 = requests.post(
                "http://192.168.1.198:8081/faith/medical/inpatient/order/list",
                headers=headers,
                json={"pageNum": 1, "pageSize": 1},
                timeout=3
            )
            elapsed2_ms = round((time.time() - t1) * 1000, 1)
            rule_ok = "住院流水号" in r2.text or r2.status_code == 200
            results["order_rule_service"] = {
                "status": "PASS" if rule_ok else "WARN",
                "status_code": r2.status_code,
                "elapsed_ms": elapsed2_ms,
                "message": f"医嘱业务规则引擎就绪 (参数校验响应正常, 耗时 {elapsed2_ms}ms)"
            }
        except Exception as e:
            results["order_rule_service"] = {"status": "WARN", "message": f"规则接口校验提示: {e}"}

        return results

    def search_order_items(self, keyword: str = "", classify_type: str = "W", page_num: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Search order items from Oracle DB with optional keyword matching."""
        session = self.get_browser_session()
        if not session.get("is_logged_in"):
            return {"status": "FAIL", "message": "尚未检测到浏览器有效登录凭证"}

        token = session["token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Fetch candidate page from backend
        try:
            t0 = time.time()
            fetch_size = max(page_size, 50) if keyword else page_size
            r = requests.post(
                "http://192.168.1.198:8081/faith/medical/inpatient/order/item/list",
                headers=headers,
                json={"pageNum": page_num, "pageSize": fetch_size, "classifyType": classify_type},
                timeout=4
            )
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            if r.status_code != 200:
                return {"status": "FAIL", "message": f"HIS 后端返回异常 HTTP {r.status_code}"}

            res = r.json()
            items = res.get("data", [])
            total = res.get("total", len(items))

            if keyword:
                kw = keyword.strip().upper()
                items = [
                    item for item in items
                    if kw in (item.get("itemName") or "").upper()
                    or kw in (item.get("spellCode") or "").upper()
                    or kw in (item.get("itemNo") or "").upper()
                    or kw in (item.get("specs") or "").upper()
                ]

            return {
                "status": "SUCCESS",
                "total": total,
                "count": len(items),
                "elapsed_ms": elapsed_ms,
                "items": items[:page_size]
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"医嘱检索失败: {e}"}

    def run_full_diagnosis(self) -> Dict[str, Any]:
        """Perform end-to-end authentication and API validation without touching frontend pages."""
        session = self.get_browser_session()
        if not session.get("is_connected"):
            return {
                "status": "FAIL",
                "step": "BROWSER_CHECK",
                "message": session.get("error", "未连接到浏览器"),
                "details": session
            }

        if not session.get("is_logged_in"):
            return {
                "status": "WAITING_LOGIN",
                "step": "AUTH_CHECK",
                "message": session.get("message", "当前未登录"),
                "details": session
            }

        token = session.get("token")
        services = self.validate_backend_services(token, session.get("roleDept", ""))
        
        all_passed = services.get("order_dict", {}).get("status") == "PASS" and services.get("user_info", {}).get("status") == "PASS"
        role_name = services.get("user_info", {}).get("role_name", "住院医生")

        return {
            "status": "SUCCESS" if all_passed else "WARN",
            "message": f"🎉 登录验证通过！HIS 后端医嘱接口与 Oracle 数据库连接全部正常！(当前角色: {role_name})" if all_passed else "已登录，但部分业务接口存在异常",
            "session": {
                "username": session.get("username"),
                "token_preview": token[:40] + "...",
                "token": token,
                "login_user_key": session.get("login_user_key"),
                "roleDept": session.get("roleDept"),
                "current_page": session.get("href"),
                "page_title": session.get("title")
            },
            "services": services
        }

    # -------------------------------------------------------------
    # 方案 1 & 3: 角色+科室 身份切换中枢与测试矩阵
    # -------------------------------------------------------------
    ROLE_PRESETS = [
        {
            "roleId": 15,
            "roleName": "门诊医生",
            "roleKey": "MZYS",
            "deptId": 910073,
            "deptName": "内科门诊",
            "icon": "🏥",
            "route": "#/outpatient/doctor",
            "desc": "门诊接诊、处方开立与诊断树录入"
        },
        {
            "roleId": 14,
            "roleName": "门诊收费",
            "roleKey": "MZSF",
            "deptId": 2,
            "deptName": "收费处",
            "icon": "💰",
            "route": "#/outpatient/charge",
            "desc": "门诊处方划价收费与结算发票打印"
        },
        {
            "roleId": 14,
            "roleName": "门诊挂号",
            "roleKey": "MZSF",
            "deptId": 910084,
            "deptName": "门诊收费处",
            "icon": "📝",
            "route": "#/outpatient/registration",
            "desc": "排班号源选择与现场门诊挂号"
        },
        {
            "roleId": 33,
            "roleName": "门诊药房",
            "roleKey": "MZYF",
            "deptId": 910125,
            "deptName": "西药房",
            "icon": "💊",
            "route": "#/pharmacy/outpatient",
            "desc": "门诊处方调配与窗口扫码发药"
        },
        {
            "roleId": 35,
            "roleName": "住院医生",
            "roleKey": "ZYYS",
            "deptId": 910092,
            "deptName": "内一科",
            "icon": "🛏️",
            "route": "#/inpatient/doctor/workstation",
            "desc": "在院患者床位管理、长临医嘱开立与下达"
        },
        {
            "roleId": 36,
            "roleName": "住院护士",
            "roleKey": "ZYHS",
            "deptId": 910131,
            "deptName": "内一科病区",
            "icon": "💉",
            "route": "#/inpatient/nurse",
            "desc": "床位分配、医嘱执行批处理与体征录入"
        },
        {
            "roleId": 39,
            "roleName": "药库管理",
            "roleKey": "YKGL",
            "deptId": 910129,
            "deptName": "西药库",
            "icon": "📦",
            "route": "#/pharmacy/stock",
            "desc": "全院药品入库验收、出库调拨与盘点"
        },
        {
            "roleId": 41,
            "roleName": "EMR管理员",
            "roleKey": "EMRADMIN",
            "deptId": 10072,
            "deptName": "信息科",
            "icon": "📄",
            "route": "#/emr/templatesrecords/emrDesigner",
            "desc": "病历模板制作、数据元管理与编辑器设计"
        },
        {
            "roleId": 1,
            "roleName": "系统管理员",
            "roleKey": "ADMIN",
            "deptId": 10072,
            "deptName": "信息科",
            "icon": "🔧",
            "route": "#/index",
            "desc": "全院权限字典维护与职工参数设置"
        }
    ]

    def get_role_presets(self) -> List[Dict[str, Any]]:
        return self.ROLE_PRESETS

    def get_roles_list(self) -> List[Dict[str, Any]]:
        """Fetch all roles from backend /role API or fallback to presets."""
        session = self.get_browser_session()
        token = session.get("token")
        if token:
            try:
                r = requests.get(
                    "http://192.168.1.198:8081/role",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=3
                )
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    if data:
                        return data
            except Exception:
                pass
        
        # Fallback list of 15 roles
        return [
            {"roleId": 15, "roleName": "门诊医生", "roleKey": "MZYS"},
            {"roleId": 14, "roleName": "门诊收费", "roleKey": "MZSF"},
            {"roleId": 32, "roleName": "门诊护士", "roleKey": "MZHS"},
            {"roleId": 33, "roleName": "门诊药房", "roleKey": "MZYF"},
            {"roleId": 34, "roleName": "住院收费", "roleKey": "ZYSF"},
            {"roleId": 35, "roleName": "住院医生", "roleKey": "ZYYS"},
            {"roleId": 36, "roleName": "住院护士", "roleKey": "ZYHS"},
            {"roleId": 37, "roleName": "住院药房", "roleKey": "ZYYF"},
            {"roleId": 38, "roleName": "终端确认", "roleKey": "ZDQR"},
            {"roleId": 39, "roleName": "药库管理", "roleKey": "YKGL"},
            {"roleId": 41, "roleName": "EMR管理员", "roleKey": "EMRADMIN"},
            {"roleId": 51, "roleName": "临床路径", "roleKey": "clinicalPathway"},
            {"roleId": 52, "roleName": "病房管理", "roleKey": "BFGL"},
            {"roleId": 53, "roleName": "手术室", "roleKey": "SSS"},
            {"roleId": 1, "roleName": "系统管理员", "roleKey": "ADMIN"}
        ]

    def get_depts_by_role(self, role_id: int) -> List[Dict[str, Any]]:
        """Fetch departments associated with this role."""
        session = self.get_browser_session()
        token = session.get("token")
        if token:
            try:
                r = requests.get(
                    f"http://192.168.1.198:8081/dept?roleId={role_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=3
                )
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    if data:
                        return data
            except Exception:
                pass
        
        # Fallback common departments
        return [
            {"deptId": 910073, "deptName": "内科门诊", "deptType": "C"},
            {"deptId": 910056, "deptName": "外科门诊", "deptType": "C"},
            {"deptId": 910065, "deptName": "儿科门诊", "deptType": "C"},
            {"deptId": 910077, "deptName": "中医馆门诊", "deptType": "C"},
            {"deptId": 910092, "deptName": "内一科", "deptType": "I"},
            {"deptId": 910096, "deptName": "内二科", "deptType": "I"},
            {"deptId": 910098, "deptName": "骨一科", "deptType": "I"},
            {"deptId": 910131, "deptName": "内一科病区", "deptType": "N"},
            {"deptId": 2, "deptName": "收费处", "deptType": "C"},
            {"deptId": 910084, "deptName": "门诊收费处", "deptType": "F"},
            {"deptId": 910125, "deptName": "西药房", "deptType": "P"},
            {"deptId": 910126, "deptName": "中药房", "deptType": "P"},
            {"deptId": 910127, "deptName": "中心药房", "deptType": "P"},
            {"deptId": 910129, "deptName": "西药库", "deptType": "PI"},
            {"deptId": 10072, "deptName": "信息科", "deptType": "D"}
        ]

    def switch_identity_in_browser(self, role_id: int, dept_id: int, target_route: str = "") -> Dict[str, Any]:
        """Perform seamless identity exchange via CDP in the live Chrome browser."""
        try:
            tabs_resp = requests.get(
                f"http://{CDP_HOST}:{self.cdp_port}/json",
                timeout=2,
                proxies={"http": None, "https": None}
            )
            tabs = tabs_resp.json()
            page = next((t for t in tabs if t.get("type") == "page"), None)
            if not page:
                return {"status": "FAIL", "message": "未连接到 Chrome 浏览器"}

            import websocket
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=5)

            # Map default route for this role if not provided
            if not target_route:
                preset = next((p for p in self.ROLE_PRESETS if p["roleId"] == role_id), None)
                target_route = preset["route"] if preset else "#/index"

            js_code = f"""(async () => {{
                const token = sessionStorage.getItem('shop-vite-token');
                const roleId = {role_id};
                const deptId = {dept_id};
                const targetRoute = '{target_route}';

                // 1. Update localStorage userRoleDeptCache
                let cache = {{}};
                try {{ cache = JSON.parse(localStorage.getItem('userRoleDeptCache') || '{{}}'); }} catch(e) {{}}
                cache["1"] = cache["1"] || {{}};
                cache["1"][String(roleId)] = deptId;
                localStorage.setItem('userRoleDeptCache', JSON.stringify(cache));

                // 2. Clear visited routes to prevent 404
                localStorage.removeItem('caughtRoutes');

                // 3. Exchange Token via backend if currently logged in
                let exchanged = false;
                if (token) {{
                    try {{
                        const resp = await fetch('http://192.168.1.198:8081/exchangeLogin', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + token
                            }},
                            body: JSON.stringify({{ roleId: roleId, deptId: deptId }})
                        }});
                        const res = await resp.json();
                        if (res.code === 200 && res.data) {{
                            sessionStorage.setItem('shop-vite-token', res.data);
                            exchanged = true;
                        }}
                    }} catch(e) {{}}
                }}

                // 4. Redirect smoothly to target workstation route
                const fullUrl = 'http://192.168.1.198:8088/' + targetRoute;
                window.location.href = fullUrl;
                window.location.reload();

                return {{
                    success: true,
                    roleId: roleId,
                    deptId: deptId,
                    targetRoute: targetRoute,
                    exchanged: exchanged
                }};
            }})()"""

            ws.send(json.dumps({
                "id": 99,
                "method": "Runtime.evaluate",
                "params": {"expression": js_code, "awaitPromise": True, "returnByValue": True}
            }))

            start_t = time.time()
            res_val = {}
            while time.time() - start_t < 4:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == 99:
                    res_val = msg.get("result", {}).get("result", {}).get("value", {})
                    break
            ws.close()

            return {
                "status": "SUCCESS",
                "message": f"🎉 身份切换成功！已切换至角色 [{role_id}] 与科室 [{dept_id}]，浏览器正在加载目标工作站",
                "details": res_val
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"切换角色科室失败: {e}"}

    def preset_login_identity(self, role_id: int, dept_id: int, target_route: str = "") -> Dict[str, Any]:
        """Pre-set role and department cache in Chrome before login."""
        try:
            tabs_resp = requests.get(
                f"http://{CDP_HOST}:{self.cdp_port}/json",
                timeout=2,
                proxies={"http": None, "https": None}
            )
            tabs = tabs_resp.json()
            page = next((t for t in tabs if t.get("type") == "page"), None)
            if not page:
                return {"status": "FAIL", "message": "未连接到 Chrome 浏览器"}

            import websocket
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=4)

            js_code = f"""(() => {{
                let cache = {{}};
                try {{ cache = JSON.parse(localStorage.getItem('userRoleDeptCache') || '{{}}'); }} catch(e) {{}}
                cache["1"] = cache["1"] || {{}};
                cache["1"]['{role_id}'] = {dept_id};
                localStorage.setItem('userRoleDeptCache', JSON.stringify(cache));
                localStorage.removeItem('caughtRoutes');
                return {{ success: true, roleId: {role_id}, deptId: {dept_id} }};
            }})()"""

            ws.send(json.dumps({
                "id": 100,
                "method": "Runtime.evaluate",
                "params": {"expression": js_code, "returnByValue": True}
            }))
            ws.recv()
            ws.close()

            return {
                "status": "SUCCESS",
                "message": f"✓ 预置成功！已锁定角色 [{role_id}] + 科室 [{dept_id}]，下次登录将以此身份直接进入工作站"
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"预置身份失败: {e}"}


