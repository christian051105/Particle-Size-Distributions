import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal


class ResultTab(QWidget);
    def init(self):
        super().__init__(self)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)