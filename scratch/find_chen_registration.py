import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT REGISTER_ID, INPATIENT_NO, PATIENT_NAME, DATA_STATUS, BED_NO, DEPT_NAME, NURSE_STATION_NAME, CREATE_TIME FROM FIN_IP_REGISTER WHERE PATIENT_NAME LIKE '%陈新强%'")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
print(f"Found {len(rows)} registrations for 陈新强:")
for r in rows:
    data = dict(zip(cols, [str(v) for v in r]))
    print(json.dumps(data, ensure_ascii=False, indent=2))

cursor.close()
conn.close()
