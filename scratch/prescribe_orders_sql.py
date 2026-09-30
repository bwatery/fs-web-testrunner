import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Get all column names except ORDER_ID, REGISTER_ID, BED_NO
cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'MED_IP_ORDER' AND column_name NOT IN ('ORDER_ID', 'REGISTER_ID', 'BED_NO')")
other_cols = [r[0] for r in cursor.fetchall()]

# Copy 5070 -> 5073 (0.9% NaCl 250ml)
cursor.execute("DELETE FROM MED_IP_ORDER WHERE ORDER_ID IN ('5073', '5074', '5075')")
sql_5073 = f"""
    INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)})
    SELECT '5073', 300011070, '401-2', {', '.join(other_cols)}
    FROM MED_IP_ORDER WHERE ORDER_ID = 5070
"""
cursor.execute(sql_5073)
print("Copied order 5073 (0.9% NaCl 250ml)")

# Copy 5069 -> 5074 (丹参注射液)
sql_5074 = f"""
    INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)})
    SELECT '5074', 300011070, '401-2', {', '.join(other_cols)}
    FROM MED_IP_ORDER WHERE ORDER_ID = 5069
"""
cursor.execute(sql_5074)
print("Copied order 5074 (丹参注射液)")

# Copy 5063 -> 5075 (利多卡因注射液)
sql_5075 = f"""
    INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)})
    SELECT '5075', 300011070, '401-2', {', '.join(other_cols)}
    FROM MED_IP_ORDER WHERE ORDER_ID = 5063
"""
cursor.execute(sql_5075)
print("Copied order 5075 (利多卡因注射液)")

# Also create EXEC_ORDER in MED_IP_EXEC_ORDER so Nurse Workstation can query and execute
cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'MED_IP_EXEC_ORDER' AND column_name NOT IN ('EXEC_ORDER_ID', 'ORDER_ID', 'REGISTER_ID', 'BED_NO')")
exec_cols = [r[0] for r in cursor.fetchall()]

cursor.execute("DELETE FROM MED_IP_EXEC_ORDER WHERE ORDER_ID IN ('5073', '5074', '5075')")
# Check if there are sample exec orders for 5070
cursor.execute("SELECT COUNT(*) FROM MED_IP_EXEC_ORDER WHERE ORDER_ID = 5070")
if cursor.fetchone()[0] > 0:
    cursor.execute(f"""
        INSERT INTO MED_IP_EXEC_ORDER (EXEC_ORDER_ID, ORDER_ID, REGISTER_ID, BED_NO, {', '.join(exec_cols)})
        SELECT '90073', '5073', 300011070, '401-2', {', '.join(exec_cols)}
        FROM MED_IP_EXEC_ORDER WHERE ORDER_ID = 5070 AND ROWNUM = 1
    """)
    print("Created EXEC_ORDER for 5073")

conn.commit()
print("All orders and exec orders committed successfully!")

cursor.close()
conn.close()
