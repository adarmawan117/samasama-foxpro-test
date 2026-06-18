# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Set offscreen platform for Qt headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtWidgets import QApplication, QMessageBox, QLineEdit, QPushButton
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt, QEventLoop, QTimer

# Import application components
from adjustment_ppn_core.database.connection import (
    get_db_connection,
    test_dual_connection,
)
from adjustment_ppn_gui import (
    ProsesAdjustmentPajakApp,
    TestConnectionWorker,
)

class TestDualConnectionChallenger(unittest.TestCase):
    def setUp(self):
        # Create temp files for SQLite databases
        self.src_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.src_db_path = self.src_db_file.name
        self.src_db_file.close()

        self.tgt_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tgt_db_path = self.tgt_db_file.name
        self.tgt_db_file.close()

    def tearDown(self):
        # Clean up database files
        for path in (self.src_db_path, self.tgt_db_path):
            try:
                os.remove(path)
            except OSError:
                pass

    def test_sqlite_success_path(self):
        """Verify that test_dual_connection succeeds with valid SQLite configurations."""
        source_config = {'database': self.src_db_path}
        target_config = {'database': self.tgt_db_path}
        
        # This should complete without raising any exception
        test_dual_connection(source_config, target_config, sandbox=True)

    def test_sqlite_failure_path_source(self):
        """Verify that test_dual_connection raises exception when source SQLite path is invalid."""
        # Using a directory path as database path should fail SQLite connection
        invalid_src_path = os.path.dirname(self.src_db_path)
        source_config = {'database': invalid_src_path}
        target_config = {'database': self.tgt_db_path}

        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=True)
        self.assertIn("Source DB gagal", str(context.exception))

    def test_sqlite_failure_path_target(self):
        """Verify that test_dual_connection raises exception when target SQLite path is invalid."""
        invalid_tgt_path = os.path.dirname(self.tgt_db_path)
        source_config = {'database': self.src_db_path}
        target_config = {'database': invalid_tgt_path}

        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=True)
        self.assertIn("Target DB gagal", str(context.exception))

    @patch("pymysql.connect")
    def test_mysql_success_path(self, mock_connect):
        """Verify that test_dual_connection succeeds with valid MySQL configurations."""
        mock_src_conn = MagicMock()
        mock_tgt_conn = MagicMock()
        mock_connect.side_effect = [mock_src_conn, mock_tgt_conn]

        source_config = {
            'host': '127.0.0.1',
            'port': '3306',
            'user': 'test_user',
            'password': 'password',
            'database': 'src_db'
        }
        target_config = {
            'host': '127.0.0.1',
            'port': '3307',
            'user': 'test_user',
            'password': 'password',
            'database': 'tgt_db'
        }

        test_dual_connection(source_config, target_config, sandbox=False)
        self.assertEqual(mock_connect.call_count, 2)

    def test_mysql_port_invalid_non_integer(self):
        """Verify that invalid port raises ValueError or is handled correctly."""
        source_config = {
            'host': '127.0.0.1',
            'port': 'invalid_port_string',
            'user': 'test_user',
            'password': 'password',
            'database': 'src_db'
        }
        target_config = {
            'host': '127.0.0.1',
            'port': '3306',
            'user': 'test_user',
            'password': 'password',
            'database': 'tgt_db'
        }

        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=False)
        # It should fail because 'invalid_port_string' cannot be converted to int
        self.assertIn("invalid literal for int()", str(context.exception))

    @patch("pymysql.connect")
    def test_mysql_port_empty_or_none(self, mock_connect):
        """Verify that empty/none port defaults to 3306 and does not crash."""
        mock_src_conn = MagicMock()
        mock_tgt_conn = MagicMock()
        mock_connect.side_effect = [mock_src_conn, mock_tgt_conn]

        source_config = {
            'host': '127.0.0.1',
            'port': '',  # Empty string
            'user': 'test_user',
            'password': 'password',
            'database': 'src_db'
        }
        target_config = {
            'host': '127.0.0.1',
            'port': None,  # None
            'user': 'test_user',
            'password': 'password',
            'database': 'tgt_db'
        }

        test_dual_connection(source_config, target_config, sandbox=False)
        self.assertEqual(mock_connect.call_count, 2)
        
        # Source port should fall back to 3306
        src_port_called = mock_connect.call_args_list[0][1]['port']
        self.assertEqual(src_port_called, 3306)

        # Target port should fall back to 3306
        tgt_port_called = mock_connect.call_args_list[1][1]['port']
        self.assertEqual(tgt_port_called, 3306)

    @patch("pymysql.connect")
    def test_mysql_missing_config_keys(self, mock_connect):
        """Verify default fallbacks when some configuration keys are missing or None."""
        mock_src_conn = MagicMock()
        mock_tgt_conn = MagicMock()
        mock_connect.side_effect = [mock_src_conn, mock_tgt_conn]

        source_config = {}  # Empty config
        target_config = {'database': 'tgt_db'}  # Host/user/password/port missing

        test_dual_connection(source_config, target_config, sandbox=False)
        self.assertEqual(mock_connect.call_count, 2)

        # Verify fallback values (e.g. host='localhost' or from db_config if import fails/succeeds)
        src_args = mock_connect.call_args_list[0][1]
        self.assertIn(src_args['host'], ['localhost', '127.0.0.1'])
        self.assertEqual(src_args['port'], 3306)


class TestSQLiteLockChallenger(unittest.TestCase):
    def setUp(self):
        # Create temp files for SQLite databases
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()

        # Initialize tables
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS test (val INT)")
        conn.execute("INSERT INTO test (val) VALUES (1)")
        conn.commit()
        conn.close()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_sqlite_locked_database_write(self):
        """Test how database operations handle a locked SQLite database."""
        # Open a connection and acquire an exclusive write lock using a transaction
        conn_lock = sqlite3.connect(self.db_path)
        conn_lock.execute("BEGIN EXCLUSIVE TRANSACTION")
        conn_lock.execute("UPDATE test SET val = 2")
        # Do not commit yet, keeping the database locked
        
        try:
            # Now try to open connection and write to it with another connection.
            # In SQLite, opening a connection (sqlite3.connect) succeeds immediately.
            # But performing a write operation (e.g. UPDATE, INSERT) will fail with OperationalError.
            conn_test = sqlite3.connect(self.db_path)
            # Set timeout low so it doesn't block the test suite
            conn_test.execute("PRAGMA busy_timeout = 100")
            
            with self.assertRaises(sqlite3.OperationalError) as context:
                conn_test.execute("UPDATE test SET val = 3")
                conn_test.commit()
            
            self.assertIn("locked", str(context.exception))
            conn_test.close()
        finally:
            conn_lock.rollback()
            conn_lock.close()


class TestPPNAdjustmentGUIAnyConnection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.src_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.src_db_path = self.src_db_file.name
        self.src_db_file.close()

        self.tgt_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tgt_db_path = self.tgt_db_file.name
        self.tgt_db_file.close()

        self.window = ProsesAdjustmentPajakApp()
        self.original_info = QMessageBox.information
        self.original_critical = QMessageBox.critical
        self.original_warning = QMessageBox.warning

        self.msg_box_calls = []
        QMessageBox.information = self.mock_info
        QMessageBox.critical = self.mock_critical
        QMessageBox.warning = self.mock_warning

    def tearDown(self):
        QMessageBox.information = self.original_info
        QMessageBox.critical = self.original_critical
        QMessageBox.warning = self.original_warning
        self.window.close()

        for path in (self.src_db_path, self.tgt_db_path):
            try:
                os.remove(path)
            except OSError:
                pass

    def mock_info(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("info", title, text))
        return QMessageBox.Ok

    def mock_critical(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("critical", title, text))
        return QMessageBox.Ok

    def mock_warning(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("warning", title, text))
        return QMessageBox.Ok

    def test_gui_async_connection_testing_success(self):
        """Verify GUI locks/unlocks inputs and shows success pop-up upon successful connection test."""
        self.window.source_db_input.setText(self.src_db_path)
        self.window.target_db_input.setText(self.tgt_db_path)
        QApplication.processEvents()

        # Click the "Test Connection" button
        QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)

        # Components must be immediately locked
        self.assertFalse(self.window.btn_test_conn.isEnabled())
        self.assertFalse(self.window.source_host_input.isEnabled())

        # Wait for connection worker thread to finish
        loop = QEventLoop()
        self.window.conn_worker.finished.connect(loop.quit)
        
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(4000)
        loop.exec_()

        # Components must be re-enabled
        self.assertTrue(self.window.btn_test_conn.isEnabled())
        self.assertTrue(self.window.source_host_input.isEnabled())

        # Verify success message box was shown
        self.assertTrue(any(call[0] == "info" and "Connection test succeeded" in call[2] for call in self.msg_box_calls))

    def test_gui_async_connection_testing_failure(self):
        """Verify GUI handles connection test failure correctly (displays error and re-enables inputs)."""
        # Set invalid path to force failure
        invalid_path = os.path.dirname(self.src_db_path)
        self.window.source_db_input.setText(invalid_path)
        self.window.target_db_input.setText(self.tgt_db_path)
        QApplication.processEvents()

        # Click the "Test Connection" button
        QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)

        # Wait for connection worker thread to finish
        loop = QEventLoop()
        self.window.conn_worker.finished.connect(loop.quit)
        
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(4000)
        loop.exec_()

        # Components must be re-enabled
        self.assertTrue(self.window.btn_test_conn.isEnabled())

        # Verify critical error message box was shown
        critical_calls = [call for call in self.msg_box_calls if call[0] == "critical"]
        self.assertTrue(len(critical_calls) > 0)
        self.assertTrue("Source DB gagal" in critical_calls[0][2] or "Source DB Error" in critical_calls[0][2])

    def test_gui_async_connection_testing_empty_entries(self):
        """Verify that testing connections with empty database inputs triggers a proper error response."""
        self.window.source_db_input.setText("")
        self.window.target_db_input.setText("")
        QApplication.processEvents()

        # Click the "Test Connection" button.
        # Since database names do not end with .db/.sqlite, is_sandbox is False.
        # It will try to run MySQL connection with localhost (default empty values).
        # Since MySQL server is likely not running/configured on default local settings, it will fail.
        # Let's mock pymysql.connect to raise a specific error to verify GUI prints it.
        with patch("pymysql.connect", side_effect=Exception("MySQL connection refused")):
            QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)

            # Wait for worker thread
            loop = QEventLoop()
            self.window.conn_worker.finished.connect(loop.quit)
            
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            timer.start(4000)
            loop.exec_()

            # Verify components are re-enabled and error is shown
            self.assertTrue(self.window.btn_test_conn.isEnabled())
            critical_calls = [call for call in self.msg_box_calls if call[0] == "critical"]
            self.assertTrue(len(critical_calls) > 0)
            self.assertTrue("Source DB gagal" in critical_calls[0][2] or "Source DB Error" in critical_calls[0][2])


if __name__ == '__main__':
    unittest.main()
