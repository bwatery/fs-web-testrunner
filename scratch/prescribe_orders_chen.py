import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Get all column names of MED_IP_ORDER
cursor.execute("SELECT column_name FROM user_tab_columns WHERE table_name = 'MED_IP_ORDER'")
cols = [r[0] for r in cursor.fetchall()]

# Filter out ORDER_ID and columns to clone from 5070 (0.9% NaCl 250ml)
cursor.execute("SELECT * FROM MED_IP_ORDER WHERE ORDER_ID = 5070")
row_5070 = cursor.fetchone()
data_5070 = dict(zip(cols, row_5070))

# Create order 5073 for 陈新强
data_5073 = dict(data_5070)
data_5073['ORDER_ID'] = '5073'
data_5073['REGISTER_ID'] = 300011070
data_5073['BED_NO'] = '401-2'
data_5073['ORDER_STATE'] = 'ET'

# Create order 5074 (丹参注射液) from 5069
cursor.execute("SELECT * FROM MED_IP_ORDER WHERE ORDER_ID = 5069")
row_5069 = cursor.fetchone()
data_5069 = dict(zip(cols, row_5069))
data_5074 = dict(data_5069)
data_5074['ORDER_ID'] = '5074'
data_5074['REGISTER_ID'] = 300011070
data_5074['BED_NO'] = '401-2'
data_5074['ORDER_STATE'] = 'ET'

# Create order 5075 (利多卡因注射液) from 5063
cursor.execute("SELECT * FROM MED_IP_ORDER WHERE ORDER_ID = 5063")
row_5063 = cursor.fetchone()
data_5063 = dict(zip(cols, row_5063))
data_5075 = dict(data_5063)
data_5075['ORDER_ID'] = '5075'
data_5075['REGISTER_ID'] = 300011070
data_5075['BED_NO'] = '401-2'
data_5075['ORDER_STATE'] = 'ET'

for d in [data_5073, data_5074, data_5075]:
    # delete if already exists
    cursor.execute(f"DELETE FROM MED_IP_ORDER WHERE ORDER_ID = '{d['ORDER_ID']}'")
    insert_cols = [c for c in cols if d.get(c) is not None]
    placeholders = [f":{c}" for c in insert_cols]
    params = {c: d[c] for c in insert_cols}
    sql = f"INSERT INTO MED_IP_ORDER ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})"
    cursor.execute(sql, params)
    print(f"Inserted order {d['ORDER_ID']} - {d['ITEM_NAME']} for 陈新强")

conn.commit()
print("All 3 orders committed successfully!")

cursor.close()
conn.close()
