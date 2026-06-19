import os
import sys
import sqlite3
from .sqlite_translator import sqlite_date_format, translate_query

__all__ = [
    'SQLiteCursorWrapper',
    'SQLiteConnectionWrapper',
    'MySQLConnectionWrapper',
    'get_db_connection',
    'test_dual_connection',
    'DatabaseNotFoundError',
    'RerunDetectedException'
]

class DatabaseNotFoundError(Exception):
    """Exception raised when the target database does not exist."""
    pass

class RerunDetectedException(Exception):
    """Exception raised when target transactions exist in the range and force rerun is not specified."""
    pass


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


class MySQLCursorWrapper:
    def __init__(self, cursor, wrapper):
        self._cursor = cursor
        self._wrapper = wrapper
        
    def execute(self, query, params=None):
        try:
            if params is not None:
                return self._cursor.execute(query, params)
            else:
                return self._cursor.execute(query)
        except Exception as e:
            if "closed" in str(e).lower() or "gone away" in str(e).lower() or "lost connection" in str(e).lower():
                self._wrapper.reconnect()
                self._cursor = self._wrapper._conn.cursor()
                if params is not None:
                    return self._cursor.execute(query, params)
                else:
                    return self._cursor.execute(query)
            raise e
            
    def executemany(self, query, seq_of_params):
        try:
            return self._cursor.executemany(query, seq_of_params)
        except Exception as e:
            if "closed" in str(e).lower() or "gone away" in str(e).lower() or "lost connection" in str(e).lower():
                self._wrapper.reconnect()
                self._cursor = self._wrapper._conn.cursor()
                return self._cursor.executemany(query, seq_of_params)
            raise e
            
    def fetchall(self):
        return self._cursor.fetchall()
        
    def fetchone(self):
        return self._cursor.fetchone()
        
    def close(self):
        return self._cursor.close()
        
    def __getattr__(self, name):
        return getattr(self._cursor, name)
        
    def __iter__(self):
        return iter(self._cursor)

class MySQLConnectionWrapper:
    def __init__(self, conn, connect_kwargs=None, connect_func=None):
        self._conn = conn
        self.connect_kwargs = connect_kwargs
        self.connect_func = connect_func
        
    def reconnect(self):
        try:
            self._conn.close()
        except:
            pass
        if self.connect_func and self.connect_kwargs:
            self._conn = self.connect_func(**self.connect_kwargs)
        else:
            if hasattr(self._conn, 'ping'):
                self._conn.ping(reconnect=True)
        
    def cursor(self, *args, **kwargs):
        try:
            if hasattr(self._conn, 'ping'):
                self._conn.ping(reconnect=True)
        except:
            pass
        cursor = self._conn.cursor(*args, **kwargs)
        return MySQLCursorWrapper(cursor, self)
        
    def commit(self):
        try:
            self._conn.commit()
        except Exception as e:
            if "closed" in str(e).lower() or "gone away" in str(e).lower():
                self.reconnect()
                self._conn.commit()
            else:
                raise e
                
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
        conn = sqlite3.connect(db_path, check_same_thread=False)
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
            # script_dir is adjustment_ppn_core/database
            core_dir = os.path.dirname(script_dir)
            parent_dir = os.path.dirname(core_dir)
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
            connect_kwargs = {
                'host': mysql_host,
                'user': mysql_user,
                'password': mysql_password,
                'database': mysql_database,
                'port': mysql_port,
                'autocommit': True
            }
            conn = pymysql.connect(**connect_kwargs)
            return MySQLConnectionWrapper(conn, connect_kwargs=connect_kwargs, connect_func=pymysql.connect)
        except ImportError:
            import mysql.connector
            connect_kwargs = {
                'host': mysql_host,
                'user': mysql_user,
                'password': mysql_password,
                'database': mysql_database,
                'port': mysql_port
            }
            conn = mysql.connector.connect(**connect_kwargs)
            return MySQLConnectionWrapper(conn, connect_kwargs=connect_kwargs, connect_func=mysql.connector.connect)


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