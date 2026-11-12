"""
gui/main_window.py
===================
Top-level QMainWindow: a QTabWidget with Home, Settings, Interactive,
Results, and Export tabs. The user is routed forward automatically
(Home -> Settings on file pick, Settings -> Interactive on confirm,
Interactive -> Results once all fits finish) rather than needing to
click tabs manually.
"""

from PyQt6.QtWidgets import QMainWindow, QTabWidget

from gui.app.home_tab import HomeTab
from gui.app.settings_tab import SettingsTab
from gui.app.interactive_tab import InteractiveTab
from gui.app.plot_tab import PlotTab
from gui.app.export_tab import ExportTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GSDFit")
        self.resize(1300, 1000)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.home_tab = HomeTab()
        self.settings_tab = SettingsTab()
        self.interactive_tab = InteractiveTab()
        self.plot_tab = PlotTab(self.interactive_tab)
        self.export_tab = ExportTab(self.plot_tab)

        self.tabs.addTab(self.home_tab, "Home")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.interactive_tab, "Interactive")
        self.tabs.addTab(self.plot_tab, "Results")
        self.tabs.addTab(self.export_tab, "Export Tab")

        self.home_tab.file_selected.connect(self._on_files_selected)
        self.settings_tab.settings_confirmed.connect(self._on_settings_confirmed)
        self.interactive_tab.fitting_complete.connect(self._on_fitting_complete)
        self.plot_tab.continue_to_export.connect(self._on_continue_to_export)
        self.plot_tab.go_to_next_fit.connect(self._on_next_fit)

    def _on_files_selected(self, paths):
        self.fileIndex=0
        self.nfiles = len(paths)
        self.paths = paths

        self._start_fit_process(self.fileIndex)

    def _start_fit_process(self,index):

        if index == self.nfiles-1:
            self.plot_tab.cont_button_to_export()
        
        path = self.paths[index]
        self.settings_tab.load_file(path)
        self.tabs.setCurrentWidget(self.settings_tab)

    def _on_settings_confirmed(self, dataset_label, arrays, model_keys, output_path):
        self.interactive_tab.load_settings(dataset_label, arrays, model_keys, output_path)
        self.tabs.setCurrentWidget(self.interactive_tab)

    def _on_fitting_complete(self):
        self.plot_tab.refresh()
        self.tabs.setCurrentWidget(self.plot_tab)

    def _on_next_fit(self):
        self.fileIndex += 1
        self._start_fit_process(self.fileIndex)
        self.tabs.setCurrentWidget(self.settings_tab)


    def _on_continue_to_export(self):
        self.tabs.setCurrentWidget(self.export_tab)
