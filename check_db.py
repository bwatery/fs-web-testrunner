import oracledb

# Oracle thin mode
conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Find users in sys_user or similar
cursor.execute("SELECT table_name FROM user_tables WHERE table_name LIKE '%USER%' OR table_name LIKE '%OPER%'")
tables = cursor.fetchall()
print("User tables:", tables)

# Let's check SYS_USER if exists
for t in ["SYS_USER", "XC_SYS_USER", "USERS", "OPERATOR"]:
    try:
        cursor.execute(f"SELECT column_name FROM user_tab_columns WHERE table_name = '{t}'")
        cols = [r[0] for r in cursor.fetchall()]
        if cols:
            print(f"Table {t} columns:", cols[:10])
            cursor.execute(f"SELECT * FROM {t} WHERE ROWNUM <= 3")
            print(f"Table {t} rows:", cursor.fetchall())
    except Exception as e:
        pass

conn.close()
