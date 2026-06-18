# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication
from adjustment_ppn_gui import ProsesAdjustmentPajakApp, AdjustmentPajakController

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Instantiate view with create_controller=False
    view = ProsesAdjustmentPajakApp(create_controller=False)
    # Instantiate controller and bind them
    controller = AdjustmentPajakController(view)
    view.controller = controller
    
    view.show()
    sys.exit(app.exec_())
