# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import sqlite3

# Set offscreen platform for Qt headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add parent and current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.calculator.adjustment_core import proses_pengurangan_fase
from test_cases import DEFAULT_BARANG
from test_infra import create_tables, insert_data

class TestSafeDeletionRules(unittest.TestCase):
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

    def test_rule_1_safe_item_deletion(self):
        """
        Rule 1: Safe Item Deletion.
        Verify that a receipt item can be deleted (reduced to Qty=0) if there are other items 
        on the same receipt (F_JUAL), preventing empty receipt violation but allowing item-level deletion.
        """
        src_conn, tgt_conn = self.init_databases()
        
        # Populate barang master
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        # Receipt J20260615 has 2 items: BRG001 (10,000) and BRG002 (1,000)
        # Total items on receipt J20260615 is 2.
        djual_data = [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', djual_data)
        insert_data(tgt_conn, 'djual', djual_data)
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # Target gap is 1,000 (value of BRG002).
        # We want to reduce BRG002 to 0. Since BRG001 is on the same receipt, the receipt will NOT be empty.
        # This is safe and should delete BRG002.
        proses_pengurangan_fase(
            source_conn=source_conn,
            target_conn=target_conn,
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_gap=1000.0,
            category_sql_filter="b.PAJAK = 1",
            phase_name="Test Rule 1",
            is_sandbox=True,
            log_callback=None
        )
        
        # Verify that BRG002 was deleted and BRG001 remains.
        cursor = target_conn.cursor()
        cursor.execute("SELECT KODE_BRG, JUMLAH FROM djual WHERE F_JUAL = 'J20260615'")
        remaining = cursor.fetchall()
        
        self.assertEqual(len(remaining), 1, "Only one item should remain on the receipt J20260615")
        self.assertEqual(remaining[0][0], "BRG001", "The remaining item should be BRG001")
        self.assertAlmostEqual(remaining[0][1], 1.0, places=2)
        
        target_conn.close()
        source_conn.close()

    def test_rule_2_chronological_deletion_and_blocking(self):
        """
        Rule 2: Chronological Deletion & Blocking.
        - Deletion of Receipt B's only item (latest) is ALLOWED.
        - Deletion of Receipt A's only item (older) is BLOCKED.
        - After Receipt B's item is deleted, Receipt A is the new last active and can be deleted.
        """
        src_conn, tgt_conn = self.init_databases()
        
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
        # Two receipts with 1 item each. 
        # J01 is older (2026-06-14), J02 is newer (2026-06-15).
        djual_data = [
            {"TGL_JUAL": "2026-06-14", "F_JUAL": "J01", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J02", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ]
        insert_data(src_conn, 'djual', djual_data)
        insert_data(tgt_conn, 'djual', djual_data)
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # 1. We ask to reduce by 10,000 (value of one item).
        # J02 (the last active receipt) should be deleted.
        # J01 (older receipt) must be blocked from deletion.
        proses_pengurangan_fase(
            source_conn=source_conn,
            target_conn=target_conn,
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_gap=10000.0,
            category_sql_filter="b.PAJAK = 1",
            phase_name="Test Rule 2 - Single Deletion",
            is_sandbox=True,
            log_callback=None
        )
        
        cursor = target_conn.cursor()
        cursor.execute("SELECT F_JUAL, KODE_BRG, JUMLAH FROM djual")
        remaining = cursor.fetchall()
        
        # J02 should have been deleted because it was the last active. J01 must remain because deleting it was blocked.
        self.assertEqual(len(remaining), 1, "Only one receipt should remain in the database")
        self.assertEqual(remaining[0][0], "J01", "The remaining receipt must be J01")
        self.assertAlmostEqual(remaining[0][2], 1.0, places=2)
        
        # 2. Reset and test chronological cascading:
        # If target gap is 20,000, J02 is deleted first, making J01 the new last active, which then gets deleted as well.
        target_conn.close()
        source_conn.close()
        
        src_conn = sqlite3.connect(self.src_db_path)
        tgt_conn = sqlite3.connect(self.tgt_db_path)
        
        # Clean target and re-insert initial
        tgt_conn.execute("DELETE FROM djual")
        tgt_conn.commit()
        insert_data(tgt_conn, 'djual', djual_data)
        
        src_conn.close()
        tgt_conn.close()
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        proses_pengurangan_fase(
            source_conn=source_conn,
            target_conn=target_conn,
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_gap=20000.0,
            category_sql_filter="b.PAJAK = 1",
            phase_name="Test Rule 2 - Cascading Deletion",
            is_sandbox=True,
            log_callback=None
        )
        
        cursor = target_conn.cursor()
        cursor.execute("SELECT F_JUAL, KODE_BRG, JUMLAH FROM djual")
        remaining = cursor.fetchall()
        
        # Both J01 and J02 should be deleted.
        self.assertEqual(len(remaining), 0, "Both receipts should have been deleted under chronological cascading")
        
        target_conn.close()
        source_conn.close()

    def test_rule_2_middle_of_month_halting(self):
        """
        Rule 2: Middle of Month Halting.
        Verify that if a single-item receipt is encountered in the middle of the month
        (meaning there is still a newer active receipt chronologically after it),
        the deletion loop must halt and not perform deletion on that middle receipt.
        """
        src_conn, tgt_conn = self.init_databases()
        
        insert_data(src_conn, 'barang', DEFAULT_BARANG)
        insert_data(tgt_conn, 'barang', DEFAULT_BARANG)
        
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
        
        source_conn = get_db_connection(sandbox=True, database=self.src_db_path)
        target_conn = get_db_connection(sandbox=True, database=self.tgt_db_path)
        
        # Target gap is 15,000.
        # J03 has non-target item (BRG006 is PAJAK=2, category filter is PAJAK=1).
        # When trying to reduce J02, it is a single-item receipt but NOT the last active receipt (since J03 is active).
        # Thus, the deletion loop must halt. No target item should be deleted.
        proses_pengurangan_fase(
            source_conn=source_conn,
            target_conn=target_conn,
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_gap=15000.0,
            category_sql_filter="b.PAJAK = 1",
            phase_name="Test Rule 2 - Halting",
            is_sandbox=True,
            log_callback=None
        )
        
        cursor = target_conn.cursor()
        cursor.execute("SELECT F_JUAL, KODE_BRG FROM djual ORDER BY F_JUAL ASC")
        remaining = cursor.fetchall()
        
        # Verify that no items were deleted because J02 halting blocked deletion of J02 and J01.
        # J03 (non-target) and both target items (J01 and J02) must remain.
        self.assertEqual(len(remaining), 3, "All three receipt items must remain because loop halted")
        self.assertEqual(remaining[0][0], "J01")
        self.assertEqual(remaining[1][0], "J02")
        self.assertEqual(remaining[2][0], "J03")
        
        target_conn.close()
        source_conn.close()

if __name__ == "__main__":
    unittest.main()
