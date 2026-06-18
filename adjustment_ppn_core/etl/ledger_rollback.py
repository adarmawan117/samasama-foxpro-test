def rollback_savings_in_range(target_conn, acc, start_date, end_date):
    """
    Rolls back savings adjustments within the specified range.
    Restores qty for consumed savings in log_mutasi_tabungan and deletes the logs.
    Deletes newly created rows in tabungan_dan_hutang.
    """
    try:
        cursor = target_conn.cursor()
        
        # 1. Fetch consumed savings logs
        if acc is not None:
            acc_tuple = (acc,) if isinstance(acc, str) else acc
            placeholders = ", ".join(["%s"] * len(acc_tuple))
            
            # Fetch products from target accounts that are redirected to A1
            cursor.execute(f"""
                SELECT KODE_BRG FROM barang 
                WHERE ACC = 'A1' AND KODE_BRG IN (
                    SELECT KODE_BRG FROM barang WHERE ACC IN ({placeholders})
                )
            """, acc_tuple)
            redirected_products = [row[0] for row in cursor.fetchall()]

            params = [start_date, end_date]
            acc_conditions = ["t.acc IN (" + placeholders + ")"]
            params.extend(acc_tuple)
            
            if redirected_products:
                placeholders_redirected = ", ".join(["%s"] * len(redirected_products))
                acc_conditions.append(f"(t.acc = 'A1' AND t.kode_brg IN ({placeholders_redirected}))")
                params.extend(redirected_products)
                
            where_clause = " OR ".join(acc_conditions)

            cursor.execute(f"""
                SELECT l.id_log, l.id_tabungan, l.qty_dipakai
                FROM log_mutasi_tabungan l
                JOIN tabungan_dan_hutang t ON l.id_tabungan = t.urutan
                WHERE l.tanggal_dipakai >= %s AND l.tanggal_dipakai <= %s AND ({where_clause})
            """, tuple(params))
        else:
            cursor.execute("""
                SELECT l.id_log, l.id_tabungan, l.qty_dipakai
                FROM log_mutasi_tabungan l
                WHERE l.tanggal_dipakai >= %s AND l.tanggal_dipakai <= %s
            """, (start_date, end_date))
            
        logs = cursor.fetchall()
        
        # 2. Restore quantity and delete the logs
        for id_log, id_tabungan, qty_dipakai in logs:
            cursor.execute(
                "UPDATE tabungan_dan_hutang SET qty = ROUND(qty + %s, 3) WHERE urutan = %s",
                (qty_dipakai, id_tabungan)
            )
            cursor.execute(
                "DELETE FROM log_mutasi_tabungan WHERE id_log = %s",
                (id_log,)
            )
            
        # 3. Delete newly created rows in tabungan_dan_hutang
        if acc is not None:
            params_del = [start_date, end_date]
            del_conditions = ["acc IN (" + placeholders + ")"]
            params_del.extend(acc_tuple)
            
            if redirected_products:
                placeholders_redirected = ", ".join(["%s"] * len(redirected_products))
                del_conditions.append(f"(acc = 'A1' AND kode_brg IN ({placeholders_redirected}))")
                params_del.extend(redirected_products)
                
            where_del = " OR ".join(del_conditions)

            cursor.execute(f"""
                DELETE FROM tabungan_dan_hutang
                WHERE tanggal_dibuat >= %s AND tanggal_dibuat <= %s AND ({where_del})
            """, tuple(params_del))
        else:
            cursor.execute("""
                DELETE FROM tabungan_dan_hutang
                WHERE tanggal_dibuat >= %s AND tanggal_dibuat <= %s
            """, (start_date, end_date))
            
        if hasattr(target_conn, 'commit') and callable(target_conn.commit):
            target_conn.commit()
            
    except Exception:
        # Bypasses execution if tables do not exist
        pass
