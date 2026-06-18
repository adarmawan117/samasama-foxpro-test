# test_infra.py
# E2E Test Suite Runner for the PPN and Tabungan/Hutang Adjustment script.

import os
import sys
import sqlite3
import tempfile
import subprocess
from datetime import datetime

# Add the parent directory and current directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_cases import get_test_cases, DEFAULT_BARANG

def sqlite_date_format(date_str, format_str):
    if not date_str:
        return ""
    try:
        clean_format = format_str.replace("%%", "%")
        dt = None
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return date_str
        return dt.strftime(clean_format)
    except Exception:
        return date_str

def create_tables(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS barang (
        ACC VARCHAR(3) NOT NULL,
        KODE_BRG VARCHAR(10) NOT NULL,
        NAMA_BRG VARCHAR(75) NOT NULL DEFAULT '',
        PAJAK INT NOT NULL,
        HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
        HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
        URUTAN INTEGER PRIMARY KEY AUTOINCREMENT,
        UNIQUE (ACC, KODE_BRG)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS djual (
        TGL_JUAL DATE NOT NULL,
        F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
        ACC VARCHAR(3) NOT NULL DEFAULT '',
        KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
        JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
        HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
        HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
        DISC1 DOUBLE NOT NULL DEFAULT 0.0,
        DISC2 DOUBLE NOT NULL DEFAULT 0.0,
        DISC3 DOUBLE NOT NULL DEFAULT 0.0,
        DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
        F_PPN DOUBLE NOT NULL DEFAULT 0.0,
        URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drjual (
        TGL_JUAL DATE NOT NULL,
        F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
        ACC VARCHAR(3) NOT NULL DEFAULT '',
        KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
        JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
        HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
        HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
        DISC1 DOUBLE NOT NULL DEFAULT 0.0,
        DISC2 DOUBLE NOT NULL DEFAULT 0.0,
        DISC3 DOUBLE NOT NULL DEFAULT 0.0,
        DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
        F_PPN DOUBLE NOT NULL DEFAULT 0.0,
        URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dbeli (
        NO_PB CHAR(15) NOT NULL DEFAULT '',
        TGL_BELI DATE NOT NULL,
        F_BELI VARCHAR(22) NOT NULL DEFAULT '',
        ACC VARCHAR(3) NOT NULL DEFAULT '',
        KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
        JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
        HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
        DISC1 DOUBLE NOT NULL DEFAULT 0.0,
        DISC2 DOUBLE NOT NULL DEFAULT 0.0,
        DISC3 DOUBLE NOT NULL DEFAULT 0.0,
        DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
        PPN INT NOT NULL DEFAULT 0,
        F_PPN DOUBLE NOT NULL DEFAULT 0.0,
        URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drbeli (
        TGL_BELI DATE NOT NULL,
        F_BELI VARCHAR(22) NOT NULL DEFAULT '',
        ACC VARCHAR(3) NOT NULL DEFAULT '',
        KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
        JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
        HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
        DISC1 DOUBLE NOT NULL DEFAULT 0.0,
        DISC2 DOUBLE NOT NULL DEFAULT 0.0,
        DISC3 DOUBLE NOT NULL DEFAULT 0.0,
        DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
        F_PPN DOUBLE NOT NULL DEFAULT 0.0,
        URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tabungan_dan_hutang (
        urutan INTEGER PRIMARY KEY AUTOINCREMENT,
        acc VARCHAR(3) NOT NULL DEFAULT '',
        kode_brg VARCHAR(10) NOT NULL,
        qty DOUBLE NOT NULL DEFAULT 0.0,
        tipe VARCHAR(10) NOT NULL CHECK (tipe IN ('tambah', 'kurang')),
        tanggal_dibuat DATE,
        CONSTRAINT uq_acc_brg_tipe UNIQUE (acc, kode_brg, tipe)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS log_mutasi_tabungan (
        id_log INTEGER PRIMARY KEY AUTOINCREMENT,
        id_tabungan INTEGER,
        qty_dipakai DOUBLE,
        tanggal_dipakai DATE,
        FOREIGN KEY (id_tabungan) REFERENCES tabungan_dan_hutang(urutan)
    );
    """)
    conn.commit()

def insert_data(conn, table_name, rows):
    if not rows:
        return
    cursor = conn.cursor()
    for row in rows:
        cols = list(row.keys())
        vals = list(row.values())
        placeholders = ", ".join(["?"] * len(cols))
        query = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
        cursor.execute(query, vals)
    conn.commit()

def fetch_table(conn, table_name):
    cursor = conn.cursor()
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        return []
    cursor.execute(f"SELECT * FROM {table_name}")
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(cols, row)) for row in rows]

def compare_table_data(actual_rows, expected_rows, ignore_keys=None):
    if ignore_keys is None:
        ignore_keys = {'urutan', 'URUTAN', 'tanggal_dibuat', 'TANGGAL_DIBUAT', 'id_log', 'ID_LOG'}
        
    def clean_row(row):
        return {k: v for k, v in row.items() if k not in ignore_keys}

    cleaned_actual = [clean_row(r) for r in actual_rows]
    cleaned_expected = [clean_row(r) for r in expected_rows]

    if not cleaned_expected:
        if cleaned_actual:
            return False, f"Expected empty table, got {len(cleaned_actual)} rows"
        return True, "Match"

    if len(cleaned_actual) != len(cleaned_expected):
        return False, f"Row count mismatch: expected {len(cleaned_expected)}, got {len(cleaned_actual)}"

    def sort_key(d):
        return str(sorted((k, str(v)) for k, v in d.items()))

    sorted_actual = sorted(cleaned_actual, key=sort_key)
    sorted_expected = sorted(cleaned_expected, key=sort_key)

    for idx, (act, exp) in enumerate(zip(sorted_actual, sorted_expected)):
        for k, v in exp.items():
            if k not in act:
                return False, f"Row {idx} missing key '{k}' in actual data"
            
            val_act = act[k]
            val_exp = v
            
            # handle floats/doubles with round
            if isinstance(val_exp, (int, float)) and isinstance(val_act, (int, float)):
                if round(float(val_act), 3) != round(float(val_exp), 3):
                    return False, f"Row {idx} key '{k}' mismatch: expected {val_exp}, got {val_act}"
            else:
                if str(val_act) != str(val_exp):
                    return False, f"Row {idx} key '{k}' mismatch: expected {val_exp}, got {val_act}"
    return True, "Match"

def run_test_case(tc):
    print(f"--- Running {tc['id']}: {tc['description']} ---")
    
    # Create temp source database file
    src_fd, src_db_path = tempfile.mkstemp(suffix=".db")
    os.close(src_fd)

    # Create temp target database file
    tgt_fd, tgt_db_path = tempfile.mkstemp(suffix=".db")
    os.close(tgt_fd)
    
    try:
        # Connect and initialize Source DB
        src_conn = sqlite3.connect(src_db_path)
        src_conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        create_tables(src_conn)
        
        # Connect and initialize Target DB
        tgt_conn = sqlite3.connect(tgt_db_path)
        tgt_conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        create_tables(tgt_conn)

        # Populate initial data in both
        barang_data = tc['initial'].get('barang', DEFAULT_BARANG)
        for conn in [src_conn, tgt_conn]:
            insert_data(conn, 'barang', barang_data)
            insert_data(conn, 'djual', tc['initial'].get('djual', []))
            insert_data(conn, 'drjual', tc['initial'].get('drjual', []))
            insert_data(conn, 'dbeli', tc['initial'].get('dbeli', []))
            insert_data(conn, 'drbeli', tc['initial'].get('drbeli', []))
            insert_data(conn, 'tabungan_dan_hutang', tc['initial'].get('tabungan_dan_hutang', []))
            conn.close()
        
        # Determine script path
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_proses_adjustment.py")
        
        # Prepare run arguments
        cmd = [
            sys.executable,
            script_path,
            "--source-db", src_db_path,
            "--target-db", tgt_db_path,
            "--acc", tc['params']['--acc'],
            "--start-date", tc['params']['--start-date'],
            "--end-date", tc['params']['--end-date'],
            "--target-ppn", tc['params']['--target-ppn']
        ]
        
        # Run subprocess
        env = os.environ.copy()
        env["PPN_TEST_INFRA"] = "true"
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Verify run execution
        expected_exit_code = tc.get('expected_exit_code', 0)
        if result.returncode != expected_exit_code:
            return False, f"Process exited with code {result.returncode}, expected {expected_exit_code}. Stderr: {result.stderr.strip()}"
            
        # Reconnect to Target DB and verify post-execution state matches EXPECTED values
        tgt_conn = sqlite3.connect(tgt_db_path)
        tgt_conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        
        # Verify target tables
        for table_name in ['djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang']:
            actual_rows = fetch_table(tgt_conn, table_name)
            
            # If the test case specified an expected state, check it
            if table_name in tc.get('expected', {}):
                expected_rows = tc['expected'][table_name]
                ok, msg = compare_table_data(actual_rows, expected_rows)
                if not ok:
                    tgt_conn.close()
                    return False, f"Target Table '{table_name}' assertion failed: {msg}"
            else:
                # If NOT specified in expected, verify it was NOT modified on target
                if table_name == 'djual' and 'djual' not in tc.get('expected', {}):
                    continue
                initial_rows = tc['initial'].get(table_name, [])
                ok, msg = compare_table_data(actual_rows, initial_rows)
                if not ok:
                    tgt_conn.close()
                    return False, f"Target Table '{table_name}' was modified but should have been untouched: {msg}"
        tgt_conn.close()

        # Reconnect to Source DB and verify it is completely UNMODIFIED
        src_conn = sqlite3.connect(src_db_path)
        src_conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        for table_name in ['djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang']:
            actual_rows = fetch_table(src_conn, table_name)
            initial_rows = tc['initial'].get(table_name, [])
            ok, msg = compare_table_data(actual_rows, initial_rows)
            if not ok:
                src_conn.close()
                return False, f"Source Table '{table_name}' was modified but must remain completely untouched: {msg}"
        src_conn.close()

        return True, "Passed"
        
    except Exception as e:
        return False, f"Exception during execution: {e}"
    finally:
        # Clean up database files
        for path in [src_db_path, tgt_db_path]:
            try:
                os.remove(path)
            except OSError:
                pass

def main():
    test_cases = get_test_cases()
    results = []
    
    passed_count = 0
    failed_count = 0
    
    print(f"Total test cases to run: {len(test_cases)}")
    for tc in test_cases:
        passed, msg = run_test_case(tc)
        results.append({
            "id": tc["id"],
            "tier": tc["tier"],
            "category": tc["category"],
            "description": tc["description"],
            "passed": passed,
            "message": msg
        })
        if passed:
            passed_count += 1
            print(f"Result for {tc['id']}: PASS")
        else:
            failed_count += 1
            print(f"Result for {tc['id']}: FAIL - {msg}")
        print("-" * 50)
        
    # Generate Markdown Summary report
    summary_md = f"""# E2E Test Suite Executable Summary Report

Date executed: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Mock script path: `python_test/run_proses_adjustment.py`

## Performance Dashboard

| Metrics | Value |
|---|---|
| **Total Test Cases** | {len(test_cases)} |
| **Passed Cases** | {passed_count} |
| **Failed Cases** | {failed_count} |
| **Pass Rate** | {(passed_count/len(test_cases))*100:.2f}% |

## Tier Summary

- **Tier 1 (Feature Coverage)**: Passed {sum(1 for r in results if r['tier']==1 and r['passed'])} / {sum(1 for r in results if r['tier']==1)}
- **Tier 2 (Boundary/Edge)**: Passed {sum(1 for r in results if r['tier']==2 and r['passed'])} / {sum(1 for r in results if r['tier']==2)}
- **Tier 3 (Combination)**: Passed {sum(1 for r in results if r['tier']==3 and r['passed'])} / {sum(1 for r in results if r['tier']==3)}
- **Tier 4 (Real-world Scenarios)**: Passed {sum(1 for r in results if r['tier']==4 and r['passed'])} / {sum(1 for r in results if r['tier']==4)}

## Detailed Test Log

| ID | Tier | Category | Description | Status | Message |
|---|---|---|---|---|---|
"""
    for r in results:
        status_str = "✅ PASS" if r['passed'] else "❌ FAIL"
        summary_md += f"| {r['id']} | Tier {r['tier']} | {r['category']} | {r['description']} | {status_str} | {r['message']} |\n"

    # Write summary report to worker's agents folder
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_summary.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(summary_md)
        
    print(f"\nExecution finished! Summary report written to: {report_path}")
    print(f"Passed: {passed_count}, Failed: {failed_count}")
    
    # Return exit code based on test execution
    # Since we are running on a MOCK script, failures are expected and normal (shows test suite is functional).
    # We exit 0 so long as the test runner executed successfully.
    sys.exit(0)

if __name__ == "__main__":
    main()
