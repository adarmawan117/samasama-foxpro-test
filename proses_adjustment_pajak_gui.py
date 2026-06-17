# -*- coding: utf-8 -*-
import sys
import os
import sqlite3
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QMessageBox, QDateEdit, QFormLayout, QProgressBar, 
                             QListWidget, QLineEdit, QFileDialog, QGroupBox, QMenu)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QDoubleValidator

# Import backend functions
from proses_adjustment_pajak import (
    get_db_connection,
    test_dual_connection,
    create_tabungan_dan_hutang_table,
    proses_pengurangan_omset,
    proses_penambahan_omset,
    distribusikan_global_gap,
    check_target_db_exists,
    clone_full_database,
    DatabaseNotFoundError,
    check_transactions_exist_in_range,
    purge_transactions_in_range,
    sync_raw_transactions_in_range,
    rollback_savings_in_range,
    RerunDetectedException
)

class TestConnectionWorker(QThread):
    finished_signal = pyqtSignal(bool, str) # success, error_message
    db_not_found_signal = pyqtSignal(str)

    def __init__(self, source_config, target_config, sandbox):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.sandbox = sandbox

    def run(self):
        try:
            is_sandbox = self.sandbox
            
            # 1. Test Source DB first
            try:
                from proses_adjustment_pajak import get_db_connection
                conn = get_db_connection(sandbox=is_sandbox, **self.source_config)
                if hasattr(conn, 'close'):
                    conn.close()
            except Exception as e:
                self.finished_signal.emit(False, f"Source DB Error: {str(e)}")
                return
            
            # 2. Check target DB existence
            if not check_target_db_exists(self.target_config, sandbox=is_sandbox):
                self.db_not_found_signal.emit("Database Target belum ada.")
                return

            # 3. Test dual connection
            test_dual_connection(self.source_config, self.target_config, sandbox=self.sandbox)
            self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class WorkerThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, float, list) # success, final_gap, logs
    error_signal = pyqtSignal(str)
    db_not_found_signal = pyqtSignal(str, dict)
    rerun_warning_signal = pyqtSignal(str, dict)

    def __init__(self, source_config, target_config, acc, start_date, end_date, target_ppn, force_rerun=False):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.acc = acc
        self.start_date = start_date
        self.end_date = end_date
        self.target_ppn = target_ppn
        self.force_rerun = force_rerun
        self.log_records = []

    def run(self):
        source_conn = None
        target_conn = None
        try:
            source_db = self.source_config.get('database', '')
            target_db = self.target_config.get('database', '')
            is_sandbox = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))
            
            # Check if target db exists
            if not check_target_db_exists(self.target_config, sandbox=is_sandbox):
                raise DatabaseNotFoundError("Database Target belum ada.")

            source_conn = get_db_connection(sandbox=is_sandbox, **self.source_config)
            target_conn = get_db_connection(sandbox=is_sandbox, **self.target_config)
            create_tabungan_dan_hutang_table(target_conn, is_sqlite=is_sandbox)

            # Check if rerun
            if check_transactions_exist_in_range(target_conn, self.acc, self.start_date, self.end_date):
                if not self.force_rerun:
                    self.rerun_warning_signal.emit(
                        "Transaksi untuk range tanggal ini sudah ada di target database. Apakah Anda ingin mengulang (rerun)?",
                        {
                            "acc": self.acc,
                            "start_date": self.start_date,
                            "end_date": self.end_date,
                            "target_ppn": self.target_ppn
                        }
                    )
                    return
                else:
                    rollback_savings_in_range(target_conn, self.acc, self.start_date, self.end_date)
                    purge_transactions_in_range(target_conn, self.acc, self.start_date, self.end_date)
                    sync_raw_transactions_in_range(source_conn, target_conn, self.acc, self.start_date, self.end_date)
            else:
                sync_raw_transactions_in_range(source_conn, target_conn, self.acc, self.start_date, self.end_date)

            def local_callback(msg):
                self.log_records.append(msg)
                self.progress_signal.emit(msg)

            target_val = self.target_ppn
            final_gap = 0.0

            if target_val < 0:
                global_gap = proses_pengurangan_omset(source_conn, target_conn, self.acc, self.start_date, self.end_date, target_val, log_callback=local_callback)
                if abs(global_gap) > 0.001:
                    distribusikan_global_gap(source_conn, target_conn, self.acc, self.start_date, self.end_date, global_gap, log_callback=local_callback)
                final_gap = global_gap
            elif target_val > 0:
                global_gap = proses_penambahan_omset(source_conn, target_conn, self.acc, self.start_date, self.end_date, target_val, log_callback=local_callback)
                if abs(global_gap) > 0.001:
                    distribusikan_global_gap(source_conn, target_conn, self.acc, self.start_date, self.end_date, global_gap, log_callback=local_callback)
                final_gap = global_gap
            else:
                # Target PPN = 0 balancing (same as main in backend)
                cursor_src = source_conn.cursor()
                cursor_tgt = target_conn.cursor()
                cursor_src.execute("""
                    SELECT TGL_JUAL, F_JUAL, COUNT(*) 
                    FROM djual 
                    WHERE ACC = ? AND TGL_JUAL >= ? AND TGL_JUAL <= ?
                    GROUP BY TGL_JUAL, F_JUAL
                """ if is_sandbox else """
                    SELECT TGL_JUAL, F_JUAL, COUNT(*) 
                    FROM djual 
                    WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
                    GROUP BY TGL_JUAL, F_JUAL
                """, (self.acc, self.start_date, self.end_date))
                receipts = cursor_src.fetchall()
                if len(receipts) >= 2:
                    cursor_src.execute("""
                        SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.HRG_BELI
                        FROM djual d
                        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                        WHERE d.ACC = ? AND d.TGL_JUAL >= ? AND d.TGL_JUAL <= ? AND b.PAJAK = 1
                        ORDER BY d.HRG_JUAL DESC, d.URUTAN DESC
                    """ if is_sandbox else """
                        SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.HRG_BELI
                        FROM djual d
                        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                        WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
                        ORDER BY d.HRG_JUAL DESC, d.URUTAN DESC
                    """, (self.acc, self.start_date, self.end_date))
                    ppn_items = cursor_src.fetchall()
                    
                    receipt_counts = {(r[0], r[1]): r[2] for r in receipts}
                    
                    reduce_item = None
                    for item in ppn_items:
                        tgl, f_jual, kode, qty, price, urutan, hrg_beli = item
                        count = receipt_counts[(tgl, f_jual)]
                        max_q = qty if count > 1 else qty - 1
                        if max_q >= 1:
                            reduce_item = item
                            break
                    
                    if reduce_item:
                        tgl_red, f_red, kode_red, qty_red, price_red, urutan_red, hrg_beli_red = reduce_item
                        new_qty = qty_red - 1
                        if new_qty <= 0:
                            cursor_tgt.execute("DELETE FROM djual WHERE urutan = ?" if is_sandbox else "DELETE FROM djual WHERE urutan = %s", (urutan_red,))
                        else:
                            cursor_tgt.execute("UPDATE djual SET jumlah = ? WHERE urutan = ?" if is_sandbox else "UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan_red))
                        
                        target_receipt = None
                        for r in receipts:
                            tgl_target, f_target, _ = r
                            if f_target != f_red:
                                target_receipt = r
                                break
                        
                        if target_receipt:
                            tgl_add, f_add, _ = target_receipt
                            cursor_tgt.execute("""
                                SELECT urutan FROM djual 
                                WHERE ACC = ? AND TGL_JUAL = ? AND F_JUAL = ? AND KODE_BRG = ?
                            """ if is_sandbox else """
                                SELECT urutan FROM djual 
                                WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s
                            """, (self.acc, tgl_add, f_add, kode_red))
                            existing = cursor_tgt.fetchone()
                            if existing:
                                cursor_tgt.execute("UPDATE djual SET jumlah = jumlah + 1 WHERE urutan = ?" if is_sandbox else "UPDATE djual SET jumlah = jumlah + 1 WHERE urutan = %s", (existing[0],))
                            else:
                                cursor_tgt.execute("""
                                    INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                                    VALUES (?, ?, ?, ?, 1.0, ?, ?, 0.0, 0.0, 0.0, 0.0, 10.0)
                                """ if is_sandbox else """
                                    INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                                    VALUES (%s, %s, %s, %s, 1.0, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
                                """, (tgl_add, f_add, self.acc, kode_red, hrg_beli_red, price_red))
                        local_callback("Action: Balanced Target PPN=0 | Shifted 1 unit of " + kode_red + " from " + f_red + " to " + f_add)

            target_conn.commit()
            self.finished_signal.emit(True, final_gap, self.log_records)
        except DatabaseNotFoundError as e:
            self.db_not_found_signal.emit(str(e), self.target_config)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_signal.emit(str(e))
        finally:
            if source_conn and hasattr(source_conn, 'close'):
                try:
                    source_conn.close()
                except Exception:
                    pass
            if target_conn and hasattr(target_conn, 'close'):
                try:
                    target_conn.close()
                except Exception:
                    pass

class CloneWorkerThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str) # success, message

    def __init__(self, source_config, target_config, sandbox):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.sandbox = sandbox

    def run(self):
        try:
            def local_callback(msg):
                self.progress_signal.emit(msg)
            clone_full_database(self.source_config, self.target_config, self.sandbox, log_callback=local_callback)
            self.finished_signal.emit(True, "Cloning database completed successfully.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

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

        # Automatically try loading accounts if path is changed
        # self.source_db_input.textChanged.connect(self.load_accounts)

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
            self.log_status("System: Database target tidak ditemukan, setuju untuk clone.")
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
        acc = self.combo_acc.currentData()
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ProsesAdjustmentPajakApp()
    ex.show()
    sys.exit(app.exec_())
