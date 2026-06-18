# -*- coding: utf-8 -*-
"""
Unit Test Suite for the Phase 3 Idempotent ETL Pipeline.
Verifies purge limits, sync idempotency, and GUI signal emission on rerun detection.
"""

import os
import sys
import unittest
import sqlite3
from unittest.mock import MagicMock, patch

# Set offscreen platform for Qt headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop, QTimer

from proses_adjustment_pajak import (
    check_transactions_exist_in_range,
    purge_transactions_in_range,
    sync_raw_transactions_in_range,
    RerunDetectedException
)
from adjustment_ppn_gui import WorkerThread


class TestIdempotentETL(unittest.TestCase):
    """
    Test suite for Phase 3 Idempotent ETL Pipeline logic.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def test_purge_transactions_in_range_constructs_queries_restricted_by_dates(self):
        """
        Verify that purge_transactions_in_range constructs and executes DELETE queries
        that are strictly restricted by start and end dates.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        start_date = "2026-06-01"
        end_date = "2026-06-30"
        acc = "001"

        purge_transactions_in_range(mock_conn, acc, start_date, end_date)

        # Retrieve all arguments from mock_cursor.execute calls
        execute_calls = mock_cursor.execute.call_args_list
        self.assertGreater(len(execute_calls), 0)

        for call in execute_calls:
            query, params = call[0]
            query_upper = query.upper()
            
            # Verify the query is a DELETE query
            self.assertTrue(query_upper.startswith("DELETE"))
            
            # Verify that query has ACC and date parameters
            self.assertIn("ACC = %S", query_upper)
            if "DJUAL" in query_upper or "DRJUAL" in query_upper:
                self.assertIn("TGL_JUAL >= %S", query_upper)
                self.assertIn("TGL_JUAL <= %S", query_upper)
            elif "DBELI" in query_upper or "DRBELI" in query_upper:
                self.assertIn("TGL_BELI >= %S", query_upper)
                self.assertIn("TGL_BELI <= %S", query_upper)
            
            # Verify params contain acc, start_date, end_date
            self.assertEqual(params, (acc, start_date, end_date))

    def test_sync_raw_transactions_in_range_idempotency(self):
        """
        Verify that sync_raw_transactions_in_range is idempotent.
        Syncing twice should not duplicate records or cause constraint violations.
        """
        # Create in-memory SQLite databases for source and target
        src_conn = sqlite3.connect(":memory:")
        tgt_conn = sqlite3.connect(":memory:")

        # We must register DATE_FORMAT dummy for SQLite compatibility wrapper
        from proses_adjustment_pajak import SQLiteConnectionWrapper
        src_conn = SQLiteConnectionWrapper(src_conn)
        tgt_conn = SQLiteConnectionWrapper(tgt_conn)

        # Create schemas in both source and target databases
        for conn in [src_conn, tgt_conn]:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE djual (
                TGL_JUAL DATE NOT NULL,
                F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
                ACC VARCHAR(3) NOT NULL DEFAULT '',
                KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
                JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
                HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
                HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
                URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
            );
            """)
            cursor.execute("""
            CREATE TABLE drjual (
                TGL_JUAL DATE NOT NULL,
                F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
                ACC VARCHAR(3) NOT NULL DEFAULT '',
                KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
                JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
                HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
                HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
                URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
            );
            """)
            cursor.execute("""
            CREATE TABLE dbeli (
                TGL_BELI DATE NOT NULL,
                ACC VARCHAR(3) NOT NULL DEFAULT '',
                KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
                JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
                HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
                URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
            );
            """)
            cursor.execute("""
            CREATE TABLE drbeli (
                TGL_BELI DATE NOT NULL,
                ACC VARCHAR(3) NOT NULL DEFAULT '',
                KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
                JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
                HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
                URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
            );
            """)
            conn.commit()

        # Insert some test data into source database
        src_cursor = src_conn.cursor()
        src_cursor.execute("INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           ("2026-06-15", "INV001", "001", "BRG001", 10.0, 5000.0, 10000.0))
        src_cursor.execute("INSERT INTO dbeli (TGL_BELI, ACC, KODE_BRG, JUMLAH, HRG_BELI) VALUES (%s, %s, %s, %s, %s)",
                           ("2026-06-16", "001", "BRG001", 5.0, 5000.0))
        src_conn.commit()

        # Run sync first time
        sync_raw_transactions_in_range(src_conn, tgt_conn, "001", "2026-06-01", "2026-06-30")

        # Verify target has the synced rows
        tgt_cursor = tgt_conn.cursor()
        tgt_cursor.execute("SELECT COUNT(*) FROM djual")
        self.assertEqual(tgt_cursor.fetchone()[0], 1)
        tgt_cursor.execute("SELECT COUNT(*) FROM dbeli")
        self.assertEqual(tgt_cursor.fetchone()[0], 1)

        # Run sync second time (idempotency check)
        sync_raw_transactions_in_range(src_conn, tgt_conn, "001", "2026-06-01", "2026-06-30")

        # Verify count does NOT double
        tgt_cursor.execute("SELECT COUNT(*) FROM djual")
        self.assertEqual(tgt_cursor.fetchone()[0], 1)
        tgt_cursor.execute("SELECT COUNT(*) FROM dbeli")
        self.assertEqual(tgt_cursor.fetchone()[0], 1)

        src_conn.close()
        tgt_conn.close()

    @patch("adjustment_ppn_gui.workers.check_target_db_exists")
    @patch("adjustment_ppn_gui.workers.get_db_connection")
    @patch("adjustment_ppn_gui.workers.create_tabungan_dan_hutang_table")
    @patch("adjustment_ppn_gui.workers.check_transactions_exist_in_range")
    def test_worker_thread_emits_rerun_warning_signal(self, mock_exist_in_range, mock_create_tbl, mock_get_conn, mock_exists):
        """
        Verify that WorkerThread emits rerun_warning_signal when target transactions
        exist in the range, and exits without executing further processing.
        """
        mock_exists.return_value = True
        mock_get_conn.return_value = MagicMock()
        mock_exist_in_range.return_value = True  # Rerun detected!

        worker = WorkerThread(
            source_config={'database': 'src.db'},
            target_config={'database': 'tgt.db'},
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_ppn=-1000.0,
            force_rerun=False
        )

        loop = QEventLoop()
        signals_captured = []

        def on_rerun_warning(msg, data):
            signals_captured.append((msg, data))
            loop.quit()

        worker.rerun_warning_signal.connect(on_rerun_warning)
        worker.start()

        QTimer.singleShot(1000, loop.quit)
        loop.exec_()

        # Assert that the signal was emitted
        self.assertEqual(len(signals_captured), 1)
        self.assertIn("sudah ada di target database", signals_captured[0][0])
        self.assertEqual(signals_captured[0][1]["acc"], "001")
        self.assertEqual(signals_captured[0][1]["start_date"], "2026-06-01")
        self.assertEqual(signals_captured[0][1]["end_date"], "2026-06-30")
        self.assertEqual(signals_captured[0][1]["target_ppn"], -1000.0)


if __name__ == "__main__":
    unittest.main()
