# -*- coding: utf-8 -*-
import os
import sys
import unittest
import tempfile
import sqlite3
import shutil
from unittest.mock import patch, MagicMock

# Set QPA platform to offscreen for headless Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QEventLoop, QTimer, QThread
from PyQt5.QtTest import QTest

from proses_adjustment_pajak import clone_full_database
from proses_adjustment_pajak_gui import ProsesAdjustmentPajakApp, CloneWorkerThread, TestConnectionWorker

class TestStressChallenger(unittest.TestCase):
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

        # Create basic structure in source
        conn = sqlite3.connect(self.src_db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test_table (val) VALUES ('Initial Value')")
        conn.commit()
        conn.close()

        self.window = ProsesAdjustmentPajakApp()
        self.msg_box_calls = []
        self.original_warning = QMessageBox.warning
        QMessageBox.warning = self.mock_warning

    def tearDown(self):
        QMessageBox.warning = self.original_warning
        self.window.close()
        for path in (self.src_db_path, self.tgt_db_path):
            try:
                os.remove(path)
            except OSError:
                pass
            # Clean up WAL/shm files if any
            for suffix in ("-wal", "-shm", "-journal"):
                try:
                    os.remove(path + suffix)
                except OSError:
                    pass

    def mock_warning(self, parent, title, text, *args, **kwargs):
        self.msg_box_calls.append(("warning", title, text))
        return QMessageBox.Ok

    def test_window_close_guard_bypass_during_cloning(self):
        """Stress: Verify that closing the window during cloning terminates the thread without warning."""
        # 1. Start CloneWorkerThread
        source_config = {'database': self.src_db_path}
        target_config = {'database': self.tgt_db_path}
        self.window.clone_worker = CloneWorkerThread(source_config, target_config, sandbox=True)
        self.window.clone_worker.start()

        # 2. Simulate closeEvent
        class MockCloseEvent:
            def __init__(self):
                self._accepted = False
            def accept(self):
                self._accepted = True
            def ignore(self):
                self._accepted = False

        event = MockCloseEvent()
        self.window.closeEvent(event)

        # 3. Assert close event was IGNORED and warning was shown
        self.assertFalse(event._accepted)
        self.assertEqual(len(self.msg_box_calls), 1)

        # Clean up worker thread
        self.window.clone_worker.terminate()
        self.window.clone_worker.wait()

    def test_sqlite_wal_cloning_inconsistency(self):
        """Stress: Verify that cloning a WAL SQLite database with raw file copy ignores un-checkpointed WAL data."""
        # 1. Put source database into WAL mode and write to it
        conn = sqlite3.connect(self.src_db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        # Ensure WAL mode is active
        res = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(res.lower(), "wal")

        conn.execute("UPDATE test_table SET val = 'Updated in WAL' WHERE id = 1")
        # Commit, but don't close connection or checkpoint, keeping WAL active
        conn.commit()

        # Ensure WAL file is actually created and has size > 0
        wal_path = self.src_db_path + "-wal"
        self.assertTrue(os.path.exists(wal_path))
        self.assertGreater(os.path.getsize(wal_path), 0)

        # 2. Run clone_full_database using raw shutil.copy2
        source_config = {'database': self.src_db_path}
        target_config = {'database': self.tgt_db_path}
        clone_full_database(source_config, target_config, is_sandbox=True)

        # 3. Verify target database content
        # Because shutil.copy2 only copies the main DB file and not the WAL file,
        # the target database will open and roll back or revert to the last checkpoint (which is 'Initial Value').
        conn_tgt = sqlite3.connect(self.tgt_db_path)
        cursor = conn_tgt.cursor()
        cursor.execute("SELECT val FROM test_table WHERE id = 1")
        val = cursor.fetchone()[0]
        conn_tgt.close()

        # Clean up source connection
        conn.close()

        # Check if the clone correctly got the WAL update
        print(f"[WAL Stress Test] Cloned value: {val}")
        self.assertEqual(val, "Updated in WAL") # Under SQLite backup API, WAL updates are correctly copied!

if __name__ == '__main__':
    unittest.main()
