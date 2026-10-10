"""
L1 · 探针 fixture 池

目的：把接口探针从"参数为空 → 400"的噪声里救出来。
很多查询接口在 Swagger 里没声明必填参数，但代码里强校验，导致盲调必然 400。
这里从**真实数据库**里取一组真实存在的 ID，供探针填充。

设计要点：
- 只读：全部是 SELECT，不做任何写入
- 可降级：数据库不可达时返回空池，探针退化为"仅按 Swagger 声明传参"，
  判定规则会把参数缺失归入 NEEDS_PARAM 而非缺陷，结论依然诚实
"""

import json
from typing import Any, Dict, List, Optional

# (fixture 键, 取数 SQL) —— 取第一条非空值
_HARVEST_SQL: List[tuple] = [
    ("patientId",     "SELECT PATIENT_ID FROM BD_PATIENT WHERE VALID_FLAG='1' AND ROWNUM=1"),
    ("patientId",     "SELECT PATIENT_ID FROM BD_PATIENT WHERE ROWNUM=1"),
    ("inpatientNo",   "SELECT INPATIENT_NO FROM BD_PATIENT WHERE INPATIENT_NO IS NOT NULL AND ROWNUM=1"),
    ("identifierNo",  "SELECT IDENTIFIER_NO FROM BD_PATIENT WHERE IDENTIFIER_NO IS NOT NULL AND ROWNUM=1"),
    ("registerId",    "SELECT REGISTER_ID FROM MED_IP_ORDER WHERE ROWNUM=1"),
    ("registerId",    "SELECT REGISTER_ID FROM FIN_IP_PREPAY WHERE ROWNUM=1"),
    ("orderId",       "SELECT ORDER_ID FROM MED_IP_ORDER WHERE ROWNUM=1"),
    ("itemId",        "SELECT ITEM_ID FROM MED_IP_ORDER WHERE ITEM_ID IS NOT NULL AND ROWNUM=1"),
    ("deptId",        "SELECT DEPT_ID FROM MED_IP_ORDER WHERE DEPT_ID IS NOT NULL AND ROWNUM=1"),
    ("prepayId",      "SELECT PREPAY_ID FROM FIN_IP_PREPAY WHERE ROWNUM=1"),
    ("dispenseBillId","SELECT DISPENSE_BILL_ID FROM PHA_IP_DISPENSE WHERE ROWNUM=1"),
    ("emplId",        "SELECT EMPL_ID FROM BD_PATIENT WHERE EMPL_ID IS NOT NULL AND ROWNUM=1"),
]


def harvest_from_oracle(oracle_cfg: Dict[str, Any], timeout_sec: int = 8) -> Dict[str, Any]:
    """从 Oracle 取一组真实 ID。任何异常都降级为空池，不阻断体检。"""
    pool: Dict[str, Any] = {}
    try:
        import oracledb
    except ImportError:
        return pool

    user = oracle_cfg.get("user")
    password = oracle_cfg.get("password")
    host = oracle_cfg.get("host")
    port = oracle_cfg.get("port", 1521)
    service = oracle_cfg.get("service_name") or oracle_cfg.get("service")
    if not (user and password and host and service):
        return pool

    conn = None
    try:
        conn = oracledb.connect(
            user=user, password=password, dsn=f"{host}:{port}/{service}"
        )
        cur = conn.cursor()
        for key, sql in _HARVEST_SQL:
            if key in pool:
                continue
            try:
                cur.execute(sql)
                row = cur.fetchone()
                if row and row[0] is not None:
                    pool[key] = row[0]
            except Exception:
                continue
    except Exception:
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return pool


# 常见 ID 类字段名的别名 → fixture 池键，用于模糊命中
_ALIASES = {
    "patientid": "patientId", "patient_id": "patientId", "pid": "patientId",
    "registerid": "registerId", "register_id": "registerId", "visitid": "registerId",
    "visit_id": "registerId", "inpatientid": "registerId",
    "orderid": "orderId", "order_id": "orderId",
    "itemid": "itemId", "item_id": "itemId", "chargeitemid": "itemId",
    "deptid": "deptId", "dept_id": "deptId", "departmentid": "deptId",
    "emplid": "emplId", "empl_id": "emplId", "operid": "emplId", "oper_id": "emplId",
    "userid": "emplId", "user_id": "emplId", "doctorid": "emplId",
    "prepayid": "prepayId", "prepay_id": "prepayId",
    "dispensebillid": "dispenseBillId", "dispense_bill_id": "dispenseBillId",
    "billid": "dispenseBillId", "bill_id": "dispenseBillId",
    "inpatientno": "inpatientNo", "inpatient_no": "inpatientNo",
    "identifierno": "identifierNo", "identifier_no": "identifierNo",
    "idcard": "identifierNo", "idcardno": "identifierNo",
}


def build_fixtures(oracle_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """构建探针 fixture 池：真实 ID + 别名展开。"""
    pool = harvest_from_oracle(oracle_cfg)
    if not pool:
        return {}
    expanded: Dict[str, Any] = dict(pool)
    for alias, key in _ALIASES.items():
        if key in pool:
            expanded[alias] = pool[key]
    # 常见分页与字典类兜底值
    expanded.setdefault("pageNum", 1)
    expanded.setdefault("pageSize", 10)
    expanded.setdefault("page", 1)
    expanded.setdefault("limit", 10)
    expanded.setdefault("current", 1)
    expanded.setdefault("size", 10)
    return expanded


def dump(pool: Dict[str, Any], path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: str(v) for k, v in pool.items()}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        pass
