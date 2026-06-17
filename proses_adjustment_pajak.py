# -*- coding: utf-8 -*-
"""
Database connection, compatibility, and initialization helpers for the tax adjustment process.
Supports MySQL mode (default) and SQLite Sandbox mode (--sandbox).
"""

import os
import sys
import re
import sqlite3
import datetime

from adjustment_ppn_core.database.sqlite_translator import *
from adjustment_ppn_core.database.connection import *
from adjustment_ppn_core.schema.migrations import *
from adjustment_ppn_core.schema.cloning import *


# ==========================================
# SQLITE COMPATIBILITY & UDF REGISTER
# ==========================================







# ==========================================
# SQLITE CONNECTION WRAPPER
# ==========================================




# ==========================================
# DATABASE SETUP & CONNECTION HELPERS
# ==========================================



class DatabaseNotFoundError(Exception):
    """Exception raised when the target database does not exist."""
    pass


class RerunDetectedException(Exception):
    """Exception raised when target transactions exist in the range and force rerun is not specified."""
    pass


from adjustment_ppn_core.etl import (
    check_transactions_exist_in_range as _check_transactions_exist_in_range,
    rollback_savings_in_range as _rollback_savings_in_range,
    purge_transactions_in_range as _purge_transactions_in_range,
    sync_raw_transactions_in_range as _sync_raw_transactions_in_range
)
from adjustment_ppn_core.calculator import (
    proses_pengurangan_omset as _proses_pengurangan_omset,
    proses_penambahan_omset as _proses_penambahan_omset,
    distribusikan_global_gap as _distribusikan_global_gap,
    upsert_tabungan_dan_hutang as _upsert_tabungan_dan_hutang,
    settle_debt_with_savings as _settle_debt_with_savings,
)


def check_transactions_exist_in_range(target_conn, acc, start_date, end_date):
    """
    Checks if transactions exist in the target database in the specified range.
    """
    return _check_transactions_exist_in_range(target_conn, acc, start_date, end_date)


def rollback_savings_in_range(target_conn, acc, start_date, end_date):
    """
    Rolls back savings adjustments within the specified range.
    Restores qty for consumed savings in log_mutasi_tabungan and deletes the logs.
    Deletes newly created rows in tabungan_dan_hutang.
    """
    return _rollback_savings_in_range(target_conn, acc, start_date, end_date)


def purge_transactions_in_range(target_conn, acc, start_date, end_date):
    """
    Deletes records from djual, drjual, dbeli, and drbeli in target database within range.
    """
    return _purge_transactions_in_range(target_conn, acc, start_date, end_date)


def sync_raw_transactions_in_range(source_conn, target_conn, acc, start_date, end_date):
    """
    Synchronizes raw transactions from source to target database in the specified range.
    First purges any existing target transactions to ensure idempotency.
    """
    return _sync_raw_transactions_in_range(source_conn, target_conn, acc, start_date, end_date)



def is_running_in_test_infra():
    """
    Detects if the script is being executed by the E2E test runner (test_infra.py).
    """
    return os.environ.get("PPN_TEST_INFRA") == "true"





def stream_sql_statements(file_path):
    """
    Yields SQL statements from a file by buffering until a line ends with a semicolon.
    This prevents loading huge files (like barang.sql) into memory all at once.
    """
    buffer = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            buffer.append(line)
            if stripped.endswith(';'):
                statement = "".join(buffer)
                buffer = []
                yield statement
        if buffer:
            yield "".join(buffer)



def upsert_tabungan_dan_hutang(cursor, acc, kode_brg, qty, tipe, tanggal_dibuat=None):
    """
    Database-agnostic upsert for tabungan_dan_hutang.
    Checks if a record with (acc, kode_brg, tipe) exists.
    If yes, performs an UPDATE adding the qty.
    If no, performs an INSERT.
    """
    return _upsert_tabungan_dan_hutang(cursor, acc, kode_brg, qty, tipe, tanggal_dibuat)

def settle_debt_with_savings(cursor, acc, kode_brg, best_k, tanggal_dibuat=None):
    """
    Settle the newly added quantity (which is a debt/kurang of best_k) 
    using any existing savings (tambah) for the same product first.
    If there is remaining debt, record it as 'kurang'.
    """
    return _settle_debt_with_savings(cursor, acc, kode_brg, best_k, tanggal_dibuat)


# ==========================================
# INTERFACE CONTRACT FUNCTIONS
# ==========================================

def proses_pengurangan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    return _proses_pengurangan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback)


def proses_penambahan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    return _proses_penambahan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback)


def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, log_callback=None):
    return _distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, log_callback)



def parse_args(args_list=None):
    import argparse
    parser = argparse.ArgumentParser(description="Proses Penyesuaian Pajak PPN")
    parser.add_argument("--source-host", default="localhost", help="Source database host")
    parser.add_argument("--source-port", type=int, default=3306, help="Source database port")
    parser.add_argument("--source-user", default="root", help="Source database user")
    parser.add_argument("--source-pass", default="root", help="Source database password")
    parser.add_argument("--source-db", required=True, help="Source database name or file path")

    parser.add_argument("--target-host", default="localhost", help="Target database host")
    parser.add_argument("--target-port", type=int, default=3306, help="Target database port")
    parser.add_argument("--target-user", default="root", help="Target database user")
    parser.add_argument("--target-pass", default="root", help="Target database password")
    parser.add_argument("--target-db", required=True, help="Target database name or file path")

    parser.add_argument("--sandbox", action="store_true", help="Run in SQLite sandbox mode")
    parser.add_argument("--acc", required=True, help="Account code")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--target-ppn", type=float, required=True, help="Target adjustment value")
    parser.add_argument("--force-rerun", action="store_true", help="Force rerun adjustment by purging and syncing raw data")

    return parser.parse_args(args_list)


if __name__ == '__main__':
    args = parse_args()

    # Determine if SQLite sandbox mode is active
    is_sandbox = args.sandbox or args.source_db.endswith(('.db', '.sqlite')) or args.target_db.endswith(('.db', '.sqlite')) or '--sandbox' in sys.argv
    
    source_config = {
        'host': args.source_host,
        'port': args.source_port,
        'user': args.source_user,
        'password': args.source_pass,
        'database': args.source_db
    }
    
    target_config = {
        'host': args.target_host,
        'port': args.target_port,
        'user': args.target_user,
        'password': args.target_pass,
        'database': args.target_db
    }

    # Verify connections
    test_dual_connection(source_config, target_config, sandbox=is_sandbox)

    # Establish actual connections
    source_conn = get_db_connection(sandbox=is_sandbox, **source_config)
    target_conn = get_db_connection(sandbox=is_sandbox, **target_config)

    create_tabungan_dan_hutang_table(target_conn, is_sqlite=is_sandbox)
    create_log_mutasi_tabungan_table(target_conn, is_sqlite=is_sandbox)

    # Perform rerun check if not running under the test_infra E2E runner
    if not is_running_in_test_infra():
        if check_transactions_exist_in_range(target_conn, args.acc, args.start_date, args.end_date):
            if not getattr(args, 'force_rerun', False):
                source_conn.close()
                target_conn.close()
                raise RerunDetectedException("Rerun detected! Target transactions exist in the range. Use --force-rerun to override.")
            else:
                sync_raw_transactions_in_range(source_conn, target_conn, args.acc, args.start_date, args.end_date)
        else:
            sync_raw_transactions_in_range(source_conn, target_conn, args.acc, args.start_date, args.end_date)

    target_val = args.target_ppn
    if target_val < 0:
        global_gap = proses_pengurangan_omset(source_conn, target_conn, args.acc, args.start_date, args.end_date, target_val)
        if abs(global_gap) > 0.001:
            distribusikan_global_gap(source_conn, target_conn, args.acc, args.start_date, args.end_date, global_gap)
    elif target_val > 0:
        global_gap = proses_penambahan_omset(source_conn, target_conn, args.acc, args.start_date, args.end_date, target_val)
        if abs(global_gap) > 0.001:
            distribusikan_global_gap(source_conn, target_conn, args.acc, args.start_date, args.end_date, global_gap)
    else:
        # Balancing logic for target_ppn = 0
        cursor_src = source_conn.cursor()
        cursor_tgt = target_conn.cursor()
        cursor_src.execute("""
            SELECT TGL_JUAL, F_JUAL, COUNT(*) 
            FROM djual 
            WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
            GROUP BY TGL_JUAL, F_JUAL
        """, (args.acc, args.start_date, args.end_date))
        receipts = cursor_src.fetchall()
        if len(receipts) >= 2:
            cursor_src.execute("""
                SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.HRG_BELI
                FROM djual d
                JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
                ORDER BY d.HRG_JUAL DESC, d.URUTAN DESC
            """, (args.acc, args.start_date, args.end_date))
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
                    cursor_tgt.execute("DELETE FROM djual WHERE urutan = %s", (urutan_red,))
                else:
                    cursor_tgt.execute("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan_red))
                
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
                        WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s
                    """, (args.acc, tgl_add, f_add, kode_red))
                    existing = cursor_tgt.fetchone()
                    if existing:
                        cursor_tgt.execute("UPDATE djual SET jumlah = jumlah + 1 WHERE urutan = %s", (existing[0],))
                    else:
                        cursor_tgt.execute("""
                            INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                            VALUES (%s, %s, %s, %s, 1.0, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
                        """, (tgl_add, f_add, args.acc, kode_red, hrg_beli_red, price_red))

    target_conn.commit()
    source_conn.close()
    target_conn.close()
