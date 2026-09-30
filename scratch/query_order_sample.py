import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT * FROM MED_IP_ORDER WHERE ORDER_ID = 5070")
cols = [c[0] for c in cursor.description]
row = cursor.fetchone()
data = dict(zip(cols, [str(v) for v in row]))
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\order_5070_sample.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Saved order_5070_sample.json")

cursor.close()
conn.close()
