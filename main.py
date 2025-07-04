import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from ui.app import MainWindow
# Removed unused imports like ccxt, ccxt.pro, asyncio, threading, pandas, etc.,
# as they are now handled within their respective modules (ui_components, data_worker)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec()) 