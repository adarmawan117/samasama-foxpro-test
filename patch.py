import os
import re

file_path = "c:/Users/adarmawan117/Downloads/UndfxffAllW/RESULTS/python_test/adjustment_ppn_core/calculator/adjustment.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject global_product_pool to proses_penambahan_omset
addition_init_search = """    savings_lock = threading.Lock()
    total_actual_addition_lock = threading.Lock()
    
    log_batcher = LogBatcher(log_callback, batch_size=20)"""

addition_init_replace = """    savings_lock = threading.Lock()
    total_actual_addition_lock = threading.Lock()
    
    # Init global product pool for Fictional Injection
    global_product_pool = []
    global_product_lock = threading.Lock()
    
    def refill_global_pool():
        pool = []
        for (b_acc, b_kode), b_info in barang_cache.items():
            if b_info['pajak'] == 1 and b_acc in acc_tuple:
                pool.append({
                    'acc': b_acc,
                    'kode_brg': b_kode,
                    'price': b_info['harga11'],
                    'hrg_beli': b_info['hrg_beli']
                })
        import random
        random.shuffle(pool)
        return pool

    global_product_pool = refill_global_pool()
    
    log_batcher = LogBatcher(log_callback, batch_size=20)"""

if addition_init_search in content:
    content = content.replace(addition_init_search, addition_init_replace)
else:
    print("FAILED to find addition_init_search")

# 2. Inject QTY Randomization and pool pop
fictional_inj_search = """            # Fictional injection
            union_set = set()
            for (b_acc, b_kode), b_info in barang_cache.items():
                if b_acc == item_acc and b_info['pajak'] == 1:
                    union_set.add((b_kode, b_info['harga11'], b_info['hrg_beli']))
            for item in receipt_items.get(f_jual, []):
                if item['acc'] == item_acc and item['f_ppn'] > 0:
                    union_set.add((item['kode_brg'], item['hrg_jual'], item['hrg_beli']))
                    
            all_ppn_products = list(union_set)
            if not all_ppn_products:
                break
                
            all_ppn_products.sort(key=lambda x: x[0])
            
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
                    
            if best_product:"""

fictional_inj_replace = """            # Fictional injection
            best_product = None
            best_k = 0
            
            with global_product_lock:
                found_idx = -1
                for i, p in enumerate(global_product_pool):
                    if p['acc'] == item_acc and 0.001 < p['price'] <= receipt_target + 0.001:
                        found_idx = i
                        break
                
                if found_idx == -1:
                    has_acc = any(p['acc'] == item_acc for p in global_product_pool)
                    if not has_acc:
                        global_product_pool = refill_global_pool()
                        for i, p in enumerate(global_product_pool):
                            if p['acc'] == item_acc and 0.001 < p['price'] <= receipt_target + 0.001:
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
                """

if fictional_inj_search in content:
    content = content.replace(fictional_inj_search, fictional_inj_replace)
else:
    print("FAILED to find fictional_inj_search")

# 3. Rewrite distribusikan_global_gap to match requirements
old_distribusikan_start = "def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, max_workers=1, log_callback=None):"
old_distribusikan_idx = content.find(old_distribusikan_start)

if old_distribusikan_idx != -1:
    new_distribute_func = """def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, max_workers=1, log_callback=None):
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
    target_cursor.execute(f\"\"\"
        SELECT urutan, qty, acc, kode_brg, tipe 
        FROM tabungan_dan_hutang 
        WHERE acc IN ({placeholders_preload}) AND qty > 0.0
    \"\"\", (*acc_tuple, 'A1'))
    
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
        target_cursor.execute(f\"\"\"
            SELECT TGL_JUAL, F_JUAL, KODE_BRG, JUMLAH, HRG_JUAL, URUTAN, ACC
            FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        \"\"\", (*acc_tuple, start_date, end_date))
        all_target_items = target_cursor.fetchall()
        items = [row for row in all_target_items if row[2] in ppn_product_codes]
        
        # Query receipt counts from target
        target_cursor.execute(f\"\"\"
            SELECT F_JUAL, COUNT(*)
            FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
            GROUP BY F_JUAL
        \"\"\", (*acc_tuple, start_date, end_date))
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
        target_cursor.execute(f\"\"\"
            SELECT DISTINCT TGL_JUAL, F_JUAL, ACC FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        \"\"\", (*acc_tuple, start_date, end_date))
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
                        for (b_acc, b_kode), b_info in barang_cache.items():
                            if b_acc in acc_tuple and b_info['pajak'] == 1:
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
                    for index, (tgl_jual, f_jual, item_acc) in enumerate(target_receipts, start=1):
                        executor.submit(worker_add, index, tgl_jual, f_jual, item_acc)
                        
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
"""
    content = content[:old_distribusikan_idx] + new_distribute_func

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
