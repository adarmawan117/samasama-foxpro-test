import re
import sys

file_path = r"c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test\adjustment_ppn_core\calculator\adjustment.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract the block from "elif global_gap > 0.001:" to "if log_callback and callable(log_callback):"
start_str = "    elif global_gap > 0.001:"
end_str = "\n    if log_callback and callable(log_callback):\n        final_gap = 0.0"

start_idx = content.find(start_str)
if start_idx == -1:
    print("Start string not found!")
    sys.exit(1)
    
end_idx = content.find(end_str, start_idx + len(start_str))
if end_idx == -1:
    print("End string not found!")
    sys.exit(1)

end_idx += 1 # skip the initial newline of end_str

new_block = """    elif global_gap > 0.001:
        # Addition gap
        gap_to_add = global_gap
        target_cursor.execute(f\"\"\"
            SELECT DISTINCT TGL_JUAL, F_JUAL, ACC FROM djual
            WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        \"\"\", (*acc_tuple, start_date, end_date))
        r_rows = target_cursor.fetchall()
        if r_rows:
            while gap_to_add > 200000:
                if gap_to_add <= 1000000:
                    num_targets = 1
                else:
                    num_targets = max(1, len(r_rows) // 4)
                
                chunk_size = gap_to_add / num_targets
                target_receipts = __import__('random').sample(r_rows, min(num_targets, len(r_rows)))
                made_progress = False
                
                for tgl_jual, f_jual, item_acc in target_receipts:
                    receipt_chunk = chunk_size
                    if gap_to_add <= 200000:
                        break
                    
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
                            "SELECT HARGA11, HRG_BELI, PAJAK FROM barang WHERE ACC = %s AND KODE_BRG = %s",
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
                            k = int(receipt_chunk // vs['price'])
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
                                val_added = k * vs['price']
                                gap_to_add -= val_added
                                receipt_chunk -= val_added
                                made_progress = True

                                if log_callback and callable(log_callback):
                                    log_callback(f"[{item_acc}] Action: Distribute Addition Gap (Savings) | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {k} | Value: {val_added} | Remaining Gap: {gap_to_add}")
                                
                    if receipt_chunk > 0.001:
                        source_cursor.execute(
                            f"SELECT KODE_BRG, HARGA11, HRG_BELI FROM barang WHERE ACC IN ({placeholders}) AND PAJAK = 1",
                            (*acc_tuple,)
                        )
                        ppn_products = list(source_cursor.fetchall())
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
                                
                                val_added = best_k * p_price
                                gap_to_add -= val_added
                                receipt_chunk -= val_added
                                made_progress = True

                                if log_callback and callable(log_callback):
                                    log_callback(f"[{item_acc}] Action: Distribute Addition Gap (Injection) | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {val_added} | Remaining Gap: {gap_to_add}")

                if not made_progress:
                    break

"""

new_content = content[:start_idx] + new_block + content[end_idx:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("File updated successfully.")
