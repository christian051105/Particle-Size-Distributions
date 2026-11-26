"""
RUN_HERE.py
=======
Entry point. Run with:  python3 RUN_HERE.py
"""
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from gsdfit.gui.app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()

    def fit_window_to_screen():
        screen = QApplication.primaryScreen().availableGeometry()

        # Let this window become smaller than the layout's preferred size.
        # Qt otherwise refuses to shrink below the QTabWidget minimum size.
        window.setMinimumSize(1, 1)

        width = min(1300, int(screen.width()*0.80))
        height = min(1000, int(screen.height()*0.80))
        width = max(1, width)
        height = max(1, height)

        window.setMaximumSize(screen.width(), screen.height())

        # setGeometry includes the OS window frame and avoids the top-left
        # centering mistake after the title bar is added by the platform.
        x = screen.x() + (screen.width() - width) // 2
        y = screen.y() + (screen.height() - height) // 2
        window.setGeometry(x, y, width, height)

    window.showNormal()
    #app.processEvents()
    fit_window_to_screen()

    # Window managers and layouts can change geometry after show()/move().
    #QTimer.singleShot(0, fit_window_to_screen)
    #QTimer.singleShot(100, fit_window_to_screen)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
