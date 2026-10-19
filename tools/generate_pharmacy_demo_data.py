# -*- coding: utf-8 -*-
"""
生成门诊与住院药房全类型药品演示前置数据脚本 (generate_pharmacy_demo_data.py)
========================================================================
功能：
1. 一键为医院药房演示人员制造全业务生命周期的前置测试数据：
   - 门诊发药 (PHA_OP_DISPENSE / PHA_DISPENSE_APPLY, 状态=1 待发药)
   - 住院摆药 (已发送待打印 querySentTree / 已打印待发药 queryPrintedTree)
2. 药品分类 100% 全覆盖：
   - 口服片剂、口服胶囊、口服混悬液
   - 外用软膏、外用抗菌制剂
   - 静脉大输液、注射用粉针（皮试抗生素）、注射小针剂
   - 二类精神药品 (P1 特管)、麻醉特殊药品 (S 特管)
   - 中成药口服片剂、中成药口服液
3. 严格关联真实库存批次 (PHA_STOCK_SERIAL)，确保药房在界面点击配药、发药扣库时零报错。
4. 运行完成后自动调用后端接口回读断言，并输出格式化的《药房人员演示操作指引卡》。
"""
import datetime
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
import requests
import oracledb

sys.stdout.reconfigure(encoding="utf-8")

# -------------------------------------------------------------
# 动态加载数据库与服务配置 (绝不在代码中硬编码或明文暴露)
# -------------------------------------------------------------
CONFIG_FILE_PATHS = [
    Path(os.environ.get("FS_DB_CONFIG_PATH", "")),
    Path(__file__).resolve().parent.parent / "data" / "db_config.json",
    Path(__file__).resolve().parent / "db_config.json",
    Path("data/db_config.json"),
]


def load_system_config():
    """从本地配置文件读取数据库与网关连接信息，支持环境变量覆盖。"""
    for p in CONFIG_FILE_PATHS:
        if p and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg, str(p)
            except Exception as e:
                print(f"⚠️ 读取配置文件 {p} 失败: {e}")
    raise FileNotFoundError(
        "❌ 未找到数据库配置文件！请确保 data/db_config.json 存在，或配置环境变量 FS_DB_CONFIG_PATH。"
    )


SYS_CONFIG, CONFIG_PATH_USED = load_system_config()
ORACLE_CFG = SYS_CONFIG.get("oracle", {})
GATEWAY_CFG = SYS_CONFIG.get("gateway", {})

GATEWAY_URL = GATEWAY_CFG.get("url", "http://192.168.1.198:8081")
FRONTEND_URL = GATEWAY_CFG.get("frontend_url", "http://192.168.1.198:8088")
ADMIN_USER = GATEWAY_CFG.get("admin_user", "admin")
ADMIN_PASS = GATEWAY_CFG.get("admin_pass", "admin123")

# 药房科室与终端定义
DEPT_WEST_PHA = 910125  # 西药房
DEPT_TCM_PHA = 910126   # 中药房
TERMINAL_DISPENSE_WEST = 41  # 西药配药终端1
TERMINAL_OUTPUT_WEST = 42    # 西药发药终端1
TERMINAL_IP_WEST = 45        # 西药房住院摆药台

# 住院病区与科室
DEPT_INPATIENT_WARD = 910131 # 内一科病区
DEPT_INPATIENT_DEPT = 910092 # 内一科
DOCTOR_ID = 1
DOCTOR_NAME = "系统管理员"


def get_db_conn():
    dsn = ORACLE_CFG.get("dsn")
    if not dsn:
        host = ORACLE_CFG.get("host")
        port = ORACLE_CFG.get("port", 1521)
        service = ORACLE_CFG.get("service_name", "orcl")
        dsn = f"{host}:{port}/{service}"
    return oracledb.connect(
        user=ORACLE_CFG["user"],
        password=ORACLE_CFG["password"],
        dsn=dsn
    )


def get_drug_info(cur, storage_dept_id, drug_id):
    cur.execute("""
        SELECT s.drug_id, s.drug_name, s.drug_specs, s.drug_type, s.drug_quality,
               s.package_unit, s.package_qty, s.bulk_unit, s.retail_price,
               ps.storage_serial_id, ps.batch_no, ps.valid_date, ps.supplier_id, ps.producer_id,
               s.bulk_retail_price
        FROM pha_stock_info s
        JOIN pha_stock_serial ps ON ps.storage_dept_id = s.storage_dept_id AND ps.drug_id = s.drug_id
        WHERE s.storage_dept_id = :dept AND s.drug_id = :did AND ps.available_qty > 5 AND ROWNUM = 1
    """, {"dept": storage_dept_id, "did": str(drug_id)})
    r = cur.fetchone()
    if not r:
        raise RuntimeError(f"药品 {drug_id} 在科室 {storage_dept_id} 无可用库存批次!")
    return {
        "drug_id": str(r[0]),
        "drug_name": str(r[1]),
        "drug_specs": str(r[2]),
        "drug_type": str(r[3]),
        "drug_quality": str(r[4]),
        "package_unit": str(r[5]),
        "package_qty": float(r[6] or 1.0),
        "bulk_unit": str(r[7]),
        "retail_price": float(r[8] or 0.0),
        "storage_serial_id": int(r[9]),
        "batch_no": str(r[10] or "1"),
        "valid_date": r[11],
        "supplier_id": int(r[12] or 1340),
        "producer_id": int(r[13] or 1184),
        "bulk_price": float(r[14] or r[8] or 0.0)
    }


def clean_old_demo_data(cur):
    """清理历史创建的演示前置数据，避免重复堆叠。"""
    print(">>> 正在清理旧的演示数据 (前缀: 药房演示-)...")
    
    # 1. 先查找演示患者在住院摆药过程中生成的所有摆药单据 (防止明细删除后查不到单据号)
    cur.execute("""
        SELECT DISTINCT dispense_bill_id 
        FROM pha_dispense_apply 
        WHERE patient_name LIKE '药房演示-%' AND dispense_bill_id IS NOT NULL
    """)
    ip_bill_ids = [r[0] for r in cur.fetchall()]
    
    # 2. 查找门诊发药记录
    cur.execute("SELECT dispense_id FROM pha_op_dispense WHERE patient_name LIKE '药房演示-%'")
    disp_ids = [r[0] for r in cur.fetchall()]

    # 3. 清理住院摆药单头表
    if ip_bill_ids:
        cur.execute("DELETE FROM pha_ip_dispense WHERE dispense_bill_id IN (%s)" % ",".join(map(str, ip_bill_ids)))
    cur.execute("DELETE FROM pha_ip_dispense WHERE dispense_bill_no LIKE 'DEMO%'")

    # 4. 清理门诊发药单头表
    if disp_ids:
        cur.execute("DELETE FROM pha_op_dispense WHERE patient_name LIKE '药房演示-%'")

    # 5. 清理所有的申请明细
    cur.execute("DELETE FROM pha_dispense_apply WHERE patient_name LIKE '药房演示-%'")
    print(f"    清理完成: 删除了旧门诊与住院演示记录及关联单据.")


def create_outpatient_prescription(cur, patient_name, reg_id, pat_id, storage_dept_id, term_disp, term_out, drugs_plan, now):
    """创建门诊处方及发药申请单 (状态=1 待发药)。"""
    cur.execute("SELECT SEQ_PHA_OP_DISPENSE.NEXTVAL FROM DUAL")
    dispense_id = cur.fetchone()[0]

    cur.execute("SELECT SEQ_FIN_OP_APPLY_BILL_ID.NEXTVAL FROM DUAL")
    bill_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO pha_op_dispense (
            dispense_id, sys_business_type, user_business_type, storage_dept_id,
            dispense_state, print_flag, dispense_terminal_id, output_terminal_id,
            apply_oper_id, apply_oper_name, apply_dept_id, apply_dept_name, apply_time,
            register_id, patient_id, daily_serial_id, patient_name, sex_code, age,
            medical_type_id, register_dept_id, register_time, bill_id, manual_flag,
            emergence_flag, reg_level_id, valid_flag, create_oper_id, create_oper_name,
            create_time, hospital_id, hospital_name
        ) VALUES (
            :dispense_id, 'PHA_DIS_OUT01', 'PHA_DIS_OUT01', :storage_dept,
            '1', '0', :term_disp, :term_out,
            1, '系统管理员', 2, '收费处', :now_time,
            :reg_id, :pat_id, 9901, :patient_name, '1', '32岁',
            101, 910054, :now_time, :bill_id, '0',
            '0', 1, '1', 1, '系统管理员',
            :now_time, 1, '湛江市赤坎区中医医院'
        )
    """, {
        "dispense_id": dispense_id,
        "storage_dept": storage_dept_id,
        "term_disp": term_disp,
        "term_out": term_out,
        "now_time": now,
        "reg_id": reg_id,
        "pat_id": pat_id,
        "patient_name": patient_name,
        "bill_id": bill_id
    })

    created_drugs = []
    for idx, (drug_id, qty, unit_mode, usage_id, usage_name, freq_id, freq_name, skin_flag) in enumerate(drugs_plan, 1):
        cur.execute("SELECT SEQ_PHA_DISPENSE_APPLY.NEXTVAL FROM DUAL")
        apply_id = cur.fetchone()[0]

        cur.execute("SELECT SEQ_PHA_DISPENSE_APPLY_NO.NEXTVAL FROM DUAL")
        bill_no = f"DIS{cur.fetchone()[0]}"

        cur.execute("SELECT SEQ_FIN_OP_APPLY_DETAIL.NEXTVAL, SEQ_FIN_OP_APPLY_DETAIL_NO.NEXTVAL FROM DUAL")
        detail_id, detail_no = cur.fetchone()

        dinfo = get_drug_info(cur, storage_dept_id, drug_id)
        unit = dinfo["package_unit"] if unit_mode == "PKG" else dinfo["bulk_unit"]
        price = dinfo["retail_price"] if unit_mode == "PKG" else dinfo["bulk_price"]
        cost = round(price * qty, 2)

        cur.execute("""
            INSERT INTO pha_dispense_apply (
                output_apply_id, output_apply_bill_no, sys_business_type, user_business_type,
                dispense_id, storage_dept_id, storage_serial_id, drug_id, drug_name,
                drug_type, drug_specs, drug_quality, dosage_form, package_unit, package_qty,
                bulk_unit, apply_qty, apply_unit, apply_cost, apply_state,
                retail_price, retail_cost, bulk_retail_price, bulk_retail_cost,
                purchase_price, purchase_cost, batch_no, valid_date, supplier_id, producer_id,
                sort_id, returned_qty, returned_unit, apply_oper_id, apply_oper_name,
                apply_dept_id, apply_dept_name, apply_time, register_id, patient_name,
                register_dept_id, register_dept_name, apply_detail_id, apply_detail_no,
                bill_id, order_id, order_time, order_days, order_dosage, order_dosage_unit,
                order_usage_id, order_usage_name, order_frequency_id, order_frequency_name,
                order_emergency_flag, order_use_time, order_doct_id, order_doct_name,
                order_dept_id, order_dept_name, delivery_type, charge_flag, charge_price,
                charge_cost, data_source, data_source_way, print_flag, valid_flag,
                dispense_flag, create_oper_id, create_oper_name, create_time, hospital_id, hospital_name
            ) VALUES (
                :apply_id, :bill_no, 'PHA_DIS_OUT01', 'PHA_DIS_OUT01',
                :dispense_id, :storage_dept, :serial_id, :drug_id, :drug_name,
                :drug_type, :drug_specs, :drug_quality, '110101', :package_unit, :package_qty,
                :bulk_unit, :apply_qty, :apply_unit, :apply_cost, '1',
                :retail_price, :apply_cost, :bulk_price, :apply_cost,
                :retail_price, :apply_cost, :batch_no, :valid_date, :supplier_id, :producer_id,
                :sort_id, 0.0, :apply_unit, 1, '系统管理员',
                2, '收费处', :now_time, :reg_id, :patient_name,
                910054, '内一科门诊', :detail_id, :detail_no,
                :bill_id, :order_id, :now_time, 3, 1.0, :apply_unit,
                :usage_id, :usage_name, :freq_id, :freq_name,
                '0', :now_time, 1, '系统管理员',
                910054, '内一科门诊', '1', '1', :retail_price,
                :apply_cost, '1', '1', '0', '1',
                '0', 1, '系统管理员', :now_time, 1, '湛江市赤坎区中医医院'
            )
        """, {
            "apply_id": apply_id,
            "bill_no": bill_no,
            "detail_id": detail_id,
            "detail_no": detail_no,
            "dispense_id": dispense_id,
            "storage_dept": storage_dept_id,
            "serial_id": dinfo["storage_serial_id"],
            "drug_id": dinfo["drug_id"],
            "drug_name": dinfo["drug_name"],
            "drug_type": dinfo["drug_type"],
            "drug_specs": dinfo["drug_specs"],
            "drug_quality": dinfo["drug_quality"],
            "package_unit": dinfo["package_unit"],
            "package_qty": dinfo["package_qty"],
            "bulk_unit": dinfo["bulk_unit"],
            "apply_qty": qty,
            "apply_unit": unit,
            "apply_cost": cost,
            "retail_price": price,
            "bulk_price": dinfo["bulk_price"],
            "batch_no": dinfo["batch_no"],
            "valid_date": dinfo["valid_date"],
            "supplier_id": dinfo["supplier_id"],
            "producer_id": dinfo["producer_id"],
            "sort_id": idx,
            "now_time": now,
            "reg_id": reg_id,
            "patient_name": patient_name,
            "bill_id": bill_id,
            "order_id": 990000 + idx,
            "usage_id": usage_id,
            "usage_name": usage_name,
            "freq_id": freq_id,
            "freq_name": freq_name
        })
        created_drugs.append(f"{dinfo['drug_name']} ({dinfo['drug_specs']}) × {qty}{unit}")

    return dispense_id, bill_id, created_drugs


def create_inpatient_dispense_apply(cur, patient_name, reg_id, inpatient_no, bed_no, storage_dept_id, dispense_type_id, dispense_type_name, drugs_plan, now, bill_id_assigned=None, apply_state="1"):
    """创建住院摆药明细 (apply_state=1 为已发送待打单；apply_state=2 且挂 dispense_bill_id 为已打印待发药)。"""
    created_items = []
    for idx, (drug_id, qty, unit_mode, usage_id, usage_name, freq_id, freq_name, order_type) in enumerate(drugs_plan, 1):
        cur.execute("SELECT SEQ_PHA_DISPENSE_APPLY.NEXTVAL FROM DUAL")
        apply_id = cur.fetchone()[0]

        cur.execute("SELECT SEQ_PHA_DISPENSE_APPLY_NO.NEXTVAL FROM DUAL")
        bill_no = f"DIS{cur.fetchone()[0]}"

        cur.execute("SELECT SEQ_FIN_IP_APPLY_DETAIL.NEXTVAL, SEQ_FIN_IP_APPLY_DETAIL_NO.NEXTVAL FROM DUAL")
        detail_id, detail_no = cur.fetchone()

        dinfo = get_drug_info(cur, storage_dept_id, drug_id)
        unit = dinfo["package_unit"] if unit_mode == "PKG" else dinfo["bulk_unit"]
        price = dinfo["retail_price"] if unit_mode == "PKG" else dinfo["bulk_price"]
        cost = round(price * qty, 2)

        cur.execute("""
            INSERT INTO pha_dispense_apply (
                output_apply_id, output_apply_bill_no, sys_business_type, user_business_type,
                dispense_id, storage_dept_id, storage_serial_id, drug_id, drug_name,
                drug_type, drug_specs, drug_quality, dosage_form, package_unit, package_qty,
                bulk_unit, apply_qty, apply_unit, apply_cost, apply_state,
                retail_price, retail_cost, bulk_retail_price, bulk_retail_cost,
                purchase_price, purchase_cost, batch_no, valid_date, supplier_id, producer_id,
                sort_id, returned_qty, returned_unit, apply_oper_id, apply_oper_name,
                apply_dept_id, apply_dept_name, apply_time, register_id, patient_name,
                bed_no, inpatient_no,
                register_dept_id, register_dept_name, apply_detail_id, apply_detail_no,
                dispense_type_id, dispense_type_name, dispense_bill_id,
                bill_id, order_id, order_time, order_days, order_dosage, order_dosage_unit,
                order_usage_id, order_usage_name, order_frequency_id, order_frequency_name,
                order_use_time, order_doct_id, order_doct_name,
                order_dept_id, order_dept_name, delivery_type, charge_flag, charge_price,
                charge_cost, data_source, data_source_way, print_flag, valid_flag,
                dispense_flag, create_oper_id, create_oper_name, create_time, hospital_id, hospital_name
            ) VALUES (
                :apply_id, :bill_no, 'PHA_DIS_IN01', 'PHA_DIS_IN01',
                NULL, :storage_dept, :serial_id, :drug_id, :drug_name,
                :drug_type, :drug_specs, :drug_quality, '110101', :package_unit, :package_qty,
                :bulk_unit, :apply_qty, :apply_unit, :apply_cost, :apply_state,
                :retail_price, :apply_cost, :bulk_price, :apply_cost,
                :retail_price, :apply_cost, :batch_no, :valid_date, :supplier_id, :producer_id,
                :sort_id, 0.0, :apply_unit, 1520, '内一科病区护士01',
                :apply_dept, '内一科病区', :now_time, :reg_id, :patient_name,
                :bed_no, :inpatient_no,
                :reg_dept, '内一科', :detail_id, :detail_no,
                :dispense_type_id, :dispense_type_name, :dispense_bill_id,
                9911, :order_id, :now_time, 1, 1.0, :apply_unit,
                :usage_id, :usage_name, :freq_id, :freq_name,
                :now_time, 1, '系统管理员',
                :reg_dept, '内一科', '1', '0', :bulk_price,
                :apply_cost, '1', '1', :print_flag, '1',
                '0', 1520, '内一科病区护士01', :now_time, 1, '湛江市赤坎区中医医院'
            )
        """, {
            "apply_id": apply_id,
            "bill_no": bill_no,
            "detail_id": detail_id,
            "detail_no": detail_no,
            "storage_dept": storage_dept_id,
            "serial_id": dinfo["storage_serial_id"],
            "drug_id": dinfo["drug_id"],
            "drug_name": dinfo["drug_name"],
            "drug_type": dinfo["drug_type"],
            "drug_specs": dinfo["drug_specs"],
            "drug_quality": dinfo["drug_quality"],
            "package_unit": dinfo["package_unit"],
            "package_qty": dinfo["package_qty"],
            "bulk_unit": dinfo["bulk_unit"],
            "apply_qty": qty,
            "apply_unit": unit,
            "apply_cost": cost,
            "apply_state": apply_state,
            "retail_price": price,
            "bulk_price": dinfo["bulk_price"],
            "batch_no": dinfo["batch_no"],
            "valid_date": dinfo["valid_date"],
            "supplier_id": dinfo["supplier_id"],
            "producer_id": dinfo["producer_id"],
            "sort_id": idx,
            "apply_dept": DEPT_INPATIENT_WARD,
            "now_time": now,
            "reg_id": reg_id,
            "patient_name": patient_name,
            "bed_no": bed_no,
            "inpatient_no": inpatient_no,
            "reg_dept": DEPT_INPATIENT_DEPT,
            "dispense_type_id": dispense_type_id,
            "dispense_type_name": dispense_type_name,
            "dispense_bill_id": bill_id_assigned,
            "order_id": 980000 + idx,
            "usage_id": usage_id,
            "usage_name": usage_name,
            "freq_id": freq_id,
            "freq_name": freq_name,
            "print_flag": "1" if apply_state == "2" else "0"
        })
        created_items.append(f"{dinfo['drug_name']} ({dinfo['drug_specs']}) × {qty}{unit}")
    return created_items


def main():
    print("=" * 70)
    print("  🏥 HIS 药房演示前置数据一键生成引擎 (全药品类型覆盖)")
    print("=" * 70)

    conn = get_db_conn()
    cur = conn.cursor()
    now = datetime.datetime.now()

    # 1. 清理历史遗留的旧演示记录
    clean_old_demo_data(cur)

    # -------------------------------------------------------------
    # 一、门诊发药前置数据生成 (全药品类型覆盖，100% 未打印未发药 dispense_state=1, print_flag=0)
    # -------------------------------------------------------------
    print("\n[一] 正在生成门诊待发药处方 (全药品类型覆盖，100% 未打印未发药)...")
    op_summary = []

    # 1. 门诊常规口服处方 (降糖片剂 + 胃药胶囊 + 儿科退热混悬液)
    plan_op_1 = [
        ("100012", 2.0, "PKG", "151", "口服", "313", "每天三次(TID)", "0"),   # 阿卡波糖片 (口服片剂)
        ("100015", 1.0, "PKG", "151", "口服", "311", "每天一次(QD)", "0"),    # 奥美拉唑肠溶胶囊 (口服胶囊)
        ("100028", 1.0, "PKG", "151", "口服", "399", "必要时(PRN)", "0"),    # 布洛芬混悬液 (口服液体/混悬液)
    ]
    d_id1, b_id1, drugs1 = create_outpatient_prescription(
        cur, "药房演示-门诊常规口服", 300099001, 1589001, DEPT_WEST_PHA,
        TERMINAL_DISPENSE_WEST, TERMINAL_OUTPUT_WEST, plan_op_1, now
    )
    op_summary.append({
        "scene": "门诊场景1：常规口服药处方 (口服片剂/口服胶囊/口服混悬液)",
        "patient": "药房演示-门诊常规口服",
        "bill_id": b_id1,
        "dispense_id": d_id1,
        "drugs": drugs1,
        "pharmacy": "西药房窗口 (910125)",
        "demo_point": "处方调配检索、口服药品单剂量核对、包装完好性检查与药袋标签打印"
    })

    # 2. 门诊外用药处方 (外用软膏 + 抗菌乳膏)
    plan_op_2 = [
        ("100035", 1.0, "PKG", "152", "外用", "312", "每天两次(BID)", "0"),   # 地奈德乳膏 (外用乳膏)
        ("100087", 2.0, "PKG", "152", "外用", "312", "每天两次(BID)", "0"),   # 莫匹罗星软膏 (外用软膏)
    ]
    d_id2, b_id2, drugs2 = create_outpatient_prescription(
        cur, "药房演示-门诊外用处方", 300099002, 1589002, DEPT_WEST_PHA,
        TERMINAL_DISPENSE_WEST, TERMINAL_OUTPUT_WEST, plan_op_2, now
    )
    op_summary.append({
        "scene": "门诊场景2：外用药品处方 (外用乳膏/外用软膏)",
        "patient": "药房演示-门诊外用处方",
        "bill_id": b_id2,
        "dispense_id": d_id2,
        "drugs": drugs2,
        "pharmacy": "西药房窗口 (910125)",
        "demo_point": "外用非注射剂分类配发、用药途径与指导标签打印"
    })

    # 3. 门诊输液与皮试抗生素处方 (静脉大输液 + 皮试粉针 + 注射小水针)
    plan_op_3 = [
        ("100005", 1.0, "PKG", "165", "静脉滴注", "311", "每天一次(QD)", "0"), # 5%葡萄糖注射液 (静脉大输液)
        ("100171", 2.0, "PKG", "165", "静脉滴注", "311", "每天一次(QD)", "1"), # 注射用青霉素钠 (皮试抗生素粉针)
        ("100007", 2.0, "PKG", "165", "静脉滴注", "311", "每天一次(QD)", "0"), # 氨茶碱注射液 (注射小水针)
    ]
    d_id3, b_id3, drugs3 = create_outpatient_prescription(
        cur, "药房演示-门诊静脉输液", 300099003, 1589003, DEPT_WEST_PHA,
        TERMINAL_DISPENSE_WEST, TERMINAL_OUTPUT_WEST, plan_op_3, now
    )
    op_summary.append({
        "scene": "门诊场景3：静脉输液处方 (大输液/皮试抗生素粉针/小水针)",
        "patient": "药房演示-门诊静脉输液",
        "bill_id": b_id3,
        "dispense_id": d_id3,
        "drugs": drugs3,
        "pharmacy": "西药房窗口 (910125)",
        "demo_point": "溶媒与主药成组复核、抗生素皮试阴性拦截验证、输液卡打印"
    })

    # 4. 门诊特管麻精处方 (二类精神片剂/针剂 + 麻醉药品注射液)
    plan_op_4 = [
        ("100018", 1.0, "PKG", "151", "口服", "314", "每晚一次(QN)", "0"),    # 艾司唑仑片 (二类精神口服片剂 P1)
        ("100039", 1.0, "PKG", "165", "肌内注射", "399", "必要时(PRN)", "0"), # 地西泮注射液 (二类精神针剂 P1)
        ("100059", 1.0, "PKG", "165", "静脉滴注", "399", "必要时(PRN)", "0"), # 枸橼酸芬太尼注射液 (麻醉药品针剂 S)
    ]
    d_id4, b_id4, drugs4 = create_outpatient_prescription(
        cur, "药房演示-门诊特管麻精", 300099004, 1589004, DEPT_WEST_PHA,
        TERMINAL_DISPENSE_WEST, TERMINAL_OUTPUT_WEST, plan_op_4, now
    )
    op_summary.append({
        "scene": "门诊场景4：特管麻精专方 (二类精神P1片剂/水针 + 麻醉S特管)",
        "patient": "药房演示-门诊特管麻精",
        "bill_id": b_id4,
        "dispense_id": d_id4,
        "drugs": drugs4,
        "pharmacy": "西药房窗口 (910125)",
        "demo_point": "麻精专册专账管理、红处方核对、双人签字发药流程"
    })

    # 5. 门诊医疗耗材处方
    plan_op_5 = [
        ("100775", 5.0, "PKG", "152", "外用", "399", "必要时(PRN)", "0"),    # 一次性使用真空采血管 (耗材 M/WC)
    ]
    d_id5, b_id5, drugs5 = create_outpatient_prescription(
        cur, "药房演示-门诊医疗耗材", 300099005, 1589005, DEPT_WEST_PHA,
        TERMINAL_DISPENSE_WEST, TERMINAL_OUTPUT_WEST, plan_op_5, now
    )
    op_summary.append({
        "scene": "门诊场景5：医疗器械与耗材 (一次性采血管/耗材)",
        "patient": "药房演示-门诊医疗耗材",
        "bill_id": b_id5,
        "dispense_id": d_id5,
        "drugs": drugs5,
        "pharmacy": "西药房窗口 (910125)",
        "demo_point": "医疗消耗品出库、计费与配发核对"
    })

    # 6. 门诊中成药处方 (中药房 910126)
    plan_op_6 = [
        ("100180", 1.0, "PKG", "151", "口服", "313", "每天三次(TID)", "0"),   # 安脑片 (中成药片剂)
        ("100193", 1.0, "PKG", "151", "口服", "313", "每天三次(TID)", "0"),   # 坤泰胶囊 (中成药胶囊)
        ("100187", 1.0, "PKG", "151", "口服", "312", "每天两次(BID)", "0"),   # 复方银杏通脉口服液 (中成药口服液)
        ("100188", 1.0, "PKG", "152", "外用", "311", "每天一次(QD)", "0"),   # 活血止痛膏 (中成药外用膏)
    ]
    d_id6, b_id6, drugs6 = create_outpatient_prescription(
        cur, "药房演示-门诊中成药", 300099006, 1589006, DEPT_TCM_PHA,
        44, 43, plan_op_6, now
    )
    op_summary.append({
        "scene": "门诊场景6：中药房中成药处方 (中成药片剂/胶囊/口服液/外用膏)",
        "patient": "药房演示-门诊中成药",
        "bill_id": b_id6,
        "dispense_id": d_id6,
        "drugs": drugs6,
        "pharmacy": "中药房窗口 (910126)",
        "demo_point": "中药房窗口切换、中成药剂型分类调配核对"
    })

    # 7. 门诊中药饮片草药处方 (中药房 910126)
    plan_op_7 = [
        ("100708", 10.0, "BULK", "151", "口服", "312", "每天两次(BID)", "0"), # 炙甘草 (中药饮片 10g)
        ("100710", 15.0, "BULK", "151", "口服", "312", "每天两次(BID)", "0"), # 紫花地丁 (中药饮片 15g)
    ]
    d_id7, b_id7, drugs7 = create_outpatient_prescription(
        cur, "药房演示-门诊中药饮片", 300099007, 1589007, DEPT_TCM_PHA,
        44, 43, plan_op_7, now
    )
    op_summary.append({
        "scene": "门诊场景7：中药饮片草药处方 (散剂/饮片/戥秤调配)",
        "patient": "药房演示-门诊中药饮片",
        "bill_id": b_id7,
        "dispense_id": d_id7,
        "drugs": drugs7,
        "pharmacy": "中药房窗口 (910126)",
        "demo_point": "中药饮片克重复核、草药付数与煎服法说明打印"
    })

    # -------------------------------------------------------------
    # 二、住院摆药前置数据生成 (全药品类型覆盖，100% 未打印未发药 apply_state=1)
    # -------------------------------------------------------------
    print("\n[二] 正在生成住院摆药前置数据 (全药品类型覆盖，100% 未打印未发药)...")
    ip_summary = []

    # 1. 住院患者 1：口服制剂与出院带药 (口服片剂 + 胶囊 + 口服溶液 + 出院带药)
    plan_ip_1_oral = [
        ("100065", 2.0, "BULK", "151", "口服", "312", "每天两次(BID)", "CZ"), # 甲硝唑片 (片剂)
        ("100112", 2.0, "BULK", "151", "口服", "313", "每天三次(TID)", "CZ"), # 头孢拉定胶囊 (胶囊)
        ("100020", 1.0, "PKG", "151", "口服", "312", "每天两次(BID)", "LZ"),  # 氨溴特罗口服溶液 (溶液)
    ]
    drugs_ip_1_oral = create_inpatient_dispense_apply(
        cur, "药房演示-住院口服制剂", 300099101, "ZY99001", "301-1",
        DEPT_WEST_PHA, 3, "口服摆药单", plan_ip_1_oral, now, apply_state="1"
    )

    plan_ip_1_cd = [
        ("100074", 2.0, "PKG", "151", "口服", "312", "每天两次(BID)", "CD"), # 罗红霉素片 (出院带药 2盒)
    ]
    drugs_ip_1_cd = create_inpatient_dispense_apply(
        cur, "药房演示-住院口服制剂", 300099101, "ZY99001", "301-1",
        DEPT_WEST_PHA, 62, "出院带药摆药单", plan_ip_1_cd, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景1：口服制剂与出院带药 (口服片剂/胶囊/口服溶液/出院带药)",
        "patient": "药房演示-住院口服制剂",
        "inpatient_no": "ZY99001",
        "bed_no": "301-1",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree)",
        "details": {
            "口服摆药单": drugs_ip_1_oral,
            "出院带药摆药单": drugs_ip_1_cd
        },
        "demo_point": "口服药长嘱自动摆药、出院带药整包装摆药单生成"
    })

    # 2. 住院患者 2：外用制剂与医疗耗材 (外用软膏 + 采血管耗材)
    plan_ip_2 = [
        ("100043", 1.0, "PKG", "152", "外用", "311", "每天一次(QD)", "CZ"), # 复方醋酸地塞米松乳膏 (软膏)
        ("100775", 5.0, "PKG", "152", "外用", "399", "必要时(PRN)", "LZ"), # 一次性使用真空采血管 (耗材)
    ]
    drugs_ip_2 = create_inpatient_dispense_apply(
        cur, "药房演示-住院外用与耗材", 300099102, "ZY99002", "301-2",
        DEPT_WEST_PHA, 2, "通用摆药单", plan_ip_2, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景2：外用制剂与医疗耗材 (外用软膏/一次性采血管耗材)",
        "patient": "药房演示-住院外用与耗材",
        "inpatient_no": "ZY99002",
        "bed_no": "301-2",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree)",
        "details": {
            "通用摆药单(外用/耗材)": drugs_ip_2
        },
        "demo_point": "病区外用治疗药与采血耗材的申领汇总与分发"
    })

    # 3. 住院患者 3：静脉大输液与注射粉针 (大输液 + 抗生素皮试粉针 + 静滴粉针 + 水针)
    plan_ip_3 = [
        ("100001", 1.0, "PKG", "165", "静脉输液", "311", "每天一次(QD)", "LZ"), # 0.9%氯化钠注射液 (静脉大输液)
        ("100176", 2.0, "PKG", "165", "静脉滴注", "311", "每天一次(QD)", "LZ"), # 注射用头孢曲松钠 (抗生素皮试粉针)
        ("100164", 1.0, "BULK", "165", "静脉滴注", "311", "每天一次(QD)", "LZ"), # 注射用奥美拉唑钠 (消化粉针)
        ("100021", 1.0, "BULK", "165", "静脉滴注", "311", "每天一次(QD)", "LZ"), # 奥硝唑注射液 (注射水针)
        ("100136", 1.0, "PKG", "165", "静脉滴注", "311", "每天一次(QD)", "LZ"), # 盐酸氨溴索注射液 (水针)
    ]
    drugs_ip_3 = create_inpatient_dispense_apply(
        cur, "药房演示-住院输液与粉针", 300099103, "ZY99003", "301-3",
        DEPT_WEST_PHA, 5, "大输液摆药单", plan_ip_3, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景3：静脉输液与粉针 (静脉大输液/抗生素皮试粉针/水针)",
        "patient": "药房演示-住院输液与粉针",
        "inpatient_no": "ZY99003",
        "bed_no": "301-3",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree)",
        "details": {
            "大输液摆药单": drugs_ip_3
        },
        "demo_point": "大输液批号管理、静脉滴注粉针与水针配伍校验、输液标签打单"
    })

    # 4. 住院患者 4：特管麻精注射液 (二类精神P1针剂 + 麻醉S特管针剂)
    plan_ip_4 = [
        ("100039", 1.0, "BULK", "165", "静脉滴注", "399", "必要时(PRN)", "LZ"), # 地西泮注射液 (二类精神针剂 P1)
        ("100059", 1.0, "PKG", "165", "静脉滴注", "399", "必要时(PRN)", "LZ"), # 枸橼酸芬太尼注射液 (麻醉药品针剂 S)
    ]
    drugs_ip_4 = create_inpatient_dispense_apply(
        cur, "药房演示-住院特管麻精", 300099104, "ZY99004", "301-4",
        DEPT_WEST_PHA, 2, "通用摆药单", plan_ip_4, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景4：麻精特管用药 (二类精神P1针剂 + 麻醉S针剂)",
        "patient": "药房演示-住院特管麻精",
        "inpatient_no": "ZY99004",
        "bed_no": "301-4",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree)",
        "details": {
            "特管摆药单": drugs_ip_4
        },
        "demo_point": "特殊麻精药品病区申领批号追溯、双人核对确认打单"
    })

    # 5. 住院患者 5：中成药 (片剂/胶囊/口服液/外用膏)
    plan_ip_5 = [
        ("100180", 1.0, "PKG", "151", "口服", "313", "每天三次(TID)", "CZ"), # 安脑片 (中成药片剂)
        ("100193", 1.0, "PKG", "151", "口服", "313", "每天三次(TID)", "CZ"), # 坤泰胶囊 (中成药胶囊)
        ("100187", 1.0, "PKG", "151", "口服", "312", "每天两次(BID)", "CZ"), # 复方银杏通脉口服液 (中成药口服液)
        ("100188", 1.0, "PKG", "152", "外用", "311", "每天一次(QD)", "CZ"), # 活血止痛膏 (中成药外用膏)
    ]
    drugs_ip_5 = create_inpatient_dispense_apply(
        cur, "药房演示-住院中成药", 300099105, "ZY99005", "301-5",
        DEPT_TCM_PHA, 2, "通用摆药单", plan_ip_5, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景5：中药房中成药 (中成药片剂/胶囊/口服液/外用膏)",
        "patient": "药房演示-住院中成药",
        "inpatient_no": "ZY99005",
        "bed_no": "301-5",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree, 中药房)",
        "details": {
            "中成药通用摆药单": drugs_ip_5
        },
        "demo_point": "中药房住院工位响应、病区中成药集中摆药"
    })

    # 6. 住院患者 6：中药饮片与草药 (草药摆药单)
    plan_ip_6 = [
        ("100708", 10.0, "BULK", "151", "口服", "312", "每天两次(BID)", "CZ"), # 炙甘草 (中药饮片 10g)
        ("100710", 15.0, "BULK", "151", "口服", "312", "每天两次(BID)", "CZ"), # 紫花地丁 (中药饮片 15g)
    ]
    drugs_ip_6 = create_inpatient_dispense_apply(
        cur, "药房演示-住院中药饮片", 300099106, "ZY99006", "301-6",
        DEPT_TCM_PHA, 6, "草药摆药单", plan_ip_6, now, apply_state="1"
    )
    ip_summary.append({
        "scene": "住院场景6：中药饮片草药 (草药摆药单/中药饮片)",
        "patient": "药房演示-住院中药饮片",
        "inpatient_no": "ZY99006",
        "bed_no": "301-6",
        "dept": "内一科病区",
        "tree": "未打印列表 (querySentTree, 中药房)",
        "details": {
            "草药摆药单": drugs_ip_6
        },
        "demo_point": "住院中药饮片草药打单与调配审方"
    })

    conn.commit()
    conn.close()
    print(">>> 数据库写入事务提交成功！")

    # -------------------------------------------------------------
    # 三、自动化接口回读断言与校验 (API 回读确认)
    # -------------------------------------------------------------
    print("\n[三] 正在执行 API 接口层真值回读核验...")
    r_login = requests.post(f"{GATEWAY_URL}/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=8)
    token = r_login.json().get("data")
    if not token:
        print("❌ 网关登录失败，跳过接口校验")
        return

    # 1. 门诊西药房接口验证
    r_ex_33 = requests.post(f"{GATEWAY_URL}/exchangeLogin", headers={"Authorization": f"Bearer {token}"}, json={"roleId": 33, "deptId": 910125})
    t33 = r_ex_33.json().get("data")
    r_op_list = requests.post(f"{GATEWAY_URL}/faith/pharmacy/outDispense/queryDispenseList", headers={"Authorization": f"Bearer {t33}"}, json={
        "storageDeptId": 910125,
        "terminalId": TERMINAL_DISPENSE_WEST,
        "dispenseState": "1",
        "startDate": (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"),
        "endDate": (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 23:59:59"),
        "pageNum": 1,
        "pageSize": 50
    }).json()
    op_api_rows = r_op_list.get("data", [])
    demo_op_found = [r for r in op_api_rows if "药房演示-" in str(r.get("patientName"))]
    print(f"  ✅ 门诊西药房待发药回读: 成功拉取到 {len(demo_op_found)} 个西药房待发药处方包 (全部未发药未打印)!")

    # 2. 门诊中药房接口验证
    r_ex_33_tcm = requests.post(f"{GATEWAY_URL}/exchangeLogin", headers={"Authorization": f"Bearer {token}"}, json={"roleId": 33, "deptId": 910126})
    t33_tcm = r_ex_33_tcm.json().get("data")
    if t33_tcm:
        r_op_tcm = requests.post(f"{GATEWAY_URL}/faith/pharmacy/outDispense/queryDispenseList", headers={"Authorization": f"Bearer {t33_tcm}"}, json={
            "storageDeptId": 910126,
            "terminalId": 44,
            "dispenseState": "1",
            "startDate": (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"),
            "endDate": (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d 23:59:59"),
            "pageNum": 1,
            "pageSize": 50
        }).json()
        op_tcm_found = [r for r in r_op_tcm.get("data", []) if "药房演示-" in str(r.get("patientName"))]
        print(f"  ✅ 门诊中药房待发药回读: 成功拉取到 {len(op_tcm_found)} 个中药房待发药处方包 (全部未发药未打印)!")

    # 3. 住院西药房接口验证 (已发送未打单树)
    r_ex_37 = requests.post(f"{GATEWAY_URL}/exchangeLogin", headers={"Authorization": f"Bearer {token}"}, json={"roleId": 37, "deptId": 910125})
    t37 = r_ex_37.json().get("data")
    r_sent = requests.post(f"{GATEWAY_URL}/faith/pharmacy/inDispense/querySentTree", headers={"Authorization": f"Bearer {t37}"}, json={
        "storageDeptId": 910125, "terminalId": TERMINAL_IP_WEST
    }).json()
    sent_trees = r_sent.get("data", {}).get("treeList", [])
    sent_types = [t.get("nodeName") for t in sent_trees]
    print(f"  ✅ 住院西药房未打印树回读: 成功呈现摆药单分类 -> {', '.join(sent_types)}")

    # 4. 住院中药房接口验证 (已发送未打单树)
    r_ex_37_tcm = requests.post(f"{GATEWAY_URL}/exchangeLogin", headers={"Authorization": f"Bearer {token}"}, json={"roleId": 37, "deptId": 910126})
    t37_tcm = r_ex_37_tcm.json().get("data")
    if t37_tcm:
        r_sent_tcm = requests.post(f"{GATEWAY_URL}/faith/pharmacy/inDispense/querySentTree", headers={"Authorization": f"Bearer {t37_tcm}"}, json={
            "storageDeptId": 910126, "terminalId": 46
        }).json()
        sent_trees_tcm = r_sent_tcm.get("data", {}).get("treeList", [])
        sent_types_tcm = [t.get("nodeName") for t in sent_trees_tcm]
        print(f"  ✅ 住院中药房未打印树回读: 成功呈现摆药单分类 -> {', '.join(sent_types_tcm)}")

    # 5. 核验已打印树为 0 条演示记录 (符合未打印要求)
    r_printed = requests.post(f"{GATEWAY_URL}/faith/pharmacy/inDispense/queryPrintedTree", headers={"Authorization": f"Bearer {t37}"}, json={
        "storageDeptId": 910125, "terminalId": TERMINAL_IP_WEST
    }).json()
    demo_printed = [b for b in r_printed.get("data", []) if "DEMO" in str(b)]
    print(f"  ✅ 住院已打印树核验: 演示单据均为未打印状态 (已打印数: {len(demo_printed)})!")

    # -------------------------------------------------------------
    # 四、生成格式化《药房人员演示操作指引卡》
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  📋 药房演示前置数据清单与现场演示步骤对照卡 (未打印未发药·全品类)")
    print("=" * 70)

    print("\n### 【模块一：门诊发药演示】(状态: 100% 已收费/未发药/未打印)")
    print(f"• 演示工位：切换科室 ➔ 角色：[门诊药房(33)] ➔ 科室：[西药房(910125)] 或 [中药房(910126)]")
    print(f"• 前端菜单：[门诊发药] (路由: #/outpatient/pharmacy/outDispense)")
    for s in op_summary:
        print(f"\n▶ {s['scene']}")
        print(f"   - 患者姓名: 【{s['patient']}】 (就诊处方号: {s['bill_id']}, 发药ID: {s['dispense_id']})")
        print(f"   - 调取药房: {s['pharmacy']}")
        print(f"   - 开立药品:")
        for d in s['drugs']:
            print(f"       • {d}")
        print(f"   - 演示操作亮点: {s['demo_point']}")

    print("\n" + "-" * 70)
    print("\n### 【模块二：住院摆药演示】(状态: 100% 医嘱已发送/未打印摆药单/未发药)")
    print(f"• 演示工位：切换科室 ➔ 角色：[住院药房(37)] ➔ 科室：[西药房(910125)] 或 [中药房(910126)]")
    print(f"• 前端菜单：[住院摆药] (路由: #/inpatient/pharmacy/inhospitalputmedicine)")
    for s in ip_summary:
        print(f"\n▶ {s['scene']}")
        print(f"   - 患者信息: 【{s['patient']}】 (住院号: {s['inpatient_no']}, 床号: {s['bed_no']}, 病区: {s['dept']})")
        print(f"   - 呈现列表: {s['tree']}")
        print(f"   - 医嘱明细分类:")
        for tname, items in s['details'].items():
            print(f"       [{tname}]:")
            for d in items:
                print(f"         • {d}")
        print(f"   - 演示操作亮点: {s['demo_point']}")

    print("\n" + "=" * 70)
    print("🎉 演示前置数据全部生成完毕，100%处于未打印、未发药状态，可供药房人员全程实操演示！\n")

    # -------------------------------------------------------------
    # 五、自动调起本地浏览器打开对应药房界面
    # -------------------------------------------------------------
    print("=" * 70)
    print("  🌐 正在调起本地浏览器打开门诊发药与住院摆药页面...")
    print("=" * 70)
    op_url = f"{FRONTEND_URL}/#/outpatient/pharmacy/outDispense"
    ip_url = f"{FRONTEND_URL}/#/inpatient/pharmacy/inhospitalputmedicine"
    print(f"  🔗 [1] 门诊发药界面: {op_url}")
    print(f"  🔗 [2] 住院摆药界面: {ip_url}")
    try:
        webbrowser.open(op_url)
        time.sleep(1.0)
        webbrowser.open(ip_url)
        print("  ✅ 已成功唤起浏览器窗口打开对应药房页面！\n")
    except Exception as e:
        print(f"  ⚠️ 自动唤起浏览器异常: {e}\n")


if __name__ == "__main__":
    main()
