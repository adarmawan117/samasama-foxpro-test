# -*- coding: utf-8 -*-
import os
import csv
import sqlite3
from PyQt5.QtCore import QObject
from .workers import TestConnectionWorker, WorkerThread, CloneWorkerThread, CurrentValueCalculatorWorker
from adjustment_ppn_core.database.connection import get_db_connection

class AdjustmentPajakController(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.log_records = []
        self.consent_clone = False
        
        self.worker = None
        self.clone_worker = None
        self.conn_worker = None
        self.calc_worker = None
        
        # Connect to view signals
        self.view.browse_source_clicked.connect(self.browse_source_db)
        self.view.browse_target_clicked.connect(self.browse_target_db)
        self.view.test_conn_clicked.connect(self.click_test_conn)
        self.view.proses_clicked.connect(self.click_proses)
        self.view.export_clicked.connect(self.click_export)
        self.view.inputs_changed.connect(self.on_inputs_changed)

    def on_inputs_changed(self):
        if not self.view.tgl_awal.isEnabled():
            return
            
        source_db = self.view.get_source_db().strip()
        is_sandbox = source_db.lower().endswith(('.db', '.sqlite'))
        
        source_config = {
            'host': self.view.source_host_input.text().strip(),
            'port': self.view.source_port_input.text().strip(),
            'user': self.view.source_user_input.text().strip(),
            'password': self.view.source_pass_input.text().strip(),
            'database': source_db
        }
        
        acc = self.view.get_selected_account()
        start_date = self.view.get_start_date()
        end_date = self.view.get_end_date()
        
        self.view.current_omset_input.setText("Menghitung...")
        self.view.target_ppn_input.setEnabled(False)
        self.view.btn_proses.setEnabled(False)
        self.view.log_status("System: Sedang menghitung Omset Saat Ini (REAL JUAL)...")
        
        if self.calc_worker is not None and self.calc_worker.isRunning():
            self.calc_worker.terminate()
            
        self.calc_worker = CurrentValueCalculatorWorker(source_config, {}, is_sandbox, acc, start_date, end_date)
        self.calc_worker.result_signal.connect(self.on_calc_finished)
        
        def on_calc_error(err):
            self.view.current_omset_input.setText("Error")
            self.view.target_ppn_input.setEnabled(True)
            self.view.btn_proses.setEnabled(True)
            self.view.log_status(f"System Error: Gagal menghitung Omset Saat Ini. {err}")
            
        self.calc_worker.error_signal.connect(on_calc_error)
        self.calc_worker.start()

    def on_calc_finished(self, data):
        self.view.current_omset_input.setText(f"{data['real_jual']:,.2f}")
        self.view.current_retur_input.setText(f"{data['r_jual']:,.2f}")
        self.view.current_net_omset_input.setText(f"{data['net_omset']:,.2f}")
        self.view.target_ppn_input.setEnabled(True)
        self.view.btn_proses.setEnabled(True)
        self.view.log_status("System: Perhitungan Omset Saat Ini selesai.")

    def browse_source_db(self):
        file_name = self.view.get_open_file_name(
            "Select Source SQLite Database", 
            "SQLite Database (*.db *.sqlite);;All Files (*)"
        )
        if file_name:
            self.view.set_source_db(file_name)

    def browse_target_db(self):
        file_name = self.view.get_open_file_name(
            "Select Target SQLite Database", 
            "SQLite Database (*.db *.sqlite);;All Files (*)"
        )
        if file_name:
            self.view.set_target_db(file_name)

    def click_test_conn(self):
        source_db = self.view.get_source_db().strip()
        target_db = self.view.get_target_db().strip()
        
        is_sandbox = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))
        
        source_config = {
            'host': self.view.source_host_input.text().strip(),
            'port': self.view.source_port_input.text().strip(),
            'user': self.view.source_user_input.text().strip(),
            'password': self.view.source_pass_input.text().strip(),
            'database': source_db
        }
        
        target_config = {
            'host': self.view.target_host_input.text().strip(),
            'port': self.view.target_port_input.text().strip(),
            'user': self.view.target_user_input.text().strip(),
            'password': self.view.target_pass_input.text().strip(),
            'database': target_db
        }
        
        # Lock inputs & buttons
        self.view.set_inputs_enabled(False)
        self.view.set_process_running(True)
        self.view.log_status("System: Testing dual database connections...")
        
        self.conn_worker = TestConnectionWorker(source_config, target_config, is_sandbox)
        # Expose worker to view for compatibility
        self.view.conn_worker = self.conn_worker
        
        self.conn_worker.finished_signal.connect(self.on_test_conn_finished)
        self.conn_worker.db_not_found_signal.connect(self.on_test_conn_db_not_found)
        self.conn_worker.start()

    def on_test_conn_db_not_found(self, err_msg):
        self.view.set_inputs_enabled(True)
        self.view.set_process_running(False)
        reply = self.view.show_question_message(
            "Database Target Belum Ada",
            "Database Target belum ada. Apakah Anda ingin melanjutkan dengan mengkloning saat proses berjalan?"
        )
        if reply:
            self.consent_clone = True
            self.view.consent_clone = True
            self.save_settings()
            self.load_accounts()
            self.view.log_status("System: Database target tidak ditemukan, setuju to clone.")
            self.view.show_info_message(
                "Info", 
                "Silakan isi parameter lalu klik Proses. Database akan dikloning otomatis."
            )
        else:
            self.view.combo_acc.setEnabled(False)
            self.view.tgl_awal.setEnabled(False)
            self.view.tgl_akhir.setEnabled(False)
            self.view.target_ppn_input.setEnabled(False)
            self.view.btn_proses.setEnabled(False)
            self.view.btn_export.setEnabled(False)
            self.view.log_status("System: Connection test failed: Database Target belum ada and user menolak clone.")
            self.view.show_critical_message("Connection Error", "Database Target belum ada.")

    def save_settings(self):
        import json
        import os
        source_config = {
            'host': self.view.source_host_input.text().strip(),
            'port': self.view.source_port_input.text().strip(),
            'user': self.view.source_user_input.text().strip(),
            'password': self.view.source_pass_input.text().strip(),
            'database': self.view.source_db_input.text().strip()
        }
        target_config = {
            'host': self.view.target_host_input.text().strip(),
            'port': self.view.target_port_input.text().strip(),
            'user': self.view.target_user_input.text().strip(),
            'password': self.view.target_pass_input.text().strip(),
            'database': self.view.target_db_input.text().strip()
        }
        data = {'source': source_config, 'target': target_config}
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "connection_settings.json")
        
        try:
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=4)
            self.view.log_status("System: Connection settings automatically saved to JSON.")
        except Exception as e:
            self.view.log_status(f"System Error: Failed to save connection settings: {e}")

    def on_test_conn_finished(self, success, err_msg):
        self.view.set_inputs_enabled(True)
        self.view.set_process_running(False)
        if success:
            self.save_settings()
            self.view.show_info_message("Success", "Connection test succeeded!")
            self.view.log_status("System: Connection test succeeded. Settings saved. Loading accounts...")
            self.load_accounts()
            self.on_inputs_changed()
        else:
            self.view.combo_acc.setEnabled(False)
            self.view.tgl_awal.setEnabled(False)
            self.view.tgl_akhir.setEnabled(False)
            self.view.target_ppn_input.setEnabled(False)
            self.view.btn_proses.setEnabled(False)
            self.view.btn_export.setEnabled(False)
            self.view.show_critical_message("Connection Error", err_msg)
            self.view.log_status(f"System: Connection test failed: {err_msg}")

    def load_accounts(self):
        self.view.combo_acc.blockSignals(True)
        try:
            self.view.combo_acc.clear()
            self.view.combo_acc.addItem("Select Account...", "")

            db_path = self.view.get_source_db().strip()
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
                    if not records:
                        cursor.execute("SELECT DISTINCT ACC FROM barang ORDER BY ACC")
                        records = [(r[0], f"Account {r[0]}") for r in cursor.fetchall() if r[0]]
                else:
                    source_config = {
                        'host': self.view.source_host_input.text().strip(),
                        'port': self.view.source_port_input.text().strip(),
                        'user': self.view.source_user_input.text().strip(),
                        'password': self.view.source_pass_input.text().strip(),
                        'database': db_path
                    }
                    conn = get_db_connection(sandbox=False, **source_config)
                    cursor = conn.cursor()
                    cursor.execute("SELECT ACC, NAMA_ACC FROM accinv ORDER BY ACC")
                    records = cursor.fetchall()
                    if not records:
                        cursor.execute("SELECT DISTINCT ACC FROM barang ORDER BY ACC")
                        records = [(r[0], f"Account {r[0]}") for r in cursor.fetchall() if r[0]]

                self.view.combo_acc.clear()
                self.view.combo_acc.addItem("Select Account...", "")
                
                # Clean records to remove trailing spaces from FoxPro/MySQL CHAR fields
                clean_records = []
                for rec in records:
                    acc_code = str(rec[0]).strip() if rec[0] else ""
                    acc_name = str(rec[1]).strip() if rec[1] else f"Account {acc_code}"
                    if acc_code:
                        clean_records.append((acc_code, acc_name))
                
                # Check if A1 and A3 both exist
                has_a1 = any(r[0] == 'A1' for r in clean_records)
                has_a3 = any(r[0] == 'A3' for r in clean_records)
                
                if has_a1 and has_a3:
                    self.view.combo_acc.addItem("ALL - A1 & A3 (Gabungan)", "ALL")
                    
                for rec in clean_records:
                    self.view.combo_acc.addItem(f"{rec[0]} - {rec[1]}", rec[0])
                    
                # Default to A1 for testing phase
                idx = self.view.combo_acc.findData("A1")
                if idx >= 0:
                    self.view.combo_acc.setCurrentIndex(idx)
                    
            except Exception as e:
                self.view.combo_acc.clear()
                self.view.combo_acc.addItem("Select Account...", "")
                self.view.log_status(f"System: Error loading accounts: {e}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
        finally:
            self.view.combo_acc.blockSignals(False)

    def click_proses(self):
        source_db = self.view.get_source_db().strip()
        target_db = self.view.get_target_db().strip()
        acc = self.view.get_selected_account()
        start_date = self.view.get_start_date()
        end_date = self.view.get_end_date()
        target_ppn_str = self.view.get_target_ppn().strip()

        is_sqlite = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))
        if not source_db or (is_sqlite and not os.path.exists(source_db)):
            self.view.show_critical_message("Error", "Invalid database path selected.")
            return

        if not acc:
            self.view.show_critical_message("Error", "Please select an account.")
            return

        if acc == "ALL":
            acc_tuple = ('A1', 'A3')
        else:
            acc_tuple = (acc,)

        if not target_ppn_str:
            self.view.show_critical_message("Error", "Please input target PPN.")
            return

        try:
            target_ppn = float(target_ppn_str.replace(',', '.'))
        except ValueError:
            self.view.show_critical_message("Error", "Target PPN must be a numeric value.")
            return

        # Lock Inputs & Start Process
        self.view.set_inputs_enabled(False)
        self.view.set_process_running(True)
        self.view.progress_bar.setVisible(True)
        self.view.progress_bar.setRange(0, 0) # Indeterminate progress
        self.view.clear_log()
        self.log_records = []
        self.view.log_records = []
        self.view.set_export_enabled(False)

        self.view.log_status("System: Starting background adjustment process...")

        source_config = {
            'host': self.view.source_host_input.text().strip(),
            'port': self.view.source_port_input.text().strip(),
            'user': self.view.source_user_input.text().strip(),
            'password': self.view.source_pass_input.text().strip(),
            'database': source_db
        }
        target_config = {
            'host': self.view.target_host_input.text().strip(),
            'port': self.view.target_port_input.text().strip(),
            'user': self.view.target_user_input.text().strip(),
            'password': self.view.target_pass_input.text().strip(),
            'database': target_db
        }

        self.worker = WorkerThread(source_config, target_config, acc_tuple, start_date, end_date, target_ppn)
        # Expose worker to view for compatibility/closeEvent
        self.view.worker = self.worker
        
        self.worker.progress_signal.connect(self.view.log_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.db_not_found_signal.connect(self.on_db_not_found)
        self.worker.rerun_warning_signal.connect(self.on_rerun_warning)
        self.worker.start()

    def on_rerun_warning(self, msg, data):
        reply = self.view.show_question_message("Konfirmasi Rerun", msg)
        if not reply:
            self.view.set_inputs_enabled(True)
            self.view.set_process_running(False)
            self.view.progress_bar.setVisible(False)
            self.view.log_status("System: Adjustment process aborted by user on rerun warning.")
            return

        self.view.log_status("System: Restarting adjustment with force rerun enabled...")
        
        source_db = self.view.get_source_db().strip()
        target_db = self.view.get_target_db().strip()
        
        self.worker = WorkerThread(
            source_config={
                'host': self.view.source_host_input.text().strip(),
                'port': self.view.source_port_input.text().strip(),
                'user': self.view.source_user_input.text().strip(),
                'password': self.view.source_pass_input.text().strip(),
                'database': source_db
            },
            target_config={
                'host': self.view.target_host_input.text().strip(),
                'port': self.view.target_port_input.text().strip(),
                'user': self.view.target_user_input.text().strip(),
                'password': self.view.target_pass_input.text().strip(),
                'database': target_db
            },
            acc=data["acc"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            target_ppn=data["target_ppn"],
            force_rerun=True
        )
        self.view.worker = self.worker
        
        self.worker.progress_signal.connect(self.view.log_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.db_not_found_signal.connect(self.on_db_not_found)
        self.worker.rerun_warning_signal.connect(self.on_rerun_warning)
        self.worker.start()

    def on_db_not_found(self, err_msg, target_config):
        if self.consent_clone:
            reply = True
        else:
            reply = self.view.show_question_message(
                "Database Target Belum Ada",
                "Database Target belum ada. Apakah Anda ingin membuat dan mengkloning seluruh isi database dari Original sekarang?"
            )
        if not reply:
            self.view.set_inputs_enabled(True)
            self.view.set_process_running(False)
            self.view.progress_bar.setVisible(False)
            self.view.log_status("System: Adjustment process aborted because target database does not exist.")
            return

        self.view.log_status("System: Starting database cloning in background...")
        source_db = self.view.get_source_db().strip()
        target_db = self.view.get_target_db().strip()
        is_sandbox = source_db.lower().endswith(('.db', '.sqlite')) or target_db.lower().endswith(('.db', '.sqlite'))

        source_config = {
            'host': self.view.source_host_input.text().strip(),
            'port': self.view.source_port_input.text().strip(),
            'user': self.view.source_user_input.text().strip(),
            'password': self.view.source_pass_input.text().strip(),
            'database': source_db
        }

        self.clone_worker = CloneWorkerThread(source_config, target_config, is_sandbox)
        self.view.clone_worker = self.clone_worker
        
        self.clone_worker.progress_signal.connect(self.view.log_status)
        self.clone_worker.finished_signal.connect(self.on_clone_finished)
        self.clone_worker.start()

    def on_clone_finished(self, success, message):
        if success:
            self.view.show_info_message(
                "Sukses",
                "Database Target berhasil dibuat dan dikloning!"
            )
            self.view.log_status("System: Database cloning successful. Restarting adjustment process...")
            self.click_proses()
        else:
            self.view.set_inputs_enabled(True)
            self.view.set_process_running(False)
            self.view.progress_bar.setVisible(False)
            self.view.log_status(f"System Error: Database cloning failed: {message}")
            self.view.show_critical_message(
                "Cloning Error",
                f"Gagal mengkloning database:\n{message}"
            )

    def on_finished(self, success, final_gap, logs):
        self.log_records = logs
        self.view.log_records = logs
        self.view.set_inputs_enabled(True)
        self.view.set_process_running(False)
        self.view.progress_bar.setRange(0, 100)
        self.view.progress_bar.setValue(100)
        self.view.progress_bar.setVisible(False)

        if success:
            self.view.log_status(f"System: Process completed. Final Gap: {final_gap}")
            self.view.set_export_enabled(True)
            self.view.show_info_message(
                "Sukses", 
                f"Proses Penyesuaian Pajak Selesai!\nFinal Remaining Gap: {final_gap:.4f}\nTotal detail tindakan: {len(logs)}"
            )

    def on_error(self, err_msg):
        self.view.set_inputs_enabled(True)
        self.view.set_process_running(False)
        self.view.progress_bar.setVisible(False)
        self.view.log_status(f"System Error: {err_msg}")
        self.view.show_critical_message("Error", f"Terjadi kesalahan saat pemrosesan:\n{err_msg}")

    def click_export(self):
        if not self.log_records:
            self.view.show_warning_message("Warning", "No adjustment details to export.")
            return

        file_name = self.view.get_save_file_name(
            "Export Adjustment Details", 
            "adjustments_detail.csv", 
            "CSV Files (*.csv)"
        )
        if file_name:
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index", "Tindakan / Action Log"])
                    for i, log in enumerate(self.log_records, 1):
                        writer.writerow([i, log])
                self.view.show_info_message(
                    "Sukses", 
                    f"Detail penyesuaian berhasil diekspor ke:\n{file_name}"
                )
            except Exception as e:
                self.view.show_critical_message("Error", f"Gagal mengekspor file: {e}")
