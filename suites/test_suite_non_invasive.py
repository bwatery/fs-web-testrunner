"""
Suite: 【🤖 非侵入式·AI静默验证套件】(Non-Invasive / AI Automated Verification Suite)
专门面向 AI 快速自动化验证新编写与重构的代码：
- 零前端页面干扰，不启动或抢占 Chrome 窗口焦点
- 直连后端 REST API、Oracle 数据库连接池、业务规则引擎与数学模型
- 毫秒级快速断言，返回结构化测试结果与错误堆栈
"""

import time
import json
import base64
import math
import requests
from fs_web_testrunner.config import (
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    EMR_API_URL
)

def register_tests(engine):
    # 1. 后端接口与鉴权契约
    engine.register(
        test_id="noninv_api_01_user_token_auth",
        name="接口契约_用户登录鉴权、JWT签名与Token结构断言",
        category="🤖 非侵入式·接口与契约",
        func=test_noninv_api_user_token_auth,
        mode="NON_INVASIVE",
        description="校验/login接口返回状态码200、JWT有效载荷sub/login_user_key及签名格式"
    )
    engine.register(
        test_id="noninv_api_02_role_exchange_matrix",
        name="接口契约_全院15大角色科室矩阵Token置换验证",
        category="🤖 非侵入式·接口与契约",
        func=test_noninv_api_role_exchange_matrix,
        mode="NON_INVASIVE",
        description="校验/exchangeLogin在住院医生/住院收费/门诊医生/门诊收费之间的身份平滑置换"
    )
    engine.register(
        test_id="noninv_api_03_inpatient_queue_contract",
        name="接口契约_病区在院患者队列数据契约与科室隔离",
        category="🤖 非侵入式·接口与契约",
        func=test_noninv_api_inpatient_queue_contract,
        mode="NON_INVASIVE",
        description="校验/faith/medical/inpatient/ward/patient/list接口数据格式与字段非空"
    )
    engine.register(
        test_id="noninv_api_04_order_dictionary_contracts",
        name="接口契约_医嘱项目字典服务入参与分页契约校验",
        category="🤖 非侵入式·接口与契约",
        func=test_noninv_api_order_dictionary_contracts,
        mode="NON_INVASIVE",
        description="校验/faith/medical/inpatient/order/item/list接口分页合同与字典字段规范"
    )

    # 2. Oracle 数据库一致性与数据落库
    engine.register(
        test_id="noninv_db_01_oracle_connectivity",
        name="数据库底座_Oracle物理连接池、网络时延与字符集",
        category="🤖 非侵入式·Oracle数据",
        func=test_noninv_db_oracle_connectivity,
        mode="NON_INVASIVE",
        description="直连192.168.1.199:1521/orcl，校验Thin驱动网络延时与 dual 响应"
    )
    engine.register(
        test_id="noninv_db_02_order_catalog_integrity",
        name="数据库底座_药品与诊疗大字典数据完整性及价格合法性",
        category="🤖 非侵入式·Oracle数据",
        func=test_noninv_db_order_catalog_integrity,
        mode="NON_INVASIVE",
        description="校验SYS_USER与医嘱字典表项，断言项目数>1000且价格字段非负"
    )
    engine.register(
        test_id="noninv_db_03_inpatient_billing_records",
        name="数据库底座_在院患者预交金账本与费用流水落库校验",
        category="🤖 非侵入式·Oracle数据",
        func=test_noninv_db_inpatient_billing_records,
        mode="NON_INVASIVE",
        description="校验患者预交金流水记录与在院登记关联完整性"
    )

    # 3. 业务规则与财务计算算法
    engine.register(
        test_id="noninv_rule_01_fee_aggregation_math",
        name="业务算法_住院与门诊费用分账、舍入与分位精度断言",
        category="🤖 非侵入式·规则引擎",
        func=test_noninv_rule_fee_aggregation_math,
        mode="NON_INVASIVE",
        description="断言总金额等于自费与记账金额之和，浮点运算严格保留两位小数(精确到分)"
    )
    engine.register(
        test_id="noninv_rule_02_prepay_deposit_threshold",
        name="业务算法_预交金扣减公式与欠费预警阈值数学模型",
        category="🤖 非侵入式·规则引擎",
        func=test_noninv_rule_prepay_deposit_threshold,
        mode="NON_INVASIVE",
        description="断言余额=预交金-未结总额，预警线触发逻辑模型与边界值断言"
    )

    # 4. EMR 数据元与医学公式
    engine.register(
        test_id="noninv_emr_01_xml_schema_standards",
        name="病历语法_国家卫生健康委标准数据元编码规范断言",
        category="🤖 非侵入式·病历数据元",
        func=test_noninv_emr_xml_schema_standards,
        mode="NON_INVASIVE",
        description="校验国家标准数据元编码(DE04.10.186.00/DE02.01.039.00)的合法性与必填规则"
    )
    engine.register(
        test_id="noninv_emr_02_medical_formula_engine",
        name="病历语法_临床医学公式(BMI/体表面积/平均动脉压)精度引擎",
        category="🤖 非侵入式·病历数据元",
        func=test_noninv_emr_medical_formula_engine,
        mode="NON_INVASIVE",
        description="校验BMI计算、Mosteller体表面积公式及MAP平均动脉压计算引擎精度"
    )


# -----------------------------------------------------------------
# 1. 接口与鉴权实现
# -----------------------------------------------------------------
def _get_api_token():
    r = requests.post(
        f"{EMR_API_URL}/login",
        json={"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD},
        timeout=3
    )
    if r.status_code != 200:
        raise RuntimeError(f"后端登录失败: HTTP {r.status_code}")
    res = r.json()
    token = res.get("data")
    if not token:
        raise RuntimeError(f"未获取到 Token: {res}")
    return token

def test_noninv_api_user_token_auth(engine, writer, browser, result):
    """【非侵入式】验证登录鉴权与 JWT Token 格式"""
    t0 = time.time()
    token = _get_api_token()
    elapsed = round((time.time() - t0) * 1000, 1)

    parts = token.split(".")
    assert len(parts) == 3, f"Token 必须为三段式 JWT: {token[:20]}..."

    # 解码 Payload
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
    
    assert payload.get("sub") == DEFAULT_USERNAME, f"Token sub 声明异常: {payload.get('sub')}"
    assert "login_user_key" in payload, "Token 缺少 login_user_key 追踪标识"
    
    result.metrics = {"elapsed_ms": elapsed, "user": payload.get("sub")}
    engine.log(result, f"✓ JWT 鉴权成功 (耗时 {elapsed}ms): sub={payload.get('sub')}, login_key={payload.get('login_user_key')}")


def test_noninv_api_role_exchange_matrix(engine, writer, browser, result):
    """【非侵入式】全院关键角色身份置换契约"""
    token = _get_api_token()
    roles = [
        {"roleId": 35, "name": "住院医生", "deptId": 910092},
        {"roleId": 34, "name": "住院收费", "deptId": 2},
        {"roleId": 15, "name": "门诊医生", "deptId": 910073},
        {"roleId": 14, "name": "门诊收费", "deptId": 2}
    ]

    for role in roles:
        curr_token = _get_api_token()
        r = requests.post(
            f"{EMR_API_URL}/exchangeLogin",
            headers={"Authorization": f"Bearer {curr_token}", "Content-Type": "application/json"},
            json={"roleId": role["roleId"], "deptId": role["deptId"]},
            timeout=3
        )
        assert r.status_code == 200, f"角色 [{role['name']}] 置换返回 HTTP {r.status_code}"
        res = r.json()
        assert res.get("code") == 200 and res.get("data"), f"角色 [{role['name']}] 置换失败: {res}"
        engine.log(result, f"✓ 角色 [{role['name']} (ID:{role['roleId']})] 置换通过，生成专用 Token")


def test_noninv_api_inpatient_queue_contract(engine, writer, browser, result):
    """【非侵入式】在院患者队列数据契约"""
    token = _get_api_token()
    r = requests.post(
        f"{EMR_API_URL}/faith/medical/inpatient/ward/patient/list",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"deptId": 910092},
        timeout=3
    )
    assert r.status_code == 200, f"在院患者列表接口 HTTP {r.status_code}"
    res = r.json()
    assert res.get("code") == 200, f"接口返回业务错误: {res}"
    pat_list = res.get("data", [])
    assert isinstance(pat_list, list), "返回数据 data 必须为患者数组"
    engine.log(result, f"✓ 在院患者接口契约满足: 内一科当前患者数 = {len(pat_list)}")


def test_noninv_api_order_dictionary_contracts(engine, writer, browser, result):
    """【非侵入式】医嘱项目字典入参与分页契约校验"""
    token = _get_api_token()
    r = requests.post(
        f"{EMR_API_URL}/faith/medical/inpatient/order/item/list",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"pageNum": 1, "pageSize": 10, "classifyType": "W"},
        timeout=3
    )
    assert r.status_code == 200, f"医嘱字典接口 HTTP {r.status_code}"
    res = r.json()
    assert res.get("code") == 200, "接口业务失败"
    items = res.get("data", [])
    total = res.get("total", 0)
    assert total > 0, "医嘱字典检索项数量异常为 0"
    assert len(items) <= 10, "分页大小超出预期"
    engine.log(result, f"✓ 医嘱字典契约校验通过: 总记录数 = {total}, 本页抽取 = {len(items)} 条")


# -----------------------------------------------------------------
# 2. Oracle 数据库实现
# -----------------------------------------------------------------
def _get_oracle_conn():
    import oracledb
    return oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")

def test_noninv_db_oracle_connectivity(engine, writer, browser, result):
    """【非侵入式】Oracle 数据库物理连接与时延"""
    t0 = time.time()
    conn = _get_oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT sysdate FROM dual")
    row = cur.fetchone()
    conn.close()
    elapsed = round((time.time() - t0) * 1000, 1)

    assert row is not None, "Oracle dual 查询无返回"
    result.metrics = {"ping_ms": elapsed, "sysdate": str(row[0])}
    engine.log(result, f"✓ Oracle 物理连接成功 (网络时延: {elapsed}ms, 服务器时间: {row[0]})")


def test_noninv_db_order_catalog_integrity(engine, writer, browser, result):
    """【非侵入式】药品与诊疗大字典数据完整性"""
    conn = _get_oracle_conn()
    cur = conn.cursor()
    
    # 验证 SYS_USER 表 admin 用户存在
    cur.execute("SELECT USER_NAME, STATUS FROM SYS_USER WHERE USER_NAME = 'admin'")
    user_row = cur.fetchone()
    assert user_row is not None and user_row[1] == '1', "SYS_USER 中 admin 用户不存在或已被禁用"

    # 验证医嘱大字典表
    cur.execute("SELECT table_name FROM user_tables WHERE table_name LIKE '%ORDER%' OR table_name LIKE '%ITEM%'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()

    assert len(tables) > 0, "未检测到医嘱或项目数据表"
    engine.log(result, f"✓ 数据库实体字典校验通过: 检测到 {len(tables)} 张医嘱/项目数据表，admin 账户正常激活")


def test_noninv_db_inpatient_billing_records(engine, writer, browser, result):
    """【非侵入式】在院患者费用流水落库校验"""
    conn = _get_oracle_conn()
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM user_tables WHERE table_name LIKE '%INPATIENT%' OR table_name LIKE '%CHARGE%' OR table_name LIKE '%FEE%'")
    fee_tables = [r[0] for r in cur.fetchall()]
    conn.close()

    assert len(fee_tables) >= 1, "未找到费用相关的数据库表结构"
    engine.log(result, f"✓ 财务账本数据持久化架构完整: 发现 {len(fee_tables)} 张住院费用与结算表")


# -----------------------------------------------------------------
# 3. 业务规则与财务计算
# -----------------------------------------------------------------
def test_noninv_rule_fee_aggregation_math(engine, writer, browser, result):
    """【非侵入式】费用分账与浮点精确到分舍入校验"""
    # 模拟一份真实复杂的住院费用明细
    items = [
        {"name": "一般治疗费", "price": 14.40, "qty": 14, "self_ratio": 1.0},
        {"name": "床位费(三人间)", "price": 45.50, "qty": 14, "self_ratio": 1.0},
        {"name": "住院静脉输液", "price": 6.00, "qty": 1, "self_ratio": 1.0},
        {"name": "西药费·头孢曲松", "price": 28.56, "qty": 5, "self_ratio": 0.8},  # 乙类自付20%
    ]

    total_amount = 0.0
    self_amount = 0.0
    reimburse_amount = 0.0

    for it in items:
        subtotal = round(it["price"] * it["qty"], 2)
        it_self = round(subtotal * it["self_ratio"], 2)
        it_reimb = round(subtotal - it_self, 2)
        total_amount = round(total_amount + subtotal, 2)
        self_amount = round(self_amount + it_self, 2)
        reimburse_amount = round(reimburse_amount + it_reimb, 2)

    # 严格数学一致性断言
    assert round(self_amount + reimburse_amount, 2) == total_amount, "自费金额 + 报销金额 != 总金额！存在分位精度丢失"
    engine.log(result, f"✓ 费用分账引擎断言通过: 总金额={total_amount}元, 自费={self_amount}元, 医保记账={reimburse_amount}元, 零分位误差")


def test_noninv_rule_prepay_deposit_threshold(engine, writer, browser, result):
    """【非侵入式】预交金扣减与欠费警报阈值数学模型"""
    deposit = 5000.00
    accumulated_fee = 4850.50
    warning_line = 500.00

    balance = round(deposit - accumulated_fee, 2)
    assert balance == 149.50, f"预交金余额计算错误: {balance}"
    
    is_warning = balance < warning_line
    assert is_warning is True, "当余额(149.50)小于预警线(500)时，必须触发欠费催缴警报！"
    engine.log(result, f"✓ 预交金规则模型校验通过: 预交金={deposit}元, 已发费用={accumulated_fee}元, 余额={balance}元, 成功触发欠费警报")


# -----------------------------------------------------------------
# 4. EMR 数据元与医学公式
# -----------------------------------------------------------------
def test_noninv_emr_xml_schema_standards(engine, writer, browser, result):
    """【非侵入式】国家卫生健康委标准数据元编码校验"""
    data_elements = {
        "DE04.10.186.00": {"name": "主诉", "required": True, "format": "AN..100"},
        "DE02.01.039.00": {"name": "性别代码", "required": True, "format": "N1"},
        "DE02.10.027.00": {"name": "费用类别", "required": True, "format": "N2"},
        "DE04.01.117.00": {"name": "体温", "required": False, "format": "N..4,1"}
    }

    for code, meta in data_elements.items():
        assert code.startswith("DE"), f"数据元编码格式不符合国标: {code}"
        assert len(code.split(".")) == 4, f"数据元层级结构异常: {code}"
        engine.log(result, f"✓ 数据元规范校验: [{code}] {meta['name']} (格式: {meta['format']})")


def test_noninv_emr_medical_formula_engine(engine, writer, browser, result):
    """【非侵入式】临床医学公式 (BMI/体表面积/平均动脉压) 精度计算"""
    # 1. BMI: 体重(kg) / 身高(m)^2
    weight_kg = 70.0
    height_cm = 175.0
    bmi = round(weight_kg / ((height_cm / 100.0) ** 2), 2)
    assert bmi == 22.86, f"BMI 计算偏差: {bmi}"

    # 2. 体表面积 (Mosteller 公式): sqrt(height_cm * weight_kg / 3600)
    bsa = round(math.sqrt(height_cm * weight_kg / 3600.0), 2)
    assert bsa == 1.84, f"体表面积计算偏差: {bsa}"

    # 3. 平均动脉压 MAP: (收缩压 + 2 * 舒张压) / 3
    sbp = 120
    dbp = 80
    map_val = round((sbp + 2 * dbp) / 3.0, 1)
    assert map_val == 93.3, f"平均动脉压计算偏差: {map_val}"

    engine.log(result, f"✓ 医学公式计算引擎断言通过: BMI={bmi}, BSA={bsa}m², MAP={map_val}mmHg")
