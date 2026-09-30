import oracledb, json

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Find patient table / inpatient registration table
cursor.execute("SELECT table_name FROM user_tables WHERE table_name LIKE '%INPATIENT%' OR table_name LIKE '%ZY%' OR table_name LIKE '%BR%' OR table_name LIKE '%PATIENT%'")
tables = [row[0] for row in cursor.fetchall()]
print("Matching tables:", tables[:20])

# Check where 陈新强 or 12328 is stored
for t in ['ZY_BRRY', 'ZY_BRXX', 'MS_BRDA', 'ZY_RCJL', 'ZY_CWSZ', 'ZY_HQCL']:
    if t in tables:
        try:
            cursor.execute(f"SELECT * FROM {t} WHERE BRXM LIKE '%陈新强%' OR ZYH = '12328' OR BRID = '1581131'")
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description]
            print(f"Table {t} found {len(rows)} rows")
            if rows:
                print("Cols:", cols)
                for r in rows:
                    print("Row:", r)
        except Exception as e:
            pass

cursor.close()
conn.close()
