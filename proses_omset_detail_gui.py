import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QMessageBox, QDateEdit, QFormLayout, QProgressBar, QListWidget)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from proses_omset_detail import ProsesOmsetLogic

class WorkerThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    error_signal = pyqtSignal(str)

    def __init__(self, logic, tgl1, tgl2, acc_data):
        super().__init__()
        self.logic = logic
        self.tgl1 = tgl1
        self.tgl2 = tgl2
        self.acc_data = acc_data

    def run(self):
        try:
            success = self.logic.proses_omset(
                self.tgl1, self.tgl2, self.acc_data, "System", 
                progress_callback=self.emit_progress
            )
            self.finished_signal.emit(success)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_signal.emit(str(e))

    def emit_progress(self, msg):
        self.progress_signal.emit(msg)

class ProsesOmsetApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logic = ProsesOmsetLogic()
        self.initUI()
        self.load_accounts()

    def initUI(self):
        self.setWindowTitle('Proses Data Omset - PPN Breakdown')
        self.setGeometry(200, 200, 500, 350)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Title
        title = QLabel("Proses Data Omset")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Form Layout
        form_layout = QFormLayout()
        
        self.combo_acc = QComboBox()
        self.combo_acc.addItem("SEMUA ACC", "") # Default empty string for all ACC
        
        self.tgl_awal = QDateEdit(QDate(QDate.currentDate().year(), 6, 1))
        self.tgl_awal.setCalendarPopup(True)
        self.tgl_awal.setDisplayFormat("yyyy-MM-dd")

        self.tgl_akhir = QDateEdit(QDate.currentDate())
        self.tgl_akhir.setCalendarPopup(True)
        self.tgl_akhir.setDisplayFormat("yyyy-MM-dd")

        form_layout.addRow("Account:", self.combo_acc)
        form_layout.addRow("Tanggal Awal:", self.tgl_awal)
        form_layout.addRow("Tanggal Akhir:", self.tgl_akhir)
        
        layout.addLayout(form_layout)

        # Status Log
        self.list_status = QListWidget()
        layout.addWidget(self.list_status)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_proses = QPushButton("Proses")
        self.btn_batal = QPushButton("Batal")
        
        self.btn_proses.clicked.connect(self.click_proses)
        self.btn_batal.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_proses)
        btn_layout.addWidget(self.btn_batal)
        
        layout.addLayout(btn_layout)

    def set_inputs_enabled(self, enabled):
        self.btn_proses.setEnabled(enabled)
        self.btn_batal.setEnabled(enabled)
        self.combo_acc.setEnabled(enabled)
        self.tgl_awal.setEnabled(enabled)
        self.tgl_akhir.setEnabled(enabled)

    def load_accounts(self):
        records = self.logic.fetch_all("SELECT ACC, NAMA_ACC FROM accinv ORDER BY ACC")
        for rec in records:
            self.combo_acc.addItem(f"{rec['ACC']} - {rec['NAMA_ACC']}", rec['ACC'])

    def log_status(self, message):
        self.list_status.addItem(message)
        self.list_status.scrollToBottom()

    def click_proses(self):
        reply = QMessageBox.question(self, 'Perhatian', "Yakin akan diproses sekarang?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.set_inputs_enabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Indeterminate mode
            self.list_status.clear()

            # Fetch Inputs
            acc_data = self.combo_acc.currentData() # returns "" if "SEMUA ACC"
            tgl1 = self.tgl_awal.date().toString("yyyy-MM-dd")
            tgl2 = self.tgl_akhir.date().toString("yyyy-MM-dd")

            # Start Worker Thread
            self.worker = WorkerThread(self.logic, tgl1, tgl2, acc_data)
            self.worker.progress_signal.connect(self.log_status)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.error_signal.connect(self.on_error)
            self.worker.start()

    def on_finished(self, success):
        self.set_inputs_enabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        
        if success:
            QMessageBox.information(self, "Sukses", "Proses kalkulasi dan rekapitulasi data omset selesai!")
        self.progress_bar.setVisible(False)

    def on_error(self, err_msg):
        self.set_inputs_enabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Terjadi kesalahan saat pemrosesan:\n{err_msg}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    try:
        import pymysql
    except ImportError:
        print("Please install required packages: pip install PyQt5 pymysql")
        sys.exit(1)
        
    ex = ProsesOmsetApp()
    ex.show()
    sys.exit(app.exec_())
