# -*- coding: utf-8 -*-
"""
Core Calculator functions for the PPN adjustment process.
"""

import random
from collections import defaultdict
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from .concurrency import DbWriterQueue, LogBatcher


def upsert_tabungan_dan_hutang(cursor, acc, kode_brg, qty, tipe, tanggal_dibuat=None):
    """
    Database-agnostic upsert for tabungan_dan_hutang.
    Checks if a record with (acc, kode_brg, tipe) exists.
    If yes, performs an UPDATE adding the qty.
    If no, performs an INSERT.
    """
    cursor.execute(
        "SELECT qty FROM tabungan_dan_hutang WHERE acc = %s AND kode_brg = %s AND tipe = %s",
        (acc, kode_brg, tipe)
    )
    row = cursor.fetchone()
    if row is not None:
        cursor.execute(
            "UPDATE tabungan_dan_hutang SET qty = qty + %s WHERE acc = %s AND kode_brg = %s AND tipe = %s",
            (qty, acc, kode_brg, tipe)
        )
    else:
        cursor.execute(
            "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe, tanggal_dibuat) VALUES (%s, %s, %s, %s, %s)",
            (acc, kode_brg, qty, tipe, tanggal_dibuat)
        )


def settle_debt_with_savings(cursor, acc_tuple, item_acc, kode_brg, best_k, tanggal_dibuat=None):
    """
    Settle the newly added quantity (which is a debt/kurang of best_k) 
    using any existing savings (tambah) for the same product first.
    If there is remaining debt, record it as 'kurang'.
    """
    # Check if the product exists under A1 in the barang table
    cursor.execute("SELECT 1 FROM barang WHERE ACC = 'A1' AND KODE_BRG = %s", (kode_brg,))
    is_a1 = cursor.fetchone() is not None
    effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
    effective_item_acc = 'A1' if is_a1 else item_acc

    placeholders = ", ".join(["%s"] * len(effective_acc_tuple))
    # 1. Check if there is a 'tambah' record for this product
    cursor.execute(
        f"SELECT urutan, qty, acc FROM tabungan_dan_hutang WHERE acc IN ({placeholders}) AND kode_brg = %s AND tipe = 'tambah' AND qty > 0.0",
        (*effective_acc_tuple, kode_brg)
    )
    row = cursor.fetchone()
    if row:
        tambah_urutan, tambah_qty, _ = row
        tambah_qty = abs(tambah_qty)
        if best_k >= tambah_qty:
            # Settle all savings, delete 'tambah' record
            cursor.execute(
                "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                (tambah_urutan, tambah_qty, tanggal_dibuat)
            )
            cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (tambah_urutan,))
            remaining_debt = best_k - tambah_qty
            if remaining_debt > 0:
                upsert_tabungan_dan_hutang(cursor, effective_item_acc, kode_brg, remaining_debt, 'kurang', tanggal_dibuat=tanggal_dibuat)
        else:
            # Settle part of savings, reduce 'tambah' quantity
            cursor.execute(
                "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                (tambah_urutan, best_k, tanggal_dibuat)
            )
            cursor.execute(
                "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                (best_k, tambah_urutan)
            )
            # No remaining debt to create/update
    else:
        # No savings found, record the entire debt
        upsert_tabungan_dan_hutang(cursor, effective_item_acc, kode_brg, best_k, 'kurang', tanggal_dibuat=tanggal_dibuat)

def upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, acc, kode_brg, qty, tipe, tanggal_dibuat=None):
    key = (acc, kode_brg, tipe)
    with savings_lock:
        records = savings_cache.get(key, [])
        if records:
            record = records[0]
            record['qty'] += qty
            if record['urutan'] == -1:
                db_queue.push(
                    "UPDATE tabungan_dan_hutang SET qty = qty + %s WHERE acc = %s AND kode_brg = %s AND tipe = %s",
                    (qty, acc, kode_brg, tipe)
                )
            else:
                db_queue.push(
                    "UPDATE tabungan_dan_hutang SET qty = qty + %s WHERE urutan = %s",
                    (qty, record['urutan'])
                )
        else:
            db_queue.push(
                "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe, tanggal_dibuat) VALUES (%s, %s, %s, %s, %s)",
                (acc, kode_brg, qty, tipe, tanggal_dibuat)
            )
            # Optional: to prevent KeyError later, append a dummy to cache. 
            # We don't have the real 'urutan' but we won't need it for 'tambah' in reduction or 'kurang' in addition.
            savings_cache[key] = [{'urutan': -1, 'qty': qty}]


def settle_debt_with_savings_async(db_queue, savings_cache, savings_lock, a1_products, acc_tuple, item_acc, kode_brg, best_k, tanggal_dibuat=None):
    is_a1 = kode_brg in a1_products
    effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
    effective_item_acc = 'A1' if is_a1 else item_acc

    remaining_debt = 0
    upsert_needed = False
    
    with savings_lock:
        tambah_records = []
        for acc in effective_acc_tuple:
            key = (acc, kode_brg, 'tambah')
            tambah_records.extend(savings_cache.get(key, []))
            
        tambah_record = next((r for r in tambah_records if r['qty'] > 0), None) if tambah_records else None
        if tambah_record:
            tambah_urutan = tambah_record['urutan']
            tambah_qty = tambah_record['qty']
            
            if best_k >= tambah_qty:
                db_queue.push(
                    "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                    (tambah_urutan, tambah_qty, tanggal_dibuat)
                )
                db_queue.push("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (tambah_urutan,))
                tambah_record['qty'] = 0.0
                
                remaining_debt = best_k - tambah_qty
                if remaining_debt > 0:
                    upsert_needed = True
            else:
                db_queue.push(
                    "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                    (tambah_urutan, best_k, tanggal_dibuat)
                )
                db_queue.push(
                    "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                    (best_k, tambah_urutan)
                )
                tambah_record['qty'] -= best_k
        else:
            remaining_debt = best_k
            upsert_needed = True
            
    if upsert_needed:
        upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, effective_item_acc, kode_brg, remaining_debt, 'kurang', tanggal_dibuat=tanggal_dibuat)


def proses_pengurangan_omset(source_conn, target_conn, acc, start_date, end_date, target_omset_change, max_workers=1, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    
    target_val = abs(float(target_omset_change)) if target_omset_change is not None else 0.0
    
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Reduction | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Target Omset Change: {target_omset_change}")

    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    if target_val < 0.001:
        if log_callback and callable(log_callback):
            log_callback(f"Action: End Reduction | Total Reduced: 0.0 | Final Gap: {target_omset_change}")
        return 0.0
        
    # Get all PPN items in djual
    source_cursor.execute(f"""
        SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.ACC
        FROM djual d
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        ORDER BY d.TGL_JUAL ASC, d.F_JUAL ASC, d.URUTAN ASC
    """, (*acc_tuple, start_date, end_date))
    ppn_items = source_cursor.fetchall()
    
    # Group items by receipt: F_JUAL
    receipt_items = defaultdict(list)
    for row in ppn_items:
        tgl_jual, f_jual, kode_brg, jumlah, hrg_jual, urutan, item_acc = row
        receipt_items[f_jual].append({
            'kode_brg': kode_brg,
            'jumlah': jumlah,
            'hrg_jual': hrg_jual,
            'urutan': urutan,
            'tgl_jual': tgl_jual,
            'item_acc': item_acc
        })
        
    # Get total item counts per receipt (including non-PPN)
    source_cursor.execute(f"""
        SELECT F_JUAL, COUNT(*)
        FROM djual
        WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        GROUP BY F_JUAL
    """, (*acc_tuple, start_date, end_date))
    receipt_item_counts = {}
    for row in source_cursor.fetchall():
        receipt_item_counts[row[0]] = row[1]
        
    # Calculate PPN-taxable omset for the month
    total_net_omset = 0.0
    for f_jual, items in receipt_items.items():
        for item in items:
            total_net_omset += item['jumlah'] * item['hrg_jual']
            
    if total_net_omset < 0.001:
        if log_callback and callable(log_callback):
            log_callback(f"Action: End Reduction | Total Reduced: 0.0 | Final Gap: {target_omset_change}")
        return target_omset_change
        
    # Reduction percentage
    P = target_val / total_net_omset
    
    total_actual_reduction = 0.0
    total_receipts = len(receipt_items)
    
    log_batcher = LogBatcher(log_callback, batch_size=20)
    db_queue = DbWriterQueue(target_conn)
    
    # Preload A1 products and tabungan
    target_cursor.execute("SELECT KODE_BRG FROM barang WHERE ACC = 'A1'")
    a1_products = {row[0] for row in target_cursor.fetchall()}
    
    placeholders_preload = ", ".join(["%s"] * (len(acc_tuple) + 1))
    target_cursor.execute(f"""
        SELECT urutan, qty, acc, kode_brg, tipe 
        FROM tabungan_dan_hutang 
        WHERE acc IN ({placeholders_preload})
    """, (*acc_tuple, 'A1'))
    
    savings_cache = {}
    for row in target_cursor.fetchall():
        urutan, qty, row_acc, kode_brg, tipe = row
        key = (row_acc, kode_brg, tipe)
        if key not in savings_cache:
            savings_cache[key] = []
        savings_cache[key].append({'urutan': urutan, 'qty': float(qty)})
        
    savings_lock = threading.Lock()
    total_actual_reduction_lock = threading.Lock()
    
    # Process each receipt
    def worker_task(index, f_jual, items):
        nonlocal total_actual_reduction
        r_key = f_jual
        # Calculate receipt's PPN omset
        receipt_ppn_omset = sum(item['jumlah'] * item['hrg_jual'] for item in items)
        receipt_target = receipt_ppn_omset * P
        
        # Sort items by urutan DESC (bottom-to-top)
        items_sorted = sorted(items, key=lambda x: x['urutan'], reverse=True)
        
        for item in items_sorted:
            if receipt_target < 0.001:
                break
            
            with total_actual_reduction_lock:
                count = receipt_item_counts[r_key]
                
            # Anti-struk kosong
            max_q = item['jumlah'] if count > 1 else item['jumlah'] - 1
            if max_q <= 0:
                continue
                
            qty_to_reduce = min(max_q, int(receipt_target // item['hrg_jual']))
            if qty_to_reduce > 0:
                new_qty = item['jumlah'] - qty_to_reduce
                if new_qty <= 0:
                    db_queue.push("DELETE FROM djual WHERE urutan = %s", (item['urutan'],))
                    with total_actual_reduction_lock:
                        receipt_item_counts[r_key] -= 1
                else:
                    db_queue.push("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, item['urutan']))
                    
                val_reduced = qty_to_reduce * item['hrg_jual']
                receipt_target -= val_reduced
                
                with total_actual_reduction_lock:
                    total_actual_reduction += val_reduced
                    current_reduction = total_actual_reduction

                remaining_gap = target_val - current_reduction
                log_batcher.add_log(f"[{item['item_acc']}] Action: Reduce Quantity [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {item['kode_brg']} | Qty Reduced: {qty_to_reduce} | Value: {val_reduced} | Remaining Gap: {remaining_gap}")
                
                # Self-healing and savings
                # Check A1 Priority Rule
                is_a1 = item['kode_brg'] in a1_products
                effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
                effective_item_acc = 'A1' if is_a1 else item['item_acc']

                debt_records = []
                with savings_lock:
                    for acc in effective_acc_tuple:
                        key = (acc, item['kode_brg'], 'kurang')
                        debt_records.extend(savings_cache.get(key, []))

                debt_record = next((r for r in debt_records if r['qty'] > 0), None)
                if debt_record:
                    debt_urutan = debt_record['urutan']
                    debt_qty = debt_record['qty']
                    if qty_to_reduce >= debt_qty:
                        db_queue.push("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                        with savings_lock:
                            debt_record['qty'] = 0.0
                        rem_qty = qty_to_reduce - debt_qty
                        if rem_qty > 0:
                            upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, effective_item_acc, item['kode_brg'], rem_qty, 'tambah', tanggal_dibuat=item['tgl_jual'])
                    else:
                        db_queue.push(
                            "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                            (qty_to_reduce, debt_urutan)
                        )
                        with savings_lock:
                            debt_record['qty'] -= qty_to_reduce
                else:
                    upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, effective_item_acc, item['kode_brg'], qty_to_reduce, 'tambah', tanggal_dibuat=item['tgl_jual'])

    # Execute Multithreading
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, (f_jual, items) in enumerate(receipt_items.items(), start=1):
            executor.submit(worker_task, index, f_jual, items)
            
    db_queue.stop_and_wait()
    log_batcher.flush()
    
    global_gap = target_omset_change + total_actual_reduction
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Reduction | Total Reduced: {total_actual_reduction} | Final Gap: {global_gap}")
    return global_gap


def proses_penambahan_omset(source_conn, target_conn, acc, start_date, end_date, target_omset_change, max_workers=1, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    target_val = abs(float(target_omset_change)) if target_omset_change is not None else 0.0
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Addition | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Target Omset Change: {target_omset_change}")
        
    if target_val < 0.001:
        if log_callback and callable(log_callback):
            log_callback("Action: End Addition Early | Reason: target_val < 0.001")
        return 0.0
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # 1. Preload barang master data
    source_cursor.execute("SELECT ACC, KODE_BRG, HARGA11, HRG_BELI, PAJAK FROM barang")
    barang_cache = {}
    a1_products = set()
    for row in source_cursor.fetchall():
        b_acc, b_kode, b_harga, b_beli, b_pajak = row
        barang_cache[(b_acc, b_kode)] = {
            'harga11': float(b_harga) if b_harga is not None else 0.0,
            'hrg_beli': float(b_beli) if b_beli is not None else 0.0,
            'pajak': int(b_pajak) if b_pajak is not None else 0
        }
        if b_acc == 'A1':
            a1_products.add(b_kode)
            
    # 2. Query djual from source_conn with all fields
    source_cursor.execute(f"""
        SELECT TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN, URUTAN
        FROM djual
        WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        ORDER BY TGL_JUAL ASC, F_JUAL ASC, URUTAN ASC
    """, (*acc_tuple, start_date, end_date))
    all_items = source_cursor.fetchall()
    
    if not all_items:
        if log_callback and callable(log_callback):
            log_callback(f"Action: End Addition Early | Reason: No items to add. Remaining Gap: {target_omset_change}")
        return float(target_omset_change) if target_omset_change is not None else 0.0
        
    # 3. Group the query on djual by F_JUAL
    receipt_items = defaultdict(list)
    for row in all_items:
        tgl_jual, f_jual, item_acc, kode_brg, jumlah, hrg_beli, hrg_jual, disc1, disc2, disc3, disc_rp, f_ppn, urutan = row
        receipt_items[f_jual].append({
            'tgl_jual': tgl_jual,
            'f_jual': f_jual,
            'acc': item_acc,
            'kode_brg': kode_brg,
            'jumlah': float(jumlah) if jumlah is not None else 0.0,
            'hrg_beli': float(hrg_beli) if hrg_beli is not None else 0.0,
            'hrg_jual': float(hrg_jual) if hrg_jual is not None else 0.0,
            'disc1': float(disc1) if disc1 is not None else 0.0,
            'disc2': float(disc2) if disc2 is not None else 0.0,
            'disc3': float(disc3) if disc3 is not None else 0.0,
            'disc_rp': float(disc_rp) if disc_rp is not None else 0.0,
            'f_ppn': float(f_ppn) if f_ppn is not None else 0.0,
            'urutan': urutan
        })
        
    receipt_totals = defaultdict(float)
    receipt_keys = []
    seen_receipts = set()
    total_omset = 0.0
    for row in all_items:
        tgl_jual, f_jual, item_acc = row[0], row[1], row[2]
        r_key = f_jual
        if r_key not in seen_receipts:
            seen_receipts.add(r_key)
            receipt_keys.append((tgl_jual, f_jual, item_acc))
            
    for f_jual, items in receipt_items.items():
        r_total = sum(item['jumlah'] * item['hrg_jual'] for item in items)
        receipt_totals[f_jual] = r_total
        total_omset += r_total
        
    if total_omset < 0.001:
        P = 1.0
    else:
        P = target_val / total_omset
        
    total_actual_addition = 0.0
    total_receipts = len(receipt_keys)
    
    # Preload savings_cache
    placeholders_preload = ", ".join(["%s"] * (len(acc_tuple) + 1))
    target_cursor.execute(f"""
        SELECT urutan, qty, acc, kode_brg, tipe 
        FROM tabungan_dan_hutang 
        WHERE acc IN ({placeholders_preload})
    """, (*acc_tuple, 'A1'))
    
    savings_cache = {}
    for row in target_cursor.fetchall():
        urutan, qty, row_acc, kode_brg, tipe = row
        key = (row_acc, kode_brg, tipe)
        if key not in savings_cache:
            savings_cache[key] = []
        savings_cache[key].append({'urutan': urutan, 'qty': float(qty)})
        
    savings_lock = threading.Lock()
    total_actual_addition_lock = threading.Lock()
    
    # Init global product pool for Fictional Injection
    global_product_pool = []
    global_product_lock = threading.Lock()
    
    def refill_global_pool():
        pool = []
        stripped_accs = {a.strip() for a in acc_tuple}
        for (b_acc, b_kode), b_info in barang_cache.items():
            if b_info['pajak'] == 1 and (b_acc is not None and b_acc.strip() in stripped_accs):
                pool.append({
                    'acc': b_acc.strip() if b_acc else b_acc,
                    'kode_brg': b_kode,
                    'price': b_info['harga11'],
                    'hrg_beli': b_info['hrg_beli']
                })
        import random
        random.shuffle(pool)
        return pool

    global_product_pool = refill_global_pool()
    
    log_batcher = LogBatcher(log_callback, batch_size=20)
    db_queue = DbWriterQueue(target_conn)
    
    def worker_task(index, tgl_jual, f_jual, item_acc):
        nonlocal total_actual_addition, global_product_pool
        receipt_target = receipt_totals[f_jual] * P
        
        local_receipt_items = {}
        for item in receipt_items[f_jual]:
            local_receipt_items[item['kode_brg']] = {
                'urutan': item['urutan'],
                'jumlah': item['jumlah'],
                'hrg_beli': item['hrg_beli'],
                'hrg_jual': item['hrg_jual']
            }
            
        while receipt_target > 0.001:
            # Draw from savings ('tambah') using savings_cache
            selected_saving = None
            qty_to_draw = 0
            
            with savings_lock:
                valid_savings = []
                for (s_acc, s_kode, s_tipe), records in savings_cache.items():
                    if s_tipe == 'tambah' and (s_acc in acc_tuple or s_acc == 'A1'):
                        for r in records:
                            s_qty = r['qty']
                            if s_qty > 0.001:
                                # Check A1 Priority Rule
                                is_a1_product = s_kode in a1_products
                                if is_a1_product:
                                    if s_acc != 'A1':
                                        continue
                                else:
                                    if s_acc not in acc_tuple:
                                        continue
                                
                                b_info = barang_cache.get((s_acc, s_kode))
                                if b_info and b_info['pajak'] == 1:
                                    valid_savings.append({
                                        'urutan': r['urutan'],
                                        'kode_brg': s_kode,
                                        'qty': s_qty,
                                        'price': b_info['harga11'],
                                        'hrg_beli': b_info['hrg_beli'],
                                        's_acc': s_acc,
                                        'record': r
                                    })
                                    
                if valid_savings:
                    valid_savings.sort(key=lambda x: (-x['price'], x['kode_brg']))
                    
                    # Priority A: exact match
                    for vs in valid_savings:
                        if abs(vs['price'] * vs['qty'] - receipt_target) < 0.001:
                            selected_saving = vs
                            qty_to_draw = vs['qty']
                            break
                            
                    # Priority B: exact match with multiple
                    if not selected_saving:
                        for vs in valid_savings:
                            k = round(receipt_target / vs['price'])
                            if 1 <= k <= vs['qty'] and abs(vs['price'] * k - receipt_target) < 0.001:
                                selected_saving = vs
                                qty_to_draw = k
                                break
                                
                    # Priority C: closest below target
                    if not selected_saving:
                        best_val = 0.0
                        for vs in valid_savings:
                            k = int(receipt_target // vs['price'])
                            if k > vs['qty']:
                                k = vs['qty']
                            if 1 <= k <= vs['qty']:
                                val = vs['price'] * k
                                if val > best_val:
                                    best_val = val
                                    selected_saving = vs
                                    qty_to_draw = k
                                    
                    if selected_saving:
                        selected_saving['record']['qty'] -= qty_to_draw
                        
            if selected_saving:
                vs = selected_saving
                new_qty = vs['qty'] - qty_to_draw
                
                db_queue.push(
                    "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                    (vs['urutan'], qty_to_draw, tgl_jual)
                )
                if new_qty <= 0:
                    db_queue.push("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (vs['urutan'],))
                else:
                    db_queue.push(
                        "UPDATE tabungan_dan_hutang SET qty = %s WHERE urutan = %s",
                        (new_qty, vs['urutan'])
                    )
                    
                p_code = vs['kode_brg']
                if p_code in local_receipt_items:
                    local_receipt_items[p_code]['jumlah'] += qty_to_draw
                    local_receipt_items[p_code]['modified'] = True
                else:
                    local_receipt_items[p_code] = {
                        'urutan': None,
                        'jumlah': qty_to_draw,
                        'hrg_beli': vs['hrg_beli'],
                        'hrg_jual': vs['price'],
                        'inserted': True
                    }
                    
                val_added = qty_to_draw * vs['price']
                receipt_target -= val_added
                
                with total_actual_addition_lock:
                    total_actual_addition += val_added
                    current_total = total_actual_addition
                    
                remaining_gap = target_val - current_total
                log_batcher.add_log(f"[{item_acc}] Action: Draw Savings [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {qty_to_draw} | Value: {val_added} | Remaining Gap: {remaining_gap}")
                continue
                
            # Fictional injection
            best_product = None
            best_k = 0
            
            with global_product_lock:
                found_idx = -1
                clean_item_acc = item_acc.strip() if item_acc else item_acc
                for i, p in enumerate(global_product_pool):
                    if p['acc'] == clean_item_acc and 0.001 < p['price'] <= receipt_target + 0.001:
                        found_idx = i
                        break
                
                if found_idx == -1:
                    has_acc = any(p['acc'] == clean_item_acc for p in global_product_pool)
                    if not has_acc:
                        global_product_pool = refill_global_pool()
                        for i, p in enumerate(global_product_pool):
                            if p['acc'] == clean_item_acc and 0.001 < p['price'] <= receipt_target + 0.001:
                                found_idx = i
                                break
                                
                if found_idx != -1:
                    best_product = global_product_pool.pop(found_idx)
                    
            if best_product:
                max_k = int(receipt_target // best_product['price'])
                if max_k < 1:
                    max_k = 1
                import random
                best_k = random.randint(1, max_k)
                
                p_code = best_product['kode_brg']
                if p_code in local_receipt_items:
                    local_receipt_items[p_code]['jumlah'] += best_k
                    local_receipt_items[p_code]['modified'] = True
                else:
                    local_receipt_items[p_code] = {
                        'urutan': None,
                        'jumlah': best_k,
                        'hrg_beli': best_product['hrg_beli'],
                        'hrg_jual': best_product['price'],
                        'inserted': True
                    }
                    
                settle_debt_with_savings_async(
                    db_queue, savings_cache, savings_lock, a1_products, 
                    acc_tuple, item_acc, p_code, best_k, tanggal_dibuat=tgl_jual
                )
                
                val_injected = best_k * best_product['price']
                receipt_target -= val_injected
                
                with total_actual_addition_lock:
                    total_actual_addition += val_injected
                    current_total = total_actual_addition
                    
                remaining_gap = target_val - current_total
                log_batcher.add_log(f"[{item_acc}] Action: Fictional Injection [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {val_injected} | Remaining Gap: {remaining_gap}")
            else:
                break
                
        for p_code, loc_item in local_receipt_items.items():
            if loc_item.get('modified'):
                db_queue.push(
                    "UPDATE djual SET jumlah = %s WHERE urutan = %s",
                    (loc_item['jumlah'], loc_item['urutan'])
                )
            elif loc_item.get('inserted'):
                db_queue.push(
                    "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                    (tgl_jual, f_jual, item_acc, p_code, loc_item['jumlah'], loc_item['hrg_beli'], loc_item['hrg_jual'])
                )
                
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for index, (tgl_jual, f_jual, item_acc) in enumerate(receipt_keys, start=1):
            futures.append(executor.submit(worker_task, index, tgl_jual, f_jual, item_acc))
            
        for future in futures:
            try:
                future.result()
            except Exception as e:
                import traceback
                error_msg = f"Action: Error | Exception in worker_task: {str(e)} \n {traceback.format_exc()}"
                if log_callback:
                    log_callback(error_msg)
                raise Exception("Exception in worker_task")
    log_batcher.flush()
    
    global_gap = float(target_omset_change) - total_actual_addition
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Addition | Total Added: {total_actual_addition} | Final Gap: {global_gap}")
    return global_gap


def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, max_workers=1, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Distribute Global Gap | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Global Gap: {global_gap}")
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    log_batcher = LogBatcher(log_callback, batch_size=20)
    db_queue = DbWriterQueue(target_conn)
    gap_lock = threading.Lock()
    
    # Preload A1 products and tabungan cache
    target_cursor.execute("SELECT KODE_BRG FROM barang WHERE ACC = 'A1'")
    a1_products = {row[0] for row in target_cursor.fetchall()}
    
    placeholders_preload = ", ".join(["%s"] * (len(acc_tuple) + 1))
    target_cursor.execute(f"""
        SELECT urutan, qty, acc, kode_brg, tipe 
        FROM tabungan_dan_hutang 
        WHERE acc IN ({placeholders_preload}) AND qty > 0.0
    """, (*acc_tuple, 'A1'))
    
    savings_cache = {}
    for row in target_cursor.fetchall():
        urutan, qty, row_acc, kode_brg, tipe = row
        key = (row_acc, kode_brg, tipe)
        if key not in savings_cache:
            savings_cache[key] = []
        savings_cache[key].append({'urutan': urutan, 'qty': float(qty)})
        
    savings_lock = threading.Lock()
    
    if global_gap < -0.001:
        # Reduction gap
        gap_to_reduce = abs(global_gap)
        
        # Get PPN taxable product codes from source_conn's barang table
        source_cursor.execute(f"SELECT KODE_BRG FROM barang WHERE ACC IN ({placeholders}) AND PAJAK = 1", (*acc_tuple,))
        ppn_product_codes = {row[0] for row in source_cursor.fetchall()}
        
        # Query target djual items
        target_cursor.execute(f"""
            SELECT TGL_JUAL, F_JUAL, KODE_BRG, JUMLAH, HRG_JUAL, URUTAN, ACC
            FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        """, (*acc_tuple, start_date, end_date))
        all_target_items = target_cursor.fetchall()
        items = [row for row in all_target_items if row[2] in ppn_product_codes]
        
        # Query receipt counts from target
        target_cursor.execute(f"""
            SELECT F_JUAL, COUNT(*)
            FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
            GROUP BY F_JUAL
        """, (*acc_tuple, start_date, end_date))
        receipt_counts = {row[0]: row[1] for row in target_cursor.fetchall()}
        
        # Group items by receipt
        receipt_to_items = defaultdict(list)
        for row in items:
            tgl, f_jual, kode, qty, price, urutan, item_acc = row
            receipt_to_items[f_jual].append(row)
            
        # Select receipts in random order
        r_keys = list(receipt_to_items.keys())
        random.shuffle(r_keys)
        total_receipts = len(r_keys)
        
        def worker_reduce(index, r_key):
            nonlocal gap_to_reduce
            r_items = receipt_to_items[r_key]
            r_items.sort(key=lambda x: (x[4], x[5]), reverse=True)
            for row in r_items:
                tgl, f_jual, kode, qty, price, urutan, item_acc = row
                
                with gap_lock:
                    if gap_to_reduce < 0.001:
                        break
                    current_gap = gap_to_reduce
                
                count = receipt_counts[r_key]
                # Anti-struk kosong
                max_q = qty if count > 1 else qty - 1
                if max_q <= 0:
                    continue
                q = min(max_q, int(current_gap // price))
                if q > 0:
                    new_qty = qty - q
                    if new_qty <= 0:
                        db_queue.push("DELETE FROM djual WHERE urutan = %s", (urutan,))
                        with gap_lock:
                            receipt_counts[r_key] -= 1
                    else:
                        db_queue.push("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan))
                    
                    val_reduced = q * price
                    with gap_lock:
                        gap_to_reduce -= val_reduced
                        rem_gap = gap_to_reduce
                        
                    log_batcher.add_log(f"[{item_acc}] Action: Distribute Reduction Gap [{index}/{total_receipts}] | Receipt: {f_jual} | Product: {kode} | Qty Reduced: {q} | Value: {val_reduced} | Remaining Gap: {-rem_gap}")
                    
                    # Self-healing and savings using async pattern
                    is_a1 = kode in a1_products
                    effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
                    effective_item_acc = 'A1' if is_a1 else item_acc
                    
                    debt_records = []
                    with savings_lock:
                        for a in effective_acc_tuple:
                            k = (a, kode, 'kurang')
                            debt_records.extend(savings_cache.get(k, []))
                            
                    debt_record = next((r for r in debt_records if r['qty'] > 0), None)
                    if debt_record:
                        debt_urutan = debt_record['urutan']
                        debt_qty = debt_record['qty']
                        if q >= debt_qty:
                            db_queue.push("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                            with savings_lock:
                                debt_record['qty'] = 0.0
                            rem_qty = q - debt_qty
                            if rem_qty > 0:
                                upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, effective_item_acc, kode, rem_qty, 'tambah', tanggal_dibuat=tgl)
                        else:
                            db_queue.push(
                                "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                                (q, debt_urutan)
                            )
                            with savings_lock:
                                debt_record['qty'] -= q
                    else:
                        upsert_tabungan_dan_hutang_async(db_queue, savings_cache, savings_lock, effective_item_acc, kode, q, 'tambah', tanggal_dibuat=tgl)
                        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for index, r_key in enumerate(r_keys, start=1):
                executor.submit(worker_reduce, index, r_key)

    elif global_gap > 0.001:
        # Addition gap
        gap_to_add = global_gap
        target_cursor.execute(f"""
            SELECT DISTINCT TGL_JUAL, F_JUAL, ACC FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        """, (*acc_tuple, start_date, end_date))
        r_rows = target_cursor.fetchall()
        
        if r_rows:
            source_cursor.execute("SELECT ACC, KODE_BRG, HARGA11, HRG_BELI, PAJAK FROM barang")
            barang_cache = {}
            for row in source_cursor.fetchall():
                b_acc, b_kode, b_harga, b_beli, b_pajak = row
                barang_cache[(b_acc, b_kode)] = {
                    'harga11': float(b_harga) if b_harga is not None else 0.0,
                    'hrg_beli': float(b_beli) if b_beli is not None else 0.0,
                    'pajak': int(b_pajak) if b_pajak is not None else 0
                }
                
            while gap_to_add > 200000:
                if gap_to_add <= 1000000:
                    num_targets = 1
                else:
                    num_targets = max(1, len(r_rows) // 4)
                
                chunk_size = gap_to_add / num_targets
                target_receipts = random.sample(r_rows, min(num_targets, len(r_rows)))
                made_progress = False
                total_targets = len(target_receipts)
                
                def worker_add(index, tgl_jual, f_jual, item_acc):
                    nonlocal gap_to_add, made_progress
                    receipt_chunk = chunk_size
                    
                    with gap_lock:
                        if gap_to_add <= 200000:
                            return
                            
                    # Draw from savings ('tambah') using savings_cache
                    selected_saving = None
                    qty_to_draw = 0
                    
                    with savings_lock:
                        valid_savings = []
                        for (s_acc, s_kode, s_tipe), records in savings_cache.items():
                            if s_tipe == 'tambah' and (s_acc in acc_tuple or s_acc == 'A1'):
                                for r in records:
                                    s_qty = r['qty']
                                    if s_qty > 0.001:
                                        is_a1_product = s_kode in a1_products
                                        if is_a1_product:
                                            if s_acc != 'A1':
                                                continue
                                        else:
                                            if s_acc not in acc_tuple:
                                                continue
                                        
                                        b_info = barang_cache.get((s_acc, s_kode))
                                        if b_info and b_info['pajak'] == 1:
                                            valid_savings.append({
                                                'urutan': r['urutan'],
                                                'kode_brg': s_kode,
                                                'qty': s_qty,
                                                'price': b_info['harga11'],
                                                'hrg_beli': b_info['hrg_beli'],
                                                's_acc': s_acc,
                                                'record': r
                                            })
                                            
                        if valid_savings:
                            valid_savings.sort(key=lambda x: (-x['price'], x['kode_brg']))
                            for vs in valid_savings:
                                k = int(receipt_chunk // vs['price'])
                                if k > vs['qty']:
                                    k = vs['qty']
                                if k > 0:
                                    selected_saving = vs
                                    qty_to_draw = k
                                    break
                                    
                        if selected_saving:
                            selected_saving['record']['qty'] -= qty_to_draw
                            
                    if selected_saving:
                        vs = selected_saving
                        new_qty = vs['qty'] - qty_to_draw
                        
                        db_queue.push(
                            "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                            (vs['urutan'], qty_to_draw, tgl_jual)
                        )
                        if new_qty <= 0:
                            db_queue.push("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (vs['urutan'],))
                        else:
                            db_queue.push("UPDATE tabungan_dan_hutang SET qty = %s WHERE urutan = %s", (new_qty, vs['urutan']))
                            
                        # Here we don't have djual local cache, so we use upsert macro in db_queue basically
                        # Actually we can just do insert directly if we don't care about merging with existing. The original checked existence.
                        # Since db_queue can't easily fetch, let's just insert.
                        db_queue.push(
                            "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                            (tgl_jual, f_jual, item_acc, vs['kode_brg'], qty_to_draw, vs['hrg_beli'], vs['price'])
                        )
                        val_added = qty_to_draw * vs['price']
                        
                        with gap_lock:
                            gap_to_add -= val_added
                            rem_gap = gap_to_add
                            made_progress = True
                            
                        log_batcher.add_log(f"[{item_acc}] Action: Distribute Addition Gap (Savings) [{index}/{total_targets}] | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {qty_to_draw} | Value: {val_added} | Remaining Gap: {rem_gap}")
                        receipt_chunk -= val_added
                        
                    if receipt_chunk > 0.001:
                        # Find product to inject
                        ppn_products = []
                        stripped_accs = {a.strip() for a in acc_tuple}
                        for (b_acc, b_kode), b_info in barang_cache.items():
                            if (b_acc is not None and b_acc.strip() in stripped_accs) and b_info['pajak'] == 1:
                                ppn_products.append((b_kode, b_info['harga11'], b_info['hrg_beli']))
                               
                        if ppn_products:
                            ppn_products.sort(key=lambda x: (x[1], x[0]))
                            best_p = None
                            best_k = 0
                            min_diff = float('inf')
                            for p in ppn_products:
                                p_code, p_price, p_beli = p
                                if p_price < 0.001 or p_price > receipt_chunk + 0.001:
                                    continue
                                k = round(receipt_chunk / p_price)
                                if k < 1:
                                    k = 1
                                diff = abs(p_price * k - receipt_chunk)
                                if diff < min_diff - 0.001:
                                    min_diff = diff
                                    best_p = p
                                    best_k = k
                                elif abs(diff - min_diff) < 0.001:
                                    if best_p is None or p_price > best_p[1]:
                                        min_diff = diff
                                        best_p = p
                                        best_k = k
                            if best_p:
                                p_code, p_price, p_beli = best_p
                                
                                db_queue.push(
                                    "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                                    (tgl_jual, f_jual, item_acc, p_code, best_k, p_beli, p_price)
                                )
                                settle_debt_with_savings_async(db_queue, savings_cache, savings_lock, a1_products, acc_tuple, item_acc, p_code, best_k, tanggal_dibuat=tgl_jual)
                                
                                val_added = best_k * p_price
                                with gap_lock:
                                    gap_to_add -= val_added
                                    rem_gap = gap_to_add
                                    made_progress = True
                                    
                                log_batcher.add_log(f"[{item_acc}] Action: Distribute Addition Gap (Injection) [{index}/{total_targets}] | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {val_added} | Remaining Gap: {rem_gap}")
                                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []
                    for index, (tgl_jual, f_jual, item_acc) in enumerate(target_receipts, start=1):
                        futures.append(executor.submit(worker_add, index, tgl_jual, f_jual, item_acc))
                        
                    for future in futures:
                        try:
                            future.result()
                        except Exception as e:
                            import traceback
                            error_msg = f"Action: Error | Exception in worker_add: {str(e)} \n {traceback.format_exc()}"
                            if log_callback:
                                log_callback(error_msg)
                            raise Exception("Exception in worker_add")
                        
                if not made_progress:
                    break

    db_queue.stop_and_wait()
    log_batcher.flush()
    
    if log_callback and callable(log_callback):
        final_gap = 0.0
        if global_gap < -0.001:
            final_gap = -gap_to_reduce
        elif global_gap > 0.001:
            final_gap = gap_to_add
        log_callback(f"Action: End Distribute Global Gap | Final Remaining Gap: {final_gap}")
