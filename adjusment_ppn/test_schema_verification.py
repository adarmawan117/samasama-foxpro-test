# -*- coding: utf-8 -*-
"""
Verification test script for database schema updates in:
1. proses_adjustment_pajak.py
2. test_infra.py

Verifies:
- Existence of `tanggal_dibuat` in `tabungan_dan_hutang` table, allowing date inserts.
- Existence of `log_mutasi_tabungan` table with `id_log`, `id_tabungan`, `qty_dipakai`, and `tanggal_dipakai`.
- SQLite foreign key constraints are correctly defined.
"""

import os
import sys
import sqlite3
import unittest

# Add directory of this file to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adjustment_ppn_core.schema.migrations import (
    create_tabungan_dan_hutang_table,
    create_log_mutasi_tabungan_table
)
import test_infra

class TestSchemaVerification(unittest.TestCase):
    def test_proses_adjustment_pajak_schema(self):
        """Verify schema definitions in proses_adjustment_pajak.py"""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Create tables
        create_tabungan_dan_hutang_table(conn, is_sqlite=True)
        create_log_mutasi_tabungan_table(conn, is_sqlite=True)
        
        # Verify tabungan_dan_hutang columns
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tabungan_dan_hutang);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        self.assertIn("tanggal_dibuat", columns)
        
        # Test inserting dates
        test_date = "2026-06-17"
        cursor.execute(
            "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe, tanggal_dibuat) VALUES (?, ?, ?, ?, ?)",
            ("acc", "BRG001", 10.0, "tambah", test_date)
        )
        conn.commit()
        
        # Retrieve and verify
        cursor.execute("SELECT tanggal_dibuat FROM tabungan_dan_hutang WHERE kode_brg = ?", ("BRG001",))
        inserted_date = cursor.fetchone()[0]
        self.assertEqual(inserted_date, test_date)
        
        # Get the auto-increment primary key
        cursor.execute("SELECT urutan FROM tabungan_dan_hutang WHERE kode_brg = ?", ("BRG001",))
        valid_id = cursor.fetchone()[0]
        
        # Verify log_mutasi_tabungan columns
        cursor.execute("PRAGMA table_info(log_mutasi_tabungan);")
        log_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        self.assertTrue(len(log_columns) > 0, "log_mutasi_tabungan table does not exist or has no columns")
        self.assertIn("id_log", log_columns)
        self.assertIn("id_tabungan", log_columns)
        self.assertIn("qty_dipakai", log_columns)
        self.assertIn("tanggal_dipakai", log_columns)
        
        # Verify foreign key constraint enforcement
        # Valid foreign key should succeed
        cursor.execute(
            "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (?, ?, ?)",
            (valid_id, 5.0, "2026-06-18")
        )
        conn.commit()
        
        # Invalid foreign key should fail
        invalid_id = 99999
        with self.assertRaises(sqlite3.IntegrityError) as context:
            cursor.execute(
                "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (?, ?, ?)",
                (invalid_id, 2.0, "2026-06-18")
            )
            conn.commit()
        self.assertIn("FOREIGN KEY constraint failed", str(context.exception))
        
        conn.close()

    def test_test_infra_schema(self):
        """Verify schema definitions in test_infra.py"""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Create tables
        test_infra.create_tables(conn)
        
        # Verify tabungan_dan_hutang columns
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tabungan_dan_hutang);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        self.assertIn("tanggal_dibuat", columns)
        
        # Test inserting dates
        test_date = "2026-06-17"
        cursor.execute(
            "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe, tanggal_dibuat) VALUES (?, ?, ?, ?, ?)",
            ("acc", "BRG002", 15.0, "tambah", test_date)
        )
        conn.commit()
        
        # Retrieve and verify
        cursor.execute("SELECT tanggal_dibuat FROM tabungan_dan_hutang WHERE kode_brg = ?", ("BRG002",))
        inserted_date = cursor.fetchone()[0]
        self.assertEqual(inserted_date, test_date)
        
        # Get the auto-increment primary key
        cursor.execute("SELECT urutan FROM tabungan_dan_hutang WHERE kode_brg = ?", ("BRG002",))
        valid_id = cursor.fetchone()[0]
        
        # Verify log_mutasi_tabungan columns
        cursor.execute("PRAGMA table_info(log_mutasi_tabungan);")
        log_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        self.assertTrue(len(log_columns) > 0, "log_mutasi_tabungan table does not exist or has no columns")
        self.assertIn("id_log", log_columns)
        self.assertIn("id_tabungan", log_columns)
        self.assertIn("qty_dipakai", log_columns)
        self.assertIn("tanggal_dipakai", log_columns)
        
        # Verify foreign key constraint enforcement
        # Valid foreign key should succeed
        cursor.execute(
            "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (?, ?, ?)",
            (valid_id, 3.0, "2026-06-18")
        )
        conn.commit()
        
        # Invalid foreign key should fail
        invalid_id = 88888
        with self.assertRaises(sqlite3.IntegrityError) as context:
            cursor.execute(
                "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (?, ?, ?)",
                (invalid_id, 1.0, "2026-06-18")
            )
            conn.commit()
        self.assertIn("FOREIGN KEY constraint failed", str(context.exception))
        
        conn.close()

if __name__ == '__main__':
    unittest.main()
