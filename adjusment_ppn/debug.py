import sys
import os
import sqlite3
import tempfile
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from test_cases import TEST_CASES, DEFAULT_BARANG
from test_infra import create_tables, insert_data, sqlite_date_format, fetch_table, compare_table_data

script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_proses_adjustment.py")

for tc in TEST_CASES:
    if tc['id'] in ['TC-T1-17', 'TC-T2-09', 'TC-T2-11', 'TC-T2-15', 'TC-T2-19', 'TC-T3-02', 'TC-T4-02', 'TC-T4-03', 'TC-T4-04']:
        print(f"--- Running {tc['id']} ---")
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        conn = sqlite3.connect(db_path)
        conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        create_tables(conn)
        insert_data(conn, 'barang', tc['initial'].get('barang', DEFAULT_BARANG))
        insert_data(conn, 'djual', tc['initial'].get('djual', []))
        insert_data(conn, 'drjual', tc['initial'].get('drjual', []))
        insert_data(conn, 'dbeli', tc['initial'].get('dbeli', []))
        insert_data(conn, 'drbeli', tc['initial'].get('drbeli', []))
        insert_data(conn, 'tabungan_dan_hutang', tc['initial'].get('tabungan_dan_hutang', []))
        conn.close()
        
        cmd = [
            sys.executable,
            script_path,
            "--db", db_path,
            "--acc", tc['params']['--acc'],
            "--start-date", tc['params']['--start-date'],
            "--end-date", tc['params']['--end-date'],
            "--target-ppn", tc['params']['--target-ppn']
        ]
        
        subprocess.run(cmd, capture_output=True, text=True)
        
        conn = sqlite3.connect(db_path)
        conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        for table_name in ['djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang']:
            actual_rows = fetch_table(conn, table_name)
            if table_name in tc.get('expected', {}):
                expected_rows = tc['expected'][table_name]
                ok, msg = compare_table_data(actual_rows, expected_rows)
                if not ok:
                    print(f"Table '{table_name}' failed:")
                    print("EXPECTED:")
                    for r in expected_rows: print(r)
                    print("ACTUAL:")
                    for r in actual_rows: print(r)
                    print(f"MSG: {msg}")
            else:
                if table_name == 'djual' and 'djual' not in tc.get('expected', {}):
                    continue
                initial_rows = tc['initial'].get(table_name, [])
                ok, msg = compare_table_data(actual_rows, initial_rows)
                if not ok:
                    print(f"Table '{table_name}' modified (should be untouched):")
                    print("EXPECTED (Initial):")
                    for r in initial_rows: print(r)
                    print("ACTUAL:")
                    for r in actual_rows: print(r)
                    print(f"MSG: {msg}")
        conn.close()
        try: os.remove(db_path)
        except: pass

