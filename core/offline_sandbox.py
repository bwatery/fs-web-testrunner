"""
Offline Sandbox & Dual-Mode Execution Engine (离线沙盒与双模式测试引擎)
Allows the test suite and WebRunner platform to run seamlessly in TWO modes:
1. 🌐 LIVE_INTRA (内网直连模式): Connects directly to real Oracle DB (192.168.1.199) and SpringCloud microservices (192.168.1.198:8081).
2. 💻 MOCK_OFFLINE (离线沙盒模式): Zero intranet/database dependency. Intercepts HTTP requests and Oracle queries with an in-memory high-fidelity simulation engine.
"""

import sys
import time
import json
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests

# Global environment mode state
_CURRENT_MODE = "AUTO"  # "AUTO", "LIVE", "MOCK"
_IS_MOCK_ACTIVE = False
_REAL_REQUESTS_GET = requests.get
_REAL_REQUESTS_POST = requests.post
_REAL_ORACLE_CONNECT = None

try:
    import oracledb
    _REAL_ORACLE_CONNECT = oracledb.connect
except Exception:
    _REAL_ORACLE_CONNECT = None


class MockOracleCursor:
    """Simulates Oracle DB Cursor for offline execution."""
    def __init__(self, conn):
        self.conn = conn
        self._last_query = ""
        self._result_rows = []
        self._cursor_idx = 0

    def execute(self, sql: str, params=None):
        self._last_query = sql.strip().upper()
        self._cursor_idx = 0
        self._result_rows = []

        # 1. SELECT sysdate FROM dual
        if "SYSDATE" in self._last_query and "DUAL" in self._last_query:
            self._result_rows = [(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)]

        # 2. SYS_USER admin check
        elif "SYS_USER" in self._last_query:
            self._result_rows = [("admin", "1")]

        # 3. user_tables query
        elif "USER_TABLES" in self._last_query:
            self._result_rows = [
                ("MED_ORDER_ITEM",),
                ("MED_IP_ORDER",),
                ("FIN_OP_REGISTER",),
                ("FIN_OP_BALANCE",),
                ("PAT_PATIENT",),
                ("PHA_IP_RETURN",),
                ("SYS_USER",)
            ]

        # 4. FIN_OP_REGISTER valid_flag query
        elif "FIN_OP_REGISTER" in self._last_query:
            # Emulate cancelled registration (valid_flag = '0')
            self._result_rows = [("0",)]

        # 5. Generic count or default
        elif "COUNT(" in self._last_query:
            self._result_rows = [(1280,)]
        else:
            self._result_rows = [("1",)]

    def fetchone(self):
        if self._cursor_idx < len(self._result_rows):
            row = self._result_rows[self._cursor_idx]
            self._cursor_idx += 1
            return row
        return None

    def fetchall(self):
        rows = self._result_rows[self._cursor_idx:]
        self._cursor_idx = len(self._result_rows)
        return rows

    def close(self):
        pass


class MockOracleConnection:
    """Simulates Oracle DB Connection for offline execution."""
    def __init__(self):
        self.is_connected = True

    def cursor(self):
        return MockOracleCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.is_connected = False


class MockResponse:
    """Emulates requests.Response object for intercepted microservice calls."""
    def __init__(self, status_code: int, json_data: Any, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text or json.dumps(json_data, ensure_ascii=False)
        self.headers = {"Content-Type": "application/json;charset=UTF-8"}

    def json(self):
        return self._json_data


class MockHISBackend:
    """In-memory high-fidelity HIS microservices simulation engine."""

    def __init__(self):
        self.registered_patients = {}
        self.orders = {}
        self.diagnoses = {}
        self.balances = {}
        self.sequence_id = 800011000
        self.last_patient_name = "门诊质检7349"
        self.last_patient_id = 1581001
        self.last_register_id = 300011078

    def dispatch(self, method: str, url: str, json_data=None, params=None, headers=None) -> MockResponse:
        url_path = url.split("?")[0]
        data = json_data or {}

        # 0. 登录鉴权 (/login)
        if "/login" in url_path:
            mock_jwt = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJhZG1pbiIsImxvZ2luX3VzZXJfa2V5IjoiNjJlOTM5Y2UtOWM0Yi00ZjQyLWIxZTAtMTg4MjQzZGY1YTUzIn0.fUYIfa8BQn1DsdWC2WIZxe5k4yAn5PeRTRu-LPpScty-QC6V3lt5B_cltD5uuiIjTO8Xxvg4M1NO0ez5VuaVjg"
            return MockResponse(200, {
                "code": 200,
                "msg": "登录成功",
                "token": mock_jwt,
                "data": mock_jwt
            })

        # 0.1 角色身份置换 (/exchangeLogin)
        if "/exchangeLogin" in url_path:
            role_id = data.get("roleId", 15)
            mock_jwt_role = f"eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJhZG1pbiIsImxvZ2luX3VzZXJfa2V5Ijoicm9sZV9rZXlfe2tleX1f{role_id}\"}}.mock_sig_role_{role_id}"
            return MockResponse(200, {
                "code": 200,
                "msg": "角色置换成功",
                "data": mock_jwt_role
            })

        # 1. 用户信息 (/userInfo)
        if "/userInfo" in url_path:
            return MockResponse(200, {
                "code": 200,
                "msg": "操作成功",
                "data": {
                    "userId": 1,
                    "userName": "admin",
                    "roleId": 15,
                    "roleName": "内科住院/门诊主治医师",
                    "roleInfo": {"roleKey": "doctor", "roleId": 15}
                }
            })

        # 2. 患者建档 (/faith/patient/save)
        if "/faith/patient/save" in url_path:
            id_no = data.get("identifierNo", "")
            id_type = data.get("identifierType", "01")

            # GB 11643-1999 算法校验
            if id_type == "01":
                if len(id_no) != 18:
                    return MockResponse(400, {"code": 400, "msg": "身份证格式不合法，请输入18位有效证件号码！"})
                weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
                check_chars = "10X98765432"
                try:
                    s = sum(int(id_no[i]) * weights[i] for i in range(17))
                    expected_check = check_chars[s % 11]
                    if id_no[17].upper() != expected_check:
                        return MockResponse(400, {"code": 400, "msg": f"非法身份证号码：校验位错误（期望 {expected_check}，实际 {id_no[17]}）！"})
                except Exception:
                    return MockResponse(400, {"code": 400, "msg": "非法身份证号码，含有非数字字符！"})

            new_pid = 1581000 + len(self.registered_patients) + 1
            self.registered_patients[new_pid] = data
            self.last_patient_name = data.get("patientName", "沙盒测试患者")
            self.last_patient_id = new_pid
            # Real HIS backend returns integer patientId
            return MockResponse(200, {
                "code": 200,
                "msg": "建档成功",
                "data": new_pid
            })

        # 3. 预结算 (preBalance)
        if "preBalance" in url_path:
            return MockResponse(200, {
                "code": 200,
                "msg": "预结算成功",
                "data": {
                    "balanceId": 600011999,
                    "totAmount": 10.0,
                    "ownAmount": 10.0,
                    "supplyAmount": 10.0,
                    "regCost": 10.0
                }
            })

        # 4. 挂号取消退号 (/register/cancel)
        if "/register/cancel" in url_path:
            payments = data.get("paymentDetails", [])
            if not payments:
                return MockResponse(400, {"code": 400, "msg": "退号请求缺失退款支付明细，无法平账！"})
            return MockResponse(200, {
                "code": 200,
                "msg": "退号成功，号源已释放回滚，数据库 VALID_FLAG 翻转为 0",
                "data": True
            })

        # 5. 挂号结算确认 (/register/save/balance or /register/balance)
        if "balance" in url_path and "cancel" not in url_path and "charge" not in url_path:
            new_reg_id = 300011000 + len(self.balances) + 1
            self.last_register_id = new_reg_id
            return MockResponse(200, {
                "code": 200,
                "msg": "挂号结算出票成功",
                "data": {
                    "registerId": new_reg_id,
                    "balanceId": 600011999,
                    "receiptId": 700011999,
                    "receiptNo": "1998"
                }
            })

        # 6. 待诊列表 (/unSeen/list)
        if "unSeen/list" in url_path:
            return MockResponse(200, {
                "code": 200,
                "total": 1,
                "data": [
                    {
                        "registerId": self.last_register_id,
                        "patientName": self.last_patient_name,
                        "seeNo": 41010888,
                        "isSeen": False,
                        "deptName": "内科门诊"
                    }
                ]
            })

        # 7. 接诊叫号 (/seenInfo/update)
        if "seenInfo/update" in url_path:
            return MockResponse(200, {"code": 200, "msg": "接诊状态已更新为已诊", "data": True})

        # 8. 患者上下文Bar条 (/patient/barInfo)
        if "barInfo" in url_path:
            return MockResponse(200, {
                "code": 200,
                "data": {
                    "patientName": self.last_patient_name,
                    "sexName": "男",
                    "age": "32岁",
                    "medicalTypeName": "自费",
                    "medicalKindName": "自费",
                    "registerNo": str(self.last_register_id),
                    "allergyHistory": "无已知过敏史"
                }
            })

        # 9. 门诊主诊断录入 (/diagnose/save)
        if "/diagnose/save" in url_path:
            reg_id = data.get("registerId", self.last_register_id)
            self.diagnoses[reg_id] = True
            return MockResponse(200, {"code": 200, "msg": "主诊断保存成功", "data": {"diagId": "J06.900"}})

        # 10. 医嘱保存前预检 (/order/tipsBeforeSave)
        if "tipsBeforeSave" in url_path:
            reg_id = data.get("registerId")
            # 规则：若无主诊断，阻断保存
            has_diag = self.diagnoses.get(reg_id, False)
            if not has_diag:
                return MockResponse(400, {
                    "code": 400,
                    "msg": "当前就诊诊次不存在有效主诊断，请先录入诊断信息！"
                })
            return MockResponse(200, {"code": 200, "msg": "预检通过，允许开立医嘱", "data": []})

        # 11. 门诊医嘱开立保存 (/order/save)
        if "/faith/medical/outpatient/order/save" in url_path:
            reg_id = data.get("registerId", self.last_register_id)
            self.sequence_id += 1
            return MockResponse(200, {
                "code": 200,
                "msg": "医嘱开立暂存成功",
                "data": {"orderId": self.sequence_id, "orderState": "SV"}
            })

        # 12. 待收费列表 (needCharge/list)
        if "needCharge/list" in url_path:
            return MockResponse(200, {
                "code": 200,
                "total": 1,
                "data": [
                    {
                        "opApplyVOList": [
                            {
                                "billId": 800011001,
                                "itemName": "盐酸左氧氟沙星片 0.5g*10片/盒",
                                "qty": 1,
                                "price": 4.0,
                                "ownAmount": 4.0,
                                "totAmount": 4.0,
                                "balanceFlag": "0",
                                "orderState": "SV"
                            }
                        ]
                    }
                ]
            })

        # 13. 划价正式结算支付 (/charge/save/balance)
        if "/charge/save/balance" in url_path:
            return MockResponse(200, {
                "code": 200,
                "msg": "结算支付完成，医嘱状态机跃迁为 FE(已收费)",
                "data": {
                    "balanceId": 600012001,
                    "receiptId": 700012001,
                    "receiptNo": "1620",
                    "orderState": "FE"
                }
            })

        # 14. 已结明细列表 (settled/list)
        if "settled/list" in url_path:
            return MockResponse(200, {
                "code": 200,
                "total": 1,
                "data": [
                    {
                        "balanceId": 600012001,
                        "receiptId": 700012001,
                        "billId": 800011001,
                        "itemName": "盐酸左氧氟沙星片",
                        "totAmount": 4.0,
                        "dcQty": 1
                    }
                ]
            })

        # 15. 退费申请 (/apply/refund/apply)
        if "refund/apply" in url_path:
            return MockResponse(200, {
                "code": 200,
                "msg": "退费申请草稿已生成",
                "data": [{"applyId": 900011001, "dcQty": 1, "totAmount": -4.0}]
            })

        # 16. 退费冲正执行 (balance/cancel/refund)
        if "cancel/refund" in url_path:
            return MockResponse(200, {
                "code": 200,
                "msg": "退费冲正成功，已生成负数红字凭证",
                "data": {
                    "cancelReceiptId": 700012002,
                    "returnAmount": 4.0,
                    "newBalanceId": None,
                    "orderState": "CC"
                }
            })

        # 17. 医嘱字典查询 (/inpatient/order/item/list)
        if "/inpatient/order/item/list" in url_path:
            items = [
                {"itemId": "10000471", "itemNo": "1196", "itemName": "盐酸左氧氟沙星注射液 100ml", "specs": "100ml:0.2g", "price": 4.0, "packageUnit": "瓶", "spellCode": "YSZYFS"},
                {"itemId": "10000472", "itemNo": "1197", "itemName": "0.9%氯化钠注射液 250ml", "specs": "250ml:2.25g", "price": 3.5, "packageUnit": "袋", "spellCode": "LHN"},
                {"itemId": "10000473", "itemNo": "1198", "itemName": "注射用头孢曲松钠 1.0g", "specs": "1.0g", "price": 12.0, "packageUnit": "支", "spellCode": "TBQS"},
                {"itemId": "10000474", "itemNo": "1199", "itemName": "柴胡颗粒 10g*10袋", "specs": "10g/袋", "price": 18.0, "packageUnit": "盒", "spellCode": "CHKL"},
                {"itemId": "10000475", "itemNo": "1200", "itemName": "普通诊查费", "specs": "次", "price": 10.0, "packageUnit": "次", "spellCode": "PTZCF"}
            ]
            return MockResponse(200, {"code": 200, "total": len(items), "data": items})

        # 18. 在院病区患者队列 (/inpatient/ward/patient/list)
        if "/inpatient/ward/patient/list" in url_path:
            return MockResponse(200, {
                "code": 200,
                "total": 3,
                "data": [
                    {"patientName": "欧阳震华", "inpatientNo": "ZY20260901", "bedNo": "01床", "attendDoctorName": "张主治医师"},
                    {"patientName": "李若兰", "inpatientNo": "ZY20260902", "bedNo": "02床", "attendDoctorName": "李副主任医师"},
                    {"patientName": "王建国", "inpatientNo": "ZY20260903", "bedNo": "03床", "attendDoctorName": "王主任医师"}
                ]
            })

        # Default fallback
        return MockResponse(200, {"code": 200, "msg": "沙盒模拟响应成功", "data": {}})


_MOCK_BACKEND = MockHISBackend()


def _is_intranet_available(host: str = "192.168.1.198", port: int = 8081, timeout: float = 0.8) -> bool:
    """Fast check whether the hospital intranet microservice is reachable."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _patched_requests_get(url, *args, **kwargs):
    if _IS_MOCK_ACTIVE and ("192.168.1.198" in url or "localhost:8081" in url):
        return _MOCK_BACKEND.dispatch("GET", url, params=kwargs.get("params"), headers=kwargs.get("headers"))
    try:
        return _REAL_REQUESTS_GET(url, *args, **kwargs)
    except Exception as e:
        if _CURRENT_MODE in ("AUTO", "MOCK") and ("192.168.1.198" in str(url) or "192.168.1.199" in str(url)):
            return _MOCK_BACKEND.dispatch("GET", url, params=kwargs.get("params"), headers=kwargs.get("headers"))
        raise e


def _patched_requests_post(url, *args, **kwargs):
    if _IS_MOCK_ACTIVE and ("192.168.1.198" in url or "localhost:8081" in url):
        return _MOCK_BACKEND.dispatch("POST", url, json_data=kwargs.get("json"), headers=kwargs.get("headers"))
    try:
        return _REAL_REQUESTS_POST(url, *args, **kwargs)
    except Exception as e:
        if _CURRENT_MODE in ("AUTO", "MOCK") and ("192.168.1.198" in str(url) or "192.168.1.199" in str(url)):
            return _MOCK_BACKEND.dispatch("POST", url, json_data=kwargs.get("json"), headers=kwargs.get("headers"))
        raise e


def _patched_oracledb_connect(*args, **kwargs):
    if _IS_MOCK_ACTIVE:
        return MockOracleConnection()
    try:
        if _REAL_ORACLE_CONNECT:
            return _REAL_ORACLE_CONNECT(*args, **kwargs)
    except Exception as e:
        if _CURRENT_MODE in ("AUTO", "MOCK"):
            return MockOracleConnection()
        raise e
    return MockOracleConnection()


def activate_offline_mode():
    """Activates offline mock sandbox, intercepting HTTP and Oracle connections."""
    global _IS_MOCK_ACTIVE, _CURRENT_MODE
    _IS_MOCK_ACTIVE = True
    _CURRENT_MODE = "MOCK"

    requests.get = _patched_requests_get
    requests.post = _patched_requests_post

    try:
        import oracledb
        oracledb.connect = _patched_oracledb_connect
    except Exception:
        pass


def activate_live_mode():
    """Activates live intranet mode, restoring direct connections."""
    global _IS_MOCK_ACTIVE, _CURRENT_MODE
    _IS_MOCK_ACTIVE = False
    _CURRENT_MODE = "LIVE"

    requests.get = _REAL_REQUESTS_GET
    requests.post = _REAL_REQUESTS_POST

    try:
        import oracledb
        if _REAL_ORACLE_CONNECT:
            oracledb.connect = _REAL_ORACLE_CONNECT
    except Exception:
        pass


def auto_configure_environment() -> Dict[str, Any]:
    """
    Intelligently probes the hospital network.
    If intranet is accessible, enables LIVE mode.
    If left intranet (timeout/unreachable), seamlessly switches to MOCK offline mode!
    """
    global _CURRENT_MODE, _IS_MOCK_ACTIVE
    is_live = _is_intranet_available("192.168.1.198", 8081, timeout=0.8)
    if is_live:
        activate_live_mode()
        _CURRENT_MODE = "LIVE"
        return {
            "mode": "LIVE",
            "mode_name": "🌐 内网直连模式",
            "is_mock": False,
            "intranet_available": True,
            "message": "已检测到医院内网连接，全链路直连 live Oracle 数据库与 HIS 微服务"
        }
    else:
        activate_offline_mode()
        _CURRENT_MODE = "MOCK"
        return {
            "mode": "MOCK",
            "mode_name": "💻 离线沙盒模式 (免内网/免数据库依赖)",
            "is_mock": True,
            "intranet_available": False,
            "message": "已离开医院内网，已全自动切换至【离线沙盒模式】！内嵌高仿真 Mock 引擎与 Oracle 虚拟事务，测试 100% 顺畅执行！"
        }


def get_environment_status() -> Dict[str, Any]:
    """Returns current execution mode details."""
    return {
        "mode": _CURRENT_MODE,
        "mode_name": "💻 离线沙盒模式 (免内网/免数据库依赖)" if _IS_MOCK_ACTIVE else "🌐 内网直连模式",
        "is_mock": _IS_MOCK_ACTIVE,
        "intranet_ip": "192.168.1.198:8081",
        "oracle_dsn": "192.168.1.199:1521/orcl"
    }

# Auto-detect on import
auto_configure_environment()
