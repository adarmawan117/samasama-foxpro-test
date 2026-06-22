import os
import sys
import traceback
import re
import sqlite3
from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.database.sqlite_translator import make_sqlite_compatible
from adjustment_ppn_core.schema.migrations import create_tabungan_dan_hutang_table, create_log_mutasi_tabungan_table

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
        temp_target_config['database'] = ""
        
        conn_server = get_db_connection(
            sandbox=False,
            host=temp_target_config.get('host'),
            port=temp_target_config.get('port'),
            user=temp_target_config.get('user'),
            password=temp_target_config.get('password'),
            database=""
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
            cursor_src_meta = conn_src.cursor()
            cursor_tgt = conn_tgt.cursor()
            
            # Disable foreign key checks on target
            cursor_tgt.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            cursor_src_meta.execute("SHOW TABLES")
            tables = [row[0] for row in cursor_src_meta.fetchall()]
            
            for table in tables:
                if log_callback:
                    log_callback(f"Cloning table schema and data for: {table}...")
                
                # Retrieve source table DDL
                cursor_src_meta.execute(f"SHOW CREATE TABLE `{table}`")
                ddl_row = cursor_src_meta.fetchone()
                ddl = ddl_row[1]
                
                # Drop table if exists on target
                cursor_tgt.execute(f"DROP TABLE IF EXISTS `{table}`")
                
                # Execute create table on target
                cursor_tgt.execute(ddl)
                
                # Select data from source and process in batches
                try:
                    import pymysql
                    cursor_src_data = conn_src.cursor(pymysql.cursors.SSCursor)
                except Exception:
                    cursor_src_data = conn_src.cursor()
                
                cursor_src_data.execute(f"SELECT * FROM `{table}`")
                rows = cursor_src_data.fetchmany(10000)
                if rows:
                    num_cols = len(rows[0])
                    placeholders = ", ".join(["%s"] * num_cols)
                    insert_query = f"INSERT INTO `{table}` VALUES ({placeholders})"
                    
                    total_rows = 0
                    while rows:
                        cursor_tgt.executemany(insert_query, rows)
                        total_rows += len(rows)
                        rows = cursor_src_data.fetchmany(10000)
                        
                    if log_callback:
                        log_callback(f"Synchronized {total_rows} rows for table {table}")
                cursor_src_data.close()
            
            # Create custom transaction tables
            if log_callback:
                log_callback("Creating custom transaction tables in target database...")
            create_tabungan_dan_hutang_table(conn_tgt, is_sqlite=False)
            create_log_mutasi_tabungan_table(conn_tgt, is_sqlite=False)
                        
            # Enable foreign key checks
            cursor_tgt.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            if hasattr(conn_tgt, 'commit'):
                conn_tgt.commit()
                
            if log_callback:
                log_callback("Cloning process completed successfully.")
        finally:
            conn_src.close()
            conn_tgt.close()


def stream_sql_statements(file_path):
    """
    Yields SQL statements from a file by buffering until a line ends with a semicolon.
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


def inisialisasi_sandbox_db(db_path, scenario_num=None):
    if not os.path.exists(db_path):
        initialize_sandbox_db(db_path)