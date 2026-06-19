import pymysql
import sys
from datetime import datetime

from db_config import DBConfig

class ProsesOmsetLogic:
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = pymysql.connect(
                host=DBConfig.HOST,
                user=DBConfig.USER,
                password=DBConfig.PASSWORD,
                database=DBConfig.NAME,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.create_detail_table_if_not_exists()
        except Exception as e:
            print(f"Error connecting to MySQL: {e}\nPastikan database 'INVENTORY' sudah dibuat.")
            sys.exit(1)

    def create_detail_table_if_not_exists(self):
        cursor = self.connection.cursor()
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

    def fetch_all(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def execute_query(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def proses_omset(self, tgl1, tgl2, acc, operator_name="System", progress_callback=None):
        dateopr = datetime.now().strftime("%m/%d/%Y-%H:%M:%S")

        def log_progress(msg):
            if progress_callback:
                progress_callback(msg)

        log_progress(f"Memulai kalkulasi omset dari {tgl1} s/d {tgl2}...")

        # Helper method for bulk calculation
        def calculate_and_upsert(source_table, target_column, is_beli=False):
            # Tentukan kolom harga (HRG_JUAL atau HRG_BELI) dan kolom pajak (F_PPN atau PPN)
            hrg_col = "HRG_BELI" if is_beli else "HRG_JUAL"
            ppn_col = "PPN" if is_beli else "F_PPN"
            
            # Base query
            query = f"""
            SELECT 
                DATE_FORMAT(d.TGL_{'BELI' if is_beli else 'JUAL'}, '%%m-%%Y') AS bulantahun,
                d.ACC,
                CASE 
                    WHEN b.PAJAK IN (1, 3) THEN 'PPN (PPN + Gung gung)'
                    WHEN b.PAJAK = 2 THEN 'BTKP'
                    ELSE 'Lain-lain' 
                END AS JENIS_PPN,
                SUM((d.JUMLAH*d.{hrg_col}*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH)) AS TOT,
                SUM(((d.JUMLAH*d.{hrg_col}*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH)) * (d.{ppn_col}/100)) AS TOT_PPN
            FROM {source_table} d
            LEFT JOIN BARANG b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
            WHERE d.TGL_{'BELI' if is_beli else 'JUAL'} BETWEEN %s AND %s
            """
            params = [tgl1, tgl2]
            
            if acc:
                query += " AND d.ACC = %s "
                params.append(acc)
                
            query += " GROUP BY bulantahun, d.ACC, JENIS_PPN"

            results = self.fetch_all(query, tuple(params))
            
            ppn_dict = {}
            for row in results:
                periode = str(row['bulantahun']).strip() if row['bulantahun'] else ''
                acc_code = str(row['ACC']).strip() if row['ACC'] else ''
                jenis_ppn = str(row['JENIS_PPN']).strip() if row['JENIS_PPN'] else ''
                tot = row['TOT'] or 0
                tot_ppn = row['TOT_PPN'] or 0
                
                # Simpan nilai PPN ke dalam dictionary untuk kalkulasi Step 5
                ppn_dict[(periode, acc_code, jenis_ppn)] = tot_ppn

                # Upsert ke SETOR_PAJAK_DETAIL
                upsert_query = f"""
                INSERT INTO SETOR_PAJAK_DETAIL 
                    (PERIODE, ACC, JENIS_PPN, {target_column}, OPR, DATEOPR)
                VALUES 
                    (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    {target_column} = VALUES({target_column}),
                    OPR = VALUES(OPR),
                    DATEOPR = VALUES(DATEOPR)
                """
                val = (periode, acc_code, jenis_ppn, tot, operator_name, dateopr)
                self.execute_query(upsert_query, val)
                
            return ppn_dict

        # 1. JUAL
        log_progress("Menghitung data Penjualan (DJUAL)...")
        ppn_djual = calculate_and_upsert("DJUAL", "REAL_JUAL", is_beli=False)
        # 2. RETUR JUAL
        log_progress("Menghitung data Retur Penjualan (DRJUAL)...")
        ppn_drjual = calculate_and_upsert("DRJUAL", "R_JUAL", is_beli=False)
        # 3. BELI
        log_progress("Menghitung data Pembelian (DBELI)...")
        ppn_dbeli = calculate_and_upsert("DBELI", "REAL_BELI", is_beli=True)
        # 4. RETUR BELI
        log_progress("Menghitung data Retur Pembelian (DRBELI)...")
        ppn_drbeli = calculate_and_upsert("DRBELI", "R_BELI", is_beli=True)

        # 5. KALKULASI P_JUAL & P_BELI (Presentase)
        log_progress("Mengkalkulasi persentase (P_JUAL & P_BELI) akhir...")
        calc_query = "SELECT * FROM SETOR_PAJAK_DETAIL"
        calc_params = []
        if acc:
            calc_query += " WHERE ACC = %s"
            calc_params.append(acc)
            
        rows = self.fetch_all(calc_query, tuple(calc_params))
        for r in rows:
            net_jual = (r['REAL_JUAL'] or 0) - (r['R_JUAL'] or 0)
            net_beli = (r['REAL_BELI'] or 0) - (r['R_BELI'] or 0)
            
            p_strip = str(r['PERIODE']).strip() if r['PERIODE'] else ''
            a_strip = str(r['ACC']).strip() if r['ACC'] else ''
            j_strip = str(r['JENIS_PPN']).strip() if r['JENIS_PPN'] else ''
            
            key = (p_strip, a_strip, j_strip)
            p_jual = ppn_djual.get(key, 0) - ppn_drjual.get(key, 0)
            p_beli = ppn_dbeli.get(key, 0) - ppn_drbeli.get(key, 0)
            
            update_query = """
            UPDATE SETOR_PAJAK_DETAIL 
            SET JUAL = %s, BELI = %s, P_JUAL = %s, P_BELI = %s 
            WHERE PERIODE = %s AND ACC = %s AND JENIS_PPN = %s
            """
            self.execute_query(update_query, (net_jual, net_beli, p_jual, p_beli, r['PERIODE'], r['ACC'], r['JENIS_PPN']))

        return True
