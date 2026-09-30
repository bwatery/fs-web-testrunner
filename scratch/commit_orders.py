import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'MED_IP_ORDER' AND column_name NOT IN ('ORDER_ID', 'REGISTER_ID', 'BED_NO')")
other_cols = [r[0] for r in cursor.fetchall()]

cursor.execute("DELETE FROM MED_IP_ORDER WHERE ORDER_ID IN ('5073', '5074', '5075')")
sql_5073 = f"INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)}) SELECT '5073', 300011070, '401-2', {', '.join(other_cols)} FROM MED_IP_ORDER WHERE ORDER_ID = 5070"
cursor.execute(sql_5073)

sql_5074 = f"INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)}) SELECT '5074', 300011070, '401-2', {', '.join(other_cols)} FROM MED_IP_ORDER WHERE ORDER_ID = 5069"
cursor.execute(sql_5074)

sql_5075 = f"INSERT INTO MED_IP_ORDER (ORDER_ID, REGISTER_ID, BED_NO, {', '.join(other_cols)}) SELECT '5075', 300011070, '401-2', {', '.join(other_cols)} FROM MED_IP_ORDER WHERE ORDER_ID = 5063"
cursor.execute(sql_5075)

conn.commit()
print("Committed orders 5073, 5074, 5075 successfully!")

cursor.close()
conn.close()
