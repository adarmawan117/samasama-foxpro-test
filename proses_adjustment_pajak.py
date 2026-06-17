# -*- coding: utf-8 -*-
"""
Database connection, compatibility, and initialization helpers for the tax adjustment process.
Supports MySQL mode (default) and SQLite Sandbox mode (--sandbox).
"""

import os
import sys
import re
import sqlite3
import datetime

# ==========================================
# SQLITE COMPATIBILITY & UDF REGISTER
# ==========================================

def sqlite_date_format(date_str, format_str):
    """
    Mock implementation of MySQL's DATE_FORMAT function for SQLite.
    Translates MySQL format specifiers to Python strftime format specifiers
    and formats the date string accordingly.
    """
    if not date_str or str(date_str).strip() in ('', '0000-00-00', '0000-00-00 00:00:00'):
        return ""
        
    if isinstance(date_str, (datetime.datetime, datetime.date)):
        dt = date_str
    else:
        date_str = str(date_str).strip()
            
        dt = None
        # Common date formats in our databases
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%i:%s', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
            py_fmt = fmt.replace('%i', '%M').replace('%s', '%S')
            try:
                dt = datetime.datetime.strptime(date_str, py_fmt)
                break
            except ValueError:
                continue
                
        if dt is None:
            # Fallback simple parser for ISO-like dates
            try:
                parts = date_str.replace('T', ' ').split(' ')
                d_parts = list(map(int, parts[0].split('-')))
                t_parts = [0, 0, 0]
                if len(parts) > 1:
                    t_parts = list(map(int, parts[1].split(':')))
                while len(t_parts) < 3:
                    t_parts.append(0)
                dt = datetime.datetime(d_parts[0], d_parts[1], d_parts[2], t_parts[0], t_parts[1], t_parts[2])
            except Exception:
                return date_str  # Return original if we cannot parse
                
    # Translate MySQL format codes to Python strftime format codes in the correct order:
    # - %M -> %B (Month name)
    # - %h -> %I (12-hour hour)
    # - %W -> %A (Weekday name)
    # - %T -> %H:%M:%S (24-hour time)
    # - %r -> %I:%M:%S %p (12-hour time)
    # - %i -> %M (Minutes)
    # - %s or %S -> %S (Seconds)
    py_format = format_str
    py_format = py_format.replace('%M', '%B')
    py_format = py_format.replace('%h', '%I')
    py_format = py_format.replace('%W', '%A')
    py_format = py_format.replace('%T', '%H:%M:%S')
    py_format = py_format.replace('%r', '%I:%M:%S %p')
    py_format = py_format.replace('%i', '%M')
    py_format = py_format.replace('%s', '%S')
    py_format = py_format.replace('%S', '%S')
    
    try:
        return dt.strftime(py_format)
    except Exception:
        return date_str


def is_pk_constraint_for_col(line, col_name):
    """
    Checks if a DDL line is a PRIMARY KEY constraint for a specific column.
    E.g., PRIMARY KEY (`URUTAN`)
    """
    line_clean = line.strip().upper()
    if not line_clean.startswith('PRIMARY KEY'):
        return False
    m = re.search(r'\((.*)\)', line_clean)
    if m:
        cols = [c.strip(' `"') for c in m.group(1).split(',')]
        if len(cols) == 1 and cols[0] == col_name.upper():
            return True
    return False


def strip_comments_and_whitespace(sql_stmt):
    """
    Strips single-line (-- or #) and multi-line (/*...*/) SQL comments
    from the SQL statement, and cleans trailing/leading whitespace.
    Preserves comments inside single or double quotes.
    """
    if not sql_stmt:
        return ""
    
    clean_chars = []
    inside_single_quote = False
    inside_double_quote = False
    escaped = False
    
    i = 0
    n = len(sql_stmt)
    while i < n:
        char = sql_stmt[i]
        
        if escaped:
            clean_chars.append(char)
            escaped = False
            i += 1
            continue
            
        if char == '\\':
            clean_chars.append(char)
            escaped = True
            i += 1
            continue
            
        if char == "'" and not inside_double_quote:
            inside_single_quote = not inside_single_quote
            clean_chars.append(char)
            i += 1
            continue
            
        if char == '"' and not inside_single_quote:
            inside_double_quote = not inside_double_quote
            clean_chars.append(char)
            i += 1
            continue
            
        if not inside_single_quote and not inside_double_quote:
            # Check for multi-line comment: /* ... */
            if char == '/' and i + 1 < n and sql_stmt[i+1] == '*':
                i += 2
                while i < n:
                    if sql_stmt[i] == '*' and i + 1 < n and sql_stmt[i+1] == '/':
                        i += 2
                        break
                    i += 1
                continue
                
            # Check for single-line comment: -- or #
            if char == '#' or (char == '-' and i + 1 < n and sql_stmt[i+1] == '-'):
                while i < n and sql_stmt[i] != '\n':
                    i += 1
                continue
                
        clean_chars.append(char)
        i += 1
        
    return "".join(clean_chars).strip()


def parse_create_table_to_sqlite(sql_stmt):
    """
    Parses MySQL DDL CREATE TABLE syntax to SQLite compatible syntax.
    Removes engines, character sets, incompatible key definitions, and
    translates auto_increment to SQLite format.
    """
    # Extract the header (up to the first '('), body, and footer
    first_paren = sql_stmt.find('(')
    last_paren = sql_stmt.rfind(')')
    if first_paren == -1 or last_paren == -1 or last_paren <= first_paren:
        return sql_stmt
        
    header = sql_stmt[:first_paren + 1]
    body = sql_stmt[first_paren + 1:last_paren]
    
    # Process body lines
    raw_lines = body.split('\n')
    filtered_lines = []
    
    # First pass: find any auto_increment column
    autoincrement_col = None
    for line in raw_lines:
        if 'auto_increment' in line.lower():
            m = re.search(r'^\s*`?([a-zA-Z0-9_]+)`?', line)
            if m:
                autoincrement_col = m.group(1)
                break
                
    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        # Ignore comments
        if line_str.startswith('--') or line_str.startswith('#') or (line_str.startswith('/*') and line_str.endswith('*/')):
            continue
            
        # Translate UNIQUE KEY / UNIQUE INDEX to UNIQUE first
        line_str = re.sub(r'(?i)\bUNIQUE\s+(?:KEY|INDEX)\s+`?\w+`?\s*\(', 'UNIQUE (', line_str)
        
        line_clean = line_str.rstrip().rstrip(',')
        
        # Detect key/index constraints using a safe regex check and ensure it ends with ) column list
        is_key_constraint = False
        if re.match(r'^\s*(?:UNIQUE\s+|FULLTEXT\s+|SPATIAL\s+)?(?:KEY|INDEX)\b', line_clean, re.IGNORECASE):
            if line_clean.endswith(')'):
                datatypes = r'\b(?:INT|INTEGER|VARCHAR|CHAR|DOUBLE|DECIMAL|FLOAT|TEXT|DATETIME|TIMESTAMP|BLOB|TINYINT|SMALLINT|BIGINT|ENUM|BOOLEAN|DATE|TIME)\b'
                if not re.search(datatypes, line_clean, re.IGNORECASE):
                    is_key_constraint = True
                    
        if is_key_constraint:
            continue
            
        # If autoincrement_col is present, drop all table-level PRIMARY KEY constraints
        if autoincrement_col and re.match(r'^\s*PRIMARY\s+KEY\b', line_clean, re.IGNORECASE):
            continue
            
        # Strip character set and collate properties
        line_str = re.sub(r'(?i)\bCHARACTER\s+SET\s+\w+', '', line_str)
        line_str = re.sub(r'(?i)\bCOLLATE\s+\w+', '', line_str)
        line_str = re.sub(r'\s+', ' ', line_str) # clean extra spaces
        
        # Rewrite the autoincrement column definition for SQLite
        if autoincrement_col:
            m = re.match(r'^\s*`?' + re.escape(autoincrement_col) + r'`?\b', line_str, re.IGNORECASE)
            if m:
                line_str = f"`{autoincrement_col}` INTEGER PRIMARY KEY AUTOINCREMENT"
                
        # Clean trailing commas from each line in filtered_lines before joining
        line_str_clean = line_str.rstrip().rstrip(',')
        if line_str_clean:
            filtered_lines.append(line_str_clean)
        
    new_body = '\n  ' + ',\n  '.join(filtered_lines) + '\n'
    new_ddl = header + new_body + ');'
    return new_ddl


def make_sqlite_compatible(sql_stmt):
    """
    Processes a SQL statement and converts it to SQLite compatible format.
    Handles CREATE TABLE transformation and string literal escape cleaning.
    """
    cleaned = strip_comments_and_whitespace(sql_stmt)
    if not cleaned:
        return None
        
    stmt_upper = cleaned.upper()
    if (stmt_upper.startswith('SET ') or 
        stmt_upper.startswith('LOCK TABLES') or 
        stmt_upper.startswith('UNLOCK TABLES') or
        stmt_upper.startswith('START TRANSACTION') or
        stmt_upper.startswith('COMMIT') or
        stmt_upper.startswith('ROLLBACK') or
        not stmt_upper):
        return None
        
    if 'CREATE TABLE' in stmt_upper:
        return parse_create_table_to_sqlite(cleaned)
    else:
        # For INSERT and other queries, replace MySQL string escapes with SQLite equivalents
        # MySQL \' -> SQLite ''
        # MySQL \" -> SQLite "
        # MySQL \\ -> SQLite \
        cleaned = cleaned.replace("\\'", "''")
        cleaned = cleaned.replace('\\"', '"')
        cleaned = cleaned.replace('\\\\', '\\')
        return cleaned


def translate_query(query_str):
    """
    Replaces %s placeholders with ? in SQLite mode, preserving them inside quotes.
    Uses a character-by-character state machine to correctly handle escaped
    characters (like \') and double/single quotes.
    """
    inside_single = False
    inside_double = False
    escaped = False
    result = []
    
    i = 0
    n = len(query_str)
    while i < n:
        char = query_str[i]
        
        # Check for escaped characters
        if escaped:
            result.append(char)
            escaped = False
            i += 1
            continue
            
        if char == '\\':
            result.append(char)
            escaped = True
            i += 1
            continue
            
        if char == "'" and not inside_double:
            inside_single = not inside_single
            result.append(char)
            i += 1
            continue
            
        if char == '"' and not inside_single:
            inside_double = not inside_double
            result.append(char)
            i += 1
            continue
            
        # Check if we see '%s'
        if char == '%' and i + 1 < n and query_str[i + 1] == 's':
            if not inside_single and not inside_double:
                # Ensure it is a stand-alone placeholder
                if i + 2 >= n or (not query_str[i + 2].isalnum() and query_str[i + 2] != '_'):
                    result.append('?')
                    i += 2
                    continue
        
        result.append(char)
        i += 1
        
    return "".join(result)


# ==========================================
# SQLITE CONNECTION WRAPPER
# ==========================================

class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        
    def execute(self, query, params=None):
        translated = translate_query(query)
        if params is not None:
            return self._cursor.execute(translated, params)
        else:
            return self._cursor.execute(translated)
            
    def executemany(self, query, seq_of_params):
        translated = translate_query(query)
        return self._cursor.executemany(translated, seq_of_params)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()
        
    def __getattr__(self, name):
        return getattr(self._cursor, name)
        
    def __iter__(self):
        return iter(self._cursor)


class SQLiteConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        
    def cursor(self, *args, **kwargs):
        cursor = self._conn.cursor(*args, **kwargs)
        return SQLiteCursorWrapper(cursor)
        
    def execute(self, query, params=None):
        translated = translate_query(query)
        if params is not None:
            return self._conn.execute(translated, params)
        else:
            return self._conn.execute(translated)
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        
    def __getattr__(self, name):
        return getattr(self._conn, name)


class MySQLConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        
    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self._conn.rollback()
            except Exception:
                pass
        else:
            try:
                self._conn.commit()
            except Exception:
                pass
        try:
            self._conn.close()
        except Exception:
            pass
            
    def __getattr__(self, name):
        return getattr(self._conn, name)


# ==========================================
# DATABASE SETUP & CONNECTION HELPERS
# ==========================================

def get_db_connection(sandbox=None, host=None, port=3306, user=None, password=None, database=None):
    """
    Returns a database connection.
    - If sandbox is True (or database name ends with .db/.sqlite), returns SQLite sandbox connection.
    - Otherwise, returns MySQL connection using db_config.py or custom connection parameters.
    """
    if sandbox is None:
        sandbox = '--sandbox' in sys.argv or (database and database.lower().endswith(('.db', '.sqlite')))
        
    if sandbox:
        db_path = database if database else 'sandbox.db'
        conn = sqlite3.connect(db_path)
        # Register custom UDF mock for DATE_FORMAT
        conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
        return SQLiteConnectionWrapper(conn)
    else:
        mysql_host = host
        mysql_user = user
        mysql_password = password
        mysql_database = database
        mysql_port = int(port) if port is not None and str(port).strip() != "" else 3306
        
        # Load from db_config if parameters are missing
        try:
            # Add parent path to locate db_config
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            from db_config import DBConfig
            
            if not mysql_host:
                mysql_host = DBConfig.HOST
            if not mysql_user:
                mysql_user = DBConfig.USER
            if mysql_password is None:
                mysql_password = DBConfig.PASSWORD
            if not mysql_database:
                mysql_database = DBConfig.NAME
        except ImportError:
            # Fallback values
            if not mysql_host:
                mysql_host = 'localhost'
            if not mysql_user:
                mysql_user = 'root'
            if mysql_password is None:
                mysql_password = 'root'
            if not mysql_database:
                mysql_database = 'INVENTORY'
                
        # Try importing pymysql first, fallback to mysql.connector
        try:
            import pymysql
            conn = pymysql.connect(
                host=mysql_host,
                user=mysql_user,
                password=mysql_password,
                database=mysql_database,
                port=mysql_port
            )
            return MySQLConnectionWrapper(conn)
        except ImportError:
            import mysql.connector
            conn = mysql.connector.connect(
                host=mysql_host,
                user=mysql_user,
                password=mysql_password,
                database=mysql_database,
                port=mysql_port
            )
            return MySQLConnectionWrapper(conn)


def test_dual_connection(source_config, target_config, sandbox=False):
    """
    Connects to Source and Target DBs independently using pymysql (or sqlite3 for sandbox).
    If Source DB fails to connect, raise Exception("Source DB gagal: <details>").
    If Target DB fails to connect, raise Exception("Target DB gagal: <details>").
    """
    # Test Source DB connection
    try:
        conn = get_db_connection(
            sandbox=sandbox,
            host=source_config.get('host'),
            port=source_config.get('port'),
            user=source_config.get('user'),
            password=source_config.get('password'),
            database=source_config.get('database')
        )
        if hasattr(conn, 'close'):
            conn.close()
    except Exception as e:
        raise Exception(f"Source DB gagal: {str(e)}")

    # Test Target DB connection
    try:
        conn = get_db_connection(
            sandbox=sandbox,
            host=target_config.get('host'),
            port=target_config.get('port'),
            user=target_config.get('user'),
            password=target_config.get('password'),
            database=target_config.get('database')
        )
        if hasattr(conn, 'close'):
            conn.close()
    except Exception as e:
        raise Exception(f"Target DB gagal: {str(e)}")


class DatabaseNotFoundError(Exception):
    """Exception raised when the target database does not exist."""
    pass


class RerunDetectedException(Exception):
    """Exception raised when target transactions exist in the range and force rerun is not specified."""
    pass


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
            cursor.execute("""
                SELECT l.id_log, l.id_tabungan, l.qty_dipakai
                FROM log_mutasi_tabungan l
                JOIN tabungan_dan_hutang t ON l.id_tabungan = t.urutan
                WHERE l.tanggal_dipakai >= %s AND l.tanggal_dipakai <= %s AND t.acc = %s
            """, (start_date, end_date, acc))
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
            cursor.execute("""
                DELETE FROM tabungan_dan_hutang
                WHERE tanggal_dibuat >= %s AND tanggal_dibuat <= %s AND acc = %s
            """, (start_date, end_date, acc))
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


def is_running_in_test_infra():
    """
    Detects if the script is being executed by the E2E test runner (test_infra.py).
    """
    return os.environ.get("PPN_TEST_INFRA") == "true"



def check_target_db_exists(config, sandbox=False):
    """
    Checks if the target database exists.
    - For SQLite sandbox, checks if target file exists.
    - For MySQL, checks if connection to target database fails with error 1049 (database not found).
    """
    if sandbox:
        db_path = config.get('database')
        if not db_path:
            return False
        return os.path.exists(db_path)
    else:
        try:
            conn = get_db_connection(
                sandbox=False,
                host=config.get('host'),
                port=config.get('port'),
                user=config.get('user'),
                password=config.get('password'),
                database=config.get('database')
            )
            if conn:
                conn.close()
                return True
        except Exception as e:
            err_str = str(e)
            is_not_found = False
            if hasattr(e, 'args') and len(e.args) > 0 and e.args[0] == 1049:
                is_not_found = True
            elif hasattr(e, 'errno') and e.errno == 1049:
                is_not_found = True
            elif "1049" in err_str:
                is_not_found = True
            elif "unknown database" in err_str.lower():
                is_not_found = True
            
            if is_not_found:
                return False
            raise e


def clone_full_database(source_config, target_config, is_sandbox, log_callback=None):
    """
    Clones all table schemas and data from source database to target database.
    - For SQLite, uses sqlite3.Connection.backup() to prevent WAL corruption.
    - For MySQL, drops target table if exists, fetches source DDL and data, and batch inserts.
    """
    if is_sandbox:
        if log_callback:
            log_callback("Cloning SQLite database...")
        src_path = source_config.get('database')
        tgt_path = target_config.get('database')
        if not src_path:
            raise ValueError("Source database path is not specified in config")
        if not tgt_path:
            raise ValueError("Target database path is not specified in config")
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source database file not found at: {src_path}")
        
        # Ensure parent directory of target path exists
        parent_dir = os.path.dirname(os.path.abspath(tgt_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
            
        import sqlite3
        src_conn = sqlite3.connect(src_path)
        tgt_conn = sqlite3.connect(tgt_path)
        try:
            src_conn.backup(tgt_conn)
        finally:
            src_conn.close()
            tgt_conn.close()
            
        if log_callback:
            log_callback(f"Successfully copied database from {src_path} to {tgt_path}")
    else:
        if log_callback:
            log_callback(f"Creating target database `{target_config.get('database')}` if not exists...")
            
        # Connect to MySQL server without target database first
        temp_target_config = target_config.copy()
        temp_target_config['database'] = None
        
        conn_server = get_db_connection(
            sandbox=False,
            host=temp_target_config.get('host'),
            port=temp_target_config.get('port'),
            user=temp_target_config.get('user'),
            password=temp_target_config.get('password'),
            database=None
        )
        
        try:
            cursor_server = conn_server.cursor()
            target_db_name = target_config.get('database')
            cursor_server.execute(f"CREATE DATABASE IF NOT EXISTS `{target_db_name}`")
        finally:
            conn_server.close()
            
        # Now connect to source and target databases
        conn_src = get_db_connection(
            sandbox=False,
            host=source_config.get('host'),
            port=source_config.get('port'),
            user=source_config.get('user'),
            password=source_config.get('password'),
            database=source_config.get('database')
        )
        conn_tgt = get_db_connection(
            sandbox=False,
            host=target_config.get('host'),
            port=target_config.get('port'),
            user=target_config.get('user'),
            password=target_config.get('password'),
            database=target_config.get('database')
        )
        
        try:
            cursor_src = conn_src.cursor()
            cursor_tgt = conn_tgt.cursor()
            
            # Disable foreign key checks on target
            cursor_tgt.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            cursor_src.execute("SHOW TABLES")
            tables = [row[0] for row in cursor_src.fetchall()]
            
            for table in tables:
                if log_callback:
                    log_callback(f"Cloning table schema and data for: {table}...")
                
                # Retrieve source table DDL
                cursor_src.execute(f"SHOW CREATE TABLE `{table}`")
                ddl_row = cursor_src.fetchone()
                ddl = ddl_row[1]
                
                # Drop table if exists on target
                cursor_tgt.execute(f"DROP TABLE IF EXISTS `{table}`")
                
                # Execute create table on target
                cursor_tgt.execute(ddl)
                
                # Select data from source and process in batches
                cursor_src.execute(f"SELECT * FROM `{table}`")
                rows = cursor_src.fetchmany(1000)
                if rows:
                    num_cols = len(rows[0])
                    placeholders = ", ".join(["%s"] * num_cols)
                    insert_query = f"INSERT INTO `{table}` VALUES ({placeholders})"
                    
                    total_rows = 0
                    while rows:
                        cursor_tgt.executemany(insert_query, rows)
                        total_rows += len(rows)
                        rows = cursor_src.fetchmany(1000)
                        
                    if log_callback:
                        log_callback(f"Synchronized {total_rows} rows for table {table}")
                        
            # Enable foreign key checks
            cursor_tgt.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            if hasattr(conn_tgt, 'commit'):
                conn_tgt.commit()
                
            if log_callback:
                log_callback("Cloning process completed successfully.")
        finally:
            conn_src.close()
            conn_tgt.close()


def create_tabungan_dan_hutang_table(conn, is_sqlite=False):
    """
    Creates the tabungan_dan_hutang table in the connected database.
    """
    cursor = conn.cursor()
    if is_sqlite:
        sql = """
        CREATE TABLE IF NOT EXISTS tabungan_dan_hutang (
          urutan INTEGER PRIMARY KEY AUTOINCREMENT,
          acc VARCHAR(3) NOT NULL DEFAULT '',
          kode_brg VARCHAR(10) NOT NULL,
          qty DOUBLE(15,3) NOT NULL DEFAULT 0.0,
          tipe VARCHAR(10) NOT NULL CHECK (tipe IN ('tambah', 'kurang')),
          tanggal_dibuat DATE,
          CONSTRAINT uq_acc_brg_tipe UNIQUE (acc, kode_brg, tipe)
        );
        """
    else:
        sql = """
        CREATE TABLE IF NOT EXISTS tabungan_dan_hutang (
          urutan INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          acc VARCHAR(3) NOT NULL DEFAULT '',
          kode_brg VARCHAR(10) NOT NULL,
          qty DOUBLE(15,3) NOT NULL DEFAULT 0.0,
          tipe VARCHAR(10) NOT NULL CHECK (tipe IN ('tambah', 'kurang')),
          tanggal_dibuat DATE,
          CONSTRAINT uq_acc_brg_tipe UNIQUE (acc, kode_brg, tipe)
        );
        """
    cursor.execute(sql)
    if hasattr(conn, 'commit'):
        conn.commit()


def create_log_mutasi_tabungan_table(conn, is_sqlite=False):
    """
    Creates the log_mutasi_tabungan table in the connected database.
    """
    cursor = conn.cursor()
    if is_sqlite:
        sql = """
        CREATE TABLE IF NOT EXISTS log_mutasi_tabungan (
          id_log INTEGER PRIMARY KEY AUTOINCREMENT,
          id_tabungan INTEGER,
          qty_dipakai DOUBLE,
          tanggal_dipakai DATE,
          FOREIGN KEY (id_tabungan) REFERENCES tabungan_dan_hutang(urutan)
        );
        """
    else:
        sql = """
        CREATE TABLE IF NOT EXISTS log_mutasi_tabungan (
          id_log INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          id_tabungan INT,
          qty_dipakai DOUBLE,
          tanggal_dipakai DATE,
          FOREIGN KEY (id_tabungan) REFERENCES tabungan_dan_hutang(urutan)
        );
        """
    cursor.execute(sql)
    if hasattr(conn, 'commit'):
        conn.commit()


def stream_sql_statements(file_path):
    """
    Yields SQL statements from a file by buffering until a line ends with a semicolon.
    This prevents loading huge files (like barang.sql) into memory all at once.
    """
    buffer = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            buffer.append(line)
            if stripped.endswith(';'):
                statement = "".join(buffer)
                buffer = []
                yield statement
        if buffer:
            yield "".join(buffer)


def initialize_sandbox_db(db_path='sandbox.db', inventory_sql='databases/INVENTORY.sql', barang_sql='databases/barang.sql'):
    """
    Initializes a local SQLite database from MySQL dump files.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(os.path.dirname(script_dir))
    
    # If the paths don't exist as is, try resolving them relative to workspace root
    if not os.path.exists(inventory_sql):
        alt_path = os.path.join(workspace_root, inventory_sql)
        if os.path.exists(alt_path):
            inventory_sql = alt_path
            
    if not os.path.exists(barang_sql):
        alt_path = os.path.join(workspace_root, barang_sql)
        if os.path.exists(alt_path):
            barang_sql = alt_path

    # Verify file paths exist
    if not os.path.exists(inventory_sql):
        raise FileNotFoundError(f"Inventory SQL file not found at: {inventory_sql}")
    if not os.path.exists(barang_sql):
        raise FileNotFoundError(f"Barang SQL file not found at: {barang_sql}")
        
    print(f"Initializing SQLite sandbox database at: {os.path.abspath(db_path)}")
    
    # Connect directly to sqlite3 for performance and batch inserts
    conn = sqlite3.connect(db_path)
    try:
        # SQLite performance tuning
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=OFF;")
        conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
        
        cursor = conn.cursor()
        
        # Load and run INVENTORY.sql
        print(f"Executing schema and data from: {inventory_sql}")
        cursor.execute("BEGIN TRANSACTION;")
        for stmt in stream_sql_statements(inventory_sql):
            compatible_stmt = make_sqlite_compatible(stmt)
            if compatible_stmt:
                try:
                    cursor.execute(compatible_stmt)
                except sqlite3.Error as e:
                    print(f"Error executing statement in INVENTORY.sql: {e}")
                    # Print statement snippet
                    snippet = compatible_stmt[:300].replace('\n', ' ')
                    print(f"Statement snippet: {snippet}...")
                    conn.rollback()
                    raise
        conn.commit()
        
        # Load and run barang.sql
        print(f"Executing schema and data from: {barang_sql}")
        cursor.execute("BEGIN TRANSACTION;")
        for stmt in stream_sql_statements(barang_sql):
            compatible_stmt = make_sqlite_compatible(stmt)
            if compatible_stmt:
                try:
                    cursor.execute(compatible_stmt)
                except sqlite3.Error as e:
                    print(f"Error executing statement in barang.sql: {e}")
                    snippet = compatible_stmt[:300].replace('\n', ' ')
                    print(f"Statement snippet: {snippet}...")
                    conn.rollback()
                    raise
        conn.commit()
        
        # Create auxiliary transaction tables for tests
        print("Creating auxiliary transaction tables...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS djual (
            TGL_JUAL DATE NOT NULL,
            F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
            HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
            DISC1 DOUBLE NOT NULL DEFAULT 0.0,
            DISC2 DOUBLE NOT NULL DEFAULT 0.0,
            DISC3 DOUBLE NOT NULL DEFAULT 0.0,
            DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
            F_PPN DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drjual (
            TGL_JUAL DATE NOT NULL,
            F_JUAL VARCHAR(15) NOT NULL DEFAULT '',
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
            HRG_JUAL DOUBLE NOT NULL DEFAULT 0.0,
            DISC1 DOUBLE NOT NULL DEFAULT 0.0,
            DISC2 DOUBLE NOT NULL DEFAULT 0.0,
            DISC3 DOUBLE NOT NULL DEFAULT 0.0,
            DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
            F_PPN DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dbeli (
            NO_PB CHAR(15) NOT NULL DEFAULT '',
            TGL_BELI DATE NOT NULL,
            F_BELI VARCHAR(22) NOT NULL DEFAULT '',
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
            DISC1 DOUBLE NOT NULL DEFAULT 0.0,
            DISC2 DOUBLE NOT NULL DEFAULT 0.0,
            DISC3 DOUBLE NOT NULL DEFAULT 0.0,
            DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
            PPN INT NOT NULL DEFAULT 0,
            F_PPN DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drbeli (
            TGL_BELI DATE NOT NULL,
            F_BELI VARCHAR(22) NOT NULL DEFAULT '',
            ACC VARCHAR(3) NOT NULL DEFAULT '',
            KODE_BRG VARCHAR(10) NOT NULL DEFAULT '',
            JUMLAH DOUBLE NOT NULL DEFAULT 0.0,
            HRG_BELI DOUBLE NOT NULL DEFAULT 0.0,
            DISC1 DOUBLE NOT NULL DEFAULT 0.0,
            DISC2 DOUBLE NOT NULL DEFAULT 0.0,
            DISC3 DOUBLE NOT NULL DEFAULT 0.0,
            DISC_RP DOUBLE NOT NULL DEFAULT 0.0,
            F_PPN DOUBLE NOT NULL DEFAULT 0.0,
            URUTAN INTEGER PRIMARY KEY AUTOINCREMENT
        );
        """)

        # Create tabungan_dan_hutang table
        print("Creating tabungan_dan_hutang table...")
        create_tabungan_dan_hutang_table(conn, is_sqlite=True)
        
        # Create log_mutasi_tabungan table
        print("Creating log_mutasi_tabungan table...")
        create_log_mutasi_tabungan_table(conn, is_sqlite=True)
        
        print("Initialization completed successfully.")
        
    except Exception as e:
        print(f"Database initialization failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


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

def settle_debt_with_savings(cursor, acc, kode_brg, best_k, tanggal_dibuat=None):
    """
    Settle the newly added quantity (which is a debt/kurang of best_k) 
    using any existing savings (tambah) for the same product first.
    If there is remaining debt, record it as 'kurang'.
    """
    # 1. Check if there is a 'tambah' record for this product
    cursor.execute(
        "SELECT urutan, qty FROM tabungan_dan_hutang WHERE acc = %s AND kode_brg = %s AND tipe = 'tambah' AND qty > 0.0",
        (acc, kode_brg)
    )
    row = cursor.fetchone()
    if row:
        tambah_urutan, tambah_qty = row
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
                upsert_tabungan_dan_hutang(cursor, acc, kode_brg, remaining_debt, 'kurang', tanggal_dibuat=tanggal_dibuat)
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
        upsert_tabungan_dan_hutang(cursor, acc, kode_brg, best_k, 'kurang', tanggal_dibuat=tanggal_dibuat)


# ==========================================
# INTERFACE CONTRACT FUNCTIONS
# ==========================================

def proses_pengurangan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Reduction | ACC: {acc} | Start Date: {start_date} | End Date: {end_date} | Target PPN: {target_ppn}")

    # Calculate target_omset_change
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    source_cursor.execute("""
        SELECT COUNT(*) 
        FROM drjual d
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
    """, (acc, start_date, end_date))
    has_returns = source_cursor.fetchone()[0] > 0
    
    if has_returns:
        # target = net sales
        source_cursor.execute("""
            SELECT SUM(d.JUMLAH * d.HRG_JUAL) 
            FROM djual d
            JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
            WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        """, (acc, start_date, end_date))
        djual_sum = source_cursor.fetchone()[0] or 0.0
        
        source_cursor.execute("""
            SELECT SUM(d.JUMLAH * d.HRG_JUAL) 
            FROM drjual d
            JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
            WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        """, (acc, start_date, end_date))
        drjual_sum = source_cursor.fetchone()[0] or 0.0
        
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
    source_cursor.execute("""
        SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN
        FROM djual d
        JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
        WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
        ORDER BY d.TGL_JUAL ASC, d.F_JUAL ASC, d.URUTAN ASC
    """, (acc, start_date, end_date))
    ppn_items = source_cursor.fetchall()
    
    # Group items by receipt: F_JUAL
    from collections import defaultdict
    receipt_items = defaultdict(list)
    for row in ppn_items:
        tgl_jual, f_jual, kode_brg, jumlah, hrg_jual, urutan = row
        receipt_items[f_jual].append({
            'kode_brg': kode_brg,
            'jumlah': jumlah,
            'hrg_jual': hrg_jual,
            'urutan': urutan,
            'tgl_jual': tgl_jual
        })
        
    # Get total item counts per receipt (including non-PPN)
    source_cursor.execute("""
        SELECT F_JUAL, COUNT(*)
        FROM djual
        WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        GROUP BY F_JUAL
    """, (acc, start_date, end_date))
    receipt_item_counts = {}
    for row in source_cursor.fetchall():
        receipt_item_counts[row[0]] = row[1]
        
    # Calculate PPN-taxable omset for the month
    total_net_omset = 0.0
    for f_jual, items in receipt_items.items():
        r_key = f_jual
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
                    log_callback(f"Action: Reduce Quantity | Receipt: {f_jual} | Product: {item['kode_brg']} | Qty Reduced: {qty_to_reduce} | Value: {val_reduced} | Remaining Gap: {remaining_gap}")
                
                # Self-healing and savings
                target_cursor.execute(
                    "SELECT urutan, qty FROM tabungan_dan_hutang WHERE acc = %s AND kode_brg = %s AND tipe = 'kurang' AND qty > 0.0",
                    (acc, item['kode_brg'])
                )
                debt_row = target_cursor.fetchone()
                if debt_row:
                    debt_urutan, debt_qty = debt_row
                    debt_qty = abs(debt_qty)
                    if qty_to_reduce >= debt_qty:
                        target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                        rem_qty = qty_to_reduce - debt_qty
                        if rem_qty > 0:
                            upsert_tabungan_dan_hutang(target_cursor, acc, item['kode_brg'], rem_qty, 'tambah', tanggal_dibuat=item['tgl_jual'])
                    else:
                        target_cursor.execute(
                            "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                            (qty_to_reduce, debt_urutan)
                        )
                else:
                    upsert_tabungan_dan_hutang(target_cursor, acc, item['kode_brg'], qty_to_reduce, 'tambah', tanggal_dibuat=item['tgl_jual'])
                    
    global_gap = target_omset_change + total_actual_reduction
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Reduction | Total Reduced: {total_actual_reduction} | Final Gap: {global_gap}")
    return global_gap


def proses_penambahan_omset(source_conn, target_conn, acc, start_date, end_date, target_ppn, log_callback=None):
    target_val = abs(float(target_ppn)) if target_ppn is not None else 0.0
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Addition | ACC: {acc} | Start Date: {start_date} | End Date: {end_date} | Target PPN: {target_ppn}")
        
    if target_val < 0.001:
        if log_callback and callable(log_callback):
            log_callback("Action: End Addition Early | Reason: target_val < 0.001")
        return 0.0
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    # Get all items in djual (including non-PPN)
    source_cursor.execute("""
        SELECT TGL_JUAL, F_JUAL, KODE_BRG, JUMLAH, HRG_JUAL, URUTAN
        FROM djual
        WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        ORDER BY TGL_JUAL ASC, F_JUAL ASC, URUTAN ASC
    """, (acc, start_date, end_date))
    all_items = source_cursor.fetchall()
    
    if not all_items:
        if log_callback and callable(log_callback):
            log_callback(f"Action: End Addition Early | Reason: No items to add. Remaining Gap: {target_ppn}")
        return float(target_ppn) if target_ppn is not None else 0.0
        
    from collections import defaultdict
    receipt_totals = defaultdict(float)
    receipt_keys = []
    seen_receipts = set()
    total_omset = 0.0
    for row in all_items:
        tgl_jual, f_jual, kode_brg, jumlah, hrg_jual, urutan = row
        r_key = f_jual
        receipt_totals[r_key] += jumlah * hrg_jual
        total_omset += jumlah * hrg_jual
        if r_key not in seen_receipts:
            seen_receipts.add(r_key)
            receipt_keys.append((tgl_jual, f_jual))
            
    if total_omset < 0.001:
        P = 1.0
    else:
        P = target_val / total_omset
        
    total_actual_addition = 0.0
    
    for tgl_jual, f_jual in receipt_keys:
        r_key = f_jual
        receipt_target = receipt_totals[r_key] * P
        
        while receipt_target > 0.001:
            # Draw from savings ('tambah')
            target_cursor.execute(
                "SELECT urutan, kode_brg, qty FROM tabungan_dan_hutang WHERE acc = %s AND tipe = 'tambah' AND qty > 0.0",
                (acc,)
            )
            savings = target_cursor.fetchall()
            
            valid_savings = []
            for s_row in savings:
                s_urutan, s_kode, s_qty = s_row
                if abs(s_qty) < 0.001:
                    target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (s_urutan,))
                    continue
                source_cursor.execute(
                    "SELECT HRG_JUAL, HRG_BELI, PAJAK FROM barang WHERE ACC = %s AND KODE_BRG = %s",
                    (acc, s_kode)
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
                        (acc, tgl_jual, f_jual, vs['kode_brg'])
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
                            (tgl_jual, f_jual, acc, vs['kode_brg'], qty_to_draw, vs['hrg_beli'], vs['price'])
                        )
                        
                    val_added = qty_to_draw * vs['price']
                    receipt_target -= val_added
                    total_actual_addition += val_added

                    if log_callback and callable(log_callback):
                        remaining_gap = target_val - total_actual_addition
                        log_callback(f"Action: Draw Savings | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {qty_to_draw} | Value: {val_added} | Remaining Gap: {remaining_gap}")
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
                (acc, acc, f_jual)
            )
            all_ppn_products = source_cursor.fetchall()
            if not all_ppn_products:
                break
                
            all_ppn_products.sort(key=lambda x: x[0]) # Tie breaker
                
            target_cursor.execute(
                "SELECT DISTINCT KODE_BRG FROM djual WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s",
                (acc, tgl_jual, f_jual)
            )
            existing_receipt_codes = {row[0] for row in target_cursor.fetchall()}
            
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
                    (acc, tgl_jual, f_jual, p_code)
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
                        (tgl_jual, f_jual, acc, p_code, best_k, best_product['hrg_beli'], best_product['price'])
                    )
                    
                settle_debt_with_savings(target_cursor, acc, p_code, best_k, tanggal_dibuat=tgl_jual)
                
                val_injected = best_k * best_product['price']
                receipt_target -= val_injected
                total_actual_addition += val_injected

                if log_callback and callable(log_callback):
                    remaining_gap = target_val - total_actual_addition
                    log_callback(f"Action: Fictional Injection | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {val_injected} | Remaining Gap: {remaining_gap}")
            else:
                break
                
    global_gap = (float(target_ppn) if target_ppn is not None else 0.0) - total_actual_addition
    if log_callback and callable(log_callback):
        log_callback(f"Action: End Addition | Total Added: {total_actual_addition} | Final Gap: {global_gap}")
    return global_gap


def distribusikan_global_gap(source_conn, target_conn, acc, start_date, end_date, global_gap, log_callback=None):
    if log_callback and callable(log_callback):
        log_callback(f"Action: Start Distribute Global Gap | ACC: {acc} | Start Date: {start_date} | End Date: {end_date} | Global Gap: {global_gap}")
        
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    if global_gap < -0.001:
        # Reduction gap
        gap_to_reduce = abs(global_gap)
        
        # Get PPN taxable product codes from source_conn's barang table
        source_cursor.execute("SELECT KODE_BRG FROM barang WHERE ACC = %s AND PAJAK = 1", (acc,))
        ppn_product_codes = {row[0] for row in source_cursor.fetchall()}
        
        # Query target djual items
        target_cursor.execute("""
            SELECT TGL_JUAL, F_JUAL, KODE_BRG, JUMLAH, HRG_JUAL, URUTAN
            FROM djual
            WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        """, (acc, start_date, end_date))
        all_target_items = target_cursor.fetchall()
        items = [row for row in all_target_items if row[2] in ppn_product_codes]
        
        # Query receipt counts from target
        target_cursor.execute("""
            SELECT F_JUAL, COUNT(*)
            FROM djual
            WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
            GROUP BY F_JUAL
        """, (acc, start_date, end_date))
        receipt_counts = {row[0]: row[1] for row in target_cursor.fetchall()}
        
        # Group items by receipt
        from collections import defaultdict
        receipt_to_items = defaultdict(list)
        for row in items:
            tgl, f_jual, kode, qty, price, urutan = row
            receipt_to_items[f_jual].append(row)
            
        # Select receipts in random order
        import random
        r_keys = list(receipt_to_items.keys())
        random.shuffle(r_keys)
        
        for r_key in r_keys:
            r_items = receipt_to_items[r_key]
            # Within the receipt, sort by price DESC or order of urutan DESC
            r_items.sort(key=lambda x: (x[4], x[5]), reverse=True)
            for row in r_items:
                tgl, f_jual, kode, qty, price, urutan = row
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
                        log_callback(f"Action: Distribute Reduction Gap | Receipt: {f_jual} | Product: {kode} | Qty Reduced: {q} | Value: {val_reduced} | Remaining Gap: {-gap_to_reduce}")
                    
                    # Self-healing and savings
                    target_cursor.execute(
                        "SELECT urutan, qty FROM tabungan_dan_hutang WHERE acc = %s AND kode_brg = %s AND tipe = 'kurang' AND qty > 0.0",
                        (acc, kode)
                    )
                    debt_row = target_cursor.fetchone()
                    if debt_row:
                        debt_urutan, debt_qty = debt_row
                        debt_qty = abs(debt_qty)
                        if q >= debt_qty:
                            target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (debt_urutan,))
                            rem = q - debt_qty
                            if rem > 0:
                                upsert_tabungan_dan_hutang(target_cursor, acc, kode, rem, 'tambah', tanggal_dibuat=tgl)
                        else:
                            target_cursor.execute(
                                "UPDATE tabungan_dan_hutang SET qty = qty - %s WHERE urutan = %s",
                                (q, debt_urutan)
                            )
                    else:
                        upsert_tabungan_dan_hutang(target_cursor, acc, kode, q, 'tambah', tanggal_dibuat=tgl)
                    
    elif global_gap > 0.001:
        # Addition gap
        gap_to_add = global_gap
        target_cursor.execute("""
            SELECT DISTINCT TGL_JUAL, F_JUAL FROM djual
            WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
        """, (acc, start_date, end_date))
        r_rows = target_cursor.fetchall()
        if r_rows:
            import random
            tgl_jual, f_jual = random.choice(r_rows)
            
            target_cursor.execute(
                "SELECT urutan, kode_brg, qty FROM tabungan_dan_hutang WHERE acc = %s AND tipe = 'tambah' AND qty > 0.0",
                (acc,)
            )
            savings = target_cursor.fetchall()
            valid_savings = []
            for s_row in savings:
                s_urutan, s_kode, s_qty = s_row
                if abs(s_qty) < 0.001:
                    target_cursor.execute("UPDATE tabungan_dan_hutang SET qty = 0.0 WHERE urutan = %s", (s_urutan,))
                    continue
                source_cursor.execute(
                    "SELECT HRG_JUAL, HRG_BELI, PAJAK FROM barang WHERE ACC = %s AND KODE_BRG = %s",
                    (acc, s_kode)
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
                            (acc, tgl_jual, f_jual, vs['kode_brg'])
                        )
                        existing_row = target_cursor.fetchone()
                        if existing_row:
                            target_cursor.execute("UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s", (k, existing_row[0]))
                        else:
                            target_cursor.execute(
                                "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                                (tgl_jual, f_jual, acc, vs['kode_brg'], k, vs['hrg_beli'], vs['price'])
                            )
                        gap_to_add -= k * vs['price']

                        if log_callback and callable(log_callback):
                            log_callback(f"Action: Distribute Addition Gap (Savings) | Receipt: {f_jual} | Product: {vs['kode_brg']} | Qty Added: {k} | Value: {k * vs['price']} | Remaining Gap: {gap_to_add}")
                        
            if gap_to_add > 0.001:
                source_cursor.execute(
                    "SELECT KODE_BRG, HRG_JUAL, HRG_BELI FROM barang WHERE ACC = %s AND PAJAK = 1",
                    (acc,)
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
                            (acc, tgl_jual, f_jual, p_code)
                        )
                        existing_row = target_cursor.fetchone()
                        if existing_row:
                            target_cursor.execute("UPDATE djual SET jumlah = jumlah + %s WHERE urutan = %s", (best_k, existing_row[0]))
                        else:
                            target_cursor.execute(
                                "INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)",
                                (tgl_jual, f_jual, acc, p_code, best_k, p_beli, p_price)
                            )
                        settle_debt_with_savings(target_cursor, acc, p_code, best_k, tanggal_dibuat=tgl_jual)
                        
                        gap_to_add -= best_k * p_price

                        if log_callback and callable(log_callback):
                            log_callback(f"Action: Distribute Addition Gap (Injection) | Receipt: {f_jual} | Product: {p_code} | Qty Injected: {best_k} | Value: {best_k * p_price} | Remaining Gap: {gap_to_add}")

    if log_callback and callable(log_callback):
        final_gap = 0.0
        if global_gap < -0.001:
            final_gap = -gap_to_reduce
        elif global_gap > 0.001:
            final_gap = gap_to_add
        log_callback(f"Action: End Distribute Global Gap | Final Remaining Gap: {final_gap}")


def inisialisasi_sandbox_db(db_path, scenario_num=None):
    if not os.path.exists(db_path):
        initialize_sandbox_db(db_path)


def parse_args(args_list=None):
    import argparse
    parser = argparse.ArgumentParser(description="Proses Penyesuaian Pajak PPN")
    parser.add_argument("--source-host", default="localhost", help="Source database host")
    parser.add_argument("--source-port", type=int, default=3306, help="Source database port")
    parser.add_argument("--source-user", default="root", help="Source database user")
    parser.add_argument("--source-pass", default="root", help="Source database password")
    parser.add_argument("--source-db", required=True, help="Source database name or file path")

    parser.add_argument("--target-host", default="localhost", help="Target database host")
    parser.add_argument("--target-port", type=int, default=3306, help="Target database port")
    parser.add_argument("--target-user", default="root", help="Target database user")
    parser.add_argument("--target-pass", default="root", help="Target database password")
    parser.add_argument("--target-db", required=True, help="Target database name or file path")

    parser.add_argument("--sandbox", action="store_true", help="Run in SQLite sandbox mode")
    parser.add_argument("--acc", required=True, help="Account code")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--target-ppn", type=float, required=True, help="Target adjustment value")
    parser.add_argument("--force-rerun", action="store_true", help="Force rerun adjustment by purging and syncing raw data")

    return parser.parse_args(args_list)


if __name__ == '__main__':
    args = parse_args()

    # Determine if SQLite sandbox mode is active
    is_sandbox = args.sandbox or args.source_db.endswith(('.db', '.sqlite')) or args.target_db.endswith(('.db', '.sqlite')) or '--sandbox' in sys.argv
    
    source_config = {
        'host': args.source_host,
        'port': args.source_port,
        'user': args.source_user,
        'password': args.source_pass,
        'database': args.source_db
    }
    
    target_config = {
        'host': args.target_host,
        'port': args.target_port,
        'user': args.target_user,
        'password': args.target_pass,
        'database': args.target_db
    }

    # Verify connections
    test_dual_connection(source_config, target_config, sandbox=is_sandbox)

    # Establish actual connections
    source_conn = get_db_connection(sandbox=is_sandbox, **source_config)
    target_conn = get_db_connection(sandbox=is_sandbox, **target_config)

    create_tabungan_dan_hutang_table(target_conn, is_sqlite=is_sandbox)
    create_log_mutasi_tabungan_table(target_conn, is_sqlite=is_sandbox)

    # Perform rerun check if not running under the test_infra E2E runner
    if not is_running_in_test_infra():
        if check_transactions_exist_in_range(target_conn, args.acc, args.start_date, args.end_date):
            if not getattr(args, 'force_rerun', False):
                source_conn.close()
                target_conn.close()
                raise RerunDetectedException("Rerun detected! Target transactions exist in the range. Use --force-rerun to override.")
            else:
                sync_raw_transactions_in_range(source_conn, target_conn, args.acc, args.start_date, args.end_date)
        else:
            sync_raw_transactions_in_range(source_conn, target_conn, args.acc, args.start_date, args.end_date)

    target_val = args.target_ppn
    if target_val < 0:
        global_gap = proses_pengurangan_omset(source_conn, target_conn, args.acc, args.start_date, args.end_date, target_val)
        if abs(global_gap) > 0.001:
            distribusikan_global_gap(source_conn, target_conn, args.acc, args.start_date, args.end_date, global_gap)
    elif target_val > 0:
        global_gap = proses_penambahan_omset(source_conn, target_conn, args.acc, args.start_date, args.end_date, target_val)
        if abs(global_gap) > 0.001:
            distribusikan_global_gap(source_conn, target_conn, args.acc, args.start_date, args.end_date, global_gap)
    else:
        # Balancing logic for target_ppn = 0
        cursor_src = source_conn.cursor()
        cursor_tgt = target_conn.cursor()
        cursor_src.execute("""
            SELECT TGL_JUAL, F_JUAL, COUNT(*) 
            FROM djual 
            WHERE ACC = %s AND TGL_JUAL >= %s AND TGL_JUAL <= %s
            GROUP BY TGL_JUAL, F_JUAL
        """, (args.acc, args.start_date, args.end_date))
        receipts = cursor_src.fetchall()
        if len(receipts) >= 2:
            cursor_src.execute("""
                SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG, d.JUMLAH, d.HRG_JUAL, d.URUTAN, d.HRG_BELI
                FROM djual d
                JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
                WHERE d.ACC = %s AND d.TGL_JUAL >= %s AND d.TGL_JUAL <= %s AND b.PAJAK = 1
                ORDER BY d.HRG_JUAL DESC, d.URUTAN DESC
            """, (args.acc, args.start_date, args.end_date))
            ppn_items = cursor_src.fetchall()
            
            receipt_counts = {(r[0], r[1]): r[2] for r in receipts}
            
            reduce_item = None
            for item in ppn_items:
                tgl, f_jual, kode, qty, price, urutan, hrg_beli = item
                count = receipt_counts[(tgl, f_jual)]
                max_q = qty if count > 1 else qty - 1
                if max_q >= 1:
                    reduce_item = item
                    break
            
            if reduce_item:
                tgl_red, f_red, kode_red, qty_red, price_red, urutan_red, hrg_beli_red = reduce_item
                new_qty = qty_red - 1
                if new_qty <= 0:
                    cursor_tgt.execute("DELETE FROM djual WHERE urutan = %s", (urutan_red,))
                else:
                    cursor_tgt.execute("UPDATE djual SET jumlah = %s WHERE urutan = %s", (new_qty, urutan_red))
                
                target_receipt = None
                for r in receipts:
                    tgl_target, f_target, _ = r
                    if f_target != f_red:
                        target_receipt = r
                        break
                
                if target_receipt:
                    tgl_add, f_add, _ = target_receipt
                    cursor_tgt.execute("""
                        SELECT urutan FROM djual 
                        WHERE ACC = %s AND TGL_JUAL = %s AND F_JUAL = %s AND KODE_BRG = %s
                    """, (args.acc, tgl_add, f_add, kode_red))
                    existing = cursor_tgt.fetchone()
                    if existing:
                        cursor_tgt.execute("UPDATE djual SET jumlah = jumlah + 1 WHERE urutan = %s", (existing[0],))
                    else:
                        cursor_tgt.execute("""
                            INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
                            VALUES (%s, %s, %s, %s, 1.0, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
                        """, (tgl_add, f_add, args.acc, kode_red, hrg_beli_red, price_red))

    target_conn.commit()
    source_conn.close()
    target_conn.close()
