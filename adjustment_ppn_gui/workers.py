# -*- coding: utf-8 -*-
import sqlite3
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

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
