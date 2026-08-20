"""
gui/plot_tab.py
================
Shows one matplotlib panel at a time ("page"), with Prev/Next buttons
to navigate, instead of one tall scrollable figure. This sidesteps
Qt+matplotlib's unreliable interaction between QScrollArea and a
canvas that changes size at runtime, and it means each panel gets its
own clean Figure -- so a log-scale panel (power-law) can never distort
a linear-scale panel (the density bar charts) by sharing layout state.

Replaces plt.ginput()'s blocking behaviour with a mpl
'button_press_event' callback, same as before.

TWO INDEPENDENT CLICK PHASES, run in order when both apply:
  Phase "density": click 2 peaks (coarse mode, then fine mode -- order
    doesn't matter) on the combined overlay page. Fits every selected
    density model (Bi-Gaussian, Bi-Weibull, Bi-Rosin-Rammler) from
    that SAME pair of clicks.
  Phase "power_law": click 2 crossover-ish points on the power-law
    page itself. Fits Bi-power-law from its OWN pair of clicks --
    deliberately separate from the density models' clicks, since its
    starting guess is structurally different (a cumulative NUMBER
    distribution, not a mass density).
If only density models are selected, phase "power_law" is skipped.
If only power-law is selected, phase "density" is skipped and
power-law's page is immediately the click target.

Page order:
  1. Combined overlay -- all selected density models plotted together
     on one mass-density page (wt.% vs phi), since they predict the
     same quantity. This is the phase-"density" click target.
  2. One individual page per selected density model.
  3. Bi-power-law's own page (cumulative NUMBER distribution, log-y)
     -- the phase-"power_law" click target when power-law is selected.
  4. If Bi-Rosin-Rammler is selected: two more pages, the cumulative
     M(>l)/M_T survival curve vs diameter (log-x) and vs phi.

When a phase completes, navigation auto-jumps to the next relevant
click-target page so the user doesn't have to hunt for it.

Every phi-based page gets a secondary mm axis on top via
models.add_mm_twin_axis(). Because that twin axis (a twiny()) sits at
the EXACT same screen bbox as the axes it decorates, matplotlib's
click hit-testing can resolve event.inaxes to the twin instead of the
original axes -- _on_canvas_click() accounts for this by accepting
either, and always remaps through the real axes' pixel transform
(never trusts event.xdata/event.ydata directly, since the twin's own
y-range defaults to (0, 1) and would silently corrupt the y-click).
"""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from models import entropy_of_info, add_mm_twin_axis
from results_store import save_fit_result
from gui.fit_worker import FitWorker, MODEL_LABELS

CDATA = '#c0392b'
FIT_COLORS = {
    "bi_gaussian": '#2c3e50',
    "bi_weibull": '#8e44ad',
    "bi_rr": '#16a085',
}
POP_COLOR_PAIRS = {
    "bi_gaussian": ('#2980b9', '#27ae60'),
    "bi_weibull": ('#2980b9', '#27ae60'),
    "bi_rr": ('#2980b9', '#27ae60'),
}
N_CLICKS_REQUIRED = 2

FIGURE_SIZE_IN = (7.5, 5.5)   # one page, generous height for a twin axis + legend


class PlotTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataset_label = None
        self.arrays = None
        self.model_keys = []
        self.output_path = None
        self.worker = None
        self._results_by_model = {}   # model_key -> result dict (successes only)
        self._click_cid = None
        self._fit_log = []
        self._panel_specs = []        # rebuilt on every settings load / phase change
        self._page_index = 0

        # -- phase state --------------------------------------------------
        # "density": clicking the overlay page, fits Gaussian/Weibull/RR.
        # "power_law": clicking the power-law page, fits power-law alone.
        # "done": both applicable phases finished (or only one applied).
        self._phase = "density"
        self.density_clicks = []
        self.power_law_clicks = []
        self.ax_click_target = None       # axes the CURRENT phase listens on
        self.ax_click_target_twin = None  # its mm-twin-axis, if any

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.instructions_label = QLabel("")
        self.instructions_label.setWordWrap(True)
        layout.addWidget(self.instructions_label)

        # -- page navigation row -------------------------------------
        nav_row = QHBoxLayout()
        self.prev_button = QPushButton("\u2190 Previous")
        self.prev_button.clicked.connect(self._go_prev)
        nav_row.addWidget(self.prev_button)

        self.page_label = QLabel("")
        self.page_label.setStyleSheet("font-weight: bold;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self.page_label, stretch=1)

        self.next_button = QPushButton("Next \u2192")
        self.next_button.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_button)
        layout.addLayout(nav_row)

        # -- single reusable figure/canvas for whichever page is shown --
        self.figure = Figure(figsize=FIGURE_SIZE_IN)
        self.canvas = FigureCanvasQTAgg(self.figure)
        # Let the canvas shrink/grow freely with the window -- do NOT
        # pin a minimum height. 
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(200, 200)
        layout.addWidget(self.canvas, stretch=1)

        button_row = QHBoxLayout()
        self.reset_button = QPushButton("Reset Clicks")
        self.reset_button.clicked.connect(self._reset_clicks)
        button_row.addWidget(self.reset_button)

        self.save_button = QPushButton("Save All Fits to Results File")
        self.save_button.clicked.connect(self._on_save)
        self.save_button.setEnabled(False)
        button_row.addWidget(self.save_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(220)
        layout.addWidget(self.results_text)

    # ---------------------------------------------------------------
    def resizeEvent(self, event):
        """Keep the matplotlib Figure's inch size in sync with the
        canvas widget's actual pixel size, so the rendered plot always
        fills the visible area instead of being clipped when the
        widget is smaller than a hardcoded figsize."""
        super().resizeEvent(event)
        self._sync_figure_size_to_canvas()
        if self._panel_specs:
            self.canvas.draw_idle()

    def _sync_figure_size_to_canvas(self):
        w_px = max(self.canvas.width(), 1)
        h_px = max(self.canvas.height(), 1)
        dpi = self.figure.get_dpi()
        self.figure.set_size_inches(w_px / dpi, h_px / dpi, forward=False)

    # ---------------------------------------------------------------
    def load_settings(self, dataset_label, arrays, model_keys, output_path):
        """Called by main_window right after Settings are confirmed."""
        self.dataset_label = dataset_label
        self.arrays = arrays
        self.model_keys = list(model_keys)
        self.output_path = output_path
        self.density_clicks = []
        self.power_law_clicks = []
        self._results_by_model = {}
        self.results_text.clear()
        self.save_button.setEnabled(False)

        # start on whichever phase actually applies
        self._phase = "density" if self._density_models() else "power_law"

        self._panel_specs = self._build_panel_specs()
        self._page_index = self._index_of_click_target_page()
        self._draw_current_page()
        self._update_instructions()
        self._connect_click_handler()

    def _has_power_law(self):
        return "bi_power_law" in self.model_keys

    def _has_rr(self):
        return "bi_rr" in self.model_keys

    def _density_models(self):
        return [k for k in self.model_keys if k != "bi_power_law"]

    def _connect_click_handler(self):
        if self._click_cid is not None:
            self.canvas.mpl_disconnect(self._click_cid)
        self._click_cid = self.canvas.mpl_connect(
            "button_press_event", self._on_canvas_click
        )

    def _update_instructions(self):
        model_names = ", ".join(MODEL_LABELS[k] for k in self.model_keys)
        if self._phase == "density":
            phase_msg = ("Click the peak of each mode on the OVERLAY page "
                          "(2 clicks: coarse mode, then fine mode -- order doesn't matter).")
            if self._has_power_law():
                phase_msg += (" Bi-power-law needs its own 2 clicks afterward -- "
                               "you'll be moved there automatically.")
        elif self._phase == "power_law":
            phase_msg = ("Now click 2 points on the Bi-power-law page "
                          "to set ITS starting guess -- separate from the "
                          "density models' clicks.")
        else:
            phase_msg = "All fits complete. Use Previous/Next to review each page."

        self.instructions_label.setText(f"Fitting: {model_names}\n{phase_msg}")
