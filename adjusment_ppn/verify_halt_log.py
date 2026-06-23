# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import sqlite3

# Add parent and current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.calculator.adjustment_core import proses_pengurangan_fase
from test_cases import DEFAULT_BARANG
from test_infra import create_tables, insert_data

def main():
    print("Starting verification of middle-of-month halt log format...")

    # Create temporary databases
    src_fd, src_db_path = tempfile.mkstemp(suffix=".db")
    os.close(src_fd)
    
    tgt_fd, tgt_db_path = tempfile.mkstemp(suffix=".db")
    os.close(tgt_fd)

    try:
        # Initialize databases
        src_conn = sqlite3.connect(src_db_path)
        tgt_conn = sqlite3.connect(tgt_db_path)
        create_tables(src_conn)
        create_tables(tgt_conn)

        # Populate barang master
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)

        # Insert receipt data (same as test_rule_2_middle_of_month_halting)
        # J01: older (2026-06-13), target item BRG001 (10,000)
        # J02: middle (2026-06-14), target item BRG001 (10,000)
        # J03: newer (2026-06-15), non-target item BRG006 (15,000)
        djual_data = [
            {"TGL_JUAL": "2026-06-13", "F_JUAL": "J01", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-14", "F_JUAL": "J02", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J03", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', djual_data)
        insert_data(tgt_conn, 'djual', djual_data)

        src_conn.close()
        tgt_conn.close()

        # Connect using app's connection translator
        source_conn = get_db_connection(sandbox=True, database=src_db_path)
        target_conn = get_db_connection(sandbox=True, database=tgt_db_path)

        captured_logs = []
        def log_callback(msg):
            captured_logs.append(msg)

        # Trigger process phase reduction
        proses_pengurangan_fase(
            source_conn=source_conn,
            target_conn=target_conn,
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_gap=15000.0,
            category_sql_filter="b.PAJAK = 1",
            phase_name="Halt Verification Phase",
            is_sandbox=True,
            log_callback=log_callback
        )

        target_conn.close()
        source_conn.close()

        # Search for warning block in captured logs
        halt_log = None
        for log in captured_logs:
            if "=== PERINGATAN KRITIS: PENGHENTIAN PAKSA PROSES DELESI (HALT DETECTED) ===" in log:
                halt_log = log
                break

        assert halt_log is not None, "Error: Captured logs do not contain the expected critical warning block!"
        
        print("\nSUCCESS: Found critical warning block in halt logs!")
        print("\nWarning block printed below:")
        print(halt_log)
        
        sys.exit(0)

    except Exception as e:
        import traceback
        print("An error occurred during verification:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        for path in (src_db_path, tgt_db_path):
            try:
                os.remove(path)
            except OSError:
                pass

if __name__ == '__main__':
    main()
