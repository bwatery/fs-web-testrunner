import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT column_name, data_type FROM user_tab_columns WHERE table_name = 'MED_IP_ORDER'")
cols = [r[0] for r in cursor.fetchall()]
print("MED_IP_ORDER columns count:", len(cols))
print("Cols:", cols[:30])

# Query existing orders for 欧伟英 (REGISTER_ID: 547)
cursor.execute(f"SELECT {', '.join(cols[:25])} FROM MED_IP_ORDER WHERE REGISTER_ID = 547")
rows = cursor.fetchall()
print(f"Found {len(rows)} orders for 欧伟英:")
for r in rows:
    data = dict(zip(cols[:25], [str(v) for v in r]))
    print(json.dumps(data, ensure_ascii=False, indent=2))

cursor.close()
conn.close()
