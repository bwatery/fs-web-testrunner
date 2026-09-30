import oracledb

conn = oracledb.connect(user="xchis", password="xchis", dsn="192.168.1.199:1521/orcl")
cursor = conn.cursor()

# Assign Bed 401-2 to 陈新强 (REGISTER_ID: 300011070)
print("Assigning Bed 401-2 to 陈新强...")
cursor.execute("""
    UPDATE FIN_IP_REGISTER 
    SET DATA_STATUS = 'I', 
        BED_ID = 321, 
        BED_NO = '401-2', 
        DEPT_ID = 910092, 
        NURSE_STATION_ID = 910131,
        RESIDENT_DOCT_ID = 1,
        RESIDENT_DOCT_NAME = '系统管理员',
        IN_TIME = SYSDATE,
        UPDATE_TIME = SYSDATE
    WHERE REGISTER_ID = 300011070
""")

cursor.execute("""
    UPDATE COM_BD_BED 
    SET BED_STATE = 'O', 
        REGISTER_ID = 300011070,
        DOCT_ID = 1,
        UPDATE_TIME = SYSDATE
    WHERE BED_ID = 321
""")

conn.commit()
print("Bed assignment committed to Oracle successfully!")

cursor.close()
conn.close()
