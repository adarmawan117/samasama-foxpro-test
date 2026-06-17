import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QTableWidget, QTableWidgetItem, QPushButton, 
                             QMessageBox, QHeaderView)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from datetime import datetime

from isi_omset import DatabaseHelper

class OmsetApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseHelper()
        self.is_edit_mode = False
        self.operator_name = "Admin" # Hardcode user for testing
        
        self.initUI()
        self.load_accounts()
        self.browse_data()
        self.reset_button_states()
        self.disable_form_inputs() # Disable inputs by default

    def initUI(self):
        self.setWindowTitle('Data Omset - Python/PyQt5 Edition')
        self.setGeometry(100, 100, 1280, 720)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Title
        title = QLabel("TABEL PROSES")
        title.setFont(QFont('Arial', 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # --- Form Inputs ---
        form_layout = QHBoxLayout()
        
        # Labels column
        label_col = QVBoxLayout()
        label_col.addWidget(QLabel("Account"))
        label_col.addWidget(QLabel("Bulan-Tahun"))
        label_col.addWidget(QLabel("Jumlah Beli"))
        label_col.addWidget(QLabel("Jumlah Jual"))
        
        # Input column
        input_col = QVBoxLayout()
        self.combo_acc = QComboBox()
        self.input_periode = QLineEdit()
        self.input_periode.setInputMask("99-9999") # MM-YYYY format
        self.input_beli = QLineEdit()
        self.input_jual = QLineEdit()
        
        input_col.addWidget(self.combo_acc)
        input_col.addWidget(self.input_periode)
        input_col.addWidget(self.input_beli)
        input_col.addWidget(self.input_jual)
        
        form_layout.addLayout(label_col)
        form_layout.addLayout(input_col)
        form_layout.addStretch() # Push inputs to the left
        
        layout.addLayout(form_layout)

        # --- Grid (TableWidget) ---
        self.grid = QTableWidget()
        self.grid.setColumnCount(14)
        self.grid.setHorizontalHeaderLabels([
            "ACC", "PERIODE", "PPN JUAL", "REAL JUAL", "RET. JUAL", "INDEX JL", "SELISIH JUAL",
            "PPN BELI", "REAL BELI", "RET. BELI", "INDEX BL", "SELISIH BELI", "OPERATOR", "TGL.UPDATE"
        ])
        header = self.grid.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.grid.setSelectionBehavior(QTableWidget.SelectRows)
        self.grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.grid.itemSelectionChanged.connect(self.on_grid_select)
        layout.addWidget(self.grid)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        
        self.btn_tambah = QPushButton("Tambah")
        self.btn_ubah = QPushButton("Ubah")
        self.btn_simpan = QPushButton("Simpan")
        self.btn_hapus = QPushButton("Hapus")
        self.btn_batal = QPushButton("Refresh/Batal")
        self.btn_close = QPushButton("Close")
        
        # Connect signals
        self.btn_tambah.clicked.connect(self.click_tambah)
        self.btn_ubah.clicked.connect(self.click_ubah)
        self.btn_simpan.clicked.connect(self.click_simpan)
        self.btn_hapus.clicked.connect(self.click_hapus)
        self.btn_batal.clicked.connect(self.click_batal)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_tambah)
        btn_layout.addWidget(self.btn_ubah)
        btn_layout.addWidget(self.btn_simpan)
        btn_layout.addWidget(self.btn_hapus)
        btn_layout.addWidget(self.btn_batal)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    # --- Methods mirroring FoxPro logic ---
    
    def enable_form_inputs(self):
        # Enable form
        self.combo_acc.setEnabled(True)
        self.input_periode.setEnabled(True)
        self.input_beli.setEnabled(True)
        self.input_jual.setEnabled(True)

    def disable_form_inputs(self):
        # Disable form
        self.combo_acc.setEnabled(False)
        self.input_periode.setEnabled(False)
        self.input_beli.setEnabled(False)
        self.input_jual.setEnabled(False)

    def clear_form_inputs(self):
        # Clear inputs
        self.input_periode.setText("")
        self.input_beli.setText("0")
        self.input_jual.setText("0")

    def reset_button_states(self):
        self.btn_tambah.setEnabled(True)
        self.btn_simpan.setEnabled(False)
        self.btn_batal.setEnabled(True)
        self.btn_hapus.setEnabled(True)
        self.btn_ubah.setEnabled(True)

    def load_accounts(self):
        self.combo_acc.clear()
        records = self.db.fetch_all("SELECT ACC FROM accinv ORDER BY ACC")
        for rec in records:
            self.combo_acc.addItem(rec['ACC'])

    def browse_data(self):
        # Fetch SETOR_PAJAK data
        query = """
        SELECT ACC, PERIODE, JUAL, REAL_JUAL, R_JUAL, P_JUAL, (REAL_JUAL - R_JUAL) as NETJUAL,
               BELI, REAL_BELI, R_BELI, P_BELI, (REAL_BELI - R_BELI) as NETBELI, OPR, DATEOPR 
        FROM SETOR_PAJAK ORDER BY PERIODE
        """
        records = self.db.fetch_all(query)
        
        self.grid.setRowCount(0)
        for row_idx, row_data in enumerate(records):
            net_jual = row_data['NETJUAL'] or 0
            jual = row_data['JUAL'] or 0
            index_jl = row_data['P_JUAL'] or 0.0
            
            net_beli = row_data['NETBELI'] or 0
            beli = row_data['BELI'] or 0
            index_bl = row_data['P_BELI'] or 0.0
            
            self.grid.insertRow(row_idx)
            self.grid.setItem(row_idx, 0, QTableWidgetItem(str(row_data['ACC'])))
            self.grid.setItem(row_idx, 1, QTableWidgetItem(str(row_data['PERIODE'])))
            self.grid.setItem(row_idx, 2, QTableWidgetItem(f"{jual:,.0f}"))
            self.grid.setItem(row_idx, 3, QTableWidgetItem(f"{row_data['REAL_JUAL']:,.0f}"))
            self.grid.setItem(row_idx, 4, QTableWidgetItem(f"{row_data['R_JUAL']:,.0f}"))
            self.grid.setItem(row_idx, 5, QTableWidgetItem(f"{index_jl:,.2f}"))
            self.grid.setItem(row_idx, 6, QTableWidgetItem(f"{net_jual:,.0f}"))
            self.grid.setItem(row_idx, 7, QTableWidgetItem(f"{beli:,.0f}"))
            self.grid.setItem(row_idx, 8, QTableWidgetItem(f"{row_data['REAL_BELI']:,.0f}"))
            self.grid.setItem(row_idx, 9, QTableWidgetItem(f"{row_data['R_BELI']:,.0f}"))
            self.grid.setItem(row_idx, 10, QTableWidgetItem(f"{index_bl:,.2f}"))
            self.grid.setItem(row_idx, 11, QTableWidgetItem(f"{net_beli:,.0f}"))
            self.grid.setItem(row_idx, 12, QTableWidgetItem(str(row_data['OPR'])))
            self.grid.setItem(row_idx, 13, QTableWidgetItem(str(row_data['DATEOPR'])))

    def populate_form_from_selection(self):
        # Fill inputs from selected grid row
        selected = self.grid.currentRow()
        if selected >= 0:
            acc = self.grid.item(selected, 0).text()
            idx = self.combo_acc.findText(acc)
            if idx >= 0:
                self.combo_acc.setCurrentIndex(idx)
            
            self.input_periode.setText(self.grid.item(selected, 1).text())
            self.input_jual.setText(self.grid.item(selected, 2).text().replace(',', ''))
            self.input_beli.setText(self.grid.item(selected, 7).text().replace(',', ''))

    def on_grid_select(self):
        if not self.is_edit_mode and not self.btn_simpan.isEnabled():
            self.populate_form_from_selection()

    def click_tambah(self):
        self.enable_form_inputs()
        self.clear_form_inputs()
        self.btn_tambah.setEnabled(False)
        self.btn_simpan.setEnabled(True)
        self.btn_batal.setEnabled(True)
        self.btn_hapus.setEnabled(False)
        self.btn_ubah.setEnabled(False)
        self.is_edit_mode = False
        self.input_periode.setFocus()

    def click_ubah(self):
        self.is_edit_mode = True
        self.populate_form_from_selection()
        self.enable_form_inputs()
        self.input_periode.setEnabled(False) # Primary key shouldn't be edited easily
        self.combo_acc.setEnabled(False)
        
        self.btn_tambah.setEnabled(False)
        self.btn_ubah.setEnabled(False)
        self.btn_simpan.setEnabled(True)
        self.btn_hapus.setEnabled(False)
        self.input_beli.setFocus()

    def click_simpan(self):
        periode_value = self.input_periode.text().strip()
        
        # Simple validation
        if not periode_value or periode_value == "-":
            QMessageBox.warning(self, "Perhatian", "Periode tidak boleh kosong!")
            return
            
        try:
            purchase_value = float(self.input_beli.text().replace(',', '') or 0)
            sales_value = float(self.input_jual.text().replace(',', '') or 0)
        except ValueError:
            QMessageBox.warning(self, "Perhatian", "Input angka tidak valid!")
            return

        current_operator = self.operator_name
        update_timestamp = datetime.now().strftime("%m/%d/%Y-%H:%M:%S")
        account_id = self.combo_acc.currentText()

        try:
            if not self.is_edit_mode:
                # Check duplicate
                exists = self.db.fetch_all("SELECT PERIODE FROM SETOR_PAJAK WHERE PERIODE=%s AND ACC=%s", (periode_value, account_id))
                if exists:
                    QMessageBox.warning(self, "Perhatian", "PERIODE tersebut sudah ada !!")
                    self.input_periode.setFocus()
                    return
                
                # Insert
                self.db.execute_query(
                    "INSERT INTO SETOR_PAJAK (PERIODE, BELI, JUAL, OPR, DATEOPR, ACC) VALUES (%s, %s, %s, %s, %s, %s)",
                    (periode_value, purchase_value, sales_value, current_operator, update_timestamp, account_id)
                )
            else:
                # Update
                self.db.execute_query(
                    "UPDATE SETOR_PAJAK SET BELI=%s, JUAL=%s, OPR=%s, DATEOPR=%s WHERE PERIODE=%s AND ACC=%s",
                    (purchase_value, sales_value, current_operator, update_timestamp, periode_value, account_id)
                )

            self.browse_data()
            self.clear_form_inputs()
            self.disable_form_inputs()
            self.reset_button_states()
            self.is_edit_mode = False

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan data!\n{str(e)}")

    def click_hapus(self):
        selected = self.grid.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Perhatian", "Pilih data yang akan dihapus!")
            return

        selected_periode = self.grid.item(selected, 1).text()
        account_id = self.grid.item(selected, 0).text()

        reply = QMessageBox.question(self, 'Perhatian', 'Yakin akan dihapus..?', 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM SETOR_PAJAK WHERE PERIODE=%s AND ACC=%s", (selected_periode, account_id))
                self.browse_data()
                self.disable_form_inputs()
                self.reset_button_states()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal menghapus data!\n{str(e)}")

    def click_batal(self):
        self.browse_data()
        self.disable_form_inputs()
        self.reset_button_states()
        self.is_edit_mode = False


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Check if pymysql is available
    try:
        import pymysql
    except ImportError:
        print("Please install required packages: pip install PyQt5 pymysql")
        sys.exit(1)
        
    ex = OmsetApp()
    ex.show()
    sys.exit(app.exec_())
