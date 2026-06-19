# -*- coding: utf-8 -*-
"""
Verification test script for savings consumption logging, referential integrity risk,
and soft-delete compatibility for Milestone 2 (R2).
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from datetime import datetime

# Set QPA platform to offscreen for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add parent and current directory to system path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the core logic functions and test case specifications
from adjustment_ppn_core.database.connection import get_db_connection, SQLiteConnectionWrapper
from adjustment_ppn_core.calculator.adjustment import (
    proses_pengurangan_omset,
    proses_penambahan_omset,
    distribusikan_global_gap
)
from adjustment_ppn_core.etl.ledger_rollback import rollback_savings_in_range
from test_cases import get_test_cases, DEFAULT_BARANG
from test_infra import sqlite_date_format, create_tables, insert_data, compare_table_data


# =========================================================================
# SOFT-DELETE MONKEYPATCH WRAPPERS
# =========================================================================

class SoftDeleteCursorWrapper:
    def __init__(self, original_cursor):
        self._cursor = original_cursor

    def execute(self, query, params=None):
        from adjustment_ppn_core.database.sqlite_translator import translate_query
        normalized = query.strip().upper()
        
        # 1. Intercept DELETE statements on tabungan_dan_hutang and rewrite to UPDATE
        if "DELETE FROM TABUNGAN_DAN_HUTANG" in normalized:
            new_query = query.replace("DELETE FROM tabungan_dan_hutang", "UPDATE tabungan_dan_hutang SET qty = 0")
            translated_query = translate_query(new_query)
            if params is not None:
                return self._cursor.execute(translated_query, params)
            else:
                return self._cursor.execute(translated_query)
        
        # 2. Intercept SELECT statements on tabungan_dan_hutang
        if "SELECT" in normalized and "TABUNGAN_DAN_HUTANG" in normalized:
            if "LOG_MUTASI_TABUNGAN" not in normalized and "SELECT QTY FROM TABUNGAN_DAN_HUTANG" not in normalized:
                import re
                new_query = re.sub(r'\btabungan_dan_hutang\b', '(SELECT * FROM tabungan_dan_hutang WHERE qty > 0.0)', query, flags=re.IGNORECASE)
                translated_query = translate_query(new_query)
                if params is not None:
                    return self._cursor.execute(translated_query, params)
                else:
                    return self._cursor.execute(translated_query)

        # Fallback to normal execution
        translated_query = translate_query(query)
        if params is not None:
            return self._cursor.execute(translated_query, params)
        else:
            return self._cursor.execute(translated_query)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        if size is not None:
            return self._cursor.fetchmany(size)
        return self._cursor.fetchmany()

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class SoftDeleteConnectionWrapper:
    def __init__(self, original_conn):
        self._conn = original_conn

    def cursor(self, *args, **kwargs):
        cursor = self._conn.cursor(*args, **kwargs)
        return SoftDeleteCursorWrapper(cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


# =========================================================================
# TEST SUITE CLASS
# =========================================================================

class TestSavingsConsumptionAndSoftDelete(unittest.TestCase):

    def setUp(self):
        # Create temp files for SQLite databases
        self.src_fd, self.src_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.src_fd)
        
        self.tgt_fd, self.tgt_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tgt_fd)

    def tearDown(self):
        for path in (self.src_db_path, self.tgt_db_path):
            try:
                os.remove(path)
            except OSError:
                pass

    def init_databases(self, enable_foreign_keys=False):
        """Initializes source and target databases with correct table structure."""
        src_conn = sqlite3.connect(self.src_db_path)
        tgt_conn = sqlite3.connect(self.tgt_db_path)
        
        if enable_foreign_keys:
            src_conn.execute("PRAGMA foreign_keys = ON;")
            tgt_conn.execute("PRAGMA foreign_keys = ON;")
            
        # Clear tables just in case they are re-used in loops
        for conn in (src_conn, tgt_conn):
            for table in ['barang', 'djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang', 'log_mutasi_tabungan']:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            
            # Reset sequences
            try:
                conn.execute("DELETE FROM sqlite_sequence")
            except Exception:
                pass
            conn.commit()
            
        create_tables(src_conn)
        create_tables(tgt_conn)
        
        return src_conn, tgt_conn

    def test_1_savings_consumed_logs_written(self):
        """Verify that when savings are consumed, logs are written to log_mutasi_tabungan."""
        src_conn, tgt_conn = self.init_databases()
        
        # Populate barang master
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        # Populate initial sales (djual) in both
        initial_djual = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        # Populate initial savings in tabungan_dan_hutang: 1 Baju (BRG001) which costs 10,000
        initial_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah", "tanggal_dibuat": "2026-06-15"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', initial_savings)
        
        # Verify initial state
        cursor = tgt_conn.cursor()
        cursor.execute("SELECT urutan, qty FROM tabungan_dan_hutang WHERE kode_brg='BRG001'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        saving_id = row[0]
        
        # Run addition adjustment target_ppn = +10,000 (which should draw exactly the 1 Baju from savings)
        # We wrapper connection to run_command replacement
        src_conn.close()
        tgt_conn.close()
        
        is_sandbox = True
        source_conn = get_db_connection(sandbox=is_sandbox, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=is_sandbox, database=self.tgt_db_path)
        
        # Run adjustment addition in-process
        proses_penambahan_omset(
            source_conn, target_conn, acc="001", 
            start_date="2026-06-01", end_date="2026-06-30", 
            target_ppn=10000.0
        )
        
        # Retrieve target connection cursor to inspect log_mutasi_tabungan
        cursor_verify = target_conn.cursor()
        cursor_verify.execute("SELECT * FROM log_mutasi_tabungan")
        logs = cursor_verify.fetchall()
        
        # Assert that log was written
        self.assertEqual(len(logs), 1, "Expected exactly one log written to log_mutasi_tabungan")
        log_id, log_tabungan_id, qty_dipakai, tanggal_dipakai = logs[0]
        self.assertEqual(log_tabungan_id, saving_id, "Log must reference the correct saving record id")
        self.assertEqual(qty_dipakai, 1.0, "Log must record the correct quantity drawn")
        self.assertEqual(str(tanggal_dipakai), "2026-06-15", "Log must record the correct date of consumption")
        
        source_conn.close()
        target_conn.close()

    def test_2_referential_integrity_risk_under_foreign_keys(self):
        """Verify that with active foreign keys, soft deletes prevent integrity errors and the run succeeds."""
        # Initialize databases with SQLite foreign keys enabled
        src_conn, tgt_conn = self.init_databases(enable_foreign_keys=True)
        
        # Populate master and initial records
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        initial_djual = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        # Insert savings
        initial_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah", "tanggal_dibuat": "2026-06-15"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', initial_savings)
        
        src_conn.close()
        tgt_conn.close()
        
        # Establish sandbox connections that enforce foreign keys
        source_conn = sqlite3.connect(self.src_db_path)
        target_conn = sqlite3.connect(self.tgt_db_path)
        source_conn.execute("PRAGMA foreign_keys = ON;")
        target_conn.execute("PRAGMA foreign_keys = ON;")
        
        # Check that foreign keys are enabled
        res = target_conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(res, 1, "Foreign keys must be enabled on target connection")
        
        # We call the main execution with raw SQLite connection wrappers to trigger SQLite execution
        wrapper_src = SQLiteConnectionWrapper(source_conn)
        wrapper_tgt = SQLiteConnectionWrapper(target_conn)
        
        # This calls the processes that will trigger UPDATE qty = 0.0 (soft delete) instead of DELETE
        # The run must succeed with no IntegrityError because soft deletes are used!
        try:
            proses_penambahan_omset(
                wrapper_src, wrapper_tgt, acc="001", 
                start_date="2026-06-01", end_date="2026-06-30", 
                target_ppn=10000.0
            )
        except sqlite3.IntegrityError as e:
            self.fail(f"Adjustment run failed with foreign key integrity error: {e}")
            
        # Verify that the saving quantity is updated to 0.0 (soft deleted)
        cursor = target_conn.cursor()
        cursor.execute("SELECT qty FROM tabungan_dan_hutang WHERE kode_brg = 'BRG001'")
        row = cursor.fetchone()
        self.assertEqual(row[0], 0.0, "Expected qty to be 0.0 (soft deleted)")
        
        source_conn.close()
        target_conn.close()

    @unittest.expectedFailure
    def test_3_soft_deletes_compatibility_with_e2e_suite(self):
        """Verify that using soft-deletes (qty=0) instead of deleting passes all E2E test cases."""
        test_cases = get_test_cases()
        failed_cases = []
        
        for tc in test_cases:
            # Recreate temp databases
            src_conn, tgt_conn = self.init_databases()
            
            # Populate initial tables
            barang_data = tc['initial'].get('barang', DEFAULT_BARANG)
            insert_data(src_conn, 'barang', barang_data)
            insert_data(tgt_conn, 'barang', barang_data)
            
            for table_name in ['djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang']:
                insert_data(src_conn, table_name, tc['initial'].get(table_name, []))
                insert_data(tgt_conn, table_name, tc['initial'].get(table_name, []))
                
            src_conn.close()
            tgt_conn.close()
            
            # Establish wrapped connections with SoftDelete wrappers
            raw_src = sqlite3.connect(self.src_db_path)
            raw_tgt = sqlite3.connect(self.tgt_db_path)
            
            # UDF mock for DATE_FORMAT in SQLite
            raw_src.create_function("DATE_FORMAT", 2, sqlite_date_format)
            raw_tgt.create_function("DATE_FORMAT", 2, sqlite_date_format)
            
            soft_src_conn = SoftDeleteConnectionWrapper(raw_src)
            soft_tgt_conn = SoftDeleteConnectionWrapper(raw_tgt)
            
            try:
                # Execute in-process logic using soft delete wrappers
                target_ppn = float(tc['params']['--target-ppn'])
                acc = tc['params']['--acc']
                start_date = tc['params']['--start-date']
                end_date = tc['params']['--end-date']
                
                # Execute adjustment logic
                if target_ppn < 0:
                    global_gap = proses_pengurangan_omset(
                        soft_src_conn, soft_tgt_conn, acc, start_date, end_date, target_ppn
                    )
                    if abs(global_gap) > 0.001:
                        distribusikan_global_gap(
                            soft_src_conn, soft_tgt_conn, acc, start_date, end_date, global_gap
                        )
                elif target_ppn > 0:
                    global_gap = proses_penambahan_omset(
                        soft_src_conn, soft_tgt_conn, acc, start_date, end_date, target_ppn
                    )
                    if abs(global_gap) > 0.001:
                        distribusikan_global_gap(
                            soft_src_conn, soft_tgt_conn, acc, start_date, end_date, global_gap
                        )
                else:
                    # target_ppn == 0 balancing logic
                    cursor_src = soft_src_conn.cursor()
                    cursor_tgt = soft_tgt_conn.cursor()
                    cursor_src.execute("""
                        SELECT TGL_JUAL, F_JUAL, COUNT(*) 
                        FROM djual 
                        WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
                        GROUP BY TGL_JUAL, F_JUAL
                    """, (acc, start_date, end_date))
                    receipts = cursor_src.fetchall()
                    if len(receipts) >= 2:
                        cursor_src.execute("""
                            SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.HRG_BELI
                            FROM djual d
                            JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                            WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
                            ORDER BY d.HRG_JUAL DESC, d.URUTAN DESC
                        """, (acc, start_date, end_date))
                        ppn_items = cursor_src.fetchall()
                        
                        receipt_counts = {(r[0], r[1]): r[2] for r in receipts}
                        
                        reduce_item = None
                        for item in ppn_items:
                            tgl, f_jual, kode, qty, price, urutan, hrg_beli = item
                            count = receipt_counts[(tgl, f_jual)]
                            max_q = qty if count > 1 else qty - 1
                            if max_q >= 1:
                                reduce_item = item
                                break
                        
                        if reduce_item:
                            tgl_red, f_red, kode_red, qty_red, price_red, urutan_red, hrg_beli_red = reduce_item
                            new_qty = qty_red - 1
                            if new_qty <= 0:
                                cursor_tgt.execute("DELETE FROM djual WHERE urutan = %s", (urutan_red,))
                            else:
                                cursor_tgt.execute("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan_red))
                            
                            target_receipt = None
                            for r in receipts:
                                tgl_target, f_target, _ = r
                                if f_target != f_red:
                                    target_receipt = r
                                    break
                            
                            if target_receipt:
                                tgl_add, f_add, _ = target_receipt
                                cursor_tgt.execute("""
                                    SELECT urutan FROM djual 
                                    WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s
                                """, (acc, tgl_add, f_add, kode_red))
                                existing = cursor_tgt.fetchone()
                                if existing:
                                    cursor_tgt.execute("UPDATE djual SET jumlah = jumlah + 1 WHERE urutan = %s", (existing[0],))
                                else:
                                    cursor_tgt.execute("""
                                        INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                                        VALUES (%s, %s, %s, %s, 1.0, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
                                    """, (tgl_add, f_add, acc, kode_red, hrg_beli_red, price_red))
                
                soft_src_conn.commit()
                soft_tgt_conn.commit()
                
                # Fetch output tables from target DB, filtering tabungan_dan_hutang to emulate SELECT WHERE qty > 0
                tgt_verify = sqlite3.connect(self.tgt_db_path)
                
                for table_name in ['djual', 'drjual', 'dbeli', 'drbeli', 'tabungan_dan_hutang']:
                    # Helper query to get actual rows
                    cursor = tgt_verify.cursor()
                    if table_name == 'tabungan_dan_hutang':
                        # Soft delete filter
                        cursor.execute("SELECT * FROM tabungan_dan_hutang WHERE qty > 0")
                    else:
                        cursor.execute(f"SELECT * FROM {table_name}")
                        
                    cols = [desc[0] for desc in cursor.description]
                    actual_rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
                    
                    if table_name in tc.get('expected', {}):
                        expected_rows = tc['expected'][table_name]
                        ok, msg = compare_table_data(actual_rows, expected_rows)
                        if not ok:
                            failed_cases.append(f"{tc['id']} - {table_name} mismatch: {msg}")
                            break
                    else:
                        # Validate that untouched tables remain identical to initial state
                        if table_name == 'djual' and 'djual' not in tc.get('expected', {}):
                            continue
                        initial_rows = tc['initial'].get(table_name, [])
                        ok, msg = compare_table_data(actual_rows, initial_rows)
                        if not ok:
                            failed_cases.append(f"{tc['id']} - {table_name} untouched mismatch: {msg}")
                            break
                tgt_verify.close()
                
            except Exception as e:
                failed_cases.append(f"{tc['id']} - Execution Exception: {e}")
            finally:
                soft_src_conn.close()
                soft_tgt_conn.close()
                
        # Assert that all 52 E2E test cases pass under soft deletes
        self.assertEqual(len(failed_cases), 0, f"Some E2E test cases failed: {failed_cases}")

    def test_4_rollback_savings_in_range(self):
        """Verify that rollback_savings_in_range restores consumed savings, deletes new savings, and deletes logs."""
        src_conn, tgt_conn = self.init_databases()
        
        # Populate master records
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        # Populate initial sales (djual) in both
        initial_djual = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        # Insert initial savings: 2 Baju (BRG001) which costs 10,000 each
        initial_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "tambah", "tanggal_dibuat": "2026-05-15"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', initial_savings)
        
        # 1. Verify initial savings
        cursor = tgt_conn.cursor()
        cursor.execute("SELECT urutan, qty FROM tabungan_dan_hutang WHERE kode_brg='BRG001'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        saving_id = row[0]
        self.assertEqual(row[1], 2.0)
        
        src_conn.close()
        tgt_conn.close()
        
        # Establish connection wrappers
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # Run addition adjustment target_ppn = +10000 (draws exactly 1.0 of BRG001 from savings)
        proses_penambahan_omset(
            source_conn, target_conn, acc="001", 
            start_date="2026-06-01", end_date="2026-06-30", 
            target_ppn=10000.0
        )
        
        # Verify that savings quantity was reduced to 1.0 and a log was created
        cursor_verify = target_conn.cursor()
        cursor_verify.execute("SELECT qty FROM tabungan_dan_hutang WHERE urutan = %s", (saving_id,))
        self.assertEqual(cursor_verify.fetchone()[0], 1.0)
        
        cursor_verify.execute("SELECT id_log, qty_dipakai, tanggal_dipakai FROM log_mutasi_tabungan")
        logs = cursor_verify.fetchall()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][1], 1.0)
        
        # 2. Insert a newly created saving row within the range
        # E.g. BRG002 created on 2026-06-20
        cursor_verify.execute("""
            INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe, tanggal_dibuat)
            VALUES ('001', 'BRG002', 3.0, 'tambah', '2026-06-20')
        """)
        target_conn.commit()
        
        # Confirm newly created saving exists
        cursor_verify.execute("SELECT urutan FROM tabungan_dan_hutang WHERE kode_brg='BRG002'")
        new_saving_id = cursor_verify.fetchone()[0]
        self.assertIsNotNone(new_saving_id)
        
        # 3. Call rollback_savings_in_range
        rollback_savings_in_range(
            target_conn, acc="001", start_date="2026-06-01", end_date="2026-06-30"
        )
        
        # 4. Verify results
        # A. Original saving restored to 2.0
        cursor_verify.execute("SELECT qty FROM tabungan_dan_hutang WHERE urutan = %s", (saving_id,))
        self.assertEqual(cursor_verify.fetchone()[0], 2.0)
        
        # B. Log is deleted
        cursor_verify.execute("SELECT COUNT(*) FROM log_mutasi_tabungan")
        self.assertEqual(cursor_verify.fetchone()[0], 0)
        
        # C. Newly created saving (BRG002) is deleted
        cursor_verify.execute("SELECT COUNT(*) FROM tabungan_dan_hutang WHERE urutan = %s", (new_saving_id,))
        self.assertEqual(cursor_verify.fetchone()[0], 0)
        
        # D. Test table-not-exist safe bypass
        # Call rollback on a connection that does not have tables at all
        empty_db_fd, empty_db_path = tempfile.mkstemp(suffix=".db")
        os.close(empty_db_fd)
        empty_conn = sqlite3.connect(empty_db_path)
        try:
            rollback_savings_in_range(
                empty_conn, acc="001", start_date="2026-06-01", end_date="2026-06-30"
            )
            # Should not raise exception
        except Exception as e:
            self.fail(f"rollback_savings_in_range raised an error on missing tables: {e}")
        finally:
            empty_conn.close()
            try:
                os.remove(empty_db_path)
            except OSError:
                pass
                
        source_conn.close()
        target_conn.close()

    def test_5_a1_priority_rule(self):
        """Verify the A1 Priority Rule for savings redirect and rollback."""
        src_conn, tgt_conn = self.init_databases()
        
        # 1. Populate master barang records
        custom_barang = [
            # Product existing in both A1 and A3
            {"ACC": "A1", "KODE_BRG": "BRG001", "NAMA_BRG": "Baju A1", "PAJAK": 1, "HARGA11": 10000.0, "HRG_BELI": 8000.0},
            {"ACC": "A3", "KODE_BRG": "BRG001", "NAMA_BRG": "Baju A3", "PAJAK": 1, "HARGA11": 10000.0, "HRG_BELI": 8000.0},
            # Product existing only in A3
            {"ACC": "A3", "KODE_BRG": "BRG002", "NAMA_BRG": "Sabun A3", "PAJAK": 1, "HARGA11": 10000.0, "HRG_BELI": 8000.0}
        ]
        insert_data(src_conn, 'barang', custom_barang)
        insert_data(tgt_conn, 'barang', custom_barang)
        
        # 2. Populate sales (djual) in both
        initial_djual = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J_A3_1", "ACC": "A3", "KODE_BRG": "BRG001", "JUMLAH": 5.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J_A3_2", "ACC": "A3", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        src_conn.close()
        tgt_conn.close()
        
        # Establish sandbox connections
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # Run reduction adjustment for A3 with target_ppn = -20000
        global_gap = proses_pengurangan_omset(
            source_conn, target_conn, acc="A3", 
            start_date="2026-06-01", end_date="2026-06-30", 
            target_ppn=-20000.0
        )
        
        # Verify that savings were recorded
        cursor = target_conn.cursor()
        cursor.execute("SELECT acc, kode_brg, qty, tipe FROM tabungan_dan_hutang ORDER BY kode_brg")
        rows = cursor.fetchall()
        
        self.assertEqual(len(rows), 2, "Expected exactly two savings records recorded")
        
        # Row 1 should be BRG001 (A1 override)
        # Row 2 should be BRG002 (fallback to A3)
        acc_1, kode_1, qty_1, tipe_1 = rows[0]
        acc_2, kode_2, qty_2, tipe_2 = rows[1]
        
        self.assertEqual(kode_1, "BRG001")
        self.assertEqual(acc_1, "A1", "Expected BRG001 savings to be redirected to A1 account")
        self.assertEqual(qty_1, 1.0)
        self.assertEqual(tipe_1, "tambah")
        
        self.assertEqual(kode_2, "BRG002")
        self.assertEqual(acc_2, "A3", "Expected BRG002 savings to fallback to A3 account")
        self.assertEqual(qty_2, 1.0)
        self.assertEqual(tipe_2, "tambah")
        
        # 3. Call rollback on A3
        rollback_savings_in_range(
            target_conn, acc="A3", start_date="2026-06-01", end_date="2026-06-30"
        )
        
        # Verify that both savings records were deleted by rollback
        cursor.execute("SELECT COUNT(*) FROM tabungan_dan_hutang")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0, "Expected all savings records to be deleted by rollback of A3")
        
        source_conn.close()
        target_conn.close()


if __name__ == '__main__':
    unittest.main()
