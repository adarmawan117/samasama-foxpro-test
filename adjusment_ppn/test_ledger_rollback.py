# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import sqlite3

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import proses_adjustment_pajak
from test_cases import DEFAULT_BARANG
from test_infra import create_tables, insert_data

class TestLedgerRollback(unittest.TestCase):
    def setUp(self):
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
        src_conn = sqlite3.connect(self.src_db_path)
        tgt_conn = sqlite3.connect(self.tgt_db_path)
        create_tables(src_conn)
        create_tables(tgt_conn)
        return src_conn, tgt_conn

    def test_1_rollback_restores_qty_and_deletes_log_accurately(self):
        """Verify that rollback restores consumed quantities without decimal loss."""
        src_conn, tgt_conn = self.init_databases()
        
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        initial_djual = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', initial_djual)
        insert_data(tgt_conn, 'djual', initial_djual)
        
        initial_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah", "tanggal_dibuat": "2026-05-15"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', initial_savings)
        
        cursor = tgt_conn.cursor()
        cursor.execute("SELECT urutan FROM tabungan_dan_hutang WHERE kode_brg='BRG001'")
        saving_id = cursor.fetchone()[0]
        
        src_conn.close()
        tgt_conn.close()
        
        is_sandbox = True
        source_conn = proses_adjustment_pajak.get_db_connection(sandbox=is_sandbox, database=self.src_db_path)
        target_conn = proses_adjustment_pajak.get_db_connection(sandbox=is_sandbox, database=self.tgt_db_path)
        
        cursor_tgt = target_conn.cursor()
        cursor_tgt.execute("INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (?, ?, ?)", (saving_id, 0.333, "2026-06-16"))
        cursor_tgt.execute("UPDATE tabungan_dan_hutang SET qty = ROUND(qty - 0.333, 3) WHERE urutan = ?", (saving_id,))
        target_conn.commit()

        # Call rollback_savings_in_range
        proses_adjustment_pajak.rollback_savings_in_range(target_conn, "001", "2026-06-01", "2026-06-30")
        
        cursor_tgt.execute("SELECT qty FROM tabungan_dan_hutang WHERE urutan = ?", (saving_id,))
        restored_qty = cursor_tgt.fetchone()[0]
        
        self.assertAlmostEqual(restored_qty, 1.0, places=3, msg="Quantity should be accurately restored to 1.0 without precision loss")
        
        cursor_tgt.execute("SELECT COUNT(*) FROM log_mutasi_tabungan WHERE id_tabungan = ?", (saving_id,))
        log_count = cursor_tgt.fetchone()[0]
        self.assertEqual(log_count, 0, "Log should be deleted after rollback")

        target_conn.close()
        source_conn.close()

    def test_2_rollback_deletes_new_savings_in_range(self):
        """Verify that rollback deletes new tabungan created during the adjustment."""
        src_conn, tgt_conn = self.init_databases()
        
        new_savings = [
            {"acc": "001", "kode_brg": "BRG001", "qty": 5.0, "tipe": "kurang", "tanggal_dibuat": "2026-06-16"}
        ]
        insert_data(tgt_conn, 'tabungan_dan_hutang', new_savings)
        
        cursor = tgt_conn.cursor()
        cursor.execute("SELECT urutan FROM tabungan_dan_hutang WHERE kode_brg='BRG001'")
        saving_id = cursor.fetchone()[0]
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = proses_adjustment_pajak.get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = proses_adjustment_pajak.get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        proses_adjustment_pajak.rollback_savings_in_range(target_conn, "001", "2026-06-01", "2026-06-30")
        
        cursor_tgt = target_conn.cursor()
        cursor_tgt.execute("SELECT COUNT(*) FROM tabungan_dan_hutang WHERE urutan = ?", (saving_id,))
        count = cursor_tgt.fetchone()[0]
        
        self.assertEqual(count, 0, "New savings record created in the range should be deleted.")
        
        target_conn.close()
        source_conn.close()

if __name__ == "__main__":
    unittest.main()
