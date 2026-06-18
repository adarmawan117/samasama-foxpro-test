# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication
from adjustment_ppn_gui import ProsesAdjustmentPajakApp

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ProsesAdjustmentPajakApp()
    ex.show()
    sys.exit(app.exec_())
