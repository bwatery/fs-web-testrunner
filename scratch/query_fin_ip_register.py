import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Get columns of FIN_IP_REGISTER
cursor.execute("SELECT column_name, data_type FROM user_tab_columns WHERE table_name = 'FIN_IP_REGISTER'")
cols = [r[0] for r in cursor.fetchall()]
print("Cols:", cols)

cursor.execute("SELECT * FROM FIN_IP_REGISTER WHERE ROWNUM <= 3")
rows = cursor.fetchall()
for r in rows:
    data = dict(zip(cols, [str(v) for v in r]))
    print("NAME:", data.get('PAT_NAME') or data.get('NAME') or data.get('PATIENT_NAME'), "INPATIENT_NO:", data.get('INPATIENT_NO'))

cursor.close()
conn.close()
