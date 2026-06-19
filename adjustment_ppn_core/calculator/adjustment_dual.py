import time
import os
import random

def get_current_omset(source_conn, acc, start_date, end_date, category_sql_filter, is_sandbox):
    acc_tuple = acc if isinstance(acc, (list, tuple)) else (acc,)
    placeholders = ", ".join(["?"] * len(acc_tuple)) if is_sandbox else ", ".join(["%s"] * len(acc_tuple))
    q = f"""
        SELECT SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        LEFT JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
    """
    c = source_conn.cursor()
    c.execute(q, (*acc_tuple, start_date, end_date))
    row = c.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def proses_adjustment_dual(source_conn, target_conn, acc, start_date, end_date, target_ppn, target_btkp, is_sandbox, max_workers=1, log_callback=None):
    from adjustment_ppn_core.calculator.adjustment_core import proses_pengurangan_fase, proses_penambahan_fase
    
    if log_callback:
        log_callback(f"Action: Start Dual Adjustment | ACC: {acc} | Target PPN: {target_ppn:,.2f} | Target BTKP: {target_btkp:,.2f}")

    # ==========================
    # FASE PPN
    # ==========================
    if target_ppn > 0.001:
        if log_callback:
            log_callback("--- Memulai Fase Penyesuaian PPN ---")
        current_ppn = get_current_omset(source_conn, acc, start_date, end_date, "b.PAJAK IN (1, 3)", is_sandbox)
        gap_ppn = target_ppn - current_ppn
        
        if log_callback:
            log_callback(f"PPN -> Current: {current_ppn:,.2f} | Gap: {gap_ppn:,.2f}")
            
        if gap_ppn < -0.001:
            proses_pengurangan_fase(source_conn, target_conn, acc, start_date, end_date, abs(gap_ppn), "b.PAJAK IN (1, 3)", "PPN", is_sandbox, log_callback)
        elif gap_ppn > 0.001:
            proses_penambahan_fase(source_conn, target_conn, acc, start_date, end_date, abs(gap_ppn), "b.PAJAK IN (1, 3)", "PPN", is_sandbox, log_callback)
        
        target_conn.commit()
        if log_callback:
            log_callback("--- Fase Penyesuaian PPN Selesai & Committed ---")

    # ==========================
    # FASE BTKP
    # ==========================
    if target_btkp > 0.001:
        if log_callback:
            log_callback("--- Memulai Fase Penyesuaian BTKP ---")
        current_btkp = get_current_omset(source_conn, acc, start_date, end_date, "b.PAJAK = 2", is_sandbox)
        gap_btkp = target_btkp - current_btkp
        
        if log_callback:
            log_callback(f"BTKP -> Current: {current_btkp:,.2f} | Gap: {gap_btkp:,.2f}")
            
        if gap_btkp < -0.001:
            proses_pengurangan_fase(source_conn, target_conn, acc, start_date, end_date, abs(gap_btkp), "b.PAJAK = 2", "BTKP", is_sandbox, log_callback)
        elif gap_btkp > 0.001:
            proses_penambahan_fase(source_conn, target_conn, acc, start_date, end_date, abs(gap_btkp), "b.PAJAK = 2", "BTKP", is_sandbox, log_callback)
        
        target_conn.commit()
        if log_callback:
            log_callback("--- Fase Penyesuaian BTKP Selesai & Committed ---")

    return 0.0
