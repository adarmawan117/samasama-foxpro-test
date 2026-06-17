from adjustment_ppn_core.etl.ledger_rollback import rollback_savings_in_range

def check_transactions_exist_in_range(target_conn, acc, start_date, end_date):
    """
    Checks if transactions exist in the target database in the specified range.
    """
    cursor = target_conn.cursor()
    query = "SELECT COUNT(*) FROM djual WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
    cursor.execute(query, (acc, start_date, end_date))
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
        if acc is not None:
            query = f"DELETE FROM {table} WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
            cursor.execute(query, (acc, start_date, end_date))
        else:
            query = f"DELETE FROM {table} WHERE TGL_JUAL >= %s AND TGL_JUAL <= %s"
            cursor.execute(query, (start_date, end_date))
            
    for table in tables_purchases:
        if acc is not None:
            query = f"DELETE FROM {table} WHERE ACC = %s AND TGL_BELI >= %s AND TGL_BELI <= %s"
            cursor.execute(query, (acc, start_date, end_date))
        else:
            query = f"DELETE FROM {table} WHERE TGL_BELI >= %s AND TGL_BELI <= %s"
            cursor.execute(query, (start_date, end_date))
            
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
        if acc is not None:
            query = f"SELECT * FROM {table} WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s"
            source_cursor.execute(query, (acc, start_date, end_date))
        else:
            query = f"SELECT * FROM {table} WHERE TGL_JUAL >= %s AND TGL_JUAL <= %s"
            source_cursor.execute(query, (start_date, end_date))
            
        rows = source_cursor.fetchall()
        if rows:
            col_count = len(rows[0])
            placeholders = ", ".join(["%s"] * col_count)
            insert_query = f"INSERT INTO {table} VALUES ({placeholders})"
            target_cursor.executemany(insert_query, rows)
            
    for table in tables_purchases:
        if acc is not None:
            query = f"SELECT * FROM {table} WHERE ACC = %s AND TGL_BELI >= %s AND TGL_BELI <= %s"
            source_cursor.execute(query, (acc, start_date, end_date))
        else:
            query = f"SELECT * FROM {table} WHERE TGL_BELI >= %s AND TGL_BELI <= %s"
            source_cursor.execute(query, (start_date, end_date))
            
        rows = source_cursor.fetchall()
        if rows:
            col_count = len(rows[0])
            placeholders = ", ".join(["%s"] * col_count)
            insert_query = f"INSERT INTO {table} VALUES ({placeholders})"
            target_cursor.executemany(insert_query, rows)
            
    if hasattr(target_conn, 'commit'):
        target_conn.commit()
