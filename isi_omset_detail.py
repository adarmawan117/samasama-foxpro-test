import pymysql
import sys

from db_config import DBConfig

class DatabaseHelperDetail:
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        try:
            # Connect directly to the database assuming it's already imported
            self.connection = pymysql.connect(
                host=DBConfig.HOST,
                user=DBConfig.USER,
                password=DBConfig.PASSWORD,
                database=DBConfig.NAME,
                charset='utf8',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.create_detail_table_if_not_exists()
        except Exception as e:
            print(f"Error connecting to MySQL: {e}\nPastikan database 'INVENTORY' sudah dibuat dan SQL dump di-import.")
            sys.exit(1)

    def create_detail_table_if_not_exists(self):
        cursor = self.connection.cursor()
        # Membuat tabel baru khusus untuk memecah PPN agar kompatibel
        # dengan aplikasi foxpro yang lama
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SETOR_PAJAK_DETAIL (
                ACC VARCHAR(50),
                PERIODE VARCHAR(10),
                JENIS_PPN VARCHAR(100),
                JUAL DECIMAL(15,2) DEFAULT 0,
                REAL_JUAL DECIMAL(15,2) DEFAULT 0,
                R_JUAL DECIMAL(15,2) DEFAULT 0,
                P_JUAL DECIMAL(15,2) DEFAULT 0,
                BELI DECIMAL(15,2) DEFAULT 0,
                REAL_BELI DECIMAL(15,2) DEFAULT 0,
                R_BELI DECIMAL(15,2) DEFAULT 0,
                P_BELI DECIMAL(15,2) DEFAULT 0,
                OPR VARCHAR(50),
                DATEOPR VARCHAR(50),
                PRIMARY KEY (ACC, PERIODE, JENIS_PPN)
            )
        """)
        self.connection.commit()
        cursor.close()

    def execute_query(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def fetch_all(self, query, params=None):
        self.connection.commit() # Reset snapshot to get latest data
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
