# -*- coding: utf-8 -*-
import sys
import os
import sqlite3
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QMessageBox, QDateEdit, QFormLayout, QProgressBar, 
                             QListWidget, QLineEdit, QFileDialog, QGroupBox, QMenu)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QDoubleValidator

# Import backend functions needed directly in GUI
from proses_adjustment_pajak import get_db_connection

# Load workers
from .workers import TestConnectionWorker, WorkerThread, CloneWorkerThread

class ProsesAdjustmentPajakApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_records = []
        self.consent_clone = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle('PPN Tax Adjustment Tool')
        self.setGeometry(200, 200, 850, 600)

        main_widget = QWidget()
        self.CentralWidget = main_widget
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Title Label
        title = QLabel("PPN Tax Adjustment Tool")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        db_layout = QHBoxLayout()

        # Group 1: Source Database
        source_group = QGroupBox("Source Database (Original)")
        source_group_layout = QFormLayout(source_group)
        
        self.source_host_input = QLineEdit("localhost")
        self.source_host_input.setObjectName("source_host_input")
        source_group_layout.addRow("Host:", self.source_host_input)
        
        self.source_port_input = QLineEdit("3306")
        self.source_port_input.setObjectName("source_port_input")
        source_group_layout.addRow("Port:", self.source_port_input)
        
        self.source_user_input = QLineEdit("root")
        self.source_user_input.setObjectName("source_user_input")
        source_group_layout.addRow("User:", self.source_user_input)
        
        self.source_pass_input = QLineEdit("root")
        self.source_pass_input.setObjectName("source_pass_input")
        self.source_pass_input.setEchoMode(QLineEdit.Password)
        source_group_layout.addRow("Password:", self.source_pass_input)
        
        source_db_layout = QHBoxLayout()
        self.source_db_input = QLineEdit("source_db")
        self.source_db_input.setObjectName("source_db_input")
        self.db_path_input = self.source_db_input # Compatibility alias
        
        self.btn_browse_source = QPushButton("Browse...")
        self.btn_browse_source.setObjectName("btn_browse_source")
        self.btn_browse = self.btn_browse_source # Compatibility alias
        self.btn_browse_source.clicked.connect(self.browse_source_db)
        
        source_db_layout.addWidget(self.source_db_input)
        source_db_layout.addWidget(self.btn_browse_source)
        source_group_layout.addRow("Database Name / Path:", source_db_layout)
        
        db_layout.addWidget(source_group)

        # Group 2: Target Database
        target_group = QGroupBox("Target Database (Pajak)")
        target_group_layout = QFormLayout(target_group)
        
        self.target_host_input = QLineEdit("localhost")
        self.target_host_input.setObjectName("target_host_input")
        target_group_layout.addRow("Host:", self.target_host_input)
        
        self.target_port_input = QLineEdit("3306")
        self.target_port_input.setObjectName("target_port_input")
        target_group_layout.addRow("Port:", self.target_port_input)
        
        self.target_user_input = QLineEdit("root")
        self.target_user_input.setObjectName("target_user_input")
        target_group_layout.addRow("User:", self.target_user_input)
        
        self.target_pass_input = QLineEdit("root")
        self.target_pass_input.setObjectName("target_pass_input")
        self.target_pass_input.setEchoMode(QLineEdit.Password)
        target_group_layout.addRow("Password:", self.target_pass_input)
        
        target_db_layout = QHBoxLayout()
        self.target_db_input = QLineEdit("target_db")
        self.target_db_input.setObjectName("target_db_input")
        
        self.btn_browse_target = QPushButton("Browse...")
        self.btn_browse_target.setObjectName("btn_browse_target")
        self.btn_browse_target.clicked.connect(self.browse_target_db)
        
        target_db_layout.addWidget(self.target_db_input)
        target_db_layout.addWidget(self.btn_browse_target)
        target_group_layout.addRow("Database Name / Path:", target_db_layout)
        
        db_layout.addWidget(target_group)
        layout.addLayout(db_layout)

        # Test Connection Button
        self.btn_test_conn = QPushButton("Test Connection")
        self.btn_test_conn.setObjectName("btn_test_conn")
        self.btn_test_conn.clicked.connect(self.click_test_conn)
        layout.addWidget(self.btn_test_conn)

        # Options Layout
        options_layout = QFormLayout()

        # Account Selection QComboBox
        self.combo_acc = QComboBox()
        self.combo_acc.setObjectName("combo_acc")
        self.combo_acc.addItem("Select Account...", "")
        self.combo_acc.setEnabled(False)
        options_layout.addRow("Account Code:", self.combo_acc)

        # Date range inputs
        self.tgl_awal = QDateEdit()
        self.tgl_awal.setObjectName("tgl_awal")
        self.tgl_awal.setCalendarPopup(True)
        self.tgl_awal.setDisplayFormat("yyyy-MM-dd")
        self.tgl_awal.setDate(QDate(2026, 6, 1))
        self.tgl_awal.setEnabled(False)

        self.tgl_akhir = QDateEdit()
        self.tgl_akhir.setObjectName("tgl_akhir")
        self.tgl_akhir.setCalendarPopup(True)
        self.tgl_akhir.setDisplayFormat("yyyy-MM-dd")
        self.tgl_akhir.setDate(QDate(2026, 6, 30))
        self.tgl_akhir.setEnabled(False)

        options_layout.addRow("Start Date:", self.tgl_awal)
        options_layout.addRow("End Date:", self.tgl_akhir)

        # Target PPN Input
        self.target_ppn_input = QLineEdit()
        self.target_ppn_input.setObjectName("target_ppn_input")
        # Allow negative/positive floating values
        self.target_ppn_input.setValidator(QDoubleValidator(-999999999.0, 999999999.0, 2, self))
        self.target_ppn_input.setEnabled(False)
        options_layout.addRow("Target PPN Adjustment:", self.target_ppn_input)

        layout.addLayout(options_layout)

        # Log status widget
        self.log_widget = QListWidget()
        self.log_widget.setObjectName("log_widget")
        self.log_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_widget.customContextMenuRequested.connect(self.show_log_context_menu)
        layout.addWidget(self.log_widget)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_proses = QPushButton("Proses")
        self.btn_proses.setObjectName("btn_proses")
        self.btn_proses.setEnabled(False)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setEnabled(False) # Only enabled after successful process

        self.btn_proses.clicked.connect(self.click_proses)
        self.btn_export.clicked.connect(self.click_export)

        btn_layout.addWidget(self.btn_proses)
        btn_layout.addWidget(self.btn_export)
        layout.addLayout(btn_layout)

    def browse_source_db(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Source SQLite Database", "", "SQLite Database (*.db *.sqlite);;All Files (*)")
        if file_name:
            self.source_db_input.setText(file_name)

    def browse_target_db(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Target SQLite Database", "", "SQLite Database (*.db *.sqlite);;All Files (*)")
        if file_name:
            self.target_db_input.setText(file_name)

    def click_test_conn(self):
        source_db = self.source_db_input.text().strip()
        target_db = self.target_db_input.text().strip()
        
        is_sandbox = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))
        
        source_config = {
            'host': self.source_host_input.text().strip(),
            'port': self.source_port_input.text().strip(),
            'user': self.source_user_input.text().strip(),
            'password': self.source_pass_input.text().strip(),
            'database': source_db
        }
        
        target_config = {
            'host': self.target_host_input.text().strip(),
            'port': self.target_port_input.text().strip(),
            'user': self.target_user_input.text().strip(),
            'password': self.target_pass_input.text().strip(),
            'database': target_db
        }
        
        # Lock inputs & buttons
        self.set_inputs_enabled(False)
        self.log_status("System: Testing dual database connections...")
        
        self.conn_worker = TestConnectionWorker(source_config, target_config, is_sandbox)
        self.conn_worker.finished_signal.connect(self.on_test_conn_finished)
        self.conn_worker.db_not_found_signal.connect(self.on_test_conn_db_not_found)
        self.conn_worker.start()

    def on_test_conn_db_not_found(self, err_msg):
        self.set_inputs_enabled(True)
        reply = QMessageBox.question(
            self, "Database Target Belum Ada",
            "Database Target belum ada. Apakah Anda ingin melanjutkan dengan mengkloning saat proses berjalan?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.consent_clone = True
            self.load_accounts()
            self.log_status("System: Database target tidak ditemukan, setuju to clone.")
            QMessageBox.information(self, "Info", "Silakan isi parameter lalu klik Proses. Database akan dikloning otomatis.")
        else:
            self.combo_acc.setEnabled(False)
            self.tgl_awal.setEnabled(False)
            self.tgl_akhir.setEnabled(False)
            self.target_ppn_input.setEnabled(False)
            self.btn_proses.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.log_status("System: Connection test failed: Database Target belum ada dan user menolak clone.")
            QMessageBox.critical(self, "Connection Error", "Database Target belum ada.")

    def on_test_conn_finished(self, success, err_msg):
        self.set_inputs_enabled(True)
        if success:
            QMessageBox.information(self, "Success", "Connection test succeeded!")
            self.log_status("System: Connection test succeeded. Loading accounts...")
            self.load_accounts()
        else:
            self.combo_acc.setEnabled(False)
            self.tgl_awal.setEnabled(False)
            self.tgl_akhir.setEnabled(False)
            self.target_ppn_input.setEnabled(False)
            self.btn_proses.setEnabled(False)
            self.btn_export.setEnabled(False)
            QMessageBox.critical(self, "Connection Error", err_msg)
            self.log_status(f"System: Connection test failed: {err_msg}")

    def load_accounts(self):
        self.combo_acc.clear()
        self.combo_acc.addItem("Select Account...", "")

        db_path = self.source_db_input.text().strip()
        if not db_path:
            return

        is_sqlite = db_path.lower().endswith(('.db', '.sqlite'))
        if is_sqlite and not os.path.exists(db_path):
            return

        conn = None
        try:
            if is_sqlite:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT ACC, NAMA_ACC FROM accinv ORDER BY ACC")
                records = cursor.fetchall()
            else:
                source_config = {
                    'host': self.source_host_input.text().strip(),
                    'port': self.source_port_input.text().strip(),
                    'user': self.source_user_input.text().strip(),
                    'password': self.source_pass_input.text().strip(),
                    'database': db_path
                }
                conn = get_db_connection(sandbox=False, **source_config)
                cursor = conn.cursor()
                cursor.execute("SELECT ACC, NAMA_ACC FROM accinv ORDER BY ACC")
                records = cursor.fetchall()

            self.combo_acc.clear()
            self.combo_acc.addItem("Select Account...", "")
            for rec in records:
                self.combo_acc.addItem(f"{rec[0]} - {rec[1]}", rec[0])
        except Exception as e:
            self.combo_acc.clear()
            self.combo_acc.addItem("Select Account...", "")
            self.log_status(f"System: Error loading accounts: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def log_status(self, message):
        self.log_widget.addItem(message)
        self.log_widget.scrollToBottom()

    def show_log_context_menu(self, position):
        menu = QMenu()
        copy_action = menu.addAction("Copy Selected")
        copy_all_action = menu.addAction("Copy All")
        
        action = menu.exec_(self.log_widget.mapToGlobal(position))
        
        if action == copy_action:
            selected_items = self.log_widget.selectedItems()
            if selected_items:
                text = "\n".join([item.text() for item in selected_items])
                QApplication.clipboard().setText(text)
        elif action == copy_all_action:
            text = "\n".join([self.log_widget.item(i).text() for i in range(self.log_widget.count())])
            QApplication.clipboard().setText(text)

    def set_inputs_enabled(self, enabled):
        self.source_host_input.setEnabled(enabled)
        self.source_port_input.setEnabled(enabled)
        self.source_user_input.setEnabled(enabled)
        self.source_pass_input.setEnabled(enabled)
        self.source_db_input.setEnabled(enabled)
        self.btn_browse_source.setEnabled(enabled)
        
        self.target_host_input.setEnabled(enabled)
        self.target_port_input.setEnabled(enabled)
        self.target_user_input.setEnabled(enabled)
        self.target_pass_input.setEnabled(enabled)
        self.target_db_input.setEnabled(enabled)
        self.btn_browse_target.setEnabled(enabled)
        
        self.btn_test_conn.setEnabled(enabled)
        self.combo_acc.setEnabled(enabled)
        self.tgl_awal.setEnabled(enabled)
        self.tgl_akhir.setEnabled(enabled)
        self.target_ppn_input.setEnabled(enabled)
        self.btn_proses.setEnabled(enabled)
        self.btn_export.setEnabled(enabled if not enabled else len(self.log_records) > 0)

    def click_proses(self):
        source_db = self.source_db_input.text().strip()
        target_db = self.target_db_input.text().strip()
        acc = self.combo_acc.itemData(self.combo_acc.currentIndex())
        start_date = self.tgl_awal.date().toString("yyyy-MM-dd")
        end_date = self.tgl_akhir.date().toString("yyyy-MM-dd")
        target_ppn_str = self.target_ppn_input.text().strip()

        is_sqlite = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))
        if not source_db or (is_sqlite and not os.path.exists(source_db)):
            QMessageBox.critical(self, "Error", "Invalid database path selected.")
            return

        if not acc:
            QMessageBox.critical(self, "Error", "Please select an account.")
            return

        if not target_ppn_str:
            QMessageBox.critical(self, "Error", "Please input target PPN.")
            return

        try:
            target_ppn = float(target_ppn_str.replace(',', '.'))
        except ValueError:
            QMessageBox.critical(self, "Error", "Target PPN must be a numeric value.")
            return

        # Lock Inputs & Start Process
        self.set_inputs_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate progress
        self.log_widget.clear()
        self.log_records = []
        self.btn_export.setEnabled(False)

        self.log_status("System: Starting background adjustment process...")

        source_config = {
            'host': self.source_host_input.text().strip(),
            'port': self.source_port_input.text().strip(),
            'user': self.source_user_input.text().strip(),
            'password': self.source_pass_input.text().strip(),
            'database': source_db
        }
        target_config = {
            'host': self.target_host_input.text().strip(),
            'port': self.target_port_input.text().strip(),
            'user': self.target_user_input.text().strip(),
            'password': self.target_pass_input.text().strip(),
            'database': target_db
        }

        self.worker = WorkerThread(source_config, target_config, acc, start_date, end_date, target_ppn)
        self.worker.progress_signal.connect(self.log_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.db_not_found_signal.connect(self.on_db_not_found)
        self.worker.rerun_warning_signal.connect(self.on_rerun_warning)
        self.worker.start()

    def on_rerun_warning(self, msg, data):
        reply = QMessageBox.question(
            self, "Konfirmasi Rerun",
            msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            self.set_inputs_enabled(True)
            self.progress_bar.setVisible(False)
            self.log_status("System: Adjustment process aborted by user on rerun warning.")
            return

        self.log_status("System: Restarting adjustment with force rerun enabled...")
        self.worker = WorkerThread(
            source_config={
                'host': self.source_host_input.text().strip(),
                'port': self.source_port_input.text().strip(),
                'user': self.source_user_input.text().strip(),
                'password': self.source_pass_input.text().strip(),
                'database': self.source_db_input.text().strip()
            },
            target_config={
                'host': self.target_host_input.text().strip(),
                'port': self.target_port_input.text().strip(),
                'user': self.target_user_input.text().strip(),
                'password': self.target_pass_input.text().strip(),
                'database': self.target_db_input.text().strip()
            },
            acc=data["acc"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            target_ppn=data["target_ppn"],
            force_rerun=True
        )
        self.worker.progress_signal.connect(self.log_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.db_not_found_signal.connect(self.on_db_not_found)
        self.worker.rerun_warning_signal.connect(self.on_rerun_warning)
        self.worker.start()

    def on_db_not_found(self, err_msg, target_config):
        if self.consent_clone:
            reply = QMessageBox.Yes
        else:
            reply = QMessageBox.question(
                self, "Database Target Belum Ada",
                "Database Target belum ada. Apakah Anda ingin membuat dan mengkloning seluruh isi database dari Original sekarang?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
        if reply == QMessageBox.No:
            self.set_inputs_enabled(True)
            self.progress_bar.setVisible(False)
            self.log_status("System: Adjustment process aborted because target database does not exist.")
            return

        self.log_status("System: Starting database cloning in background...")
        source_db = self.source_db_input.text().strip()
        target_db = self.target_db_input.text().strip()
        is_sandbox = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))

        source_config = {
            'host': self.source_host_input.text().strip(),
            'port': self.source_port_input.text().strip(),
            'user': self.source_user_input.text().strip(),
            'password': self.source_pass_input.text().strip(),
            'database': source_db
        }

        self.clone_worker = CloneWorkerThread(source_config, target_config, is_sandbox)
        self.clone_worker.progress_signal.connect(self.log_status)
        self.clone_worker.finished_signal.connect(self.on_clone_finished)
        self.clone_worker.start()

    def on_clone_finished(self, success, message):
        if success:
            QMessageBox.information(
                self, "Sukses",
                "Database Target berhasil dibuat dan dikloning!"
            )
            self.log_status("System: Database cloning successful. Restarting adjustment process...")
            self.click_proses()
        else:
            self.set_inputs_enabled(True)
            self.progress_bar.setVisible(False)
            self.log_status(f"System Error: Database cloning failed: {message}")
            QMessageBox.critical(
                self, "Cloning Error",
                f"Gagal mengkloning database:\n{message}"
            )

    def on_finished(self, success, final_gap, logs):
        self.log_records = logs
        self.set_inputs_enabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)

        if success:
            self.log_status(f"System: Process completed. Final Gap: {final_gap}")
            self.btn_export.setEnabled(True)
            QMessageBox.information(
                self, "Sukses", 
                f"Proses Penyesuaian Pajak Selesai!\nFinal Remaining Gap: {final_gap:.4f}\nTotal detail tindakan: {len(logs)}"
            )

    def on_error(self, err_msg):
        self.set_inputs_enabled(True)
        self.progress_bar.setVisible(False)
        self.log_status(f"System Error: {err_msg}")
        QMessageBox.critical(self, "Error", f"Terjadi kesalahan saat pemrosesan:\n{err_msg}")

    def click_export(self):
        if not self.log_records:
            QMessageBox.warning(self, "Warning", "No adjustment details to export.")
            return

        file_name, _ = QFileDialog.getSaveFileName(self, "Export Adjustment Details", "adjustments_detail.csv", "CSV Files (*.csv)")
        if file_name:
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index", "Tindakan / Action Log"])
                    for i, log in enumerate(self.log_records, 1):
                        writer.writerow([i, log])
                QMessageBox.information(self, "Sukses", f"Detail penyesuaian berhasil diekspor ke:\n{file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal mengekspor file: {e}")

    def closeEvent(self, event):
        worker_running = False
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            worker_running = True
        elif hasattr(self, 'clone_worker') and self.clone_worker and self.clone_worker.isRunning():
            worker_running = True
        elif hasattr(self, 'conn_worker') and self.conn_worker and self.conn_worker.isRunning():
            worker_running = True
            
        if worker_running:
            QMessageBox.warning(self, "Warning", "Proses penyesuaian sedang berjalan. Harap tunggu hingga selesai.")
            event.ignore()
        else:
            event.accept()
