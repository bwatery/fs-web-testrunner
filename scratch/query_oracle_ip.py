import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

cursor.execute("SELECT table_name FROM user_tables WHERE table_name LIKE '%IP%' OR table_name LIKE '%BED%'")
tables = [row[0] for row in cursor.fetchall()]
print("IP/BED tables:", tables)

# Query BD_PATIENT
cursor.execute("SELECT * FROM BD_PATIENT WHERE PAT_NAME LIKE '%陈新强%' OR PAT_ID = '1581131'")
rows = cursor.fetchall()
cols = [c[0] for c in cursor.description]
print(f"BD_PATIENT found {len(rows)} rows")
if rows:
    print(dict(zip(cols[:15], rows[0][:15])))

# Query IP inpatient info tables
for t in tables:
    if 'INPATIENT' in t or 'REGISTER' in t or 'INFO' in t:
        try:
            cursor.execute(f"SELECT * FROM {t} WHERE INPATIENT_NO = '12328' OR PAT_ID = '1581131'")
            r = cursor.fetchall()
            if r:
                c = [col[0] for col in cursor.description]
                print(f"Table {t} found {len(r)} rows:", dict(zip(c[:10], r[0][:10])))
        except Exception:
            pass

cursor.close()
conn.close()
