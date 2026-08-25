"""
gui/settings_tab.py
====================
Everything that used to be terminal prompts in data_loading.py, as
widgets: header-row preview/selection, column mapping (phi/size/
weight), size-unit convention, phi bin width confirmation, which
model to fit, and where to save results. One "Confirm" button builds
the clean arrays and signals main_window to open the Plot tab.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QListWidget, QComboBox, QSpinBox, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QDoubleSpinBox,
    QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal

from gui.data_prep import (
    preview_csv_lines, load_raw_table, build_arrays,
    detect_phi_bin_width, suggest_bin_width,
)
from gui.results_store import RESULTS_PATH

MODEL_CHOICES = [
    ("Bi-Gaussian", "bi_gaussian"),
    ("Bi-Length Biased Weibull", "bi_lb_weibull"),
    ("Bi-power-law", "bi_power_law"),
    ("Bi-Rosin-Rammler", "bi_rr"),
]

NONE_OPTION = "(none)"


class SettingsTab(QWidget):
    # emits (dataset_label:str, arrays:dict, model_keys:list[str], output_path:str)
    settings_confirmed = pyqtSignal(str, dict, list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.csv_path = None
        self.raw_df = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.file_label = QLabel("No file loaded yet.")
        self.file_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.file_label)

        # --- header row selection -------------------------------------
        header_box = QGroupBox("1. Confirm header row")
        header_layout = QVBoxLayout(header_box)
        header_layout.addWidget(QLabel(
            "Select the line number containing your column headers. "
            "Everything above it is skipped."
        ))
        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(160)
        self.preview_list.itemClicked.connect(self._on_preview_row_clicked)
        header_layout.addWidget(self.preview_list)

        header_row_row = QHBoxLayout()
        header_row_row.addWidget(QLabel("Header row index:"))
        self.header_row_spin = QSpinBox()
        self.header_row_spin.setRange(0, 19)
        header_row_row.addWidget(self.header_row_spin)
        self.load_columns_button = QPushButton("Load Columns")
        self.load_columns_button.clicked.connect(self._on_load_columns)
        header_row_row.addWidget(self.load_columns_button)
        header_row_row.addStretch()
        header_layout.addLayout(header_row_row)
        layout.addWidget(header_box)

        # --- column mapping ---------------------------------------------
        mapping_box = QGroupBox("2. Map columns")
        mapping_form = QFormLayout(mapping_box)
        self.size_combo = QComboBox()
        self.weight_combo = QComboBox()
        self.size_combo.currentIndexChanged.connect(self._try_suggest_bin_width)
        mapping_form.addRow("Grain size column:", self.size_combo)
 
        self.size_type_combo = QComboBox()
        self.size_type_combo.addItems(["\u03a6 (phi)", "mm", "\u00b5m"])
        self.size_type_combo.currentIndexChanged.connect(self._try_suggest_bin_width)
        mapping_form.addRow("Grain size column is in:", self.size_type_combo)
 
        mapping_form.addRow("Weight / mass column:", self.weight_combo)
        layout.addWidget(mapping_box)


        # --- bin width ---------------------------------------------------
        bin_box = QGroupBox("3. Phi bin width")
        bin_layout = QHBoxLayout(bin_box)
        bin_layout.addWidget(QLabel(
            "Needed so entropy is comparable across datasets."
        ))
        self.bin_width_spin = QDoubleSpinBox()
        self.bin_width_spin.setRange(0.05, 5.0)
        self.bin_width_spin.setSingleStep(0.05)
        self.bin_width_spin.setValue(1.0)
        bin_layout.addWidget(self.bin_width_spin)
        self.bin_width_note = QLabel("")
        self.bin_width_note.setStyleSheet("color: grey;")
        bin_layout.addWidget(self.bin_width_note)
        bin_layout.addStretch()
        layout.addWidget(bin_box)

        # --- model + output ------------------------------------------------
        model_box = QGroupBox("4. Model(s) to fit and results file")
        model_box_layout = QVBoxLayout(model_box)
        model_box_layout.addWidget(QLabel(
            "Select one or more models. All selected models are fit from "
            "the same two peak clicks on the next tab."
        ))
        self.model_checkboxes = {}
        for label, key in MODEL_CHOICES:
            cb = QCheckBox(label)
            if key == "bi_gaussian":
                cb.setChecked(True)
            self.model_checkboxes[key] = cb
            model_box_layout.addWidget(cb)

        self.power_law_note = QLabel(
            "Bi-power-law needs a physical size column (mm/\u00b5m) -- "
            "select one above, or deselect Bi-power-law."
        )
        self.power_law_note.setStyleSheet("color: #a06000;")
        self.power_law_note.setWordWrap(True)
        self.power_law_note.setVisible(False)
        model_box_layout.addWidget(self.power_law_note)

        model_form = QFormLayout()
        output_row = QHBoxLayout()
        self.output_path_edit = QLineEdit(RESULTS_PATH)
        output_row.addWidget(self.output_path_edit)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_output)
        output_row.addWidget(browse_button)
        output_container = QWidget()
        output_container.setLayout(output_row)
        model_form.addRow("Save results to:", output_container)
        model_box_layout.addLayout(model_form)
        layout.addWidget(model_box)

        # --- confirm -----------------------------------------------------
        self.confirm_button = QPushButton("Confirm and Continue to Plot \u2192")
        self.confirm_button.setMinimumHeight(40)
        self.confirm_button.clicked.connect(self._on_confirm)
        layout.addWidget(self.confirm_button)

        layout.addStretch()
        self._set_columns_enabled(False)

    # ---------------------------------------------------------------
    def _set_columns_enabled(self, enabled):
        for w in (self.size_combo, self.size_type_combo, self.weight_combo,
                   self.bin_width_spin, self.confirm_button):
            w.setEnabled(enabled)
        for cb in self.model_checkboxes.values():
            cb.setEnabled(enabled)
 

    def load_file(self, path):
        """Called by main_window when a file is selected on the Home tab."""
        self.csv_path = path
        self.raw_df = None
        self.file_label.setText(f"File: {os.path.basename(path)}  ({path})")
        self.preview_list.clear()
        try:
            lines = preview_csv_lines(path, n_preview_rows=20)
        except Exception as e:
            QMessageBox.warning(self, "Could not read file", str(e))
            return
        for i, line in enumerate(lines):
            self.preview_list.addItem(f"{i:>3}: {line}")
        self._set_columns_enabled(False)

    def _on_preview_row_clicked(self, item):
        idx = self.preview_list.row(item)
        self.header_row_spin.setValue(idx)

    def _on_load_columns(self):
        if not self.csv_path:
            QMessageBox.warning(self, "No file", "Select a CSV file first.")
            return
        header_row = self.header_row_spin.value()
        try:
            self.raw_df = load_raw_table(self.csv_path, header_row)
        except Exception as e:
            QMessageBox.warning(self, "Could not parse file",
                                 f"Failed to read the table with header row "
                                 f"{header_row}:\n{e}")
            return

        cols = list(self.raw_df.columns)
        if not cols:
            QMessageBox.warning(self, "No columns found",
                                 "That header row produced no columns. Try a different row.")
            return

        for combo in (self.size_combo, self.weight_combo):
            combo.clear()
        self.size_combo.addItems(cols)
        self.weight_combo.addItems([NONE_OPTION] + cols)

        # best-effort guesses
        guessed_phi_idx = None
        guessed_size_idx = None
        for i, c in enumerate(cols):
            lc = c.lower()
            if "weight" in lc or "wt" in lc or "mass" in lc:
                self.weight_combo.setCurrentText(c)
            if guessed_phi_idx is None and ("phi" in lc or "\u03a6" in lc):
                guessed_phi_idx = i
            if guessed_size_idx is None and (any(tok in lc for tok in ("size", "diameter", "d_mm")) or lc.strip() == "mm"):
                guessed_size_idx = i
 
        if guessed_phi_idx is not None:
            self.size_combo.setCurrentIndex(guessed_phi_idx)
            self.size_type_combo.setCurrentText("\u03a6 (phi)")
        elif guessed_size_idx is not None:
            self.size_combo.setCurrentIndex(guessed_size_idx)
            self.size_type_combo.setCurrentText("mm")
 
        self._set_columns_enabled(True)
        self._try_suggest_bin_width()


    def _try_suggest_bin_width(self):
        """Best-effort bin-width suggestion straight from the raw phi
        column, so the user gets a sensible default without needing to
        confirm first."""
        try:
            import numpy as np
            import pandas as pd
            size_col = self.size_combo.currentText()
            size_raw = pd.to_numeric(self.raw_df[size_col], errors="coerce").dropna().to_numpy()
            size_type = self._current_size_type()
            if size_type == "mm":
                with np.errstate(divide="ignore", invalid="ignore"):
                    phi_raw = -np.log2(size_raw)
            elif size_type == "\u00b5m":
                with np.errstate(divide="ignore", invalid="ignore"):
                    phi_raw = -np.log2(size_raw / 1000.0)
            else:
                phi_raw = size_raw
            phi_raw = phi_raw[np.isfinite(phi_raw)]
            self.suggest_bin_width_from_phi(phi_raw)
        except Exception:
            pass
            
    def _current_size_type(self):
        """Map the size-type combo's display text to the internal key
        used by data_prep.build_arrays."""
        text = self.size_type_combo.currentText()
        if text.startswith("\u03a6"):
            return "phi"
        return text  # "mm" or "\u00b5m"


    def _on_browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose results CSV location", self.output_path_edit.text(),
            "CSV files (*.csv)"
        )
        if path:
            self.output_path_edit.setText(path)

    def _selected_model_keys(self):
        return [key for key in self.model_checkboxes if self.model_checkboxes[key].isChecked()]

    def _on_confirm(self):
        if self.raw_df is None:
            QMessageBox.warning(self, "Not ready", "Load columns before confirming.")
            return

        size_col = self.size_combo.currentText()
        weight_col = self.weight_combo.currentText()
        weight_col = None if weight_col == NONE_OPTION else weight_col

        model_keys = self._selected_model_keys()
        if not model_keys:
            QMessageBox.warning(self, "No model selected",
                                 "Select at least one model to fit.")
            return
        if not size_col:
            QMessageBox.warning(self, "Grain size column required",
                                 "All models need a grain size column (\u03a6, mm, or \u00b5m).")
            return
        if weight_col is None:
            QMessageBox.warning(self, "Weight column required",
                                 "All models need a weight/mass column.")
            return

        mapping = {"size": size_col, "size_type": self._current_size_type(), "weight": weight_col}

        try:
            arrays = build_arrays(self.raw_df, mapping)
        except ValueError as e:
            QMessageBox.warning(self, "Could not build data", str(e))
            return

        if arrays["n_points"] == 0:
            QMessageBox.warning(self, "No valid rows",
                                 "No valid rows were found -- check your column mapping.")
            return

        arrays["phi_bin_width"] = self.bin_width_spin.value()

        dataset_label = os.path.basename(self.csv_path).rsplit(".", 1)[0]
        output_path = self.output_path_edit.text().strip() or RESULTS_PATH

        self.settings_confirmed.emit(dataset_label, arrays, model_keys, output_path)

    # called after load_columns, once we know phi values, to suggest a bin width
    def suggest_bin_width_from_phi(self, phi):
        detected = detect_phi_bin_width(phi)
        suggested = suggest_bin_width(detected)
        self.bin_width_spin.setValue(suggested)
        if detected is not None:
            self.bin_width_note.setText(f"(detected ~{detected:.3f})")
        else:
            self.bin_width_note.setText("(could not auto-detect)")
