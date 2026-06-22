import pymysql
import sys

from db_config import DBConfig

class DatabaseHelper:
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
        except Exception as e:
            print(f"Error connecting to MySQL: {e}\nPastikan database 'INVENTORY' sudah dibuat dan SQL dump di-import.")
            sys.exit(1)

    def execute_query(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def fetch_all(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
