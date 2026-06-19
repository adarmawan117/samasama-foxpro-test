import time
import random
import threading
from collections import defaultdict

def _upsert_tabungan(c_tgt, acc, kode_brg, qty, tipe, is_sandbox):
    c_tgt.execute(f"SELECT urutan FROM tabungan_dan_hutang WHERE acc = {'?' if is_sandbox else '%s'} AND kode_brg = {'?' if is_sandbox else '%s'} AND tipe = {'?' if is_sandbox else '%s'}", (acc, kode_brg, tipe))
    row = c_tgt.fetchone()
    if row:
        c_tgt.execute(f"UPDATE tabungan_dan_hutang SET qty = qty + {'?' if is_sandbox else '%s'} WHERE urutan = {'?' if is_sandbox else '%s'}", (qty, row[0]))
    else:
        c_tgt.execute(f"INSERT INTO tabungan_dan_hutang (qty, acc, kode_brg, tipe) VALUES ({'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'})", (qty, acc, kode_brg, tipe))


def proses_pengurangan_fase(source_conn, target_conn, acc, start_date, end_date, target_gap, category_sql_filter, phase_name, is_sandbox, log_callback):
    if log_callback:
        log_callback(f"[{phase_name}] Target Pemotongan: {target_gap:,.2f}")
    
    acc_tuple = acc if isinstance(acc, (list, tuple)) else (acc,)
    placeholders = ", ".join(["?"] * len(acc_tuple)) if is_sandbox else ", ".join(["%s"] * len(acc_tuple))
    
    c_src = source_conn.cursor()
    c_tgt = target_conn.cursor()
    
    # 1. Total Base for proportion
    c_src.execute(f"""
        SELECT SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
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
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
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
    
    # PASS 1: Proportional Reduction
    for index, (f_jual, receipt_items) in enumerate(faktur_dict.items(), start=1):
        receipt_omset = sum(i['jumlah'] * i['actual_price'] for i in receipt_items)
        receipt_target = receipt_omset * P
        
        for item in sorted(receipt_items, key=lambda x: x['urutan'], reverse=True):
            if receipt_target < 0.001:
                break
                
            max_qty_to_reduce = item['jumlah'] - 1 # STRICT ANTI-DELETE RULE: minimum qty is 1
            if max_qty_to_reduce <= 0:
                continue # Already at qty=1, cannot reduce
                
            ideal_qty_to_reduce = int(receipt_target // item['actual_price']) if item['actual_price'] > 0 else 0
            qty_to_reduce = min(max_qty_to_reduce, ideal_qty_to_reduce)
            
            if qty_to_reduce > 0:
                new_qty = item['jumlah'] - qty_to_reduce
                c_tgt.execute("UPDATE djual SET jumlah = ? WHERE urutan = ?" if is_sandbox else "UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, item['urutan']))
                
                # Update in memory for Pass 2
                item['jumlah'] = new_qty
                
                val_reduced = qty_to_reduce * item['actual_price']
                receipt_target -= val_reduced
                total_reduced += val_reduced
                
                if log_callback and (index % 500 == 0 or index == total_receipts):
                    remaining = target_gap - total_reduced
                    log_callback(f"[{item['item_acc']}] Action: Reduce Qty [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {item['kode_brg']} | Qty Reduced: {qty_to_reduce} | Value: {val_reduced:,.2f} | Remaining Gap: {remaining:,.2f}")
                
                # Save to savings (for penambahan later)
                _upsert_tabungan(c_tgt, item['item_acc'], item['kode_brg'], qty_to_reduce, 'tambah', is_sandbox)
                
    remaining_gap = target_gap - total_reduced
    if log_callback:
        log_callback(f"[{phase_name}] Selesai Proporsional. Total Dipotong: {total_reduced:,.2f}. Sisa Gap: {remaining_gap:,.2f}")
        
    # PASS 2: Global Reduction Loop (The "Sisa Pemotongan Global" logic)
    if remaining_gap > 1000:
        if log_callback:
            log_callback(f"[{phase_name}] Memulai Global Reduction Loop untuk menutupi sisa Gap...")
        
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
                    _upsert_tabungan(c_tgt, item['item_acc'], item['kode_brg'], 1, 'tambah', is_sandbox)
                    
            if not made_progress:
                break # All items are at qty=1
                
        if log_callback:
            log_callback(f"[{phase_name}] Global Loop selesai. Dipotong: {loop_reduced:,.2f}. Sisa Gap Akhir: {remaining_gap:,.2f}")
            if remaining_gap > 1000:
                log_callback(f"[{phase_name}] PERINGATAN: Semua produk telah mentok di Qty=1. Operasi Menyerah. Gap tidak bisa dipenuhi 100%.")

def proses_penambahan_fase(source_conn, target_conn, acc, start_date, end_date, target_gap, category_sql_filter, phase_name, is_sandbox, log_callback):
    if log_callback:
        log_callback(f"[{phase_name}] Target Penambahan: {target_gap:,.2f}")
    
    acc_tuple = acc if isinstance(acc, (list, tuple)) else (acc,)
    placeholders = ", ".join(["?"] * len(acc_tuple)) if is_sandbox else ", ".join(["%s"] * len(acc_tuple))
    
    c_src = source_conn.cursor()
    c_tgt = target_conn.cursor()
    
    # 1. Base Omset
    c_src.execute(f"""
        SELECT SUM((d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH))
        FROM djual d
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
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
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= {'?' if is_sandbox else '%s'} AND d.TGL_JUAL <= {'?' if is_sandbox else '%s'}
        AND {category_sql_filter}
        GROUP BY d.TGL_JUAL, d.F_JUAL
    """, (*acc_tuple, start_date, end_date))
    
    valid_receipts = c_src.fetchall()
    
    # Load Available Savings for this specific category
    c_tgt.execute(f"""
        SELECT t.urutan, t.qty, t.acc, t.kode_brg, 
               b.HARGA11 as base_price
        FROM tabungan_dan_hutang t
        JOIN barang b ON t.kode_brg = b.kode_brg AND t.acc = b.acc
        WHERE t.acc IN ({placeholders}) AND t.qty > 0 AND t.tipe = 'tambah'
        AND {category_sql_filter}
    """, (*acc_tuple,))
    savings = c_tgt.fetchall()
    savings_list = [{'urutan': s[0], 'qty': float(s[1]), 'item_acc': s[2], 'kode_brg': s[3], 'price': float(s[4])} for s in savings]
    
    # Load Master Barang Fiktif as fallback (only for this category!)
    c_src.execute(f"""
        SELECT KODE_BRG, ACC, HRG_BELI, HARGA11, 0, 0, 0, 0,
               HARGA11 as actual_price
        FROM barang b
        WHERE ACC IN ({placeholders}) AND {category_sql_filter} AND HARGA11 > 0
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
                    SELECT {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, {'?' if is_sandbox else '%s'}, 
                           HRG_BELI, HARGA11, 0.0, 0.0, 0.0, 0.0, 10.0
                    FROM barang WHERE KODE_BRG = {'?' if is_sandbox else '%s'} AND ACC = {'?' if is_sandbox else '%s'}
                """, (tgl_jual, f_jual, sav['item_acc'], sav['kode_brg'], qty_used, sav['kode_brg'], sav['item_acc']))
                
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
                
            c_tgt.execute(f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10.0)
            """ if is_sandbox else f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 10.0)
            """, (tgl_jual, f_jual, fiktif[1], fiktif[0], float(qty_needed), float(fiktif[2]), float(fiktif[3]), float(fiktif[4]), float(fiktif[5]), float(fiktif[6]), float(fiktif[7])))
            
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10.0)
            """ if is_sandbox else f"""
                INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, 10.0)
            """, (tgl_jual, f_jual, fiktif[1], fiktif[0], float(fiktif[2]), float(fiktif[3]), float(fiktif[4]), float(fiktif[5]), float(fiktif[6]), float(fiktif[7])))
            
            val_added = price
            remaining_gap -= val_added
            loop_added += val_added
            total_added += val_added
            
            valid_fiktifs = [f for f in fiktif_items if float(f[8]) <= remaining_gap and float(f[8]) > 0]
            
        if log_callback:
            log_callback(f"[{phase_name}] Global Addition Selesai. Ditambah: {loop_added:,.2f}. Sisa Gap Akhir: {remaining_gap:,.2f}")
