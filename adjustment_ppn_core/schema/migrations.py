import traceback
import logging

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