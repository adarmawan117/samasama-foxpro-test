import sys
import os

# Menambahkan root folder ke sys.path agar import modul adjustment_ppn_core berhasil
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.etl.sync_manager import (
    sync_master_data, 
    sync_raw_transactions_in_range, 
    purge_transactions_in_range
)
from adjustment_ppn_core.etl.ledger_rollback import rollback_savings_in_range
from adjustment_ppn_core.schema.migrations import create_tabungan_dan_hutang_table, create_log_mutasi_tabungan_table
from adjustment_ppn_core.calculator.adjustment_dual import proses_adjustment_dual
from proses_omset_detail import ProsesOmsetLogic

import locale
locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8') or locale.setlocale(locale.LC_ALL, '')

import json
import datetime

# ==========================================
# KONFIGURASI TEST
# ==========================================
with open(os.path.join(os.path.dirname(__file__), 'connection_settings.json'), 'r') as f:
    settings = json.load(f)

source_config = settings['source']
# Ensure port is int
if 'port' in source_config:
    source_config['port'] = int(source_config['port'])

target_config = settings['target']
if 'port' in target_config:
    target_config['port'] = int(target_config['port'])

ACC = 'A1'
START_DATE = '2025-08-01'
END_DATE = '2025-08-31'
PERIODE_STR = '08-2025'

# Daftar Test Case sesuai request Anda
TEST_CASES = [
    {"name": "TARGET UP", "ppn": 4000000000, "btkp": 300000000},
    {"name": "TARGET UP JAUH", "ppn": 6000000000, "btkp": 600000000},
    {"name": "TARGET DOWN", "ppn": 3000000000, "btkp": 200000000},
    {"name": "TARGET DOWN JAUH", "ppn": 1000000000, "btkp": 100000000},
    {"name": "TARGET UP DOWN", "ppn": 6000000000, "btkp": 100000000},
    {"name": "TARGET DOWN UP", "ppn": 1000000000, "btkp": 1000000000}
]

def format_rp(val):
    if val is None or val == 0:
        return "" # Agar sesuai format yang diminta (kosong jika 0/None untuk target Lain-lain)
    return "{:,.0f}".format(val)

def fetch_current_omset(conn):
    cursor = conn.cursor()
    # Penjualan
    q_jual = """
    SELECT 
        SUM(CASE WHEN b.PAJAK IN (1, 3) THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as PPNDJ,
        SUM(CASE WHEN b.PAJAK = 2 THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as BTKPDJ,
        SUM(CASE WHEN b.PAJAK NOT IN (1, 2, 3) OR b.PAJAK IS NULL THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as LAINDJ
    FROM djual d
    LEFT JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
    WHERE d.TGL_JUAL BETWEEN %s AND %s AND d.ACC = %s
    """
    # Retur
    q_retur = """
    SELECT 
        SUM(CASE WHEN b.PAJAK IN (1, 3) THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as PPNDR,
        SUM(CASE WHEN b.PAJAK = 2 THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as BTKPDR,
        SUM(CASE WHEN b.PAJAK NOT IN (1, 2, 3) OR b.PAJAK IS NULL THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END) as LAINDR
    FROM drjual d
    LEFT JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
    WHERE d.TGL_JUAL BETWEEN %s AND %s AND d.ACC = %s
    """
    cursor.execute(q_jual, (START_DATE, END_DATE, ACC))
    dj = cursor.fetchone()
    cursor.execute(q_retur, (START_DATE, END_DATE, ACC))
    dr = cursor.fetchone()
    
    ppn = (dj[0] or 0) - (dr[0] or 0)
    btkp = (dj[1] or 0) - (dr[1] or 0)
    lain = (dj[2] or 0) - (dr[2] or 0)
    
    return ppn, btkp, lain

def dummy_callback(msg):
    pass # Disembunyikan agar log CMD tetap rapi untuk print report final

def run_all_tests():
    start_time = datetime.datetime.now()
    print("========================================")
    print(" BATCH AUTOMATION TEST: ADJUSTMENT PPN  ")
    print("========================================")
    print(f"PERIODE : {PERIODE_STR}")
    print(f"ACCOUNT : {ACC}")
    print(f"STARTED : {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    source_conn = get_db_connection(sandbox=False, **source_config)
    
    # Ambil CURRENT BASELINE
    c_ppn, c_btkp, c_lain = fetch_current_omset(source_conn)
    
    print("CURRENT")
    print("-------")
    print(f"PPN + Gunggung : {format_rp(c_ppn)}")
    print(f"BTKP           : {format_rp(c_btkp)}")
    print(f"Lain Lain      : {format_rp(c_lain)}")
    print("====================================\n")
    
    max_workers = max(1, int(os.cpu_count() * 0.7))
    
    for case in TEST_CASES:
        target_ppn = case['ppn']
        target_btkp = case['btkp']
        name = case['name']
        
        print(f"Memproses >> {name} (PPN: {format_rp(target_ppn)} | BTKP: {format_rp(target_btkp)})")
        print(" > Sinkronisasi Ulang / Reset Database Target...")
        
        # Connect Target
        target_conn = get_db_connection(sandbox=False, **target_config)
        create_tabungan_dan_hutang_table(target_conn, is_sqlite=False)
        create_log_mutasi_tabungan_table(target_conn, is_sqlite=False)
        
        # Reset DB before testing
        sync_master_data(source_conn, target_conn, is_sandbox=False)
        rollback_savings_in_range(target_conn, ACC, START_DATE, END_DATE)
        purge_transactions_in_range(target_conn, ACC, START_DATE, END_DATE)
        sync_raw_transactions_in_range(source_conn, target_conn, ACC, START_DATE, END_DATE)
        
        print(" > Menjalankan Dual-Loop Adjustment Engine...")
        proses_adjustment_dual(
            source_conn=source_conn,
            target_conn=target_conn,
            acc=ACC,
            start_date=START_DATE,
            end_date=END_DATE,
            target_ppn=float(target_ppn),
            target_btkp=float(target_btkp),
            is_sandbox=False,
            max_workers=max_workers,
            log_callback=dummy_callback
        )
        target_conn.commit()
        target_conn.close()
        
        print(" > Menjalankan Kalkulasi Reporting Proses Omset...")
        proses_logic = ProsesOmsetLogic()
        proses_logic.proses_omset(START_DATE, END_DATE, ACC, "AutoTest", dummy_callback)
        
        # REKAP RESULTS
        r_conn = get_db_connection(sandbox=False, **target_config)
        r_c = r_conn.cursor()
        r_c.execute("SELECT JENIS_PPN, JUAL FROM SETOR_PAJAK_DETAIL WHERE PERIODE = %s AND ACC = %s", (PERIODE_STR, ACC))
        res = r_c.fetchall()
        r_conn.close()
        
        res_dict = {r[0]: r[1] for r in res}
        p1 = res_dict.get('PPN (PPN + Gung gung)', 0)
        p2 = res_dict.get('BTKP', 0)
        p3 = res_dict.get('Lain-lain', 0)
        
        print(f"\n{name}")
        print("-------")
        print(f"PPN + Gunggung : {format_rp(target_ppn)}")
        print(f"BTKP           : {format_rp(target_btkp)}")
        print(f"Lain Lain      : ")
        print(f"\nRESULTS")
        print("-------")
        if p1 == 0 and p2 == 0 and p3 == 0:
            print(f"PPN + Gunggung : ")
            print(f"BTKP           : ")
            print(f"Lain Lain      : ")
        else:
            print(f"PPN + Gunggung : {format_rp(p1) if p1 else ''}")
            print(f"BTKP           : {format_rp(p2) if p2 else ''}")
            print(f"Lain Lain      : {format_rp(p3) if p3 else ''}")
        print("====================================\n")

    end_time = datetime.datetime.now()
    duration = end_time - start_time
    print("========================================")
    print(f"FINISHED : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DURATION : {duration}")
    print("========================================")

if __name__ == '__main__':
    run_all_tests()
