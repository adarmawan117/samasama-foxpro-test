import pymysql
from db_config import DBConfig
import locale

locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8') or locale.setlocale(locale.LC_ALL, '')

try:
    conn = pymysql.connect(host=DBConfig.HOST, user=DBConfig.USER, password=DBConfig.PASSWORD, database=DBConfig.NAME, cursorclass=pymysql.cursors.DictCursor)
    c = conn.cursor()
    
    q = """
        SELECT KODE_BRG, COUNT(*) as CNT, SUM(JUMLAH) as TOT_QTY, MAX(JUMLAH) as MAX_QTY 
        FROM djual 
        WHERE KODE_BRG = '0360093' AND TGL_JUAL BETWEEN '2025-12-01' AND '2025-12-31'
        GROUP BY KODE_BRG
    """
    c.execute(q)
    print("DJUAL stats for 0360093:", c.fetchall())

    q2 = """
        SELECT * FROM BARANG WHERE KODE_BRG = '0360093' AND ACC = 'A1'
    """
    c.execute(q2)
    print("BARANG entries for 0360093:", c.fetchall())

except Exception as e:
    print('ERROR:', e)
