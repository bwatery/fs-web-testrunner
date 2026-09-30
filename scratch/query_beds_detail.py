import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT BED_ID, BED_NO, BED_STATE, NURSE_STATION_ID, DEPT_ID, REGISTER_ID FROM COM_BD_BED WHERE BED_NO = '401-2'")
cols = [c[0] for c in cursor.description]
b = cursor.fetchone()
print("Bed 401-2:", dict(zip(cols, [str(v) for v in b])))

# Let's inspect 欧伟英's bed
cursor.execute("SELECT BED_ID, BED_NO, BED_STATE, NURSE_STATION_ID, DEPT_ID, REGISTER_ID FROM COM_BD_BED WHERE BED_NO = '401-10'")
b10 = cursor.fetchone()
print("Bed 401-10:", dict(zip(cols, [str(v) for v in b10])))

cursor.close()
conn.close()
