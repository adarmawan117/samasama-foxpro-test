# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import sqlite3
import csv

# Set offscreen platform for Qt headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QLineEdit, QPushButton, QComboBox, QDateEdit, QListWidget
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt, QDate, QEventLoop, QTimer

# Import the GUI application class and controller
from adjustment_ppn_gui import ProsesAdjustmentPajakApp, AdjustmentPajakController, WorkerThread, TestConnectionWorker


def create_mock_db(db_path):
    """Creates a mock database matching schemas expected by the adjustment backend."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Create accinv table (for account listing)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accinv (
            ACC VARCHAR(3) NOT NULL PRIMARY KEY,
            NAMA_ACC VARCHAR(75) NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO accinv (ACC, NAMA_ACC) VALUES ('001', 'Account Utama')")
    
    # 2. Create barang table (Master goods)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS barang (
            ACC VARCHAR(3) NOT NULL,
            KODE_BRG VARCHAR(10) NOT NULL,
            NAMA_BRG VARCHAR(75) NOT NULL DEFAULT '',
            PAJAK INT NOT NULL,
            HARGA11 DOUBLE NOT NULL DEFAULT 0.0,
            HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT,
            UNIQUE (ACC, KODE_BRG)
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO barang (ACC, KODE_BRG, NAMA_BRG, PAJAK, HARGA11, HRG_BELI) VALUES ('001', 'BRG001', 'Barang PPN 1', 1, 10000.0, 8000.0)")
    cursor.execute("INSERT OR IGNORE INTO barang (ACC, KODE_BRG, NAMA_BRG, PAJAK, HARGA11, HRG_BELI) VALUES ('001', 'BRG002', 'Barang PPN 2', 1, 15000.0, 12000.0)")
    
    # 3. Create djual table (Sales Transactions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS djual (
            TGL_JUAL DATE NOT NULL,
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
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT,
            F_JUAL VARCHAR(15) NOT NULL DEFAULT ''
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO djual (TGL_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, F_PPN, F_JUAL)
        VALUES ('2026-06-15', '001', 'BRG001', 5.0, 8000.0, 10000.0, 10.0, 'J2026061501')
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO djual (TGL_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, F_PPN, F_JUAL)
        VALUES ('2026-06-15', '001', 'BRG002', 2.0, 12000.0, 15000.0, 10.0, 'J2026061501')
    """)
    
    # 4. Create empty drjual table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drjual (
            TGL_JUAL DATE NOT NULL,
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
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT,
            F_JUAL VARCHAR(15) NOT NULL DEFAULT ''
        )
    """)
    
    # 5. Create empty dbeli table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dbeli (
            TGL_BELI DATE NOT NULL,
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    # 6. Create empty drbeli table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drbeli (
            TGL_BELI DATE NOT NULL,
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    
    conn.commit()
    conn.close()


class TestPPNAdjustmentGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Obtain QApplication instance, required for GUI test execution
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        # Create temp file database for sandboxed runs
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        create_mock_db(self.db_path)
        
        # Create target temp file database
        self.target_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.target_db_path = self.target_db_file.name
        self.target_db_file.close()
        create_mock_db(self.target_db_path)
        
        # Clear transactions in target to avoid rerun prompt in tests
        conn = sqlite3.connect(self.target_db_path)
        conn.execute("DELETE FROM djual")
        conn.execute("DELETE FROM drjual")
        conn.execute("DELETE FROM dbeli")
        conn.execute("DELETE FROM drbeli")
        conn.commit()
        conn.close()

        # Instantiate GUI QMainWindow and Controller
        self.window = ProsesAdjustmentPajakApp(create_controller=False)
        self.controller = AdjustmentPajakController(self.window)
        self.window.controller = self.controller
        
        # Monkeypatch QMessageBox to prevent blocking execution during test runs
        self.original_info = QMessageBox.information
        self.original_critical = QMessageBox.critical
        self.original_warning = QMessageBox.warning
        self.original_question = QMessageBox.question
        
        self.msg_box_calls = []
        
        QMessageBox.information = self.mock_info
        QMessageBox.critical = self.mock_critical
        QMessageBox.warning = self.mock_warning
        QMessageBox.question = self.mock_question

    def tearDown(self):
        # Restore QMessageBox original functions
        QMessageBox.information = self.original_info
        QMessageBox.critical = self.original_critical
        QMessageBox.warning = self.original_warning
        QMessageBox.question = self.original_question
        
        # Close the central window object
        self.window.close()
        
        # Clean up database files
        try:
            os.remove(self.db_path)
        except OSError:
            pass
        try:
            os.remove(self.target_db_path)
        except OSError:
            pass

    # Mock QMessageBox callbacks
    def mock_info(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("info", title, text))
        return QMessageBox.Ok

    def mock_critical(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("critical", title, text))
        return QMessageBox.Ok

    def mock_warning(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("warning", title, text))
        return QMessageBox.Ok

    def mock_question(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("question", title, text))
        return QMessageBox.Yes

    def test_1_form_components_exist(self):
        """Verifies that the GUI window initializes and contains all required form components."""
        # 1. Source Database Group fields
        self.assertIsInstance(self.window.source_host_input, QLineEdit)
        self.assertIsInstance(self.window.source_port_input, QLineEdit)
        self.assertIsInstance(self.window.source_user_input, QLineEdit)
        self.assertIsInstance(self.window.source_pass_input, QLineEdit)
        self.assertIsInstance(self.window.source_db_input, QLineEdit)
        self.assertIsInstance(self.window.btn_browse_source, QPushButton)
        
        # 2. Target Database Group fields
        self.assertIsInstance(self.window.target_host_input, QLineEdit)
        self.assertIsInstance(self.window.target_port_input, QLineEdit)
        self.assertIsInstance(self.window.target_user_input, QLineEdit)
        self.assertIsInstance(self.window.target_pass_input, QLineEdit)
        self.assertIsInstance(self.window.target_db_input, QLineEdit)
        self.assertIsInstance(self.window.btn_browse_target, QPushButton)

        # 3. Test Connection button
        self.assertIsInstance(self.window.btn_test_conn, QPushButton)
        
        # 4. Database name/path input & Browse button aliases (for backwards compatibility)
        self.assertIsInstance(self.window.db_path_input, QLineEdit)
        self.assertIsInstance(self.window.btn_browse, QPushButton)
        
        # 5. Account selection QComboBox
        self.assertIsInstance(self.window.combo_acc, QComboBox)
        
        # 6. Start Date and End Date inputs
        self.assertIsInstance(self.window.tgl_awal, QDateEdit)
        self.assertIsInstance(self.window.tgl_akhir, QDateEdit)
        
        # 7. Target PPN line edit
        self.assertIsInstance(self.window.target_ppn_input, QLineEdit)
        
        # 8. Real-time debug log widget
        self.assertIsInstance(self.window.log_widget, QListWidget)
        
        # 9. "Proses" or run button
        self.assertIsInstance(self.window.btn_proses, QPushButton)
        
        # 10. "Export" button
        self.assertIsInstance(self.window.btn_export, QPushButton)
        
        # Ensure initial state matches specifications
        self.assertFalse(self.window.combo_acc.isEnabled())
        self.assertFalse(self.window.tgl_awal.isEnabled())
        self.assertFalse(self.window.tgl_akhir.isEnabled())
        self.assertFalse(self.window.target_ppn_input.isEnabled())
        self.assertFalse(self.window.btn_proses.isEnabled())
        self.assertFalse(self.window.btn_export.isEnabled())

    def test_2_load_accounts_on_test_connection_success(self):
        """Verifies that accounts are loaded dynamically when test connection succeeds."""
        self.window.source_db_input.setText(self.db_path)
        self.window.target_db_input.setText(self.target_db_path)
        QApplication.processEvents()
        
        QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)
        
        loop = QEventLoop()
        self.window.conn_worker.finished_signal.connect(lambda success, err: loop.quit())
        
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(4000)
        loop.exec_()
        
        # Ensure combo box has options loaded from database
        self.assertGreater(self.window.combo_acc.count(), 1)
        # Index 0 is placeholder, Index 1 is ALL, Index 2 should be Account '001'
        self.assertEqual(self.window.combo_acc.itemData(1), ("001",))
        # Ensure the components are enabled
        self.assertTrue(self.window.combo_acc.isEnabled())

    def test_3_state_management_multithreading_and_logging(self):
        """Verifies input lock state, multithread responsiveness, real-time logging, and post-process summary."""
        # Set up valid form parameters
        self.window.db_path_input.setText(self.db_path)
        self.window.target_db_input.setText(self.target_db_path)
        # MUST simulate a successful test connection to enable inputs and load accounts
        self.window.set_inputs_enabled(True)
        self.window.load_accounts()
        QApplication.processEvents()
        
        self.window.combo_acc.setCurrentIndex(1) # Account 001
        self.window.tgl_awal.setDate(QDate(2026, 6, 1))
        self.window.tgl_akhir.setDate(QDate(2026, 6, 30))
        self.window.target_ppn_input.setText("-15000.0") # Target decrease

        # Trigger process execution
        QTest.mouseClick(self.window.btn_proses, Qt.LeftButton)
        
        # 1. State Management: inputs and buttons should be disabled immediately during execution
        self.assertFalse(self.window.source_host_input.isEnabled())
        self.assertFalse(self.window.source_port_input.isEnabled())
        self.assertFalse(self.window.source_user_input.isEnabled())
        self.assertFalse(self.window.source_pass_input.isEnabled())
        self.assertFalse(self.window.source_db_input.isEnabled())
        self.assertFalse(self.window.btn_browse_source.isEnabled())
        
        self.assertFalse(self.window.target_host_input.isEnabled())
        self.assertFalse(self.window.target_port_input.isEnabled())
        self.assertFalse(self.window.target_user_input.isEnabled())
        self.assertFalse(self.window.target_pass_input.isEnabled())
        self.assertFalse(self.window.target_db_input.isEnabled())
        self.assertFalse(self.window.btn_browse_target.isEnabled())
        
        self.assertFalse(self.window.btn_test_conn.isEnabled())
        self.assertFalse(self.window.db_path_input.isEnabled())
        self.assertFalse(self.window.btn_browse.isEnabled())
        self.assertFalse(self.window.combo_acc.isEnabled())
        self.assertFalse(self.window.tgl_awal.isEnabled())
        self.assertFalse(self.window.tgl_akhir.isEnabled())
        self.assertFalse(self.window.target_ppn_input.isEnabled())
        self.assertFalse(self.window.btn_proses.isEnabled())
        self.assertFalse(self.window.btn_export.isEnabled())

        # 2. Multithreading: run event loop synchronously so Qt signals/callbacks execute
        # without freezing the main thread, waiting for background worker completion.
        loop = QEventLoop()
        self.window.worker.finished.connect(loop.quit)
        self.window.worker.error_signal.connect(loop.quit)
        
        # Safe execution timeout
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(4000)
        
        loop.exec_()
        
        # 3. State Management: Inputs should be re-enabled upon thread finish
        self.assertTrue(self.window.source_host_input.isEnabled())
        self.assertTrue(self.window.target_host_input.isEnabled())
        self.assertTrue(self.window.db_path_input.isEnabled())
        self.assertTrue(self.window.btn_proses.isEnabled())
        
        # 4. Real-time logging: Log widget must contain actions recorded during process run
        self.assertGreater(self.window.log_widget.count(), 0)
        
        # Ensure log lines reflect actual operations from backend callbacks
        log_contents = [self.window.log_widget.item(i).text() for i in range(self.window.log_widget.count())]
        self.assertTrue(any("Start Reduction" in line or "Reduce Quantity" in line for line in log_contents))

        # 5. Post-process summary: QMessageBox.information should show summary to user
        self.assertTrue(any(call[0] == "info" and "Sukses" in call[1] for call in self.msg_box_calls))
        self.assertTrue(self.window.btn_export.isEnabled())

    def test_4_csv_export_operation(self):
        """Verifies that clicking "Export" generates a CSV containing the detail of adjustments."""
        # 1. Prepare run data
        self.window.db_path_input.setText(self.db_path)
        self.window.target_db_input.setText(self.target_db_path)
        self.window.set_inputs_enabled(True)
        self.window.load_accounts()
        QApplication.processEvents()
        
        self.window.combo_acc.setCurrentIndex(2)
        self.window.tgl_awal.setDate(QDate(2026, 6, 1))
        self.window.tgl_akhir.setDate(QDate(2026, 6, 30))
        self.window.target_ppn_input.setText("-10000.0")

        # Run process to populate log details
        QTest.mouseClick(self.window.btn_proses, Qt.LeftButton)
        
        loop = QEventLoop()
        self.window.worker.finished.connect(loop.quit)
        loop.exec_()

        # 2. Mock QFileDialog to return a temp CSV output filename
        temp_csv = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        csv_path = temp_csv.name
        temp_csv.close()

        original_getSave = QFileDialog.getSaveFileName
        QFileDialog.getSaveFileName = lambda *args, **kwargs: (csv_path, "CSV Files (*.csv)")

        try:
            # Trigger CSV export
            QTest.mouseClick(self.window.btn_export, Qt.LeftButton)

            # Assert file exists and contains correct headers and details
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                self.assertGreater(len(reader), 1)
                self.assertEqual(reader[0], ["Index", "Tindakan / Action Log"])
                # The first row contains detailed logs of the reduction actions
                self.assertTrue(any("Action" in row[1] for row in reader[1:]))
        finally:
            # Clean up original file dialog function and temp csv file
            QFileDialog.getSaveFileName = original_getSave
            try:
                os.remove(csv_path)
            except OSError:
                pass

    def test_5_stale_accounts_cleared_on_invalid_db(self):
        """Verifies that the account combo box is cleared when an invalid database is selected."""
        # First load valid accounts
        self.window.db_path_input.setText(self.db_path)
        self.window.target_db_input.setText(self.db_path)
        self.window.set_inputs_enabled(True)
        self.window.load_accounts()
        QApplication.processEvents()
        self.assertGreater(self.window.combo_acc.count(), 1)
        
        # Now set an invalid db path
        self.window.db_path_input.setText("non_existent_file.db")
        self.window.load_accounts()
        QApplication.processEvents()
        
        # Verify it has been cleared and contains only "Select Account..."
        self.assertEqual(self.window.combo_acc.count(), 1)
        self.assertEqual(self.window.combo_acc.itemText(0), "Select Account...")

    def test_6_database_casing_support(self):
        """Verifies that database paths with uppercase extensions (like .DB) are supported."""
        temp_db = tempfile.NamedTemporaryFile(suffix=".DB", delete=False)
        db_path_upper = temp_db.name
        temp_db.close()
        try:
            create_mock_db(db_path_upper)
            self.window.db_path_input.setText(db_path_upper)
            self.window.set_inputs_enabled(True)
            self.window.load_accounts()
            QApplication.processEvents()
            # It should load the accounts successfully because .DB is recognized
            self.assertGreater(self.window.combo_acc.count(), 1)
            self.assertEqual(self.window.combo_acc.itemData(1), ("001",))
        finally:
            try:
                os.remove(db_path_upper)
            except OSError:
                pass

    def test_7_remote_mysql_bypass(self):
        """Verifies that MySQL connections bypass the local file existence check."""
        # Set database path to a MySQL schema name (not ending with .db or .sqlite)
        self.window.db_path_input.setText("my_mysql_database")
        self.window.target_db_input.setText("my_mysql_target_database")
        # Ensure combo box has account selected (otherwise it stops at account check)
        self.window.combo_acc.addItem("Account 001", "001")
        self.window.combo_acc.setCurrentIndex(self.window.combo_acc.count() - 1)
        self.window.target_ppn_input.setText("100.0")
        
        start_called = [False]
        window_ref = self.window
        def mock_start(worker_self):
            start_called[0] = True
            window_ref.set_process_running(False)
        WorkerThread.start = mock_start
        
        try:
            self.window.click_proses()
            self.assertTrue(start_called[0])
            critical_calls = [call for call in self.msg_box_calls if call[0] == "critical"]
            self.assertFalse(any("Invalid database path" in call[2] for call in critical_calls))
        finally:
            if hasattr(WorkerThread, 'start') and 'start' in WorkerThread.__dict__:
                del WorkerThread.start

    def test_8_window_close_guard(self):
        """Verifies that window close is guarded while worker thread is active."""
        # 1. When worker is running
        class MockWorker:
            def isRunning(self):
                return True
        self.window.worker = MockWorker()
        
        class MockCloseEvent:
            def __init__(self):
                self._accepted = False
            def accept(self):
                self._accepted = True
            def ignore(self):
                self._accepted = False
                
        event = MockCloseEvent()
        self.window.closeEvent(event)
        self.assertFalse(event._accepted)
        
        # Cleanup so tearDown doesn't hang
        self.window.worker = None
        self.window.set_process_running(False)
        # Verify warning dialog was shown
        warning_calls = [call for call in self.msg_box_calls if call[0] == "warning"]
        self.assertTrue(any("Proses penyesuaian sedang berjalan" in call[2] for call in warning_calls))
        
        # 2. When worker is not running/None
        self.window.worker = None
        event2 = MockCloseEvent()
        self.window.closeEvent(event2)
        self.assertTrue(event2._accepted)

    def test_9_connection_testing(self):
        """Verifies that Test Connection button triggers connection testing and handles success."""
        self.window.source_db_input.setText(self.db_path)
        self.window.target_db_input.setText(self.db_path)
        QApplication.processEvents()
        
        # Click test connection
        QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)
        
        # It should lock inputs
        self.assertFalse(self.window.btn_test_conn.isEnabled())
        
        # Wait for the worker thread to finish
        loop = QEventLoop()
        self.window.conn_worker.finished_signal.connect(lambda success, err: loop.quit())
        
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(4000)
        
        loop.exec_()
        
        # Verify inputs are re-enabled and QMessageBox shows success
        self.assertTrue(self.window.btn_test_conn.isEnabled())
        self.assertTrue(any(call[0] == "info" and "Connection test succeeded" in call[2] for call in self.msg_box_calls))

    def test_10_connection_testing_failure(self):
        """Verifies that Test Connection button handles failures correctly."""
        # Mock test_dual_connection to fail
        from unittest.mock import patch
        with patch("adjustment_ppn_gui.workers.test_dual_connection") as mock_test_conn:
            mock_test_conn.side_effect = Exception("Connection refused by target database")
            
            self.window.source_db_input.setText(self.db_path)
            self.window.target_db_input.setText(self.db_path)
            QApplication.processEvents()
            
            # Click test connection
            QTest.mouseClick(self.window.btn_test_conn, Qt.LeftButton)
            
            # Wait for worker thread to finish
            loop = QEventLoop()
            self.window.conn_worker.finished_signal.connect(lambda success, err: loop.quit())
            loop.exec_()
            
            # Verify inputs are re-enabled
            self.assertTrue(self.window.btn_test_conn.isEnabled())
            # Verify critical message box was shown with error message
            critical_calls = [call for call in self.msg_box_calls if call[0] == "critical"]
            self.assertTrue(any("Connection refused by target database" in call[2] for call in critical_calls))
            
            # Verify status log has error message
            log_contents = [self.window.log_widget.item(i).text() for i in range(self.window.log_widget.count())]
            self.assertTrue(any("Connection test failed" in line for line in log_contents))

    def test_11_empty_entries_validation(self):
        """Verifies that empty fields trigger validation and show critical messages."""
        # Scenario 1: Empty database path
        self.window.db_path_input.setText("")
        QApplication.processEvents()
        self.window.click_proses()
        self.assertTrue(any("Invalid database path" in call[2] for call in self.msg_box_calls))
        self.msg_box_calls.clear()

        # Scenario 2: Valid database path but empty account
        self.window.db_path_input.setText(self.db_path)
        self.window.target_db_input.setText(self.db_path)
        QApplication.processEvents()
        self.window.combo_acc.setCurrentIndex(0) # Select Account... (placeholder)
        self.window.target_ppn_input.setText("-1000.0")
        self.window.click_proses()
        self.assertTrue(any("Please select an account" in call[2] for call in self.msg_box_calls))
        self.msg_box_calls.clear()

        # Scenario 3: Valid database and account, but empty target PPN
        self.window.db_path_input.setText(self.db_path)
        self.window.target_db_input.setText(self.db_path)
        self.window.load_accounts()
        QApplication.processEvents()
        self.window.combo_acc.setCurrentIndex(2)
        self.window.target_ppn_input.setText("")
        QApplication.processEvents()
        self.window.click_proses()
        self.assertTrue(any("Please input target PPN" in call[2] for call in self.msg_box_calls))


if __name__ == '__main__':
    unittest.main()

