import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT MAX(TO_NUMBER(ORDER_ID)) FROM MED_IP_ORDER WHERE REGEXP_LIKE(ORDER_ID, '^[0-9]+$')")
max_id = cursor.fetchone()[0]
print("Max ORDER_ID:", max_id)

cursor.close()
conn.close()
