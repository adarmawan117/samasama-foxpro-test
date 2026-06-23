import pymysql
from db_config import DBConfig
import locale

locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8') or locale.setlocale(locale.LC_ALL, '')

def format_rp(val):
    return '{:,.0f}'.format(val or 0)

try:
    print('--- INVENTORY (SOURCE DB) DJUAL (TGL 12-2025) ---')
    conn1 = pymysql.connect(host=DBConfig.HOST, user=DBConfig.USER, password=DBConfig.PASSWORD, database='INVENTORY', cursorclass=pymysql.cursors.DictCursor)
    c1 = conn1.cursor()
    
    q = """
        SELECT 
            b.PAJAK, 
            SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH)) AS TOT_OMSET,
            COUNT(*) as ROW_COUNT
        FROM djual d
        LEFT JOIN (
            SELECT KODE_BRG, ACC, 
                   MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK
            FROM BARANG 
            GROUP BY KODE_BRG, ACC
        ) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.TGL_JUAL BETWEEN '2025-12-01' AND '2025-12-31' AND d.ACC = 'A1'
        GROUP BY b.PAJAK
    """
    c1.execute(q)
    rows = c1.fetchall()
    
    total_all = 0
    for r in rows:
        pajak = r['PAJAK']
        tot = r['TOT_OMSET']
        rc = r['ROW_COUNT']
        total_all += (tot or 0)
        print(f'PAJAK: {pajak} | ROWS: {rc} | OMSET: {format_rp(tot)}')
    print(f'TOTAL OMSET: {format_rp(total_all)}')
    
    print('\n--- INVENTORY_TARGET (ADJUSTED DB) DJUAL (TGL 12-2025) ---')
    conn2 = pymysql.connect(host=DBConfig.HOST, user=DBConfig.USER, password=DBConfig.PASSWORD, database=DBConfig.NAME, cursorclass=pymysql.cursors.DictCursor)
    c2 = conn2.cursor()
    c2.execute(q)
    rows2 = c2.fetchall()
    
    total_all2 = 0
    for r in rows2:
        pajak = r['PAJAK']
        tot = r['TOT_OMSET']
        rc = r['ROW_COUNT']
        total_all2 += (tot or 0)
        print(f'PAJAK: {pajak} | ROWS: {rc} | OMSET: {format_rp(tot)}')
    print(f'TOTAL OMSET: {format_rp(total_all2)}')

except Exception as e:
    print('ERROR:', e)
