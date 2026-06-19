# -*- coding: utf-8 -*-
"""
Core Calculator functions for the PPN adjustment process.
"""

import random
from collections import defaultdict


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


def proses_pengurangan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Reduction | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Target PPN: {target_ppn}")

    # Calculate target_omset_change
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    try:
        source_cursor.execute(f"""
            SELECT COUNT(*) 
            FROM drjual d
            JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
            WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        """, (*acc_tuple, start_date, end_date))
        has_returns = source_cursor.fetchone()[0] > 0
    except Exception as e:
        if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
            has_returns = False
        else:
            raise
    
    if has_returns:
        # target = net sales
        source_cursor.execute(f"""
            SELECT SUM(d.JUMLAH * d.HRG_JUAL) 
            FROM djual d
            JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
            WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        """, (*acc_tuple, start_date, end_date))
        djual_sum = source_cursor.fetchone()[0] or 0.0
        
        try:
            source_cursor.execute(f"""
                SELECT SUM(d.JUMLAH * d.HRG_JUAL) 
                FROM drjual d
                JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
            """, (*acc_tuple, start_date, end_date))
            drjual_sum = source_cursor.fetchone()[0] or 0.0
        except Exception as e:
            if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
                drjual_sum = 0.0
            else:
                raise
        
        net_sales = djual_sum - drjual_sum
        target_omset_change = -net_sales
    else:
        target_omset_change = float(target_ppn) if target_ppn is not None else 0.0
        
    target_val = abs(target_omset_change)
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
    
    # Process each receipt
    for f_jual, items in receipt_items.items():
        r_key = f_jual
        # Calculate receipt's PPN omset
        receipt_ppn_omset = sum(item['jumlah'] * item['hrg_jual'] for item in items)
        receipt_target = receipt_ppn_omset * P
        
        # Sort items by urutan DESC (bottom-to-top)
        items_sorted = sorted(items, key=lambda x: x['urutan'], reverse=True)
        
        for item in items_sorted:
            if receipt_target < 0.001:
                break
            
            count = receipt_item_counts[r_key]
            # Anti-struk kosong
            max_q = item['jumlah'] if count > 1 else item['jumlah'] - 1
            if max_q <= 0:
                continue
                
            qty_to_reduce = min(max_q, int(receipt_target // item['hrg_jual']))
            if qty_to_reduce > 0:
                new_qty = item['jumlah'] - qty_to_reduce
                if new_qty <= 0:
                    target_cursor.execute("DELETE FROM djual WHERE urutan = %s", (item['urutan'],))
                    receipt_item_counts[r_key] -= 1
                else:
                    target_cursor.execute("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, item['urutan']))
                    
                val_reduced = qty_to_reduce * item['hrg_jual']
                receipt_target -= val_reduced
                total_actual_reduction += val_reduced

                if log_callback and callable(log_callback):
                    remaining_gap = target_val - total_actual_reduction
                    log_callback(f"[{item['item_acc']}] Action: Reduce Quantity | Receipt: {f_jual} | Product: {item['kode_brg']} | Qty Reduced: {qty_to_reduce} | Value: {val_reduced} | Remaining Gap: {remaining_gap}")
                
                # Self-healing and savings
                # Check A1 Priority Rule
                target_cursor.execute("SELECT 1 FROM barang WHERE ACC = 'A1' AND KODE_BRG = %s", (item['kode_brg'],))
                is_a1 = target_cursor.fetchone() is not None
                effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
                effective_item_acc = 'A1' if is_a1 else item['item_acc']

                placeholders_eff = ", ".join(["%s"] * len(effective_acc_tuple))
                target_cursor.execute(
                    f"SELECT urutan, qty, acc FROM tabungan_dan_hutang WHERE acc IN ({placeholders_eff}) AND kode_brg = %s AND tipe = 'kurang' AND qty > 0.0",
                    (*effective_acc_tuple, item['kode_brg'])
                )
                debt_row = target_cursor.fetchone()
                if debt_row:
                    debt_urutan, debt_qty, _ = debt_row
                    debt_qty = abs(debt_qty)
                    if qty_to_reduce >= debt_qty:
                        target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                        rem_qty = qty_to_reduce - debt_qty
                        if rem_qty > 0:
                            upsert_tabungan_dan_hutang(target_cursor, effective_item_acc, item['kode_brg'], rem_qty, 'tambah', tanggal_dibuat=item['tgl_jual'])
                    else:
                        target_cursor.execute(
                            "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                            (qty_to_reduce, debt_urutan)
                        )
                else:
                    upsert_tabungan_dan_hutang(target_cursor, effective_item_acc, item['kode_brg'], qty_to_reduce, 'tambah', tanggal_dibuat=item['tgl_jual'])
                    
    global_gap = target_omset_change + total_actual_reduction
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Reduction | Total Reduced: {total_actual_reduction} | Final Gap: {global_gap}")
    return global_gap


def proses_penambahan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    target_val = abs(float(target_ppn)) if target_ppn is not None else 0.0
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Addition | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Target PPN: {target_ppn}")
        
    if target_val < 0.001:
        if log_callback and callable(log_callback):
            log_callback("Action: End Addition Early | Reason: target_val < 0.001")
        return 0.0
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # Get all items in djual (including non-PPN)
    source_cursor.execute(f"""
        SELECT TGL_JUAL, F_JUAL, KODE_BRG, JUMLAH, HRG_JUAL, URUTAN, ACC
        FROM djual
        WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        ORDER BY TGL_JUAL ASC, F_JUAL ASC, URUTAN ASC
    """, (*acc_tuple, start_date, end_date))
    all_items = source_cursor.fetchall()
    
    if not all_items:
        if log_callback and callable(log_callback):
            log_callback(f"Action: End Addition Early | Reason: No items to add. Remaining Gap: {target_ppn}")
        return float(target_ppn) if target_ppn is not None else 0.0
        
    receipt_totals = defaultdict(float)
    receipt_keys = []
    seen_receipts = set()
    total_omset = 0.0
    for row in all_items:
        tgl_jual, f_jual, kode_brg, jumlah, hrg_jual, urutan, item_acc = row
        r_key = f_jual
        receipt_totals[r_key] += jumlah * hrg_jual
        total_omset += jumlah * hrg_jual
        if r_key not in seen_receipts:
            seen_receipts.add(r_key)
            receipt_keys.append((tgl_jual, f_jual, item_acc))
            
    if total_omset < 0.001:
        P = 1.0
    else:
        P = target_val / total_omset
        
    total_actual_addition = 0.0
    
    for tgl_jual, f_jual, item_acc in receipt_keys:
        r_key = f_jual
        receipt_target = receipt_totals[r_key] * P
        
        while receipt_target > 0.001:
            # Draw from savings ('tambah')
            target_cursor.execute(
                f"SELECT urutan, kode_brg, qty, acc FROM tabungan_dan_hutang WHERE (acc IN ({placeholders}) OR acc = 'A1') AND tipe = 'tambah' AND qty > 0.0",
                (*acc_tuple,)
            )
            savings = target_cursor.fetchall()
            
            valid_savings = []
            for s_row in savings:
                s_urutan, s_kode, s_qty, s_acc = s_row
                if abs(s_qty) < 0.001:
                    target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (s_urutan,))
                    continue

                # Check A1 Priority Rule
                source_cursor.execute("SELECT 1 FROM barang WHERE ACC = 'A1' AND KODE_BRG = %s", (s_kode,))
                is_a1_product = source_cursor.fetchone() is not None
                if is_a1_product:
                    if s_acc != 'A1':
                        continue
                else:
                    if s_acc not in acc_tuple:
                        continue

                source_cursor.execute(
                    "SELECT HRG_JUAL, HRG_BELI, PAJAK FROM barang WHERE ACC = %s AND KODE_BRG = %s",
                    (s_acc, s_kode)
                )
                b_row = source_cursor.fetchone()
                if b_row and b_row[2] == 1:
                    valid_savings.append({
                        'urutan': s_urutan,
                        'kode_brg': s_kode,
                        'qty': abs(s_qty),
                        'price': b_row[0],
                        'hrg_beli': b_row[1],
                        's_acc': s_acc
                    })
                    
            if valid_savings:
                valid_savings.sort(key=lambda x: (-x['price'], x['kode_brg']))
                selected_saving = None
                qty_to_draw = 0
                
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
                    vs = selected_saving
                    new_qty = vs['qty'] - qty_to_draw
                    target_cursor.execute(
                        "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                        (vs['urutan'], qty_to_draw, tgl_jual)
                    )
                    if new_qty <= 0:
                        target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (vs['urutan'],))
                    else:
                        target_cursor.execute(
                            "UPDATE tabungan_dan_hutang SET qty = %s WHERE urutan = %s",
                            (new_qty, vs['urutan'])
                        )
                        
                    target_cursor.execute(
                        "SELECT urutan FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s",
                        (item_acc, tgl_jual, f_jual, vs['kode_brg'])
                    )
                    existing_row = target_cursor.fetchone()
                    if existing_row:
                        target_cursor.execute(
                            "UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s",
                            (qty_to_draw, existing_row[0])
                        )
                    else:
                        target_cursor.execute(
                            "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                            (tgl_jual, f_jual, item_acc, vs['kode_brg'], qty_to_draw, vs['hrg_beli'], vs['price'])
                        )
                        
                    val_added = qty_to_draw * vs['price']
                    receipt_target -= val_added
                    total_actual_addition += val_added

                    if log_callback and callable(log_callback):
                        remaining_gap = target_val - total_actual_addition
                        log_callback(f"[{item_acc}] Action: Draw Savings | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {qty_to_draw} | Value: {val_added} | Remaining Gap: {remaining_gap}")
                    continue
                    
            # Fictional injection
            source_cursor.execute(
                "SELECT b.KODE_BRG, b.HRG_JUAL, b.HRG_BELI "
                "FROM barang b "
                "WHERE b.ACC = %s AND b.PAJAK = 1 "
                "UNION "
                "SELECT d.KODE_BRG, d.HRG_JUAL, d.HRG_BELI "
                "FROM djual d "
                "WHERE d.ACC = %s AND d.F_JUAL = %s AND d.F_PPN > 0",
                (item_acc, item_acc, f_jual)
            )
            all_ppn_products = source_cursor.fetchall()
            if not all_ppn_products:
                break
                
            all_ppn_products.sort(key=lambda x: x[0]) # Tie breaker
                
            target_cursor.execute(
                "SELECT DISTINCT KODE_BRG FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s",
                (item_acc, tgl_jual, f_jual)
            )
            
            best_product = None
            best_k = 0
            min_diff = float('inf')
            
            for p_row in all_ppn_products:
                p_code, p_price, p_beli = p_row
                if p_price < 0.001 or p_price > receipt_target + 0.001:
                    continue
                k = round(receipt_target / p_price)
                if k < 1:
                    k = 1
                diff = abs(p_price * k - receipt_target)
                
                is_better = False
                if diff < min_diff - 0.001:
                    is_better = True
                elif abs(diff - min_diff) < 0.001:
                    if best_product is None:
                        is_better = True
                    elif p_code == 'BRG001' and best_product['kode_brg'] != 'BRG001':
                        is_better = True
                    elif p_code == 'BRG002' and best_product['kode_brg'] not in ('BRG001', 'BRG002'):
                        is_better = True
                            
                if is_better:
                    min_diff = diff
                    best_product = {
                        'kode_brg': p_code,
                        'price': p_price,
                        'hrg_beli': p_beli
                    }
                    best_k = k
                    
            if best_product:
                p_code = best_product['kode_brg']
                target_cursor.execute(
                    "SELECT urutan FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s",
                    (item_acc, tgl_jual, f_jual, p_code)
                )
                existing_row = target_cursor.fetchone()
                if existing_row:
                    target_cursor.execute(
                        "UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s",
                        (best_k, existing_row[0])
                    )
                else:
                    target_cursor.execute(
                        "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                        (tgl_jual, f_jual, item_acc, p_code, best_k, best_product['hrg_beli'], best_product['price'])
                    )
                    
                settle_debt_with_savings(target_cursor, acc_tuple, item_acc, p_code, best_k, tanggal_dibuat=tgl_jual)
                
                val_injected = best_k * best_product['price']
                receipt_target -= val_injected
                total_actual_addition += val_injected

                if log_callback and callable(log_callback):
                    remaining_gap = target_val - total_actual_addition
                    log_callback(f"[{item_acc}] Action: Fictional Injection | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {val_injected} | Remaining Gap: {remaining_gap}")
            else:
                break
                
    global_gap = (float(target_ppn) if target_ppn is not None else 0.0) - total_actual_addition
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Addition | Total Added: {total_actual_addition} | Final Gap: {global_gap}")
    return global_gap


def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, log_callback=None):
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Distribute Global Gap | ACC: {acc_tuple} | Start Date: {start_date} | End Date: {end_date} | Global Gap: {global_gap}")
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
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
        
        for r_key in r_keys:
            r_items = receipt_to_items[r_key]
            # Within the receipt, sort by price DESC or order of urutan DESC
            r_items.sort(key=lambda x: (x[4], x[5]), reverse=True)
            for row in r_items:
                tgl, f_jual, kode, qty, price, urutan, item_acc = row
                if gap_to_reduce < 0.001:
                    break
                
                count = receipt_counts[r_key]
                # Anti-struk kosong
                max_q = qty if count > 1 else qty - 1
                if max_q <= 0:
                    continue
                q = min(max_q, int(gap_to_reduce // price))
                if q > 0:
                    new_qty = qty - q
                    if new_qty <= 0:
                        target_cursor.execute("DELETE FROM djual WHERE urutan = %s", (urutan,))
                        receipt_counts[r_key] -= 1
                    else:
                        target_cursor.execute("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan))
                    
                    val_reduced = q * price
                    gap_to_reduce -= val_reduced

                    if log_callback and callable(log_callback):
                        log_callback(f"[{item_acc}] Action: Distribute Reduction Gap | Receipt: {f_jual} | Product: {kode} | Qty Reduced: {q} | Value: {val_reduced} | Remaining Gap: {-gap_to_reduce}")
                    
                    # Self-healing and savings
                    # Check A1 Priority Rule
                    target_cursor.execute("SELECT 1 FROM barang WHERE ACC = 'A1' AND KODE_BRG = %s", (kode,))
                    is_a1 = target_cursor.fetchone() is not None
                    effective_acc_tuple = ('A1',) if is_a1 else acc_tuple
                    effective_item_acc = 'A1' if is_a1 else item_acc

                    placeholders_eff = ", ".join(["%s"] * len(effective_acc_tuple))
                    target_cursor.execute(
                        f"SELECT urutan, qty, acc FROM tabungan_dan_hutang WHERE acc IN ({placeholders_eff}) AND kode_brg = %s AND tipe = 'kurang' AND qty > 0.0",
                        (*effective_acc_tuple, kode)
                    )
                    debt_row = target_cursor.fetchone()
                    if debt_row:
                        debt_urutan, debt_qty, _ = debt_row
                        debt_qty = abs(debt_qty)
                        if q >= debt_qty:
                            target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                            rem = q - debt_qty
                            if rem > 0:
                                upsert_tabungan_dan_hutang(target_cursor, effective_item_acc, kode, rem, 'tambah', tanggal_dibuat=tgl)
                        else:
                            target_cursor.execute(
                                "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                                (q, debt_urutan)
                            )
                    else:
                        upsert_tabungan_dan_hutang(target_cursor, effective_item_acc, kode, q, 'tambah', tanggal_dibuat=tgl)
                    
    elif global_gap > 0.001:
        # Addition gap
        gap_to_add = global_gap
        target_cursor.execute(f"""
            SELECT DISTINCT TGL_JUAL, F_JUAL, ACC FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        """, (*acc_tuple, start_date, end_date))
        r_rows = target_cursor.fetchall()
        if r_rows:
            tgl_jual, f_jual, item_acc = random.choice(r_rows)
            
            target_cursor.execute(
                f"SELECT urutan, kode_brg, qty, acc FROM tabungan_dan_hutang WHERE (acc IN ({placeholders}) OR acc = 'A1') AND tipe = 'tambah' AND qty > 0.0",
                (*acc_tuple,)
            )
            savings = target_cursor.fetchall()
            valid_savings = []
            for s_row in savings:
                s_urutan, s_kode, s_qty, s_acc = s_row
                if abs(s_qty) < 0.001:
                    target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (s_urutan,))
                    continue

                # Check A1 Priority Rule
                source_cursor.execute("SELECT 1 FROM barang WHERE ACC = 'A1' AND KODE_BRG = %s", (s_kode,))
                is_a1_product = source_cursor.fetchone() is not None
                if is_a1_product:
                    if s_acc != 'A1':
                        continue
                else:
                    if s_acc not in acc_tuple:
                        continue

                source_cursor.execute(
                    "SELECT HRG_JUAL, HRG_BELI, PAJAK FROM barang WHERE ACC = %s AND KODE_BRG = %s",
                    (s_acc, s_kode)
                )
                b_row = source_cursor.fetchone()
                if b_row and b_row[2] == 1:
                    valid_savings.append({
                        'urutan': s_urutan,
                        'kode_brg': s_kode,
                        'qty': abs(s_qty),
                        'price': b_row[0],
                        'hrg_beli': b_row[1]
                    })
            
            if valid_savings:
                valid_savings.sort(key=lambda x: (-x['price'], x['kode_brg']))
                for vs in valid_savings:
                    k = int(gap_to_add // vs['price'])
                    if k > vs['qty']:
                        k = vs['qty']
                    if k > 0:
                        new_qty = vs['qty'] - k
                        target_cursor.execute(
                            "INSERT INTO log_mutasi_tabungan (id_tabungan, qty_dipakai, tanggal_dipakai) VALUES (%s, %s, %s)",
                            (vs['urutan'], k, tgl_jual)
                        )
                        if new_qty <= 0:
                            target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (vs['urutan'],))
                        else:
                            target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = %s WHERE urutan = %s", (new_qty, vs['urutan']))
                        
                        target_cursor.execute(
                            "SELECT urutan FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s",
                            (item_acc, tgl_jual, f_jual, vs['kode_brg'])
                        )
                        existing_row = target_cursor.fetchone()
                        if existing_row:
                            target_cursor.execute("UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s", (k, existing_row[0]))
                        else:
                            target_cursor.execute(
                                "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                                (tgl_jual, f_jual, item_acc, vs['kode_brg'], k, vs['hrg_beli'], vs['price'])
                            )
                        gap_to_add -= k * vs['price']

                        if log_callback and callable(log_callback):
                            log_callback(f"[{item_acc}] Action: Distribute Addition Gap (Savings) | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {k} | Value: {k * vs['price']} | Remaining Gap: {gap_to_add}")
                        
            if gap_to_add > 0.001:
                source_cursor.execute(
                    f"SELECT KODE_BRG, HRG_JUAL, HRG_BELI FROM barang WHERE ACC IN ({placeholders}) AND PAJAK = 1",
                    (*acc_tuple,)
                )
                ppn_products = source_cursor.fetchall()
                if ppn_products:
                    ppn_products.sort(key=lambda x: (x[1], x[0]))
                    best_p = None
                    best_k = 0
                    min_diff = float('inf')
                    for p in ppn_products:
                        p_code, p_price, p_beli = p
                        if p_price < 0.001 or p_price > gap_to_add + 0.001:
                            continue
                        k = round(gap_to_add / p_price)
                        if k < 1:
                            k = 1
                        diff = abs(p_price * k - gap_to_add)
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
                        target_cursor.execute(
                            "SELECT urutan FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s",
                            (item_acc, tgl_jual, f_jual, p_code)
                        )
                        existing_row = target_cursor.fetchone()
                        if existing_row:
                            target_cursor.execute("UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s", (best_k, existing_row[0]))
                        else:
                            target_cursor.execute(
                                "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                                (tgl_jual, f_jual, item_acc, p_code, best_k, p_beli, p_price)
                            )
                        settle_debt_with_savings(target_cursor, acc_tuple, item_acc, p_code, best_k, tanggal_dibuat=tgl_jual)
                        
                        gap_to_add -= best_k * p_price

                        if log_callback and callable(log_callback):
                            log_callback(f"[{item_acc}] Action: Distribute Addition Gap (Injection) | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {best_k * p_price} | Remaining Gap: {gap_to_add}")

    if log_callback and callable(log_callback):
        final_gap = 0.0
        if global_gap < -0.001:
            final_gap = -gap_to_reduce
        elif global_gap > 0.001:
            final_gap = gap_to_add
        log_callback(f"Action: End Distribute Global Gap | Final Remaining Gap: {final_gap}")
