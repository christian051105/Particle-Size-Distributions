# gui/app/settings_tab.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal

class SettingsTab(QWidget):
    settings_confirmed = pyqtSignal()  # add args here if main_window expects data, e.g. pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
