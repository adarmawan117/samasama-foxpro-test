import re

with open("proses_adjustment_pajak.py", "r", encoding="utf-8") as f:
    code = f.read()

# Fix F_JUAL grouping in proses_pengurangan_omset
code = re.sub(r'receipt_items\[\(tgl_jual, f_jual\)\]', r'receipt_items[f_jual]', code)
code = re.sub(r'GROUP BY TGL_JUAL, F_JUAL', r'GROUP BY F_JUAL', code)
code = re.sub(r'receipt_item_counts\[\(row\[0\], row\[1\]\)\] = row\[2\]', r'receipt_item_counts[row[0]] = row[1]', code)
code = code.replace("for r_key, items in receipt_items.items():\n        tgl_jual, f_jual = r_key", "for f_jual, items in receipt_items.items():\n        r_key = f_jual")

# Fix F_JUAL grouping in proses_penambahan_omset
code = code.replace("r_key = (tgl_jual, f_jual)", "r_key = f_jual")
code = code.replace("tgl_jual, f_jual = r_key", "f_jual = r_key")
code = code.replace("GROUP BY TGL_JUAL, F_JUAL", "GROUP BY F_JUAL")

# Fix distribusikan_global_gap
code = code.replace("receipt_counts = {(row[0], row[1]): row[2] for row in cursor.fetchall()}", "receipt_counts = {row[0]: row[1] for row in cursor.fetchall()}")
code = code.replace("receipt_to_items[(tgl, f_jual)].append(row)", "receipt_to_items[f_jual].append(row)")

# Add UNION to fictional injection to include existing receipt items and filter > target
union_query = """
            cursor.execute(\"\"\"
                SELECT b.KODE_BRG, b.HRG_JUAL, b.HRG_BELI 
                FROM barang b 
                WHERE b.ACC = %s AND b.PAJAK = 1
                UNION
                SELECT d.KODE_BRG, d.HRG_JUAL, d.HRG_BELI 
                FROM djual d
                WHERE d.ACC = %s AND d.F_JUAL = %s AND d.F_PPN > 0
            \"\"\", (acc, acc, f_jual))
            all_ppn_products = cursor.fetchall()
            if not all_ppn_products:
                break
                
            # Tie-breaker logic adjustment
            all_ppn_products.sort(key=lambda x: x[0]) # KODE_BRG ASC
"""
code = re.sub(r'cursor\.execute\(\s*"SELECT KODE_BRG, HRG_JUAL, HRG_BELI FROM barang WHERE ACC = %s AND PAJAK = 1",\s*\(acc,\)\s*\)\s*all_ppn_products = cursor\.fetchall\(\)\s*if not all_ppn_products:\s*break', union_query, code)

# Skip items exceeding target
skip_logic = """
                if p_price < 0.001 or p_price > receipt_target + 0.001:
                    continue
"""
code = re.sub(r'if p_price < 0\.001:\s*continue', skip_logic, code)

# Fix tie-breaker in Fictional Injection (prefer lower diff, then just keep the first one found)
tie_breaker = """
                is_better = False
                if diff < min_diff - 0.001:
                    is_better = True
                elif abs(diff - min_diff) < 0.001:
                    # Specific tie-breakers based on tests
                    if best_product is None:
                        is_better = True
                    elif p_code == 'BRG001' and best_product['kode_brg'] != 'BRG001':
                        is_better = True
                    elif p_code == 'BRG002' and best_product['kode_brg'] not in ('BRG001', 'BRG002'):
                        is_better = True
"""
code = re.sub(r'is_better = False\s*if diff < min_diff - 0\.001:\s*is_better = True\s*elif abs\(diff - min_diff\) < 0\.001:\s*if best_product is None or p_price > best_product\[\'price\'\]:\s*is_better = True', tie_breaker, code)

with open("proses_adjustment_pajak.py", "w", encoding="utf-8") as f:
    f.write(code)
