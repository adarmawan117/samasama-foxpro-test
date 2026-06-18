# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QMessageBox, QDateEdit, QFormLayout, QProgressBar, 
                             QListWidget, QLineEdit, QFileDialog, QGroupBox, QMenu)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont, QDoubleValidator

class ProsesAdjustmentPajakApp(QMainWindow):
    # Custom signals for MVC communication
    browse_source_clicked = pyqtSignal()
    browse_target_clicked = pyqtSignal()
    test_conn_clicked = pyqtSignal()
    proses_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    def __init__(self, create_controller=True):
        super().__init__()
        self.log_records = []
        self.consent_clone = False
        self._process_running = False
        self.worker = None
        self.clone_worker = None
        self.conn_worker = None
        
        self.initUI()
        
        if create_controller:
            from .controller import AdjustmentPajakController
            self.controller = AdjustmentPajakController(self)
        else:
            self.controller = None

    def initUI(self):
        self.setWindowTitle('PPN Tax Adjustment Tool')
        self.setGeometry(200, 200, 850, 600)

        main_widget = QWidget()
        self.CentralWidget = main_widget
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Title Label
        title = QLabel("PPN Tax Adjustment Tool")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        db_layout = QHBoxLayout()

        # Group 1: Source Database
        source_group = QGroupBox("Source Database (Original)")
        source_group_layout = QFormLayout(source_group)
        
        self.source_host_input = QLineEdit("localhost")
        self.source_host_input.setObjectName("source_host_input")
        source_group_layout.addRow("Host:", self.source_host_input)
        
        self.source_port_input = QLineEdit("3306")
        self.source_port_input.setObjectName("source_port_input")
        source_group_layout.addRow("Port:", self.source_port_input)
        
        self.source_user_input = QLineEdit("root")
        self.source_user_input.setObjectName("source_user_input")
        source_group_layout.addRow("User:", self.source_user_input)
        
        self.source_pass_input = QLineEdit("root")
        self.source_pass_input.setObjectName("source_pass_input")
        self.source_pass_input.setEchoMode(QLineEdit.Password)
        source_group_layout.addRow("Password:", self.source_pass_input)
        
        source_db_layout = QHBoxLayout()
        self.source_db_input = QLineEdit("source_db")
        self.source_db_input.setObjectName("source_db_input")
        self.db_path_input = self.source_db_input # Compatibility alias
        
        self.btn_browse_source = QPushButton("Browse...")
        self.btn_browse_source.setObjectName("btn_browse_source")
        self.btn_browse = self.btn_browse_source # Compatibility alias
        
        source_db_layout.addWidget(self.source_db_input)
        source_db_layout.addWidget(self.btn_browse_source)
        source_group_layout.addRow("Database Name / Path:", source_db_layout)
        
        db_layout.addWidget(source_group)

        # Group 2: Target Database
        target_group = QGroupBox("Target Database (Pajak)")
        target_group_layout = QFormLayout(target_group)
        
        self.target_host_input = QLineEdit("localhost")
        self.target_host_input.setObjectName("target_host_input")
        target_group_layout.addRow("Host:", self.target_host_input)
        
        self.target_port_input = QLineEdit("3306")
        self.target_port_input.setObjectName("target_port_input")
        target_group_layout.addRow("Port:", self.target_port_input)
        
        self.target_user_input = QLineEdit("root")
        self.target_user_input.setObjectName("target_user_input")
        target_group_layout.addRow("User:", self.target_user_input)
        
        self.target_pass_input = QLineEdit("root")
        self.target_pass_input.setObjectName("target_pass_input")
        self.target_pass_input.setEchoMode(QLineEdit.Password)
        target_group_layout.addRow("Password:", self.target_pass_input)
        
        target_db_layout = QHBoxLayout()
        self.target_db_input = QLineEdit("target_db")
        self.target_db_input.setObjectName("target_db_input")
        
        self.btn_browse_target = QPushButton("Browse...")
        self.btn_browse_target.setObjectName("btn_browse_target")
        
        target_db_layout.addWidget(self.target_db_input)
        target_db_layout.addWidget(self.btn_browse_target)
        target_group_layout.addRow("Database Name / Path:", target_db_layout)
        
        db_layout.addWidget(target_group)
        layout.addLayout(db_layout)

        # Test Connection Button
        self.btn_test_conn = QPushButton("Test Connection")
        self.btn_test_conn.setObjectName("btn_test_conn")
        layout.addWidget(self.btn_test_conn)

        # Options Layout
        options_layout = QFormLayout()

        # Account Selection QComboBox
        self.combo_acc = QComboBox()
        self.combo_acc.setObjectName("combo_acc")
        self.combo_acc.addItem("Select Account...", "")
        self.combo_acc.setEnabled(False)
        options_layout.addRow("Account Code:", self.combo_acc)

        # Date range inputs
        self.tgl_awal = QDateEdit()
        self.tgl_awal.setObjectName("tgl_awal")
        self.tgl_awal.setCalendarPopup(True)
        self.tgl_awal.setDisplayFormat("yyyy-MM-dd")
        self.tgl_awal.setDate(QDate(2026, 6, 1))
        self.tgl_awal.setEnabled(False)

        self.tgl_akhir = QDateEdit()
        self.tgl_akhir.setObjectName("tgl_akhir")
        self.tgl_akhir.setCalendarPopup(True)
        self.tgl_akhir.setDisplayFormat("yyyy-MM-dd")
        self.tgl_akhir.setDate(QDate(2026, 6, 30))
        self.tgl_akhir.setEnabled(False)

        options_layout.addRow("Start Date:", self.tgl_awal)
        options_layout.addRow("End Date:", self.tgl_akhir)

        # Target PPN Input
        self.target_ppn_input = QLineEdit()
        self.target_ppn_input.setObjectName("target_ppn_input")
        # Allow negative/positive floating values
        self.target_ppn_input.setValidator(QDoubleValidator(-999999999.0, 999999999.0, 2, self))
        self.target_ppn_input.setEnabled(False)
        options_layout.addRow("Target PPN Adjustment:", self.target_ppn_input)

        layout.addLayout(options_layout)

        # Log status widget
        self.log_widget = QListWidget()
        self.log_widget.setObjectName("log_widget")
        self.log_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_widget.customContextMenuRequested.connect(self.show_log_context_menu)
        layout.addWidget(self.log_widget)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_proses = QPushButton("Proses")
        self.btn_proses.setObjectName("btn_proses")
        self.btn_proses.setEnabled(False)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setEnabled(False)

        btn_layout.addWidget(self.btn_proses)
        btn_layout.addWidget(self.btn_export)
        layout.addLayout(btn_layout)

        # Connect button clicks to emit custom signals
        self.btn_browse_source.clicked.connect(self.browse_source_clicked.emit)
        self.btn_browse_target.clicked.connect(self.browse_target_clicked.emit)
        self.btn_test_conn.clicked.connect(self.test_conn_clicked.emit)
        self.btn_proses.clicked.connect(self.proses_clicked.emit)
        self.btn_export.clicked.connect(self.export_clicked.emit)

    # Getters
    def get_source_db(self) -> str:
        return self.source_db_input.text()

    def get_target_db(self) -> str:
        return self.target_db_input.text()

    def get_selected_account(self) -> str:
        return self.combo_acc.itemData(self.combo_acc.currentIndex())

    def get_start_date(self) -> str:
        return self.tgl_awal.date().toString("yyyy-MM-dd")

    def get_end_date(self) -> str:
        return self.tgl_akhir.date().toString("yyyy-MM-dd")

    def get_target_ppn(self) -> str:
        return self.target_ppn_input.text()

    # Setters/Mutators
    def set_source_db(self, path: str):
        self.source_db_input.setText(path)

    def set_target_db(self, path: str):
        self.target_db_input.setText(path)

    def set_inputs_enabled(self, enabled: bool):
        self.source_host_input.setEnabled(enabled)
        self.source_port_input.setEnabled(enabled)
        self.source_user_input.setEnabled(enabled)
        self.source_pass_input.setEnabled(enabled)
        self.source_db_input.setEnabled(enabled)
        self.btn_browse_source.setEnabled(enabled)
        
        self.target_host_input.setEnabled(enabled)
        self.target_port_input.setEnabled(enabled)
        self.target_user_input.setEnabled(enabled)
        self.target_pass_input.setEnabled(enabled)
        self.target_db_input.setEnabled(enabled)
        self.btn_browse_target.setEnabled(enabled)
        
        self.btn_test_conn.setEnabled(enabled)
        self.combo_acc.setEnabled(enabled)
        self.tgl_awal.setEnabled(enabled)
        self.tgl_akhir.setEnabled(enabled)
        self.target_ppn_input.setEnabled(enabled)
        self.btn_proses.setEnabled(enabled)
        self.btn_export.setEnabled(enabled if not enabled else len(self.log_records) > 0)

    def set_export_enabled(self, enabled: bool):
        self.btn_export.setEnabled(enabled)

    def set_proses_enabled(self, enabled: bool):
        self.btn_proses.setEnabled(enabled)

    def clear_log(self):
        self.log_widget.clear()

    def log_status(self, message: str):
        self.log_widget.addItem(message)
        self.log_widget.scrollToBottom()

    def set_process_running(self, running: bool):
        self._process_running = running

    def is_process_running(self) -> bool:
        if self._process_running:
            return True
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            return True
        if hasattr(self, 'clone_worker') and self.clone_worker and self.clone_worker.isRunning():
            return True
        if hasattr(self, 'conn_worker') and self.conn_worker and self.conn_worker.isRunning():
            return True
        return False

    # Wrappers for Dialogs
    def show_info_message(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def show_critical_message(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def show_warning_message(self, title: str, message: str):
        QMessageBox.warning(self, title, message)

    def show_question_message(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def get_open_file_name(self, title: str, filter_str: str) -> str:
        file_name, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
        return file_name

    def get_save_file_name(self, title: str, default_filename: str, filter_str: str) -> str:
        file_name, _ = QFileDialog.getSaveFileName(self, title, default_filename, filter_str)
        return file_name

    def show_log_context_menu(self, position):
        menu = QMenu()
        copy_action = menu.addAction("Copy Selected")
        copy_all_action = menu.addAction("Copy All")
        
        action = menu.exec_(self.log_widget.mapToGlobal(position))
        
        if action == copy_action:
            selected_items = self.log_widget.selectedItems()
            if selected_items:
                text = "\n".join([item.text() for item in selected_items])
                QApplication.clipboard().setText(text)
        elif action == copy_all_action:
            text = "\n".join([self.log_widget.item(i).text() for i in range(self.log_widget.count())])
            QApplication.clipboard().setText(text)

    # Delegating methods for backward compatibility in unit tests
    def on_test_conn_db_not_found(self, err_msg):
        if self.controller:
            self.controller.on_test_conn_db_not_found(err_msg)

    def on_test_conn_finished(self, success, err_msg):
        if self.controller:
            self.controller.on_test_conn_finished(success, err_msg)

    def on_rerun_warning(self, msg, data):
        if self.controller:
            self.controller.on_rerun_warning(msg, data)

    def on_db_not_found(self, err_msg, target_config):
        if self.controller:
            self.controller.on_db_not_found(err_msg, target_config)

    def on_clone_finished(self, success, message):
        if self.controller:
            self.controller.on_clone_finished(success, message)

    def on_finished(self, success, final_gap, logs):
        if self.controller:
            self.controller.on_finished(success, final_gap, logs)

    def on_error(self, err_msg):
        if self.controller:
            self.controller.on_error(err_msg)

    def browse_source_db(self):
        if self.controller:
            self.controller.browse_source_db()

    def browse_target_db(self):
        if self.controller:
            self.controller.browse_target_db()

    def click_test_conn(self):
        if self.controller:
            self.controller.click_test_conn()

    def click_proses(self):
        if self.controller:
            self.controller.click_proses()

    def click_export(self):
        if self.controller:
            self.controller.click_export()

    def load_accounts(self):
        if self.controller:
            self.controller.load_accounts()

    def closeEvent(self, event):
        if self.is_process_running():
            self.show_warning_message("Warning", "Proses penyesuaian sedang berjalan. Harap tunggu hingga selesai.")
            event.ignore()
        else:
            event.accept()
