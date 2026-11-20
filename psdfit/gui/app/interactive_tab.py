"""
gui/app/interactive_tab.py
===========================
Owns the actual click-drive fitting workflow.
Shows ONLY the pages that still need a click to complete, one at a time,
and auto-advances to the next one as soon as the current page's fit finishes.
Once every selected model has been fit (or has failed), it emits `fitting_complete` and
main_window switches to the Results tab.


TWO INDEPENDENT CLICK PHASES, run in order when each applies, plus ONE
FULLY AUTOMATIC FIT that needs no clicks at all:
  Phase "density": click 2 peaks (coarse mode, then fine mode -- order
    doesn't matter) on the combined overlay page. Fits every selected
    density model (Bi-Gaussian, Bi-Length Biased Weibull, Bi-Rosin-
    Rammler PDF) from that SAME pair of clicks.
  Phase "power_law": click 2 crossover-ish points on the power-law
    page itself. Fits Bi-power-law from its OWN pair of clicks.
  Bi-Rosin-Rammler-Cumulative (bi_rr_cdf), if selected, fits
    automatically once the click phases above finish (or immediately,
    if neither density nor power-law models are selected) -- no page
    is shown for it here; it's reviewed on the Results tab.

Every phi-based page gets a secondary mm axis on top via
models.add_mm_twin_axis(). Because that twin axis (a twiny()) sits at
the EXACT same screen bbox as the axes it decorates, matplotlib's
click hit-testing can resolve event.inaxes to the twin instead of the
original axes -- _on_canvas_click() accounts for this by accepting
either, and always remaps through the real axes' pixel transform.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from gui.models import add_mm_twin_axis
from gui.app.fit_worker import FitWorker, MODEL_LABELS

CB_color_cycle = ['#377eb8', '#ff7f00', '#4daf4a',
                  '#f781bf', '#a65628', '#984ea3',
                  '#999999', '#e41a1c', '#dede00']


class InteractiveTab(QWidget):
    # emitted once every selected model has been fit (or failed) --
    # main_window listens for this to switch to the Results tab.
    fitting_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataset_label = None
        self.arrays = None
        self.model_keys = []
        self.output_path = None
        self.worker = None
        self._results_by_model = {}   # model_key -> result dict (successes only)
        self._fit_log = []
        self._click_cid = None
        self._panel_specs = []        # rebuilt on every settings load / phase change
        self._page_index = 0
        self.compare_constant=False
        #--Plot Style parameters -----------------------------------------
        self.CDATA = '#FF7F00'
        self.FIT_COLORS = {
            "bi_gaussian": "#377eb8",
            "bi_lb_weibull": '#984ea3',
            "bi_rr_pdf": '#4daf4a',
        }
        self.POP_MARKER_PAIRS = {
            "bi_gaussian": ('dashed', 'dotted'),
            "bi_lb_weibull": ('dashed', 'dotted'),
            "bi_rr_pdf": ('dashed', 'dotted'),
        }
        self.N_CLICKS_REQUIRED = 2

        self.FIGURE_SIZE_IN = (7.5, 5.5)

        # -- phase state --------------------------------------------------
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

        self.page_label = QLabel("")
        self.page_label.setStyleSheet("font-weight: bold;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.page_label)

        # -- single reusable figure/canvas for whichever click-target
        # page is currently showing --
        self.figure = Figure(figsize=self.FIGURE_SIZE_IN)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(200, 200)
        layout.addWidget(self.canvas, stretch=1)

        button_row = QHBoxLayout()
        self.reset_button = QPushButton("Reset Clicks")
        self.reset_button.clicked.connect(self._reset_clicks)
        button_row.addWidget(self.reset_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(140)
        layout.addWidget(self.results_text)

    # ---------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_figure_size_to_canvas()
        if self._panel_specs:
            self.canvas.draw_idle()

    def _sync_figure_size_to_canvas(self):
        dpr = self.canvas.devicePixelRatioF()
        w_px = max(self.canvas.width(), 1)
        h_px = max(self.canvas.height(), 1)
        FIXED_DPI = 100.0
        target_dpi = FIXED_DPI * dpr
        if self.figure.get_dpi() != target_dpi:
            self.figure.set_dpi(target_dpi)
        self.figure.set_size_inches(w_px / FIXED_DPI, h_px / FIXED_DPI, forward=False)

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
        self._fit_log = []
        self.results_text.clear()

        self._phase = self._first_applicable_phase()

        self._panel_specs = self._build_panel_specs()
        self._page_index = 0
        self._draw_current_page()
        self._update_instructions()
        self._connect_click_handler()

        # bi_rr_cdf needs no clicks -- if there's no click-driven phase
        # ahead of it, fit it immediately.
        if self._phase == "done" and self._has_rr_cdf():
            self._run_auto_rr_cdf_fit()
        elif self._phase == "done":
            self._finish_all_fits()

    def _has_power_law(self):
        return "bi_power_law" in self.model_keys

    def _has_rr_cdf(self):
        return "bi_rr_cdf" in self.model_keys

    def _density_models(self):
        return [k for k in self.model_keys if k not in ("bi_power_law", "bi_rr_cdf")]

    def _first_applicable_phase(self):
        if self._density_models():
            return "density"
        if self._has_power_law():
            return "power_law"
        return "done"

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
            if self._has_rr_cdf():
                phase_msg += (" Bi-Rosin-Rammler Cumulative fits automatically -- "
                               "no clicks needed for it.")
        elif self._phase == "power_law":
            phase_msg = ("Now click 2 points on the Bi-power-law page "
                          "to set ITS starting guess -- separate from the "
                          "density models' clicks.")
            if self._has_rr_cdf():
                phase_msg += (" Bi-Rosin-Rammler Cumulative fits automatically "
                               "once this is done -- no clicks needed for it.")
        else:
            phase_msg = "All fits complete. Moving to the Results tab..."

        self.instructions_label.setText(f"Fitting: {model_names}\n{phase_msg}")

    # ---------------------------------------------------------------
    # Panel plan:
    # ---------------------------------------------------------------
    def _build_panel_specs(self):
        specs = []
        if self._density_models():
            specs.append({"kind": "overlay", "model_keys": self._density_models(),
                           "is_click_target": self._phase == "density"})
        if self._has_power_law():
            specs.append({"kind": "power_law",
                           "is_click_target": self._phase == "power_law"})
        return specs

    def _page_title_for(self, spec):
        kind = spec["kind"]
        if kind == "overlay":
            return "Overlay (all density models)"
        if kind == "power_law":
            return "Bi-power-law"
        return kind

    # ---------------------------------------------------------------
    def _draw_current_page(self):
        """Draws whichever page is the CURRENT click target. Since
        this tab only ever shows one relevant page per phase, there's
        no Prev/Next here -- advancing pages happens automatically as
        phases complete."""
        if not self._panel_specs:
            self.figure.clear()
            self._sync_figure_size_to_canvas()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No click-driven models selected.",
                    ha='center', va='center')
            self.canvas.draw()
            self.canvas.repaint()
            self.page_label.setText("")
            return

        self._page_index = max(0, min(self._page_index, len(self._panel_specs) - 1))
        spec = self._panel_specs[self._page_index]

        for ax in self.figure.axes:
            ax.set_yscale('linear')
        self.figure.clear()

        self._sync_figure_size_to_canvas()
        ax = self.figure.add_subplot(111)

        self.ax_click_target = None
        self.ax_click_target_twin = None

        phi = self.arrays["phi"]
        weight_pct = self.arrays["weight_pct"]
        kind = spec["kind"]
        is_target = spec.get("is_click_target", False)

        if kind == "overlay":
            density_keys_done = [k for k in self._density_models() if k in self._results_by_model]
            title = f"{self.dataset_label} -- ALL SELECTED PDF MODELS"
            if is_target:
                title += " (click the peaks to set starting guess)"
            twin = self._render_density_panel(ax, phi, weight_pct, density_keys_done,
                                               title=title, is_overlay=True)
            if is_target:
                self.ax_click_target = ax
                self.ax_click_target_twin = twin

            if self.density_clicks:
                clicks = np.array(self.density_clicks)
                cx = clicks[:, 0]
                cy = clicks[:, 1]
                ax.plot(cx, cy, 'x', color='black', markersize=10,
                        markeredgewidth=2, zorder=5, label="Clicked peak positions")

            ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1.0),
                      borderaxespad=0.0)

        elif kind == "power_law":
            twin = self._render_power_law_panel(
                ax, self._results_by_model.get("bi_power_law"),
                is_click_target=is_target,
            )
            if is_target:
                self.ax_click_target = ax
                self.ax_click_target_twin = twin
            for cx, cy in self.power_law_clicks:
                ax.plot(cx, cy, 'x', color='black', markersize=10,
                        markeredgewidth=2, zorder=5)

        legend = ax.get_legend()
        is_outside_legend = (
            kind == "overlay" and legend is not None
            and legend._bbox_to_anchor is not None
        )

        if is_outside_legend:
            self.figure.subplots_adjust(top=0.85, bottom=0.09, left=0.09, right=0.98)
            self.canvas.draw()

            renderer = self.canvas.get_renderer()
            legend_bbox_px = legend.get_window_extent(renderer)
            fig_w_px = self.figure.get_size_inches()[0] * self.figure.get_dpi()
            legend_w_frac = legend_bbox_px.width / fig_w_px
            right_margin = max(0.68, 1.0 - legend_w_frac - 0.04)
            self.figure.subplots_adjust(right=right_margin)
        else:
            self.figure.subplots_adjust(top=0.85, bottom=0.09, left=0.09, right=0.97)

        self.canvas.draw()
        self.canvas.repaint()

        n = len(self._panel_specs)
        self.page_label.setText(f"{self._page_title_for(spec)}  (page {self._page_index + 1} / {n})")

    def _reset_clicks(self):
        self.density_clicks = []
        self.power_law_clicks = []
        self._results_by_model = {}
        self._fit_log = []
        self.results_text.clear()
        self._phase = self._first_applicable_phase()
        self._panel_specs = self._build_panel_specs()
        self._page_index = 0
        self._draw_current_page()
        self._update_instructions()
        self._connect_click_handler()

        if self._phase == "done" and self._has_rr_cdf():
            self._run_auto_rr_cdf_fit()
        elif self._phase == "done":
            self._finish_all_fits()

    # ---------------------------------------------------------------
    def _current_clicks(self):
        if self._phase == "density":
            return self.density_clicks
        return self.power_law_clicks

    def _on_canvas_click(self, event):
        if self.ax_click_target is None or event.xdata is None:
            return
        if event.inaxes not in (self.ax_click_target, self.ax_click_target_twin):
            return

        inv = self.ax_click_target.transData.inverted()
        x_data, y_data = inv.transform((event.x, event.y))

        clicks = self._current_clicks()
        clicks.append((x_data, y_data))
        self.ax_click_target.plot(x_data, y_data, 'x', color='black',
                                   markersize=10, markeredgewidth=2, zorder=5)
        self.canvas.draw()

        if len(clicks) >= self.N_CLICKS_REQUIRED:
            self._run_current_phase_fit()

    # ---------------------------------------------------------------
    def _run_current_phase_fit(self):
        if self._click_cid is not None:
            self.canvas.mpl_disconnect(self._click_cid)
            self._click_cid = None

        if self._phase == "density":
            phase_models = self._density_models()
            clicks = self.density_clicks
        else:
            phase_models = ["bi_power_law"]
            clicks = self.power_law_clicks
            if self.compare_constant:
                phase_models.append("cd_bi_power")

        prior_text = self.results_text.toPlainText()
        self.results_text.setPlainText((prior_text + "\n\n" if prior_text else "") + "Fitting...")
        self.worker = FitWorker(phase_models, self.arrays, clicks)
        self.worker.model_done.connect(self._on_model_done)
        self.worker.model_failed.connect(self._on_model_failed)
        self.worker.all_finished.connect(self._on_phase_finished)
        self.worker.start()

    def _on_model_done(self, model_key, result):
        self._results_by_model[model_key] = result
        self._fit_log.append(result["summary_text"])

    def _on_model_failed(self, model_key, message):
        label = MODEL_LABELS.get(model_key, model_key)
        self._fit_log.append(f"{label.upper()} FIT FAILED\n  {message}")

    def _on_phase_finished(self):
        self.results_text.setPlainText("\n\n".join(self._fit_log))

        # advance to the next click-driven phase, if any -- this is
        # the "auto-advance to the next relevant page" behaviour.
        if self._phase == "density":
            self._phase = "power_law" if self._has_power_law() else "done"
        else:  # was "power_law"
            self._phase = "done"

        self._panel_specs = self._build_panel_specs()
        self._page_index = len(self._panel_specs) - 1 if self._panel_specs else 0
        self._draw_current_page()
        self._update_instructions()

        if self._phase == "power_law":
            self._connect_click_handler()
        elif self._phase == "done":
            if self._has_rr_cdf():
                self._run_auto_rr_cdf_fit()
            else:
                self._finish_all_fits()

    # ---------------------------------------------------------------
    def _run_auto_rr_cdf_fit(self):
        prior_text = self.results_text.toPlainText()
        self.results_text.setPlainText(
            (prior_text + "\n\n" if prior_text else "") + "Fitting Bi-Rosin-Rammler Cumulative automatically...")

        self._auto_worker = FitWorker(["bi_rr_cdf"], self.arrays, clicks=[])
        self._auto_worker.model_done.connect(self._on_model_done)
        self._auto_worker.model_failed.connect(self._on_model_failed)
        self._auto_worker.all_finished.connect(self._on_auto_rr_cdf_finished)
        self._auto_worker.start()

    def _on_auto_rr_cdf_finished(self):
        self.results_text.setPlainText("\n\n".join(self._fit_log))
        self._finish_all_fits()

    def _finish_all_fits(self):
        if self._results_by_model:
            self.fitting_complete.emit()
        else:
            QMessageBox.warning(self, "All fits failed",
                                 "None of the selected models converged. "
                                 "Try Reset Clicks and click closer to each "
                                 "mode's true peak.")

    # ---------------------------------------------------------------
    def _render_density_panel(self, ax, phi, weight_pct, model_keys_to_plot, title, is_overlay=False):
        bar_width = 0.90 * self.arrays.get("phi_bin_width", 1.0)
        ax.bar(phi, weight_pct, width=bar_width, color=self.CDATA, alpha=0.55,
               edgecolor='grey', linewidth=0.5, label='Data')
        ax.set_xlabel(r'Grain size ($\phi$)')
        ax.set_ylabel('Mass (wt.%)')
        ax.set_title(title, fontsize=10, fontweight='bold', pad=32)
        ax.set_xlim(phi.min() - 1, phi.max() + 1)
        ax.set_ylim(0, weight_pct.max() * 1.35)
        ax.grid(alpha=0.3)

        for model_key in model_keys_to_plot:
            result = self._results_by_model[model_key]
            color = self.FIT_COLORS.get(model_key, '#2c3e50')
            pop1_ls, pop2_ls = self.POP_MARKER_PAIRS.get(model_key)
            phi_smooth = result["phi_smooth"]
            ax.plot(phi_smooth, result["y_total"], color=color, lw=2.0,
                    label=result.get("total_label", MODEL_LABELS[model_key]))
            if "y_pop1" in result:
                ax.plot(phi_smooth, result["y_pop1"], color=color, lw=1.50,
                        ls=pop1_ls, alpha=0.7, label=result.get("pop1_label", "Pop. 1"))
            if "y_pop2" in result:
                ax.plot(phi_smooth, result["y_pop2"], color=color, lw=1.50,
                        ls=pop2_ls, alpha=0.7, label=result.get("pop2_label", "Pop. 2"))

        twin = add_mm_twin_axis(ax)

        if not is_overlay:
            ax.legend(fontsize=7, loc='upper left', framealpha=0.85)
        return twin

    def _render_power_law_panel(self, ax, result, is_click_target=False):
        ax.set_xlabel(r'Grain size ($\phi$)')
        ax.set_ylabel(r'$N(\leq\phi)/N_0$')
        title = 'Bi-power-law'
        if is_click_target:
            title += ' -- click crossover(s) (change of direction) to set starting guess'
        ax.set_title(title, fontsize=10, fontweight='bold', pad=32)
        phi = self.arrays["phi"]
        ax.set_xlim(phi.min() - 4, phi.max() + 4)
        ax.grid(alpha=0.3, which='both')

        if result is not None:
            cum = result["cumulative_data"]
            ax.semilogy(cum["phi"], cum["N_cum"], 'ok', markersize=5,
                        label='Data', zorder=4)
            ax.semilogy(result["phi_smooth"], result["y_total"],
                        '-', color='crimson', lw=2,
                        label=result.get("total_label", "Bi-power-law fit"))

            params = result.get("params", {})
            lambda_f = params.get("lambda_f")
            lambda_c = params.get("lambda_c")
            D_f = params.get("Df")
            D_c = params.get("Dc")

            if lambda_f is not None:
                ax.axvline(lambda_f, color='#2980b9', lw=1.3, ls='--',
                           zorder=3, label=f'λ$_f$ (fine crossover) = {lambda_f:.2f} $\\phi$')
            if lambda_c is not None:
                ax.axvline(lambda_c, color='#27ae60', lw=1.3, ls='--',
                           zorder=3, label=f'λ$_c$ (coarse crossover) = {lambda_c:.2f} $\\phi$')
            if D_f and D_c is not None:
                D_str = f"$D_f$ = {D_f:.3f}, $D_c$={D_c:.3f}"
                ax.plot([], [], ' ', label=D_str)

            ax.legend(fontsize=7, loc='lower left', framealpha=0.85)
        else:
            weight_pct = self.arrays["weight_pct"]
            size_mm = self.arrays.get("size_mm")
            density = self.arrays.get("density",[1.0])

            num_raw_cd = weight_pct / (1*(size_mm ** 3))

            if size_mm is not None:
                with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                    num_raw = weight_pct / (density*(size_mm ** 3))
                num_raw = np.nan_to_num(num_raw, nan=0.0, posinf=0.0, neginf=0.0)

                order = np.argsort(phi)
                phi_sorted = phi[order]
                num_sorted = num_raw[order]
                total = num_sorted.sum()
                if total > 0:
                    N_cum = np.cumsum(num_sorted) / total
                    N_cum_cd = np.cumsum(num_raw_cd[order]) / num_raw_cd.sum()
                    mask = N_cum > 0
                    ax.semilogy(phi_sorted[mask], N_cum[mask], 'ok',
                                markersize=5, label='Data', zorder=4)
                    if self.compare_constant:
                        ax.semilogy(phi_sorted[mask], N_cum_cd[mask], 'ob',
                                                        markersize=5, label='Data', zorder=4)
                    ax.legend(fontsize=7, loc='lower left', framealpha=0.85)
            else:
                ax.text(0.5, 0.5, "No size column mapped -- cannot preview data",
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=9, color='grey')

        ax.invert_xaxis()
        return add_mm_twin_axis(ax)
