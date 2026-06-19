# -*- coding: utf-8 -*-
import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from adjustment_ppn_gui import ProsesAdjustmentPajakApp, AdjustmentPajakController

def global_exception_hook(exctype, value, tb):
    err_msg = ''.join(traceback.format_exception(exctype, value, tb))
    print(err_msg, file=sys.stderr)
    try:
        with open("crash_log.txt", "w") as f:
            f.write(err_msg)
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Fatal Error")
        msg_box.setText("Aplikasi berhenti secara tidak terduga!")
        msg_box.setDetailedText(err_msg)
        msg_box.exec_()
    except:
        pass
    sys.exit(1)

sys.excepthook = global_exception_hook

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Instantiate view with create_controller=False
    view = ProsesAdjustmentPajakApp(create_controller=False)
    # Instantiate controller and bind them
    controller = AdjustmentPajakController(view)
    view.controller = controller
    
    view.show()
    sys.exit(app.exec_())
