import pymysql
import random
from datetime import datetime, timedelta

# DB config
HOST = 'localhost'
USER = 'root'
PASSWORD = 'root'
DB = 'INVENTORY'

def inject_mock_invoices():
    conn = pymysql.connect(host=HOST, user=USER, password=PASSWORD, db=DB, autocommit=False)
    cursor = conn.cursor()

    try:
        # Fetch some random taxable products from barang
        cursor.execute("SELECT KODE_BRG, ACC, NAMA_BRG, HRG_BELI FROM barang WHERE PAJAK = 1 LIMIT 50")
        products = cursor.fetchall()
        if not products:
            print("No taxable products found in barang table. Fetching any products.")
            cursor.execute("SELECT KODE_BRG, ACC, NAMA_BRG, HRG_BELI FROM barang LIMIT 50")
            products = cursor.fetchall()

        if not products:
            print("Barang table is empty! Cannot inject invoices.")
            return

        total_invoices = 20
        start_date = datetime(2026, 7, 1)

        print(f"Injecting {total_invoices} invoices into {DB}.djual for July 2026...")

        for i in range(1, total_invoices + 1):
            # Random date in July 2026
            day_offset = random.randint(0, 30)
            tgl_jual = start_date + timedelta(days=day_offset)
            tgl_str = tgl_jual.strftime('%Y-%m-%d')
            tgl_short = tgl_jual.strftime('%y%m%d')

            acc = random.choice(['A1', 'A3'])
            # Generate F_JUAL like 01-260701/00001
            # We'll use random 5 digit string or just zero padded index
            f_jual = f"01-{tgl_short}/{i:05d}"

            # Random number of items in this invoice (1 to 5)
            num_items = random.randint(1, 5)

            for urutan in range(1, num_items + 1):
                prod = random.choice(products)
                kode_brg = prod[0]
                prod_acc = prod[1] if prod[1] else acc # fallback
                nama_brg = prod[2]
                hrg_beli = prod[3] if prod[3] else random.randint(10, 80) * 1000
                hrg_jual = hrg_beli * 1.2 # 20% markup

                jumlah = random.randint(1, 10)

                # INSERT INTO djual
                sql = """
                INSERT INTO djual (
                    TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_JUAL, HRG_BELI, NAMA_BRG
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                cursor.execute(sql, (
                    tgl_str, f_jual, acc, kode_brg, jumlah, hrg_jual, hrg_beli, nama_brg
                ))

        conn.commit()
        print("Successfully injected 200 mock invoices into database INVENTORY.")

    except Exception as e:
        conn.rollback()
        print(f"Error injecting invoices: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    inject_mock_invoices()
