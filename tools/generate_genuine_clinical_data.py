# -*- coding: utf-8 -*-
"""
Generate Complete Authentic Clinical Pharmacy Demo Data:
1. Inpatient (住院):
   - Patient: TEST_跨科复测01 (register_id=98026101501, inpatient_no=TC26101501, bed=T-RUN15-01)
   - Complete clinical chain: MED_IP_ORDER -> MED_IP_EXEC_ORDER -> FIN_IP_APPLY -> FIN_IP_APPLY_DETAIL -> PHA_DISPENSE_APPLY
   - Status: apply_state='1' (未打印未发药), print_flag='0', dispense_bill_id=NULL
2. Outpatient (门诊):
   - Patient: 李石凤 (register_id=300000975, age 74, 内一科门诊)
   - Complete clinical chain: MED_OP_ORDER -> FIN_OP_APPLY -> PHA_OP_DISPENSE + PHA_DISPENSE_APPLY
   - Status: dispense_state='1' (未配药未发药), print_flag='0'
"""

import json, datetime, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('data/db_config.json', 'r', encoding='utf-8') as f:
    full_cfg = json.load(f)
    ora_cfg = full_cfg['oracle']

import oracledb
conn = oracledb.connect(user=ora_cfg['user'], password=ora_cfg['password'], dsn=f"{ora_cfg['host']}:{ora_cfg['port']}/{ora_cfg['service_name']}")
cur = conn.cursor()

def get_safe_id(cur, seq_name, table_name, col_name):
    cur.execute(f"SELECT NVL(MAX({col_name}), 0) FROM {table_name}")
    max_id = cur.fetchone()[0]
    try:
        cur.execute(f"SELECT {seq_name}.NEXTVAL FROM DUAL")
        seq_id = cur.fetchone()[0]
    except Exception:
        seq_id = max_id + 1
    return max(max_id + 1, seq_id)

DEMO_DRUGS = [
    {
        "drug_id": "100017", "category": "口服片剂", "order_type": "CZ",
        "usage_id": "151", "usage_name": "口服", "freq_id": "311", "freq_name": "每天一次",
        "qty": 1.0, "apply_qty": 36.0, "unit_type": "0", "dosage": 100, "dosage_unit": "mg"
    },
    {
        "drug_id": "100112", "category": "口服胶囊", "order_type": "CZ",
        "usage_id": "151", "usage_name": "口服", "freq_id": "340", "freq_name": "每天三次",
        "qty": 1.0, "apply_qty": 50.0, "unit_type": "0", "dosage": 0.25, "dosage_unit": "g"
    },
    {
        "drug_id": "100020", "category": "口服溶液", "order_type": "CZ",
        "usage_id": "151", "usage_name": "口服", "freq_id": "311", "freq_name": "每天一次",
        "qty": 1.0, "apply_qty": 1.0, "unit_type": "1", "dosage": 10, "dosage_unit": "ml"
    },
    {
        "drug_id": "100001", "category": "静脉输液", "order_type": "CZ",
        "usage_id": "166", "usage_name": "静脉输液", "freq_id": "311", "freq_name": "每天一次",
        "qty": 1.0, "apply_qty": 1.0, "unit_type": "1", "dosage": 0.9, "dosage_unit": "g"
    },
    {
        "drug_id": "100021", "category": "注射小针剂", "order_type": "CZ",
        "usage_id": "167", "usage_name": "静脉注射", "freq_id": "320", "freq_name": "每天两次",
        "qty": 1.0, "apply_qty": 5.0, "unit_type": "0", "dosage": 0.5, "dosage_unit": "g"
    },
    {
        "drug_id": "100164", "category": "注射用粉针", "order_type": "CZ",
        "usage_id": "167", "usage_name": "静脉滴注", "freq_id": "311", "freq_name": "每天一次",
        "qty": 1.0, "apply_qty": 10.0, "unit_type": "0", "dosage": 40, "dosage_unit": "mg"
    },
    {
        "drug_id": "100107", "category": "外用药膏", "order_type": "CZ",
        "usage_id": "173", "usage_name": "外用", "freq_id": "320", "freq_name": "每天两次",
        "qty": 1.0, "apply_qty": 1.0, "unit_type": "1", "dosage": 20, "dosage_unit": "g"
    },
    {
        "drug_id": "100775", "category": "医用耗材", "order_type": "LZ",
        "usage_id": "173", "usage_name": "采血使用", "freq_id": "301", "freq_name": "必要时",
        "qty": 2.0, "apply_qty": 2.0, "unit_type": "1", "dosage": 2, "dosage_unit": "ml"
    },
    {
        "drug_id": "100018", "category": "二类精神P1", "order_type": "LZ",
        "usage_id": "151", "usage_name": "口服(睡前)", "freq_id": "312", "freq_name": "每晚一次",
        "qty": 1.0, "apply_qty": 20.0, "unit_type": "0", "dosage": 1, "dosage_unit": "mg"
    },
    {
        "drug_id": "100059", "category": "麻醉药品S", "order_type": "LZ",
        "usage_id": "167", "usage_name": "静脉推注", "freq_id": "301", "freq_name": "必要时",
        "qty": 1.0, "apply_qty": 1.0, "unit_type": "1", "dosage": 0.1, "dosage_unit": "mg"
    }
]

# Fetch stock info for each drug
stock_map = {}
for d in DEMO_DRUGS:
    cur.execute("""
        SELECT storage_serial_id, drug_id, drug_name, drug_specs, drug_type, drug_quality,
               package_unit, package_qty, bulk_unit, retail_price, bulk_retail_price,
               purchase_price, batch_no, valid_date, producer_id, supplier_id
        FROM pha_stock_serial
        WHERE storage_dept_id = 910125 AND drug_id = :1 AND storage_qty > 0
        ORDER BY storage_serial_id DESC
        FETCH FIRST 1 ROWS ONLY
    """, [d["drug_id"]])
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Stock not found for drug {d['drug_id']}")
    stock_map[d["drug_id"]] = row

print(f"Loaded stock info for {len(stock_map)} drugs successfully.")

now = datetime.datetime.now()
now_str = now.strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# 1. INPATIENT CLINICAL GENERATION
# ==========================================
ip_reg_id = 98026101501
inpatient_no = "TC26101501"
patient_name = "TEST_跨科复测01"
bed_no = "T-RUN15-01"
dept_id = 910092 # 内一科
ward_id = 910131 # 内一科病区
doct_id = 1508
doct_name = "内一科住院医生01"
nurse_id = 1520
nurse_name = "内一科病区护士01"

print("\n--- Generating Inpatient Clinical Chain ---")

# Clean existing pha_dispense_apply for this patient except 1752
cur.execute("DELETE FROM pha_dispense_apply WHERE register_id = :1 AND output_apply_id != 1752", [ip_reg_id])
print(f"Cleaned previous non-benchmark rows: {cur.rowcount}")

for d in DEMO_DRUGS:
    stk = stock_map[d["drug_id"]]
    (s_serial_id, s_did, s_dname, s_dspecs, s_dtype, s_dquality,
     s_pkg_unit, s_pkg_qty, s_bulk_unit, s_retail_price, s_bulk_price,
     s_purchase_price, s_batch_no, s_valid_date, s_producer_id, s_supplier_id) = stk

    order_id = get_safe_id(cur, 'SEQ_MED_IP_ORDER', 'MED_IP_ORDER', 'ORDER_ID')
    order_exec_id = get_safe_id(cur, 'SEQ_MED_IP_EXEC_ORDER', 'MED_IP_EXEC_ORDER', 'EXEC_ID')
    apply_id = get_safe_id(cur, 'SEQ_FIN_IP_APPLY', 'FIN_IP_APPLY', 'APPLY_ID')
    apply_detail_id = get_safe_id(cur, 'SEQ_FIN_IP_APPLY_DETAIL', 'FIN_IP_APPLY_DETAIL', 'APPLY_DETAIL_ID')
    bill_id = get_safe_id(cur, 'SEQ_FIN_IP_APPLY_BILL_ID', 'FIN_IP_APPLY', 'APPLY_BILL_ID')
    output_apply_id = get_safe_id(cur, 'SEQ_PHA_DISPENSE_APPLY', 'PHA_DISPENSE_APPLY', 'OUTPUT_APPLY_ID')

    comb_id = 14950 + (order_id % 100)

    apply_qty = d["apply_qty"]
    apply_unit = s_bulk_unit if d["unit_type"] == "0" else s_pkg_unit
    charge_price = float(s_bulk_price if d["unit_type"] == "0" else s_retail_price)
    cost = round(apply_qty * charge_price, 2)

    # 1. Insert MED_IP_ORDER
    cur.execute("""
        INSERT INTO med_ip_order (
            order_id, register_id, bed_no, dept_id, nurse_station_id, item_id, item_no, item_name,
            item_specs, drug_quality, package_unit, package_qty, bulk_unit, std_dosage, std_dosage_unit,
            item_sys_parent_type, item_fee_type, item_sys_type, order_classify_type, order_type,
            group_no, comb_id, ord_dosage, ord_dosage_unit, qty, qty_unit, unit_type, order_state,
            usage_id, usage_name, freq_id, freq_name, freq_cycle_count, freq_cycle_type, freq_days,
            item_price, item_original_price, emergency_flag, sub_material_flag, show_flag, charge_flag,
            need_confirm_flag, begin_time, first_day_count, source_type,
            storage_dept_id, storage_dept_name, recipe_dept_id, recipe_dept_name, recipe_doct_id, recipe_doct_name,
            approved_doct_id, approved_doct_name, approved_time, exec_dept_id, exec_dept_name,
            check_flag, check_time, check_oper_id, check_oper_name, confirm_flag, confirm_time,
            confirm_oper_id, confirm_oper_name, second_confirm_flag, current_deco_time, dc_flag,
            print_flag, sort_id, create_oper_id, create_oper_name, create_time,
            hospital_id, hospital_name
        ) VALUES (
            :1, :2, :3, :4, :5, :6, :7, :8,
            :9, :10, :11, :12, :13, :14, :15,
            '0', '2', 'WM', 'S', :16,
            1, :17, :18, :19, :20, :21, :22, 'CK',
            :23, :24, :25, :26, 1, 'D', 1,
            :27, :28, '0', '0', '1', '1',
            '1', :29, 1, '1',
            910125, '西药房', :30, '内一科', :31, :32,
            :33, :34, :35, :36, '内一科病区',
            '1', :37, :38, :39, '1', :40,
            :41, :42, '1', :43, '0',
            '0', 0, :44, :45, :46,
            1, '湛江市赤坎区中医医院'
        )
    """, [
        order_id, ip_reg_id, bed_no, dept_id, ward_id, s_did, s_did, s_dname,
        s_dspecs, s_dquality, s_pkg_unit, s_pkg_qty, s_bulk_unit, d["dosage"], d["dosage_unit"],
        d["order_type"], comb_id, d["dosage"], d["dosage_unit"], d["qty"], s_pkg_unit, d["unit_type"],
        d["usage_id"], d["usage_name"], d["freq_id"], d["freq_name"],
        charge_price, charge_price, now,
        dept_id, doct_id, doct_name, doct_id, doct_name, now, ward_id,
        now, doct_id, doct_name, now, nurse_id, nurse_name, now,
        doct_id, doct_name, now
    ])

    # 2. Insert MED_IP_EXEC_ORDER
    cur.execute("""
        INSERT INTO med_ip_exec_order (
            exec_id, order_id, register_id, bed_no, dept_id, nurse_station_id, item_id, item_no, item_name,
            item_specs, drug_quality, package_unit, package_qty, bulk_unit, std_dosage, std_dosage_unit,
            item_sys_parent_type, item_fee_type, item_sys_type, order_classify_type, order_type,
            group_no, comb_id, ord_dosage, ord_dosage_unit, qty, qty_unit, unit_type,
            usage_id, usage_name, freq_id, freq_name, freq_cycle_count, freq_cycle_type, freq_days,
            storage_dept_id, recipe_dept_id, recipe_doctor_id, item_price, item_original_price,
            need_confirm_flag, show_flag, emergency_flag, order_charge_flag, sub_material_flag,
            check_flag, exec_flag, charge_flag, send_flag, batch_send_flag, dispense_flag,
            confirm_flag, label_print_flag, patrol_print_flag, exec_print_flag, sort_no, valid_flag,
            update_oper_id, update_oper_name, update_time, create_oper_id, create_oper_name, create_time,
            hospital_id, hospital_name
        ) VALUES (
            :1, :2, :3, :4, :5, :6, :7, :8, :9,
            :10, :11, :12, :13, :14, :15, :16,
            '0', '2', 'WM', 'S', :17,
            1, :18, :19, :20, :21, :22, :23,
            :24, :25, :26, :27, 1, 'D', 1,
            910125, :28, :29, :30, :31,
            '0', '1', '0', '1', '0',
            '1', '0', '0', '1', '0', '0',
            '0', '0', '0', '0', 1, '1',
            :32, :33, :34, :35, :36, :37,
            1, '湛江市赤坎区中医医院'
        )
    """, [
        order_exec_id, order_id, ip_reg_id, bed_no, dept_id, ward_id, s_did, s_did, s_dname,
        s_dspecs, s_dquality, s_pkg_unit, s_pkg_qty, s_bulk_unit, d["dosage"], d["dosage_unit"],
        d["order_type"], comb_id, d["dosage"], d["dosage_unit"], d["qty"], s_pkg_unit, d["unit_type"],
        d["usage_id"], d["usage_name"], d["freq_id"], d["freq_name"],
        dept_id, doct_id, charge_price, charge_price,
        nurse_id, nurse_name, now, nurse_id, nurse_name, now
    ])

    # 3. Insert FIN_IP_APPLY
    cur.execute("""
        INSERT INTO fin_ip_apply (
            apply_id, apply_no, apply_bill_id, trans_flag, register_id, pay_type,
            medical_type_id, medical_kind_id, dept_id, nurse_station_id,
            resident_doct_id, resident_nurse_id, recipe_doct_id, recipe_dept_id,
            storage_dept_id, order_id, group_no, comb_id, ord_dosage, ord_dosage_unit,
            freq_id, freq_days, usage_id, usage_name, exec_bill_id, order_exec_dept_id,
            order_exec_time, apply_status, apply_oper_id, apply_oper_name, apply_dept_id, apply_time,
            item_sys_parent_type, item_id, item_no, item_name, item_sys_type, item_fee_type, item_specs,
            unit, retail_price, purchase_price, special_price, drug_type, drug_quality, dosage_form,
            drug_dosage, drug_dosage_unit, package_unit, package_qty, bulk_unit, bulk_unit_price,
            package_flag, item_rate, show_qty, show_unit, charge_flag, charge_time, charge_qty,
            charge_price, charge_unit, tot_cost, need_confirm_flag, confirm_qty, noback_qty,
            exec_flag, child_add_flag, indication_flag, illness_flag, data_source, data_source_way,
            balance_flag, cancel_flag, valid_flag, update_oper_id, update_oper_name, update_time,
            create_oper_id, create_oper_name, create_time, hospital_id, hospital_name
        ) VALUES (
            :1, :2, :3, '1', :4, 'O',
            101, 10101, :5, :6,
            1, :7, :8, :9,
            910125, :10, 1, :11, :12, :13,
            :14, 1, :15, :16, :17, :18,
            :19, '0', :20, :21, :22, :23,
            '0', :24, :25, :26, 'WM', '2', :27,
            :28, :29, :30, 0.0, :31, :32, '100000',
            :33, :34, :35, :36, :37, :38,
            '0', 1.0, :39, :40, '0', :41, :42,
            :43, :44, :45, '1', :46, :47,
            '0', '0', '1', '0', '1', '1',
            '0', '0', '1', :48, :49, :50,
            :51, :52, :53, 1, '湛江市赤坎区中医医院'
        )
    """, [
        apply_id, str(bill_id), bill_id, ip_reg_id,
        dept_id, ward_id, nurse_id, doct_id, dept_id,
        order_id, comb_id, d["dosage"], d["dosage_unit"],
        d["freq_id"], d["usage_id"], d["usage_name"], order_exec_id, ward_id,
        now, nurse_id, nurse_name, ward_id, now,
        s_did, s_did, s_dname, s_dspecs,
        apply_unit, s_retail_price, s_purchase_price, s_dtype, s_dquality,
        d["dosage"], d["dosage_unit"], s_pkg_unit, s_pkg_qty, s_bulk_unit, s_bulk_price,
        apply_qty, apply_unit, now, apply_qty,
        charge_price, apply_unit, cost, apply_qty, apply_qty,
        nurse_id, nurse_name, now, nurse_id, nurse_name, now
    ])

    # 4. Insert FIN_IP_APPLY_DETAIL
    cur.execute("""
        INSERT INTO fin_ip_apply_detail (
            apply_detail_id, apply_detail_no, apply_id, register_id, item_sys_parent_type,
            item_id, item_no, item_name, item_sys_type, item_fee_type, item_specs,
            unit, retail_price, purchase_price, drug_type, drug_quality, dosage_form,
            std_dosage, std_dosage_unit, package_unit, package_qty, bulk_unit, bulk_unit_price,
            batch_no, storage_serial_id, producer_id, item_rate, charge_price, charge_qty, charge_unit,
            tot_cost, own_item_flag, child_add_flag, indication_flag, illness_flag,
            package_duplication_flag, duplication_flag, charge_flag,
            update_oper_id, update_oper_name, update_time, create_oper_id, create_oper_name, create_time,
            hospital_id, hospital_name
        ) VALUES (
            :1, '1049', :2, :3, '0',
            :4, :5, :6, 'WM', '2', :7,
            :8, :9, :10, :11, :12, '100000',
            :13, :14, :15, :16, :17, :18,
            :19, :20, :21, 1.0, :22, :23, :24,
            :25, '0', '0', '1', '0',
            '0', '0', '1',
            :26, :27, :28, :29, :30, :31,
            1, '湛江市赤坎区中医医院'
        )
    """, [
        apply_detail_id, apply_id, ip_reg_id,
        s_did, s_did, s_dname, s_dspecs,
        apply_unit, s_retail_price, s_purchase_price, s_dtype, s_dquality,
        d["dosage"], d["dosage_unit"], s_pkg_unit, s_pkg_qty, s_bulk_unit, s_bulk_price,
        s_batch_no, s_serial_id, s_producer_id, charge_price, apply_qty, apply_unit,
        cost,
        nurse_id, nurse_name, now, nurse_id, nurse_name, now
    ])

    # 5. Insert PHA_DISPENSE_APPLY
    cur.execute("""
        INSERT INTO pha_dispense_apply (
            output_apply_id, output_apply_bill_no, sys_business_type, user_business_type,
            storage_dept_id, storage_serial_id, drug_id, drug_name, drug_type, drug_specs,
            drug_quality, dosage_form, package_unit, package_qty, bulk_unit, apply_qty, apply_unit,
            apply_cost, apply_state, std_dosage, std_dosage_unit, retail_price, retail_cost,
            bulk_retail_price, bulk_retail_cost, purchase_price, purchase_cost, batch_no, valid_date,
            supplier_id, producer_id, sort_id, returned_qty, returned_unit,
            apply_oper_id, apply_oper_name, apply_dept_id, apply_dept_name, apply_time,
            register_id, patient_name, bed_no, inpatient_no, register_dept_id, register_dept_name,
            apply_detail_id, apply_detail_no, dispense_type_id, dispense_type_name, bill_id,
            order_id, order_time, order_exec_id, order_comb_id, order_days, order_dosage, order_dosage_unit,
            order_usage_id, order_usage_name, order_frequency_id, order_frequency_name, order_use_time,
            order_doct_id, order_doct_name, approved_doct_id, approved_doct_name, order_dept_id, order_dept_name,
            delivery_type, charge_flag, charge_price, charge_cost, data_source, data_source_way,
            print_flag, valid_flag, dispense_flag, create_oper_id, create_oper_name, create_time,
            hospital_id, hospital_name
        ) VALUES (
            :1, :2, 'PHA_DIS_IN01', 'PHA_DIS_IN01',
            910125, :3, :4, :5, :6, :7,
            :8, '100000', :9, :10, :11, :12, :13,
            :14, '1', :15, :16, :17, :18,
            :19, :20, :21, :22, :23, :24,
            :25, :26, :27, 0.0, :28,
            :29, :30, :31, '内一科病区', :32,
            :33, :34, :35, :36, 910092, '内一科',
            :37, '1049', '2', '通用摆药单', :38,
            :39, :40, :41, :42, 1, :43, :44,
            :45, :46, :47, :48, :49,
            :50, :51, :52, :53, 910092, '内一科',
            '1', '0', :54, :55, '1', '1',
            '0', '1', '0', :56, :57, :58,
            1, '湛江市赤坎区中医医院'
        )
    """, [
        output_apply_id, f"DIS{bill_id}",
        s_serial_id, s_did, s_dname, s_dtype, s_dspecs,
        s_dquality, s_pkg_unit, s_pkg_qty, s_bulk_unit, apply_qty, apply_unit,
        cost, d["dosage"], d["dosage_unit"], s_retail_price, cost,
        s_bulk_price, cost, s_purchase_price, cost, s_batch_no, s_valid_date,
        s_supplier_id, s_producer_id, apply_detail_id, apply_unit,
        nurse_id, nurse_name, ward_id, now,
        ip_reg_id, patient_name, bed_no, inpatient_no,
        apply_detail_id, bill_id,
        order_id, now, order_exec_id, comb_id, d["dosage"], d["dosage_unit"],
        d["usage_id"], d["usage_name"], d["freq_id"], d["freq_name"], now,
        doct_id, doct_name, doct_id, doct_name,
        charge_price, cost, nurse_id, nurse_name, now
    ])
    print(f"Created Inpatient [{d['category']}] {s_dname} (Order {order_id}, Apply {output_apply_id})")

conn.commit()
print("Committed Inpatient data successfully!")

# ==========================================
# 2. OUTPATIENT CLINICAL GENERATION
# ==========================================
print("\n--- Generating Outpatient Clinical Chain ---")

op_reg_id = 300000975
op_pat_id = 1580991
op_pat_name = "李石凤"
op_dept_id = 910054 # 内一科门诊
op_doct_id = 1501   # mzys01
op_doct_name = "内一科门诊医生01"
op_see_no = 41010145

# Clean previous outpatient rows
cur.execute("DELETE FROM pha_dispense_apply WHERE register_id = :1", [op_reg_id])
cur.execute("DELETE FROM pha_op_dispense WHERE register_id = :1", [op_reg_id])
cur.execute("DELETE FROM fin_op_apply WHERE register_id = :1 AND item_sys_parent_type = '0'", [op_reg_id])
cur.execute("DELETE FROM med_op_order WHERE register_id = :1", [op_reg_id])
conn.commit()

op_dispense_id = get_safe_id(cur, 'SEQ_PHA_OP_DISPENSE', 'PHA_OP_DISPENSE', 'DISPENSE_ID')
cur.execute("SELECT NVL(MAX(bill_id), 2000) + 1 FROM pha_op_dispense")
op_bill_id = cur.fetchone()[0]

cur.execute("""
    INSERT INTO pha_op_dispense (
        dispense_id, register_id, patient_id, daily_serial_id, patient_name, sex_code, birthday, age,
        medical_type_id, register_dept_id, register_time, bill_id, manual_flag, emergence_flag,
        reg_level_id, usage_id, drug_type, drug_quality, bill_doct_id, bill_dept_id, recipe_diagnose,
        valid_flag, create_oper_id, create_oper_name, create_time, hospital_id, hospital_name,
        sys_business_type, user_business_type, storage_dept_id, dispense_state, print_flag,
        dispense_terminal_id, actual_dispense_terminal_id, output_terminal_id, actual_output_terminal_id,
        apply_oper_id, apply_oper_name, apply_dept_id, apply_dept_name, apply_time
    ) VALUES (
        :1, :2, :3, 1209, :4, '2', TO_DATE('1951-10-09', 'YYYY-MM-DD'), '74岁',
        201, :5, :6, :7, '0', '0',
        1, NULL, 'P', 'O', :8, :9, '高血压病',
        '1', :10, :11, :12, 1, '湛江市赤坎区中医医院',
        'PHA_DIS_OUT01', 'PHA_DIS_OUT01', 910125, '1', '0',
        41, 41, 42, 42,
        :13, :14, :15, '内一科门诊', :16
    )
""", [
    op_dispense_id, op_reg_id, op_pat_id, op_pat_name,
    op_dept_id, now, op_bill_id, op_doct_id, op_dept_id,
    op_doct_id, op_doct_name, now,
    op_doct_id, op_doct_name, op_dept_id, now
])

print(f"Created PHA_OP_DISPENSE: dispense_id={op_dispense_id}, bill_id={op_bill_id}")

for d in DEMO_DRUGS:
    stk = stock_map[d["drug_id"]]
    (s_serial_id, s_did, s_dname, s_dspecs, s_dtype, s_dquality,
     s_pkg_unit, s_pkg_qty, s_bulk_unit, s_retail_price, s_bulk_price,
     s_purchase_price, s_batch_no, s_valid_date, s_producer_id, s_supplier_id) = stk

    op_order_id = get_safe_id(cur, 'SEQ_MED_OP_ORDER', 'MED_OP_ORDER', 'ORDER_ID')
    op_apply_id = get_safe_id(cur, 'SEQ_FIN_OP_APPLY', 'FIN_OP_APPLY', 'APPLY_ID')
    op_output_apply_id = get_safe_id(cur, 'SEQ_PHA_DISPENSE_APPLY', 'PHA_DISPENSE_APPLY', 'OUTPUT_APPLY_ID')

    apply_qty = d["apply_qty"]
    apply_unit = s_bulk_unit if d["unit_type"] == "0" else s_pkg_unit
    charge_price = float(s_bulk_price if d["unit_type"] == "0" else s_retail_price)
    cost = round(apply_qty * charge_price, 2)
    comb_id = 14000 + (op_order_id % 100)

    # 1. Insert MED_OP_ORDER
    cur.execute("""
        INSERT INTO med_op_order (
            order_id, register_id, see_no, item_id, item_no, item_name, item_specs, drug_quality,
            package_unit, package_qty, bulk_unit, std_dosage, std_dosage_unit, dosage_form,
            item_sys_parent_type, item_fee_type, item_sys_type, user_defined_type,
            order_classify_type, order_type, bill_id, group_no, comb_id, ord_dosage,
            ord_dosage_unit, qty, qty_unit, unit_type, order_state, usage_id, usage_name,
            freq_id, freq_name, freq_cycle_count, freq_cycle_type, freq_days,
            storage_dept_id, exec_dept_id, charge_flag, print_flag, item_price, item_original_price,
            reg_dept_id, reg_doct_id, record_doct_id, recipe_dept_id, recipe_doct_id,
            emergency_flag, need_confirm_flag, sub_material_flag, show_flag, sort_id, backend_calc_sub_flag,
            create_oper_id, create_oper_name, create_time, hospital_id, hospital_name
        ) VALUES (
            :1, :2, :3, :4, :5, :6, :7, :8,
            :9, :10, :11, :12, :13, '100000',
            '0', '2', 'WM', 'P',
            'O', 'MZ', :14, 1, :15, :16,
            :17, :18, :19, :20, 'FE', :21, :22,
            :23, :24, 1, 'D', 1,
            910125, :25, '1', '0', :26, :27,
            :28, :29, :30, :31, :32,
            '0', '0', '0', '1', 1, '0',
            :33, :34, :35, 1, '湛江市赤坎区中医医院'
        )
    """, [
        op_order_id, op_reg_id, op_see_no, s_did, s_did, s_dname, s_dspecs, s_dquality,
        s_pkg_unit, s_pkg_qty, s_bulk_unit, d["dosage"], d["dosage_unit"],
        op_bill_id, comb_id, d["dosage"],
        d["dosage_unit"], d["qty"], s_pkg_unit, d["unit_type"], d["usage_id"], d["usage_name"],
        d["freq_id"], d["freq_name"],
        op_dept_id, charge_price, charge_price,
        op_dept_id, op_doct_id, op_doct_id, op_dept_id, op_doct_id,
        op_doct_id, op_doct_name, now
    ])

    # 2. Insert FIN_OP_APPLY
    cur.execute("""
        INSERT INTO fin_op_apply (
            apply_id, apply_no, apply_bill_id, trans_flag, register_id, recipe_doct_id, recipe_dept_id,
            storage_dept_id, order_id, bill_id, group_no, comb_id, ord_dosage, ord_dosage_unit,
            freq_id, freq_days, usage_id, usage_name, ord_exec_dept_id, ord_exec_time,
            emergency_flag, sub_material_flag, out_flag, apply_status, apply_oper_id, apply_dept_id, apply_time,
            item_sys_parent_type, item_id, item_no, item_name, item_sys_type, item_fee_type, item_specs,
            unit, retail_price, purchase_price, special_price, drug_type, drug_quality, dosage_form,
            std_dosage, std_dosage_unit, package_unit, package_qty, bulk_unit, bulk_unit_price,
            package_flag, item_rate, show_qty, show_unit, charge_flag, dispense_flag,
            charge_qty, charge_price, charge_unit, tot_cost, need_confirm_flag, confirm_qty, no_back_qty,
            confirm_flag, exec_max_count, exec_cur_count, exec_flag, child_add_flag, merge_flag,
            upload_si_flag, register_fee_flag, data_source, data_source_way, data_source_type,
            balance_flag, cancel_flag, valid_flag, update_oper_id, update_oper_name, update_time,
            create_oper_id, create_oper_name, create_time, hospital_id, hospital_name
        ) VALUES (
            :1, :2, :3, '1', :4, :5, :6,
            910125, :7, :8, 1, :9, :10, :11,
            :12, 1, :13, :14, :15, :16,
            '0', '0', '0', '0', :17, :18, :19,
            '0', :20, :21, :22, 'WM', '2', :23,
            :24, :25, :26, 0.0, :27, :28, '100000',
            :29, :30, :31, :32, :33, :34,
            '0', 1.0, :35, :36, '1', '0',
            :37, :38, :39, :40, '1', :41, :42,
            '0', 1, 0, '0', '0', '0',
            '1', '0', '1', '1', '0',
            '1', '0', '1', :43, :44, :45,
            :46, :47, :48, 1, '湛江市赤坎区中医医院'
        )
    """, [
        op_apply_id, int(op_bill_id), op_bill_id, op_reg_id, op_doct_id, op_dept_id,
        op_order_id, op_bill_id, comb_id, d["dosage"], d["dosage_unit"],
        d["freq_id"], d["usage_id"], d["usage_name"], op_dept_id, now,
        op_doct_id, op_dept_id, now,
        s_did, s_did, s_dname, s_dspecs,
        apply_unit, s_retail_price, s_purchase_price, s_dtype, s_dquality,
        d["dosage"], d["dosage_unit"], s_pkg_unit, s_pkg_qty, s_bulk_unit, s_bulk_price,
        apply_qty, apply_unit,
        apply_qty, charge_price, apply_unit, cost, apply_qty, apply_qty,
        op_doct_id, op_doct_name, now, op_doct_id, op_doct_name, now
    ])

    # 3. Insert PHA_DISPENSE_APPLY (Outpatient line, BED_NO is NULL)
    cur.execute("""
        INSERT INTO pha_dispense_apply (
            output_apply_id, output_apply_bill_no, sys_business_type, user_business_type,
            storage_dept_id, storage_serial_id, drug_id, drug_name, drug_type, drug_specs,
            drug_quality, dosage_form, package_unit, package_qty, bulk_unit, apply_qty, apply_unit,
            apply_cost, apply_state, std_dosage, std_dosage_unit, retail_price, retail_cost,
            bulk_retail_price, bulk_retail_cost, purchase_price, purchase_cost, batch_no, valid_date,
            supplier_id, producer_id, sort_id, returned_qty, returned_unit,
            apply_oper_id, apply_oper_name, apply_dept_id, apply_dept_name, apply_time,
            register_id, patient_name, bed_no, inpatient_no, register_dept_id, register_dept_name,
            apply_detail_id, apply_detail_no, dispense_type_id, dispense_type_name, bill_id, dispense_id,
            order_id, order_time, order_exec_id, order_comb_id, order_days, order_dosage, order_dosage_unit,
            order_usage_id, order_usage_name, order_frequency_id, order_frequency_name, order_use_time,
            order_doct_id, order_doct_name, approved_doct_id, approved_doct_name, order_dept_id, order_dept_name,
            delivery_type, charge_flag, charge_price, charge_cost, data_source, data_source_way,
            print_flag, valid_flag, dispense_flag, create_oper_id, create_oper_name, create_time,
            hospital_id, hospital_name
        ) VALUES (
            :1, :2, 'PHA_DIS_OUT01', 'PHA_DIS_OUT01',
            910125, :3, :4, :5, :6, :7,
            :8, '100000', :9, :10, :11, :12, :13,
            :14, '1', :15, :16, :17, :18,
            :19, :20, :21, :22, :23, :24,
            :25, :26, :27, 0.0, :28,
            :29, :30, :31, '内一科门诊', :32,
            :33, :34, NULL, NULL, :35, '内一科门诊',
            :36, '1049', '1', '门诊处方发药', :37, :38,
            :39, :40, NULL, :41, 1, :42, :43,
            :44, :45, :46, :47, :48,
            :49, :50, :51, :52, :53, '内一科门诊',
            '1', '1', :54, :55, '1', '1',
            '0', '1', '0', :56, :57, :58,
            1, '湛江市赤坎区中医医院'
        )
    """, [
        op_output_apply_id, f"REC{op_bill_id}",
        s_serial_id, s_did, s_dname, s_dtype, s_dspecs,
        s_dquality, s_pkg_unit, s_pkg_qty, s_bulk_unit, apply_qty, apply_unit,
        cost, d["dosage"], d["dosage_unit"], s_retail_price, cost,
        s_bulk_price, cost, s_purchase_price, cost, s_batch_no, s_valid_date,
        s_supplier_id, s_producer_id, op_apply_id, apply_unit,
        op_doct_id, op_doct_name, op_dept_id, now,
        op_reg_id, op_pat_name, op_dept_id,
        op_apply_id, op_bill_id, op_dispense_id,
        op_order_id, now, comb_id, d["dosage"], d["dosage_unit"],
        d["usage_id"], d["usage_name"], d["freq_id"], d["freq_name"], now,
        op_doct_id, op_doct_name, op_doct_id, op_doct_name, op_dept_id,
        charge_price, cost, op_doct_id, op_doct_name, now
    ])
    print(f"Created Outpatient [{d['category']}] {s_dname} (Order {op_order_id}, Apply {op_output_apply_id})")

conn.commit()
print("Committed Outpatient data successfully!")
conn.close()
