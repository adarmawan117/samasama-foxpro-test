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
            cursor.execute(f"""
                SELECT l.id_log, l.id_tabungan, l.qty_dipakai
                FROM log_mutasi_tabungan l
                JOIN tabungan_dan_hutang t ON l.id_tabungan = t.urutan
                WHERE l.tanggal_dipakai >= %s AND l.tanggal_dipakai <= %s AND t.acc IN ({placeholders})
            """, (start_date, end_date, *acc_tuple))
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
            acc_tuple = (acc,) if isinstance(acc, str) else acc
            placeholders = ", ".join(["%s"] * len(acc_tuple))
            cursor.execute(f"""
                DELETE FROM tabungan_dan_hutang
                WHERE tanggal_dibuat >= %s AND tanggal_dibuat <= %s AND acc IN ({placeholders})
            """, (start_date, end_date, *acc_tuple))
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
