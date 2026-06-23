import time
import random
import threading
from collections import defaultdict

def _upsert_tabungan(c_tgt, acc, kode_brg, qty, tipe, is_sandbox, tanggal_dibuat=None):
    c_tgt.execute(f"SELECT urutan FROM tabungan_dan_hutang WHERE acc = {'?' if is_sandbox else '%s'} AND kode_brg = {'?' if is_sandbox else '%s'} AND tipe = {'?' if is_sandbox else '%s'}", (acc, kode_brg, tipe))
    row = c_tgt.fetchone()
    if row:
        c_tgt.execute(f"UPDATE tabungan_dan_hutang SET qty = qty + {'?' if is_sandbox else '%s'} WHERE urutan = {'?' if is_sandbox else '%s'}", (qty, row[0]))
    else:
        if tanggal_dibuat is not None:
            c_tgt.execute(f"INSERT INTO tabungan_dan_hutang (qty, acc, kode_brg, tipe, tanggal_dibuat) VALUES ({'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'})", (qty, acc, kode_brg, tipe, tanggal_dibuat))
        else:
            c_tgt.execute(f"INSERT INTO tabungan_dan_hutang (qty, acc, kode_brg, tipe) VALUES ({'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'})", (qty, acc, kode_brg, tipe))


def _process_reduction_savings(c_tgt, target_acc, kode_brg, qty_to_reduce, tanggal_dibuat, is_sandbox):
    # 1. Check and reduce 'kurang' records of the same product (self-healing debt settlement)
    c_tgt.execute(
        f"SELECT urutan, qty FROM tabungan_dan_hutang WHERE acc = {'?' if is_sandbox else '%s'} AND kode_brg = {'?' if is_sandbox else '%s'} AND tipe = 'kurang'",
        (target_acc, kode_brg)
    )
    debt_row = c_tgt.fetchone()
    if debt_row:
        debt_urutan, debt_qty = debt_row[0], float(debt_row[1])
        if debt_qty > 0:
            settled = min(qty_to_reduce, debt_qty)
            new_debt_qty = debt_qty - settled
            c_tgt.execute(
                f"UPDATE tabungan_dan_hutang SET qty = {'?' if is_sandbox else '%s'} WHERE urutan = {'?' if is_sandbox else '%s'}",
                (new_debt_qty, debt_urutan)
            )
            qty_to_reduce -= settled
            
    # 2. If there's still quantity remaining to reduce (which becomes savings), insert/update as 'tambah'
    if qty_to_reduce > 0:
        _upsert_tabungan(c_tgt, target_acc, kode_brg, qty_to_reduce, 'tambah', is_sandbox, tanggal_dibuat)


def proses_pengurangan_fase(source_conn, target_conn, acc, start_date, end_date, target_gap, category_sql_filter, phase_name, is_sandbox, log_callback):
    if log_callback:
        log_callback(f"[{phase_name}] Target Pemotongan: {target_gap:,.2f}")
    
    acc_tuple = acc if isinstance(acc, (list, tuple)) else (acc,)
    placeholders = ", ".join(["?"] * len(acc_tuple)) if is_sandbox else ", ".join(["%s"] * len(acc_tuple))
    
    c_src = source_conn.cursor()
    c_tgt = target_conn.cursor()
    
    c_tgt.execute("SELECT DISTINCT KODE_BRG FROM barang WHERE ACC = 'A1'")
    a1_products = {row[0] for row in c_tgt.fetchall()}

    
    # 1. Total Base for proportion
    c_src.execute(f"""
        SELECT SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
    """, (*acc_tuple, start_date, end_date))
    row = c_src.fetchone()
    total_phase_omset = float(row[0]) if row and row[0] is not None else 0.0
    
    if total_phase_omset <= 0:
        if log_callback:
            log_callback(f"[{phase_name}] Omset 0. Tidak ada yang bisa dipotong.")
        return
        
    P = target_gap / total_phase_omset if total_phase_omset > 0 else 0
    if P > 1.0:
        P = 1.0 # Cannot reduce more than 100%
        
    if log_callback:
        log_callback(f"[{phase_name}] Faktor Proporsi (P): {P:.4f}")

    # Load items to reduce
    c_src.execute(f"""
        SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.ACC, b.PAJAK,
               ((d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-d.DISC_RP) as actual_price
        FROM djual d
        JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
    """, (*acc_tuple, start_date, end_date))
    
    items = c_src.fetchall()
    faktur_dict = defaultdict(list)
    for item in items:
        faktur_dict[item[1]].append({
            'tgl': item[0],
            'f_jual': item[1],
            'kode_brg': item[2],
            'jumlah': float(item[3]),
            'hrg_jual': float(item[4]),
            'urutan': item[5],
            'item_acc': item[6],
            'pajak': item[7],
            'actual_price': float(item[8])
        })
        
    total_reduced = 0.0
    
    total_receipts = len(faktur_dict)

    # Count of all items (regardless of category) per F_JUAL in target database
    c_tgt.execute(f"""
        SELECT F_JUAL, COUNT(*) 
        FROM djual 
        WHERE ACC IN ({placeholders}) AND TGL_JUAL >= {'?' if is_sandbox else '%s'} AND TGL_JUAL <= {'?' if is_sandbox else '%s'}
        GROUP BY F_JUAL
    """, (*acc_tuple, start_date, end_date))
    receipt_item_counts = {row[0]: row[1] for row in c_tgt.fetchall()}

    # Get all unique receipts sorted chronologically ascending (TGL_JUAL, F_JUAL)
    c_tgt.execute(f"""
        SELECT DISTINCT F_JUAL, TGL_JUAL 
        FROM djual 
        WHERE ACC IN ({placeholders}) AND TGL_JUAL >= {'?' if is_sandbox else '%s'} AND TGL_JUAL <= {'?' if is_sandbox else '%s'}
    """, (*acc_tuple, start_date, end_date))
    receipt_dates = c_tgt.fetchall()
    # Convert to list and sort to avoid tuple attribute error
    receipt_dates = sorted(list(receipt_dates), key=lambda x: (x[1], x[0]))
    sorted_receipts = [r[0] for r in receipt_dates]

    def is_chronologically_last_active(f_jual):
        # Scan sorted_receipts backwards to find the first one with active items
        for r in reversed(sorted_receipts):
            if receipt_item_counts.get(r, 0) > 0:
                return r == f_jual
        return False
    
    # PASS 1: Proportional Reduction
    for index, (f_jual, receipt_items) in enumerate(faktur_dict.items(), start=1):
        receipt_omset = sum(i['jumlah'] * i['actual_price'] for i in receipt_items)
        receipt_target = receipt_omset * P
        
        for item in sorted(receipt_items, key=lambda x: x['urutan'], reverse=True):
            if receipt_target < 0.001:
                break
                
            max_qty_to_reduce = item['jumlah'] - 1
            if max_qty_to_reduce <= 0:
                continue # Already at qty=1 and cannot reduce further in this pass
                
            ideal_qty_to_reduce = int(receipt_target // item['actual_price']) if item['actual_price'] > 0 else 0
            qty_to_reduce = min(max_qty_to_reduce, ideal_qty_to_reduce)
            
            if qty_to_reduce > 0:
                new_qty = item['jumlah'] - qty_to_reduce
                c_tgt.execute("UPDATE djual SET jumlah = ? WHERE urutan = ?" if is_sandbox else "UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, item['urutan']))
                
                # Update in memory for Pass 2 and Pass 3
                item['jumlah'] = new_qty
                
                val_reduced = qty_to_reduce * item['actual_price']
                receipt_target -= val_reduced
                total_reduced += val_reduced
                
                if log_callback and (index % 500 == 0 or index == total_receipts):
                    remaining = target_gap - total_reduced
                    log_callback(f"[{item['item_acc']}] Action: Reduce Qty [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {item['kode_brg']} | Qty Reduced: {qty_to_reduce} | Value: {val_reduced:,.2f} | Remaining Gap: {remaining:,.2f}")
                
                # Save to savings (for penambahan later) with redirection & self-healing
                target_acc = 'A1' if item['kode_brg'] in a1_products else item['item_acc']
                _process_reduction_savings(c_tgt, target_acc, item['kode_brg'], qty_to_reduce, item['tgl'], is_sandbox)
                
    remaining_gap = target_gap - total_reduced
    if log_callback:
        log_callback(f"[{phase_name}] Selesai Proporsional. Total Dipotong: {total_reduced:,.2f}. Sisa Gap: {remaining_gap:,.2f}")
        
    # PASS 2: Global Reduction Loop (QTY reduction down to 1 only)
    if remaining_gap > 1000:
        if log_callback:
            log_callback(f"[{phase_name}] Memulai Global Reduction Loop untuk menutupi sisa Gap (QTY reduction)...")
        
        # Flatten all items that still have qty > 1
        reducible_items = []
        for receipt_items in faktur_dict.values():
            for item in receipt_items:
                if item['jumlah'] > 1:
                    reducible_items.append(item)
                    
        random.shuffle(reducible_items)
        
        loop_reduced = 0.0
        while remaining_gap > 1000 and reducible_items:
            made_progress = False
            for item in reducible_items:
                if remaining_gap <= 1000:
                    break
                
                if item['jumlah'] > 1:
                    item['jumlah'] -= 1
                    val_reduced = item['actual_price']
                    remaining_gap -= val_reduced
                    loop_reduced += val_reduced
                    total_reduced += val_reduced
                    made_progress = True
                    
                    c_tgt.execute("UPDATE djual SET jumlah = ? WHERE urutan = ?" if is_sandbox else "UPDATE djual SET jumlah = %s WHERE urutan = %s", (item['jumlah'], item['urutan']))
                        
                    target_acc = 'A1' if item['kode_brg'] in a1_products else item['item_acc']
                    _process_reduction_savings(c_tgt, target_acc, item['kode_brg'], 1.0, item['tgl'], is_sandbox)
                    
            # Clean up items that have reached 1
            reducible_items = [item for item in reducible_items if item['jumlah'] > 1]
            if not made_progress:
                break
                
        if log_callback:
            log_callback(f"[{phase_name}] Global Loop selesai. Dipotong: {loop_reduced:,.2f}. Sisa Gap: {remaining_gap:,.2f}")

    # PASS 3: Deletion Phase (Safe Item Deletion and Chronological Receipt Deletion)
    remaining_gap = target_gap - total_reduced
    if remaining_gap > 1000:
        if log_callback:
            log_callback(f"[{phase_name}] Memulai Deletion Phase (Pass 3) untuk menutupi sisa Gap...")
            
        # Gather all items in this phase that still have QTY > 0
        phase_items_by_receipt = defaultdict(list)
        for receipt_items in faktur_dict.values():
            for item in receipt_items:
                if item['jumlah'] > 0:
                    phase_items_by_receipt[item['f_jual']].append(item)
                    
        # Pass 3a: Delete target items from multiple-item receipts (Rule 1)
        for r in sorted_receipts:
            if remaining_gap <= 1000:
                break
                
            items_in_receipt = phase_items_by_receipt[r]
            if not items_in_receipt:
                continue
                
            for item in list(items_in_receipt):
                if remaining_gap <= 1000:
                    break
                    
                total_items = receipt_item_counts.get(r, 0)
                if total_items > 1:
                    # Rule 1: Safe deletion because other items exist in the Target DB
                    qty_reduced = item['jumlah']
                    val_reduced = qty_reduced * item['actual_price']
                    
                    c_tgt.execute("DELETE FROM djual WHERE urutan = ?" if is_sandbox else "DELETE FROM djual WHERE urutan = %s", (item['urutan'],))
                    
                    receipt_item_counts[r] -= 1
                    item['jumlah'] = 0
                    items_in_receipt.remove(item)
                    
                    remaining_gap -= val_reduced
                    total_reduced += val_reduced
                    
                    if log_callback:
                        log_batcher = f"[{item['item_acc']}] Action: Safe Delete Item (Pass 3a) | Receipt: {r} | Product: {item['kode_brg']} | Qty: {qty_reduced} | Value: {val_reduced:,.2f} | Remaining Gap: {remaining_gap:,.2f}"
                        log_callback(log_batcher)
                        
                    target_acc = 'A1' if item['kode_brg'] in a1_products else item['item_acc']
                    _process_reduction_savings(c_tgt, target_acc, item['kode_brg'], qty_reduced, item['tgl'], is_sandbox)
                    
        # Pass 3b: Chronological receipt deletion (Rule 2)
        # Cascade backwards through the sorted receipts
        halt_deletion = False
        for r in reversed(sorted_receipts):
            if remaining_gap <= 1000 or halt_deletion:
                break
                
            items_in_receipt = phase_items_by_receipt[r]
            if not items_in_receipt:
                continue
                
            for item in list(items_in_receipt):
                if remaining_gap <= 1000:
                    break
                    
                total_items = receipt_item_counts.get(r, 0)
                if total_items == 1:
                    if is_chronologically_last_active(r):
                        # Rule 2: Can be deleted because it is the chronologically last active receipt
                        qty_reduced = item['jumlah']
                        val_reduced = qty_reduced * item['actual_price']
                        
                        c_tgt.execute("DELETE FROM djual WHERE urutan = ?" if is_sandbox else "DELETE FROM djual WHERE urutan = %s", (item['urutan'],))
                        
                        receipt_item_counts[r] -= 1
                        item['jumlah'] = 0
                        items_in_receipt.remove(item)
                        
                        remaining_gap -= val_reduced
                        total_reduced += val_reduced
                        
                        if log_callback:
                            log_batcher = f"[{item['item_acc']}] Action: Chronological Receipt Delete (Pass 3b) | Receipt: {r} | Product: {item['kode_brg']} | Qty: {qty_reduced} | Value: {val_reduced:,.2f} | Remaining Gap: {remaining_gap:,.2f}"
                            log_callback(log_batcher)
                            
                        target_acc = 'A1' if item['kode_brg'] in a1_products else item['item_acc']
                        _process_reduction_savings(c_tgt, target_acc, item['kode_brg'], qty_reduced, item['tgl'], is_sandbox)
                    else:
                        # Encountered a single-item receipt in the middle of the month
                        halt_deletion = True
                        if log_callback:
                            last_active = next((x for x in reversed(sorted_receipts) if receipt_item_counts.get(x, 0) > 0), None)
                            halt_msg = (
                                "\n"
                                "================================================================================\n"
                                "=== PERINGATAN KRITIS: PENGHENTIAN PAKSA PROSES DELESI (HALT DETECTED) ===\n"
                                f"Fase: {phase_name}\n"
                                f"Status: Loop Deletion Fase 3b DIHENTIKAN secara paksa.\n"
                                f"Penyebab: Menemukan single-item receipt '{r}' di tengah bulan.\n"
                                f"Penjelasan: Sesuai dengan aturan integritas data (Chronological Receipt Deletion),\n"
                                f"            transaksi dengan hanya satu item (single-item receipt) tidak boleh dihapus\n"
                                f"            jika masih ada transaksi aktif setelahnya di bulan yang sama.\n"
                                f"Detail Transaksi:\n"
                                f"  - Receipt yang memicu halt: '{r}'\n"
                                f"  - Transaksi aktif terakhir saat ini: '{last_active}'\n"
                                f"  - Sisa gap target pengurangan omset: {remaining_gap:,.2f}\n"
                                "================================================================================\n"
                            )
                            log_callback(halt_msg)
                        break
                elif total_items > 1:
                    # In case we still have multiple items here
                    qty_reduced = item['jumlah']
                    val_reduced = qty_reduced * item['actual_price']
                    
                    c_tgt.execute("DELETE FROM djual WHERE urutan = ?" if is_sandbox else "DELETE FROM djual WHERE urutan = %s", (item['urutan'],))
                    
                    receipt_item_counts[r] -= 1
                    item['jumlah'] = 0
                    items_in_receipt.remove(item)
                    
                    remaining_gap -= val_reduced
                    total_reduced += val_reduced
                    
                    if log_callback:
                        log_batcher = f"[{item['item_acc']}] Action: Safe Delete Item (Pass 3b) | Receipt: {r} | Product: {item['kode_brg']} | Qty: {qty_reduced} | Value: {val_reduced:,.2f} | Remaining Gap: {remaining_gap:,.2f}"
                        log_callback(log_batcher)
                        
                    target_acc = 'A1' if item['kode_brg'] in a1_products else item['item_acc']
                    _process_reduction_savings(c_tgt, target_acc, item['kode_brg'], qty_reduced, item['tgl'], is_sandbox)
                    
        if log_callback:
            log_callback(f"[{phase_name}] Deletion Phase selesai. Sisa Gap Akhir: {remaining_gap:,.2f}")
            if remaining_gap > 1000:
                log_callback(f"[{phase_name}] PERINGATAN: Semua produk telah mentok atau tidak bisa dihapus lagi. Gap tidak bisa dipenuhi 100%.")

def proses_penambahan_fase(source_conn, target_conn, acc, start_date, end_date, target_gap, category_sql_filter, phase_name, is_sandbox, log_callback):
    if log_callback:
        log_callback(f"[{phase_name}] Target Penambahan: {target_gap:,.2f}")
    
    acc_tuple = acc if isinstance(acc, (list, tuple)) else (acc,)
    placeholders = ", ".join(["?"] * len(acc_tuple)) if is_sandbox else ", ".join(["%s"] * len(acc_tuple))
    
    c_src = source_conn.cursor()
    c_tgt = target_conn.cursor()
    
    c_tgt.execute("SELECT DISTINCT KODE_BRG FROM barang WHERE ACC = 'A1'")
    a1_products = {row[0] for row in c_tgt.fetchall()}
    
    # 1. Base Omset
    c_src.execute(f"""
        SELECT SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
    """, (*acc_tuple, start_date, end_date))
    row = c_src.fetchone()
    total_phase_omset = float(row[0]) if row and row[0] is not None else 0.0
    
    P = target_gap / total_phase_omset if total_phase_omset > 0 else 0
    if log_callback:
        log_callback(f"[{phase_name}] Faktor Penambahan (P): {P:.4f}")
        
    # Get all receipts that ALREADY HAVE at least one item of this phase's tax type (Strict Scoping)
    c_src.execute(f"""
        SELECT d.TGL_JUAL, d.F_JUAL, SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        JOIN (SELECT KODE_BRG, ACC, MIN(CASE WHEN PAJAK IN (1, 3) THEN PAJAK WHEN PAJAK = 2 THEN PAJAK ELSE 99 END) AS PAJAK FROM BARANG GROUP BY KODE_BRG, ACC) b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
        GROUP BY d.TGL_JUAL, d.F_JUAL
    """, (*acc_tuple, start_date, end_date))
    
    valid_receipts = c_src.fetchall()
    
    # Load Available Savings for this specific category
    c_tgt.execute(f"""
        SELECT t.urutan, t.qty, t.acc, t.kode_brg, 
               MAX(b.HARGA11) as base_price,
               MAX(b.HRG_BELI) as hrg_beli
        FROM tabungan_dan_hutang t
        JOIN barang b ON t.kode_brg = b.kode_brg AND t.acc = b.acc
        WHERE (t.acc IN ({placeholders}) OR t.acc = 'A1') AND t.qty > 0 AND t.tipe = 'tambah'
        AND {category_sql_filter}
        GROUP BY t.urutan, t.qty, t.acc, t.kode_brg
    """, (*acc_tuple,))
    savings = c_tgt.fetchall()
    savings_list = [{'urutan': s[0], 'qty': float(s[1]), 'item_acc': s[2], 'kode_brg': s[3], 'price': float(s[4]), 'hrg_beli': float(s[5])} for s in savings]
    
    # Load Master Barang Fiktif as fallback (only for this category!)
    c_src.execute(f"""
        SELECT KODE_BRG, ACC, MAX(HRG_BELI), MAX(HARGA11), 0, 0, 0, 0,
               MAX(HARGA11) as actual_price
        FROM barang b
        WHERE ACC IN ({placeholders}) AND {category_sql_filter} AND HARGA11 > 0
        GROUP BY KODE_BRG, ACC
    """, (*acc_tuple,))
    fiktif_items = c_src.fetchall()
    if not fiktif_items:
        if log_callback:
            log_callback(f"[{phase_name}] ERROR FATAL: Tidak ada master barang untuk kategori ini! Penambahan dibatalkan.")
        return
        
    total_added = 0.0
    remaining_gap = target_gap
    
    total_receipts = len(valid_receipts)
    
    # Proportional Addition
    for index, r in enumerate(valid_receipts, start=1):
        tgl_jual, f_jual, r_omset = r
        r_omset = float(r_omset) if r_omset is not None else 0.0
        
        target_addition = r_omset * P
        if target_addition < 0.001:
            continue
            
        # Try to fulfill using savings first
        for sav in savings_list:
            if target_addition < 0.001: break
            if sav['qty'] <= 0: continue
            
            price = sav['price']
            if price <= 0: continue
            
            qty_needed = int(target_addition // price)
            if qty_needed > 0:
                qty_used = min(qty_needed, sav['qty'])
                
                # Consume savings
                sav['qty'] -= qty_used
                c_tgt.execute("UPDATE tabungan_dan_hutang SET qty = ? WHERE urutan = ?" if is_sandbox else "UPDATE tabungan_dan_hutang SET qty = %s WHERE urutan = %s", (sav['qty'], sav['urutan']))
                
                c_tgt.execute(f"""
                    INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, 0.0, 0.0, 10.0)
                """ if is_sandbox else f"""
                    INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
                """, (tgl_jual, f_jual, sav['item_acc'], sav['kode_brg'], float(qty_used), sav['hrg_beli'], sav['price']))
                
                # Log consumed savings
                c_tgt.execute(f"""
                    INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai)
                    VALUES ({'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'})
                """, (sav['urutan'], float(qty_used), tgl_jual))
                
                val_added = qty_used * price
                target_addition -= val_added
                total_added += val_added
                
                if log_callback and (index % 500 == 0 or index == total_receipts):
                    remaining = target_gap - total_added
                    log_callback(f"[{sav['item_acc']}] Action: Draw Savings [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {sav['kode_brg']} | Qty Added: {qty_used} | Value: {val_added:,.2f} | Remaining Gap: {remaining:,.2f}")
                
        # If still missing target, use Fiktif Items
        while target_addition > 1000:
            valid_fiktifs_pass1 = [f for f in fiktif_items if float(f[8]) <= target_addition and float(f[8]) > 0]
            if not valid_fiktifs_pass1:
                break
            
            fiktif = random.choice(valid_fiktifs_pass1)
            price = float(fiktif[8])
            
            qty_needed = int(target_addition // price)
            if qty_needed <= 0:
                break
                
            c_tgt.execute(f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10.0)
            """ if is_sandbox else f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 10.0)
            """, (tgl_jual, f_jual, fiktif[1], fiktif[0], float(qty_needed), float(fiktif[2]), float(fiktif[3]), float(fiktif[4]), float(fiktif[5]), float(fiktif[6]), float(fiktif[7])))
            
            # Record debt with A1 Priority redirect
            debt_acc = 'A1' if fiktif[0] in a1_products else fiktif[1]
            _upsert_tabungan(c_tgt, debt_acc, fiktif[0], float(qty_needed), 'kurang', is_sandbox, tgl_jual)
            
            val_added = qty_needed * price
            target_addition -= val_added
            total_added += val_added
            
            if log_callback and (index % 500 == 0 or index == total_receipts):
                remaining = target_gap - total_added
                log_callback(f"[{fiktif[1]}] Action: Inject Fiktif [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {fiktif[0]} | Qty Added: {qty_needed} | Value: {val_added:,.2f} | Remaining Gap: {remaining:,.2f}")
            
    remaining_gap = target_gap - total_added
    if log_callback:
        log_callback(f"[{phase_name}] Selesai Proporsional. Total Ditambah: {total_added:,.2f}. Sisa Gap: {remaining_gap:,.2f}")
        
    # PASS 2: Global Addition
    if remaining_gap > 1000 and valid_receipts:
        if log_callback:
            log_callback(f"[{phase_name}] Memulai Global Addition Loop...")
            
        loop_added = 0.0
        valid_fiktifs = [f for f in fiktif_items if float(f[8]) <= remaining_gap and float(f[8]) > 0]
        
        while remaining_gap > 1000 and valid_fiktifs:
            fiktif = random.choice(valid_fiktifs)
            price = float(fiktif[8])
            
            target_r = random.choice(valid_receipts)
            tgl_jual, f_jual, _ = target_r
            
            c_tgt.execute(f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, 10.0)
            """ if is_sandbox else f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, 10.0)
            """, (tgl_jual, f_jual, fiktif[1], fiktif[0], float(fiktif[2]), float(fiktif[3]), float(fiktif[4]), float(fiktif[5]), float(fiktif[6]), float(fiktif[7])))
            
            # Record debt with A1 Priority redirect
            debt_acc = 'A1' if fiktif[0] in a1_products else fiktif[1]
            _upsert_tabungan(c_tgt, debt_acc, fiktif[0], 1.0, 'kurang', is_sandbox, tgl_jual)
            
            val_added = price
            remaining_gap -= val_added
            loop_added += val_added
            total_added += val_added
            
            valid_fiktifs = [f for f in fiktif_items if float(f[8]) <= remaining_gap and float(f[8]) > 0]
            
        if log_callback:
            log_callback(f"[{phase_name}] Global Addition Selesai. Ditambah: {loop_added:,.2f}. Sisa Gap Akhir: {remaining_gap:,.2f}")
