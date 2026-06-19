# -*- coding: utf-8 -*-
"""
Verification tests for multithreaded execution, RAM-based pre-loading, 
and thread safety of proses_penambahan_omset in adjustment.py.
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import threading

# Add parent and current directory to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.calculator.adjustment import (
    proses_penambahan_omset
)
from test_infra import create_tables, insert_data
from test_cases import DEFAULT_BARANG

class TestMultithreadedAddition(unittest.TestCase):

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

    def init_databases(self):
        """Initializes source and target databases with correct table structure."""
        src_conn = sqlite3.connect(self.src_db_path, check_same_thread=False)
        tgt_conn = sqlite3.connect(self.tgt_db_path, check_same_thread=False)
        
        for conn in (src_conn, tgt_conn):
            for table in ['barang', 'djual', 'tabungan_dan_hutang', 'log_mutasi_tabungan']:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            
        create_tables(src_conn)
        create_tables(tgt_conn)
        
        return src_conn, tgt_conn

    def test_multithreaded_addition_zero_target(self):
        """Verify that target < 0.001 returns 0.0 early and makes no database changes."""
        src_conn, tgt_conn = self.init_databases()
        
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        gap = proses_penambahan_omset(
            source_conn, target_conn, acc="001",
            start_date="2026-06-01", end_date="2026-06-30",
            target_omset_change=0.0, max_workers=2
        )
        self.assertEqual(gap, 0.0)
        
        source_conn.close()
        target_conn.close()

    def test_multithreaded_addition_no_items(self):
        """Verify that when there are no items in range, returns target_omset_change."""
        src_conn, tgt_conn = self.init_databases()
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        target_change = 50000.0
        gap = proses_penambahan_omset(
            source_conn, target_conn, acc="001",
            start_date="2026-06-01", end_date="2026-06-30",
            target_omset_change=target_change, max_workers=2
        )
        self.assertEqual(gap, target_change)
        
        source_conn.close()
        target_conn.close()

    def test_basic_multithreaded_addition_draw_savings(self):
        """Verify multithreaded addition with multiple workers drawing from savings."""
        src_conn, tgt_conn = self.init_databases()
        
        # Populate barang
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        # Populate initial sales
        initial_djual = [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J1", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J2", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J3", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        # Populate initial savings for BRG001 (Baju, price 10000)
        initial_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 10.0, "tipe": "tambah", "tanggal_dibuat": "2026-06-01"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', initial_savings)
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # We target an addition of 30,000. Under P = target / total_omset = 30000 / 3000 = 10.
        # P = 10.
        # For J1, receipt_target = 1000 * 10 = 10,000. It will draw 1 BRG001 (value 10000).
        # For J2, receipt_target = 1000 * 10 = 10,000. It will draw 1 BRG001 (value 10000).
        # For J3, receipt_target = 1000 * 10 = 10,000. It will draw 1 BRG001 (value 10000).
        # Total added should be exactly 30,000. Gap should be 0.
        gap = proses_penambahan_omset(
            source_conn, target_conn, acc="001",
            start_date="2026-06-01", end_date="2026-06-30",
            target_omset_change=30000.0, max_workers=3
        )
        
        self.assertAlmostEqual(gap, 0.0, places=2)
        
        # Verify changes in target database
        cursor = target_conn.cursor()
        cursor.execute("SELECT qty FROM tabungan_dan_hutang WHERE kode_brg='BRG001'")
        qty_left = cursor.fetchone()[0]
        self.assertEqual(qty_left, 7.0) # 10 - 3 drawn = 7
        
        # Check logs written
        cursor.execute("SELECT SUM(qty_dipakai) FROM log_mutasi_tabungan")
        sum_used = cursor.fetchone()[0]
        self.assertEqual(sum_used, 3.0)
        
        # Check that djual has new items inserted/updated
        cursor.execute("SELECT COUNT(*) FROM djual WHERE KODE_BRG='BRG001'")
        inserted_count = cursor.fetchone()[0]
        self.assertEqual(inserted_count, 3) # One BRG001 added to each of J1, J2, J3
        
        source_conn.close()
        target_conn.close()

    def test_multithreaded_addition_fictional_injection(self):
        """Verify fictional injection with multiple workers when no savings exist."""
        src_conn, tgt_conn = self.init_databases()
        
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        initial_djual = [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J1", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J2", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # Target addition of 2,000. Total omset is 2000. P = 1.0.
        # J1 target = 1000, J2 target = 1000.
        # Since there are no savings, they will perform fictional injection.
        # The best product below target is BRG002 (Sabun, price 1000).
        # J1 injected 1 BRG002 (value 1000).
        # J2 injected 1 BRG002 (value 1000).
        # Total actual addition = 2000. Gap = 0.
        gap = proses_penambahan_omset(
            source_conn, target_conn, acc="001",
            start_date="2026-06-01", end_date="2026-06-30",
            target_omset_change=2000.0, max_workers=2
        )
        
        self.assertAlmostEqual(gap, 0.0, places=2)
        
        # Verify that BRG002 quantity on each receipt increased from 1.0 to 2.0
        cursor = target_conn.cursor()
        cursor.execute("SELECT F_JUAL, JUMLAH FROM djual WHERE KODE_BRG='BRG002'")
        results = dict(cursor.fetchall())
        self.assertEqual(results['J1'], 2.0)
        self.assertEqual(results['J2'], 2.0)
        
        # Verify that a debt record of type 'kurang' was recorded for BRG002
        cursor.execute("SELECT acc, kode_brg, qty, tipe FROM tabungan_dan_hutang")
        debt_rows = cursor.fetchall()
        # We injected 1 BRG002 in J1 and 1 in J2, so total debt of 2.0 BRG002
        self.assertEqual(len(debt_rows), 1)
        self.assertEqual(debt_rows[0][1], 'BRG002')
        self.assertEqual(debt_rows[0][2], 2.0)
        self.assertEqual(debt_rows[0][3], 'kurang')
        
        source_conn.close()
        target_conn.close()

if __name__ == '__main__':
    unittest.main()
