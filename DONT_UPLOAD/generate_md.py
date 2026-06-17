import pymysql

def generate_markdown():
    conn = pymysql.connect(host='localhost', user='root', password='root', database='INVENTORY')
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    query = """
    SELECT ACC, PERIODE, JENIS_PPN, 
           P_JUAL, REAL_JUAL, R_JUAL, JUAL, (REAL_JUAL - R_JUAL - JUAL) as SELISIH_JUAL,
           P_BELI, REAL_BELI, R_BELI, BELI, (REAL_BELI - R_BELI - BELI) as SELISIH_BELI, 
           OPR, DATEOPR 
    FROM SETOR_PAJAK_DETAIL 
    ORDER BY PERIODE, JENIS_PPN
    """
    cursor.execute(query)
    records = cursor.fetchall()
    
    md = "# Hasil Query: TABEL PROSES (KATEGORI PPN)\n\n"
    md += "| ACC | PERIODE | JENIS PPN | PPN JUAL | REAL JUAL | RET. JUAL | NET JUAL | SELISIH JUAL | PPN BELI | REAL BELI | RET. BELI | NET BELI | SELISIH BELI | OPERATOR | TGL.UPDATE |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    
    for r in records:
        md += f"| {r['ACC']} "
        md += f"| {r['PERIODE']} "
        md += f"| {r['JENIS_PPN']} "
        md += f"| {r['P_JUAL']:,.0f} "
        md += f"| {r['REAL_JUAL']:,.0f} "
        md += f"| {r['R_JUAL']:,.0f} "
        md += f"| {r['JUAL']:,.0f} "
        md += f"| {r['SELISIH_JUAL']:,.0f} "
        md += f"| {r['P_BELI']:,.0f} "
        md += f"| {r['REAL_BELI']:,.0f} "
        md += f"| {r['R_BELI']:,.0f} "
        md += f"| {r['BELI']:,.0f} "
        md += f"| {r['SELISIH_BELI']:,.0f} "
        md += f"| {r['OPR']} "
        md += f"| {r['DATEOPR']} |\n"
        
    with open(r'c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test\.docs\hasil_tabel_proses.md', 'w', encoding='utf-8') as f:
        f.write(md)
        
    print("Markdown file generated successfully.")

if __name__ == '__main__':
    generate_markdown()
