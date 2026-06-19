# -*- coding: utf-8 -*-
"""
Unit Test Suite for testing database schema cloning, database existence detection,
and PyQt5 GUI worker thread signal/QMessageBox flows.
"""

import sys
import os
import unittest
import shutil
from unittest.mock import patch, MagicMock

# Set QPA platform to offscreen for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import PyQt5 components
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QEventLoop, QTimer, QThread

# Import target functions and classes
from adjustment_ppn_core.database.sqlite_translator import (
    parse_create_table_to_sqlite,
    make_sqlite_compatible,
    translate_query
)
from adjustment_ppn_core.database.connection import (
    SQLiteCursorWrapper,
    SQLiteConnectionWrapper,
    test_dual_connection,
    DatabaseNotFoundError
)
from adjustment_ppn_core.schema.cloning import (
    stream_sql_statements,
    check_target_db_exists,
    clone_full_database
)
from adjustment_ppn_gui import (
    TestConnectionWorker,
    WorkerThread,
    CloneWorkerThread,
    ProsesAdjustmentPajakApp
)


class TestSchemaCloningLogic(unittest.TestCase):
    """Tests for MySQL to SQLite schema translation and query compatibility wrappers."""

    def test_parse_create_table_to_sqlite_basic(self):
        """Test basic CREATE TABLE conversion from MySQL to SQLite syntax."""
        mysql_ddl = (
            "CREATE TABLE `barang` (\n"
            "  `ACC` varchar(3) NOT NULL,\n"
            "  `KODE_BRG` varchar(10) NOT NULL,\n"
            "  `NAMA_BRG` varchar(75) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL DEFAULT '',\n"
            "  `PAJAK` int(11) NOT NULL,\n"
            "  `HARGA11` double NOT NULL DEFAULT '0',\n"
            "  PRIMARY KEY (`ACC`,`KODE_BRG`)\n"
            ") ENGINE=InnoDB DEFAULT CHARSET=latin1;"
        )
        sqlite_ddl = parse_create_table_to_sqlite(mysql_ddl)
        
        # Verify ENGINE and CHARACTER SET/COLLATE are stripped or normalized
        self.assertNotIn("ENGINE=InnoDB", sqlite_ddl)
        self.assertNotIn("CHARACTER SET utf8", sqlite_ddl)
        self.assertNotIn("COLLATE utf8_general_ci", sqlite_ddl)
        self.assertIn("CREATE TABLE `barang`", sqlite_ddl)

    def test_parse_create_table_with_autoincrement(self):
        """Test conversion of auto_increment and primary key constraint handling."""
        mysql_ddl = (
            "CREATE TABLE `tabungan_dan_hutang` (\n"
            "  `urutan` int(11) NOT NULL AUTO_INCREMENT,\n"
            "  `acc` varchar(3) NOT NULL DEFAULT '',\n"
            "  `qty` double(15,3) NOT NULL DEFAULT '0.000',\n"
            "  PRIMARY KEY (`urutan`)\n"
            ");"
        )
        sqlite_ddl = parse_create_table_to_sqlite(mysql_ddl)
        
        # Auto increment column should become INTEGER PRIMARY KEY AUTOINCREMENT
        self.assertIn("`urutan` INTEGER PRIMARY KEY AUTOINCREMENT", sqlite_ddl)
        # Primary key statement should be stripped to avoid duplication in SQLite
        self.assertNotIn("PRIMARY KEY (`urutan`)", sqlite_ddl)

    def test_make_sqlite_compatible(self):
        """Test make_sqlite_compatible strips comments and administrative tasks."""
        # Administrative commands should return None
        self.assertIsNone(make_sqlite_compatible("LOCK TABLES `barang` WRITE;"))
        self.assertIsNone(make_sqlite_compatible("UNLOCK TABLES;"))
        self.assertIsNone(make_sqlite_compatible("SET FOREIGN_KEY_CHECKS=0;"))
        
        # String escape conversions (MySQL \' -> SQLite '')
        mysql_insert = "INSERT INTO test VALUES ('Value with \\'escaped\\' quote');"
        expected_sqlite = "INSERT INTO test VALUES ('Value with ''escaped'' quote');"
        self.assertEqual(make_sqlite_compatible(mysql_insert), expected_sqlite)

    def test_translate_query_placeholders(self):
        """Test translate_query correctly maps %s to ? while ignoring values inside quotes."""
        # Simple translation
        query = "SELECT * FROM djual WHERE acc = %s AND tgl_jual >= %s"
        expected = "SELECT * FROM djual WHERE acc = ? AND tgl_jual >= ?"
        self.assertEqual(translate_query(query), expected)

        # Placeholders inside string literals should NOT be translated
        query_with_quotes = "SELECT * FROM djual WHERE description = 'Value %s' AND acc = %s"
        expected_with_quotes = "SELECT * FROM djual WHERE description = 'Value %s' AND acc = ?"
        self.assertEqual(translate_query(query_with_quotes), expected_with_quotes)

        # Double quotes checking
        query_double = 'SELECT * FROM djual WHERE name = "Test %s" AND acc = %s'
        expected_double = 'SELECT * FROM djual WHERE name = "Test %s" AND acc = ?'
        self.assertEqual(translate_query(query_double), expected_double)

    def test_sqlite_wrappers(self):
        """Test SQLiteConnectionWrapper and SQLiteCursorWrapper correctly translate execution queries."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        wrapper_conn = SQLiteConnectionWrapper(mock_conn)
        wrapper_cursor = wrapper_conn.cursor()

        # Execute query and verify translation called
        query = "SELECT * FROM test WHERE id = %s"
        wrapper_cursor.execute(query, (1,))
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = ?", (1,))

        # Executemany check
        mock_cursor.reset_mock()
        wrapper_cursor.executemany("INSERT INTO test VALUES (%s)", [(1,), (2,)])
        mock_cursor.executemany.assert_called_once_with("INSERT INTO test VALUES (?)", [(1,), (2,)])

    def test_parse_composite_primary_key_with_autoincrement(self):
        """Test that composite primary keys are dropped if auto_increment is present."""
        mysql_ddl = (
            "CREATE TABLE `comp_test` (\n"
            "  `urutan` int(11) NOT NULL AUTO_INCREMENT,\n"
            "  `acc` varchar(3) NOT NULL DEFAULT '',\n"
            "  PRIMARY KEY (`urutan`,`acc`)\n"
            ");"
        )
        sqlite_ddl = parse_create_table_to_sqlite(mysql_ddl)
        self.assertIn("`urutan` INTEGER PRIMARY KEY AUTOINCREMENT", sqlite_ddl)
        self.assertNotIn("PRIMARY KEY (", sqlite_ddl)

    def test_parse_columns_named_key_and_index(self):
        """Test that columns named key or index are not incorrectly stripped as constraints."""
        mysql_ddl = (
            "CREATE TABLE `key_col_test` (\n"
            "  `key` varchar(50) NOT NULL,\n"
            "  `index` int(11) NOT NULL,\n"
            "  KEY `idx_key` (`key`)\n"
            ");"
        )
        sqlite_ddl = parse_create_table_to_sqlite(mysql_ddl)
        self.assertIn("`key` varchar(50) NOT NULL", sqlite_ddl)
        self.assertIn("`index` int(11) NOT NULL", sqlite_ddl)
        self.assertNotIn("KEY `idx_key`", sqlite_ddl)

    def test_make_sqlite_compatible_comments_before_set(self):
        """Test that make_sqlite_compatible ignores administrative queries even with preceding comments."""
        sql_with_comment = "-- This is a comment\nSET FOREIGN_KEY_CHECKS = 0;"
        self.assertIsNone(make_sqlite_compatible(sql_with_comment))
        
        sql_with_multi_comment = "/* Multi-line\ncomment */ LOCK TABLES `barang` WRITE;"
        self.assertIsNone(make_sqlite_compatible(sql_with_multi_comment))

    def test_translate_query_modulo_expressions(self):
        """Test that %s is only replaced when it is a stand-alone placeholder, not in modulo expressions."""
        # Modulo expression like value%size should not be replaced
        self.assertEqual(translate_query("SELECT value%size FROM test"), "SELECT value%size FROM test")
        self.assertEqual(translate_query("SELECT value%s_column FROM test"), "SELECT value%s_column FROM test")
        
        # Real placeholder should still be replaced
        self.assertEqual(translate_query("SELECT * FROM test WHERE name = %s"), "SELECT * FROM test WHERE name = ?")


class TestDatabaseExistenceDetection(unittest.TestCase):
    """Tests for database path validation, existence checks, and custom exceptions."""

    @patch("os.path.exists")
    def test_sqlite_existence_validation(self, mock_exists):
        """Verify database existence check logic when path exists vs. when it is missing."""
        mock_exists.return_value = True
        self.assertTrue(check_target_db_exists({'database': 'exists.db'}, sandbox=True))
        
        mock_exists.return_value = False
        self.assertFalse(check_target_db_exists({'database': 'missing.db'}, sandbox=True))

    @patch("adjustment_ppn_core.schema.cloning.get_db_connection")
    def test_mysql_existence_validation(self, mock_get_conn):
        """Verify MySQL existence check when database exists (succeeds) vs when it throws 1049."""
        # Case 1: database exists (connection succeeds)
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        
        self.assertTrue(check_target_db_exists({'database': 'exists_mysql'}, sandbox=False))
        mock_conn.close.assert_called_once()
        
        # Case 2: database not found (throws 1049)
        mock_get_conn.reset_mock()
        # Mock error with args[0] = 1049
        mock_err = Exception()
        mock_err.args = (1049, "Unknown database 'missing_mysql'")
        mock_get_conn.side_effect = mock_err
        
        self.assertFalse(check_target_db_exists({'database': 'missing_mysql'}, sandbox=False))

    @patch("os.path.exists")
    def test_sqlite_missing_database_raises_error(self, mock_exists):
        """Verify missing SQLite databases correctly raise file-not-found exceptions in stream_sql_statements."""
        mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            stream_sql_statements("nonexistent_schema.sql").__next__()


class TestSchemaCloningOperations(unittest.TestCase):
    """Tests cloning logic for both SQLite (sandbox) and MySQL modes."""

    @patch("sqlite3.connect")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_clone_full_database_sqlite(self, mock_makedirs, mock_exists, mock_connect):
        """Verify SQLite database cloning performs backup using sqlite3.Connection.backup."""
        mock_exists.return_value = True
        
        mock_src_conn = MagicMock()
        mock_tgt_conn = MagicMock()
        mock_connect.side_effect = [mock_src_conn, mock_tgt_conn]
        
        source_config = {'database': 'src.db'}
        target_config = {'database': 'tgt.db'}
        
        clone_full_database(source_config, target_config, is_sandbox=True)
        
        # Verify connections were opened
        mock_connect.assert_any_call('src.db')
        mock_connect.assert_any_call('tgt.db')
        
        # Verify backup was called
        mock_src_conn.backup.assert_called_once_with(mock_tgt_conn)
        # Verify closed
        mock_src_conn.close.assert_called_once()
        mock_tgt_conn.close.assert_called_once()

    @patch("adjustment_ppn_core.schema.cloning.get_db_connection")
    def test_clone_full_database_mysql(self, mock_get_conn):
        """Verify MySQL database cloning creates database, retrieves schemas, and copies data."""
        # Setup mocks for server, source, and target connections
        mock_conn_server = MagicMock()
        mock_conn_src = MagicMock()
        mock_conn_tgt = MagicMock()
        
        mock_get_conn.side_effect = [mock_conn_server, mock_conn_src, mock_conn_tgt]
        
        # Mock SHOW TABLES, DDL and SELECT * data
        cursor_src = mock_conn_src.cursor.return_value
        cursor_src.fetchall.return_value = [("table1",), ("table2",)]
        cursor_src.fetchone.side_effect = [
            ("table1", "CREATE TABLE table1 (id INT)"),
            ("table2", "CREATE TABLE table2 (id INT, name VARCHAR(20))")
        ]
        cursor_src.fetchmany.side_effect = [
            [("val1", "val2")], # table1 first batch
            [], # table1 end of data
            [] # table2 first batch (empty)
        ]
        
        source_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'source_db'
        }
        target_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'target_db'
        }
        
        clone_full_database(source_config, target_config, is_sandbox=False)
        
        # Verify CREATE DATABASE was executed
        cursor_server = mock_conn_server.cursor.return_value
        cursor_server.execute.assert_called_with("CREATE DATABASE IF NOT EXISTS `target_db`")
        
        # Verify target tables were dropped and recreated, and foreign key checks toggled
        cursor_tgt = mock_conn_tgt.cursor.return_value
        cursor_tgt.execute.assert_any_call("SET FOREIGN_KEY_CHECKS = 0")
        cursor_tgt.execute.assert_any_call("DROP TABLE IF EXISTS `table1`")
        cursor_tgt.execute.assert_any_call("SET FOREIGN_KEY_CHECKS = 1")
        
        # Verify target commit was called
        mock_conn_tgt.commit.assert_called_once()


class TestPyQt5SignalTriggers(unittest.TestCase):
    """Tests PyQt5 custom workers thread signals under mock database connections."""

    @classmethod
    def setUpClass(cls):
        # Initialize QApplication for signals and GUI test harness
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    @patch("adjustment_ppn_gui.workers.check_target_db_exists")
    @patch("adjustment_ppn_gui.workers.test_dual_connection")
    def test_connection_worker_success(self, mock_test_conn, mock_check_target):
        """Verify TestConnectionWorker emits success signal upon successful test connection."""
        mock_check_target.return_value = True
        mock_test_conn.return_value = None
        
        worker = TestConnectionWorker(
            source_config={},
            target_config={},
            sandbox=True
        )
        
        loop = QEventLoop()
        signals_captured = []

        def on_finished(success, err_msg):
            signals_captured.append((success, err_msg))
            loop.quit()

        worker.finished_signal.connect(on_finished)
        worker.start()
        
        QTimer.singleShot(1000, loop.quit)
        loop.exec_()
        
        self.assertEqual(len(signals_captured), 1)
        self.assertEqual(signals_captured[0], (True, ""))

    @patch("adjustment_ppn_gui.workers.check_target_db_exists")
    @patch("adjustment_ppn_gui.workers.test_dual_connection")
    def test_connection_worker_failure(self, mock_test_conn, mock_check_target):
        """Verify TestConnectionWorker emits failure signals with error details."""
        mock_check_target.return_value = True
        mock_test_conn.side_effect = Exception("Connection Refused")
        
        worker = TestConnectionWorker(
            source_config={},
            target_config={},
            sandbox=True
        )
        
        loop = QEventLoop()
        signals_captured = []

        def on_finished(success, err_msg):
            signals_captured.append((success, err_msg))
            loop.quit()

        worker.finished_signal.connect(on_finished)
        worker.start()
        
        QTimer.singleShot(1000, loop.quit)
        loop.exec_()
        
        self.assertEqual(len(signals_captured), 1)
        self.assertEqual(signals_captured[0][0], False)
        self.assertIn("Connection Refused", signals_captured[0][1])

    @patch("adjustment_ppn_gui.workers.check_target_db_exists")
    @patch("adjustment_ppn_gui.workers.get_db_connection")
    @patch("adjustment_ppn_gui.workers.create_tabungan_dan_hutang_table")
    @patch("adjustment_ppn_gui.workers.check_transactions_exist_in_range")
    @patch("adjustment_ppn_gui.workers.proses_pengurangan_omset")
    @patch("adjustment_ppn_gui.workers.sync_master_data")
    def test_worker_thread_reduction_success(self, mock_sync_master, mock_proses_red, mock_check_trx, mock_create_tbl, mock_get_conn, mock_exists):
        """Verify WorkerThread reduction triggers proper progression and finish signals."""
        mock_exists.return_value = True
        mock_check_trx.return_value = False
        mock_get_conn.return_value = MagicMock()
        mock_proses_red.side_effect = lambda s, t, acc, st, end, val, log_callback: (
            log_callback("Reducing revenue..."),
            -150.00
        )[1]

        worker = WorkerThread(
            source_config={'database': 'src.db'},
            target_config={'database': 'tgt.db'},
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_ppn=-1000.0
        )

        loop = QEventLoop()
        progress_msgs = []
        finished_results = []

        worker.progress_signal.connect(lambda msg: progress_msgs.append(msg))
        
        def on_finished(success, final_gap, logs):
            finished_results.append((success, final_gap, logs))
            loop.quit()

        worker.finished_signal.connect(on_finished)
        worker.start()
        
        QTimer.singleShot(1000, loop.quit)
        loop.exec_()

        # Check signals
        self.assertIn("Reducing revenue...", progress_msgs)
        self.assertEqual(len(finished_results), 1)
        self.assertEqual(finished_results[0][0], True)
        self.assertEqual(finished_results[0][1], -150.00)

    @patch("adjustment_ppn_gui.workers.check_target_db_exists")
    def test_worker_thread_raises_db_not_found(self, mock_exists):
        """Verify WorkerThread raises DatabaseNotFoundError and emits db_not_found_signal if target DB does not exist."""
        mock_exists.return_value = False
        
        worker = WorkerThread(
            source_config={'database': 'src.db'},
            target_config={'database': 'tgt.db'},
            acc="001",
            start_date="2026-06-01",
            end_date="2026-06-30",
            target_ppn=-1000.0
        )
        
        loop = QEventLoop()
        captured_signals = []
        
        def on_db_not_found(err_msg, target_config):
            captured_signals.append((err_msg, target_config))
            loop.quit()
            
        worker.db_not_found_signal.connect(on_db_not_found)
        worker.start()
        
        QTimer.singleShot(1000, loop.quit)
        loop.exec_()
        
        self.assertEqual(len(captured_signals), 1)
        self.assertEqual(captured_signals[0][0], "Database Target belum ada.")
        self.assertEqual(captured_signals[0][1], {'database': 'tgt.db'})


class TestGUIPopupFlows(unittest.TestCase):
    """Tests the QMessageBox popups and the automatic cloning and restart flow in the GUI."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    @patch("adjustment_ppn_gui.main_window.QMessageBox.question")
    @patch("adjustment_ppn_gui.controller.CloneWorkerThread")
    def test_on_db_not_found_yes_flow(self, mock_clone_worker_cls, mock_question):
        """Verify that choosing Yes in the popup spawns the CloneWorkerThread."""
        mock_question.return_value = QMessageBox.Yes
        mock_worker = MagicMock()
        mock_clone_worker_cls.return_value = mock_worker
        
        app_gui = ProsesAdjustmentPajakApp()
        app_gui.source_db_input.setText("src.db")
        app_gui.target_db_input.setText("tgt.db")
        
        # Call on_db_not_found
        app_gui.on_db_not_found("Database Target belum ada.", {'database': 'tgt.db'})
        
        # Verify question was shown
        mock_question.assert_called_once()
        
        # Verify CloneWorkerThread was started
        mock_worker.start.assert_called_once()

    @patch("adjustment_ppn_gui.main_window.QMessageBox.question")
    def test_on_db_not_found_no_flow(self, mock_question):
        """Verify that choosing No in the popup unlocks GUI and aborts process."""
        mock_question.return_value = QMessageBox.No
        
        app_gui = ProsesAdjustmentPajakApp()
        app_gui.set_inputs_enabled(False) # lock GUI
        
        app_gui.on_db_not_found("Database Target belum ada.", {'database': 'tgt.db'})
        
        # Verify inputs are re-enabled
        self.assertTrue(app_gui.source_host_input.isEnabled())

    @patch("adjustment_ppn_gui.main_window.QMessageBox.information")
    @patch("adjustment_ppn_gui.controller.AdjustmentPajakController.click_proses")
    def test_on_clone_finished_success_restarts_process(self, mock_click_proses, mock_info):
        """Verify that a successful clone displays an information dialog and restarts adjustment process."""
        app_gui = ProsesAdjustmentPajakApp()
        app_gui.on_clone_finished(True, "Success")
        
        mock_info.assert_called_once()
        mock_click_proses.assert_called_once()


if __name__ == "__main__":
    unittest.main()
