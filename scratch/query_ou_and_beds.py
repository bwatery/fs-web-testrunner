import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT REGISTER_ID, INPATIENT_NO, PATIENT_NAME, DATA_STATUS, BED_ID, BED_NO, DEPT_NAME, NURSE_STATION_NAME FROM FIN_IP_REGISTER WHERE PATIENT_NAME = '欧伟英'")
cols = [c[0] for c in cursor.description]
rows = cursor.fetchall()
for r in rows:
    print(dict(zip(cols, [str(v) for v in r])))

cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'COM_BD_BED'")
bed_cols = [r[0] for r in cursor.fetchall()]
print("Bed cols:", bed_cols)

cursor.execute(f"SELECT BED_ID, BED_NO, WARD_ID, DEPT_ID FROM COM_BD_BED WHERE BED_NO = '401-2'")
b = cursor.fetchone()
print("Bed 401-2:", b)

cursor.close()
conn.close()
