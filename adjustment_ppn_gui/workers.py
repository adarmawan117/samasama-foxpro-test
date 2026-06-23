# -*- coding: utf-8 -*-
import sqlite3
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

# Import backend functions from modular paths
from adjustment_ppn_core.database.connection import (
    get_db_connection,
    test_dual_connection,
    DatabaseNotFoundError,
    RerunDetectedException
)
from adjustment_ppn_core.schema.migrations import (
    create_tabungan_dan_hutang_table
)
from adjustment_ppn_core.calculator.adjustment import (
    proses_pengurangan_omset,
    proses_penambahan_omset,
    distribusikan_global_gap
)
from adjustment_ppn_core.schema.cloning import (
    check_target_db_exists,
    clone_full_database
)
from adjustment_ppn_core.etl.sync_manager import (
    check_transactions_exist_in_range,
    purge_transactions_in_range,
    sync_raw_transactions_in_range,
    sync_master_data
)
from adjustment_ppn_core.etl.ledger_rollback import (
    rollback_savings_in_range
)

class TestConnectionWorker(QThread):
    finished_signal = pyqtSignal(bool, str) # success, error_message
    db_not_found_signal = pyqtSignal(str)

    def __init__(self, source_config, target_config, sandbox):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.sandbox = sandbox

    def _translate_db_error(self, err_str, context="Database"):
        err_str = str(err_str)
        if "1049" in err_str:
            return f"Gagal Terhubung: {context} tidak ditemukan di server. Pastikan nama database sudah benar."
        elif "1045" in err_str:
            return f"Gagal Terhubung: Akses ditolak untuk {context}. Pastikan Username dan Password sudah benar."
        elif "2003" in err_str or "2002" in err_str:
            return f"Gagal Terhubung: Server {context} tidak merespons. Pastikan Host/IP dan Port sudah benar, serta server MySQL sedang menyala."
        elif "no such table" in err_str:
            return f"Gagal Terhubung: Struktur tabel pada {context} tidak sesuai atau tabel belum dibuat."
        else:
            return f"Terjadi kesalahan pada koneksi {context}:\n{err_str}"

    def run(self):
        try:
            is_sandbox = self.sandbox
            
            # 1. Test Source DB first
            try:
                from adjustment_ppn_core.database.connection import get_db_connection
                conn = get_db_connection(sandbox=is_sandbox, **self.source_config)
                if hasattr(conn, 'close'):
                    conn.close()
            except Exception as e:
                friendly_msg = self._translate_db_error(e, "Database Asal (Source)")
                self.finished_signal.emit(False, friendly_msg)
                return
            
            # 2. Check target DB existence
            if not check_target_db_exists(self.target_config, sandbox=is_sandbox):
                self.db_not_found_signal.emit("Database Target belum ada.")
                return
 
            # 3. Test dual connection
            test_dual_connection(self.source_config, self.target_config, sandbox=self.sandbox)
            self.finished_signal.emit(True, "")
        except Exception as e:
            friendly_msg = self._translate_db_error(e, "Database Target")
            self.finished_signal.emit(False, friendly_msg)

class CurrentValueCalculatorWorker(QThread):
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, source_config, target_config, sandbox, acc, start_date, end_date):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.sandbox = sandbox
        self.acc = acc
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            from adjustment_ppn_core.database.connection import get_db_connection
            conn = get_db_connection(sandbox=self.sandbox, **self.source_config)
            cursor = conn.cursor()
            
            if self.acc == "ALL":
                acc_tuple = ('A1', 'A3')
            else:
                acc_tuple = self.acc if isinstance(self.acc, (list, tuple)) else (self.acc,)
            placeholders = ", ".join(["?"] if self.sandbox else ["%s"] * len(acc_tuple))
            
            # Real Jual (Penjualan)
            djual_query = f"""
                SELECT 
                    SUM(CASE WHEN b.PAJAK IN (1, 3) THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END),
                    SUM(CASE WHEN b.PAJAK = 2 THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END)
                FROM djual d
                LEFT JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if self.sandbox else '%s'} AND d.TGL_JUAL <= {'?' if self.sandbox else '%s'}
            """
            cursor.execute(djual_query, (*acc_tuple, self.start_date, self.end_date))
            row = cursor.fetchone()
            real_ppn = float(row[0]) if row and row[0] is not None else 0.0
            real_btkp = float(row[1]) if row and row[1] is not None else 0.0
            
            # R_Jual (Retur Penjualan)
            drjual_query = f"""
                SELECT 
                    SUM(CASE WHEN b.PAJAK IN (1, 3) THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END),
                    SUM(CASE WHEN b.PAJAK = 2 THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END)
                FROM drjual d
                LEFT JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if self.sandbox else '%s'} AND d.TGL_JUAL <= {'?' if self.sandbox else '%s'}
            """
            cursor.execute(drjual_query, (*acc_tuple, self.start_date, self.end_date))
            row = cursor.fetchone()
            r_ppn = float(row[0]) if row and row[0] is not None else 0.0
            r_btkp = float(row[1]) if row and row[1] is not None else 0.0
            
            self.result_signal.emit({
                'real_ppn': real_ppn,
                'real_btkp': real_btkp,
                'r_ppn': r_ppn,
                'r_btkp': r_btkp,
                'net_ppn': real_ppn - r_ppn,
                'net_btkp': real_btkp - r_btkp
            })
        except Exception as e:
            import traceback
            self.error_signal.emit(f"Gagal menghitung Omset: {str(e)}\n{traceback.format_exc()}")
        finally:
            if 'conn' in locals() and hasattr(conn, 'close'):
                try:
                    conn.close()
                except:
                    pass

class WorkerThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, float, list) # success, final_gap, logs
    error_signal = pyqtSignal(str)
    db_not_found_signal = pyqtSignal(str, dict)
    rerun_warning_signal = pyqtSignal(str, dict)

    def __init__(self, source_config, target_config, acc, start_date, end_date, target_ppn, target_btkp, force_rerun=False):
        super().__init__()
        self.source_config = source_config
        self.target_config = target_config
        self.acc = acc
        self.start_date = start_date
        self.end_date = end_date
        self.target_ppn = target_ppn
        self.target_btkp = target_btkp
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
            
            from adjustment_ppn_core.schema.migrations import create_tabungan_dan_hutang_table, create_log_mutasi_tabungan_table
            create_tabungan_dan_hutang_table(target_conn, is_sqlite=is_sandbox)
            create_log_mutasi_tabungan_table(target_conn, is_sqlite=is_sandbox)

            # Check if rerun
            if check_transactions_exist_in_range(target_conn, self.acc, self.start_date, self.end_date):
                if not self.force_rerun:
                    self.rerun_warning_signal.emit(
                        "Transaksi untuk range tanggal ini sudah ada di target database. Apakah Anda ingin mengulang (rerun)?",
                        {
                            "acc": self.acc,
                            "start_date": self.start_date,
                            "end_date": self.end_date,
                            "target_ppn": self.target_ppn,
                            "target_btkp": self.target_btkp
                        }
                    )
                    return
                else:
                    sync_master_data(source_conn, target_conn, is_sandbox=is_sandbox)
                    rollback_savings_in_range(target_conn, self.acc, self.start_date, self.end_date)
                    purge_transactions_in_range(target_conn, self.acc, self.start_date, self.end_date)
                    sync_raw_transactions_in_range(source_conn, target_conn, self.acc, self.start_date, self.end_date)
            else:
                sync_master_data(source_conn, target_conn, is_sandbox=is_sandbox)
                sync_raw_transactions_in_range(source_conn, target_conn, self.acc, self.start_date, self.end_date)

            def local_callback(msg):
                self.log_records.append(msg)
                self.progress_signal.emit(msg)

            from adjustment_ppn_core.calculator.adjustment_dual import proses_adjustment_dual
            
            import os
            max_workers = max(1, int(os.cpu_count() * 0.7))
            
            try:
                target_ppn_float = float(self.target_ppn)
            except Exception:
                target_ppn_float = 0.0
                
            try:
                target_btkp_float = float(self.target_btkp)
            except Exception:
                target_btkp_float = 0.0
                
            final_gap = proses_adjustment_dual(
                source_conn=source_conn,
                target_conn=target_conn,
                acc=self.acc,
                start_date=self.start_date,
                end_date=self.end_date,
                target_ppn=target_ppn_float,
                target_btkp=target_btkp_float,
                is_sandbox=is_sandbox,
                max_workers=max_workers,
                log_callback=local_callback
            )

            target_conn.commit()
            self.finished_signal.emit(True, final_gap, self.log_records)
        except DatabaseNotFoundError as e:
            self.db_not_found_signal.emit(str(e), self.target_config)
        except Exception as e:
            import traceback
            self.error_signal.emit(f"{str(e)}\n{traceback.format_exc()}")
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
