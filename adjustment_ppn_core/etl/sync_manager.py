from adjustment_ppn_core.etl.ledger_rollback import rollback_savings_in_range

def check_transactions_exist_in_range(target_conn, acc, start_date, end_date):
    """
    Checks if transactions exist in the target database in the specified range.
    """
    cursor = target_conn.cursor()
    acc_tuple = (acc,) if isinstance(acc, str) else acc
    placeholders = ", ".join(["%s"] * len(acc_tuple))
    query = f"SELECT COUNT(*) FROM djual WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
    cursor.execute(query, (*acc_tuple, start_date, end_date))
    row = cursor.fetchone()
    count = row[0] if row else 0
    return count > 0


def purge_transactions_in_range(target_conn, acc, start_date, end_date):
    """
    Deletes records from djual, drjual, dbeli, and drbeli in target database within range.
    """
    cursor = target_conn.cursor()
    tables_sales = ['djual', 'drjual']
    tables_purchases = ['dbeli', 'drbeli']
    
    for table in tables_sales:
        try:
            if acc is not None:
                acc_tuple = (acc,) if isinstance(acc, str) else acc
                placeholders = ", ".join(["%s"] * len(acc_tuple))
                query = f"DELETE FROM {table} WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
                cursor.execute(query, (*acc_tuple, start_date, end_date))
            else:
                query = f"DELETE FROM {table} WHERE TGL_JUAL >= %s AND TGL_JUAL <= %s"
                cursor.execute(query, (start_date, end_date))
        except Exception as e:
            if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
                pass
            else:
                raise
                
    for table in tables_purchases:
        try:
            if acc is not None:
                acc_tuple = (acc,) if isinstance(acc, str) else acc
                placeholders = ", ".join(["%s"] * len(acc_tuple))
                query = f"DELETE FROM {table} WHERE ACC IN ({placeholders}) AND TGL_BELI >= %s AND TGL_BELI <= %s"
                cursor.execute(query, (*acc_tuple, start_date, end_date))
            else:
                query = f"DELETE FROM {table} WHERE TGL_BELI >= %s AND TGL_BELI <= %s"
                cursor.execute(query, (start_date, end_date))
        except Exception as e:
            if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
                pass
            else:
                raise
            
    if hasattr(target_conn, 'commit'):
        target_conn.commit()


def sync_raw_transactions_in_range(source_conn, target_conn, acc, start_date, end_date):
    """
    Synchronizes raw transactions from source to target database in the specified range.
    First purges any existing target transactions to ensure idempotency.
    """
    rollback_savings_in_range(target_conn, acc, start_date, end_date)
    purge_transactions_in_range(target_conn, acc, start_date, end_date)
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    tables_sales = ['djual', 'drjual']
    tables_purchases = ['dbeli', 'drbeli']
    
    for table in tables_sales:
        try:
            if acc is not None:
                acc_tuple = (acc,) if isinstance(acc, str) else acc
                placeholders = ", ".join(["%s"] * len(acc_tuple))
                query = f"SELECT * FROM {table} WHERE ACC IN ({placeholders}) AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
                source_cursor.execute(query, (*acc_tuple, start_date, end_date))
            else:
                query = f"SELECT * FROM {table} WHERE TGL_JUAL >= %s AND TGL_JUAL <= %s"
                source_cursor.execute(query, (start_date, end_date))
                
            rows = source_cursor.fetchall()
            if rows:
                col_count = len(rows[0])
                placeholders_vals = ", ".join(["%s"] * col_count)
                insert_query = f"INSERT INTO {table} VALUES ({placeholders_vals})"
                try:
                    target_cursor.executemany(insert_query, rows)
                except Exception as e_tgt:
                    if "1146" in str(e_tgt) or "no such table" in str(e_tgt).lower() or "doesn't exist" in str(e_tgt).lower():
                        try:
                            source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
                            ddl = source_cursor.fetchone()[1]
                        except Exception:
                            source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                            ddl = source_cursor.fetchone()[0]
                        target_cursor.execute(ddl)
                        target_cursor.executemany(insert_query, rows)
                    else:
                        raise
        except Exception as e:
            if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
                continue
            raise
            
    for table in tables_purchases:
        try:
            if acc is not None:
                acc_tuple = (acc,) if isinstance(acc, str) else acc
                placeholders = ", ".join(["%s"] * len(acc_tuple))
                query = f"SELECT * FROM {table} WHERE ACC IN ({placeholders}) AND TGL_BELI >= %s AND TGL_BELI <= %s"
                source_cursor.execute(query, (*acc_tuple, start_date, end_date))
            else:
                query = f"SELECT * FROM {table} WHERE TGL_BELI >= %s AND TGL_BELI <= %s"
                source_cursor.execute(query, (start_date, end_date))
                
            rows = source_cursor.fetchall()
            if rows:
                col_count = len(rows[0])
                placeholders_vals = ", ".join(["%s"] * col_count)
                insert_query = f"INSERT INTO {table} VALUES ({placeholders_vals})"
                try:
                    target_cursor.executemany(insert_query, rows)
                except Exception as e_tgt:
                    if "1146" in str(e_tgt) or "no such table" in str(e_tgt).lower() or "doesn't exist" in str(e_tgt).lower():
                        try:
                            source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
                            ddl = source_cursor.fetchone()[1]
                        except Exception:
                            source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
                            ddl = source_cursor.fetchone()[0]
                        target_cursor.execute(ddl)
                        target_cursor.executemany(insert_query, rows)
                    else:
                        raise
        except Exception as e:
            if "1146" in str(e) or "no such table" in str(e).lower() or "doesn't exist" in str(e).lower():
                continue
            raise
            
    if hasattr(target_conn, 'commit'):
        target_conn.commit()
