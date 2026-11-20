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

Page order:
  1. Combined overlay -- all selected density models plotted together
     on one mass-density page (wt.% vs phi), since they predict the
     same quantity. This is the phase-"density" click target.
  2. One individual page per selected density model.
  3. Bi-power-law's own page (cumulative NUMBER distribution, log-y)
     -- the phase-"power_law" click target when power-law is selected.
  4. Bi-Rosin-Rammler-Cumulative's own page (M(>l)/M_T survival curve)
     -- pure review page, never a click target, since it fits itself
     automatically.

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
from PyQt6.QtCore import Qt, pyqtSignal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from psdfit.gui.models import entropy_of_info, add_mm_twin_axis
from psdfit.gui.results_store import save_fit_result
from psdfit.gui.app.fit_worker import MODEL_LABELS


class PlotTab(QWidget):
    continue_to_export = pyqtSignal()
    go_to_next_fit = pyqtSignal()

    def __init__(self, interactive_tab, parent=None):
        super().__init__(parent)
        # Reference to the live InteractiveTab instance -- all fit
        # state (arrays, results, dataset_label, output_path) is read
        # from it on demand, never duplicated here.
        self.interactive_tab = interactive_tab

        self._panel_specs = []
        self._page_index = 0

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
        self.FIGURE_SIZE_IN = (7.5, 5.5)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("<h3>Results</h3>")
        layout.addWidget(header)

        nav_row = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self._go_prev)
        nav_row.addWidget(self.prev_button)

        self.page_label = QLabel("")
        self.page_label.setStyleSheet("font-weight: bold;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self.page_label, stretch=1)

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_button)
        layout.addLayout(nav_row)

        self.figure = Figure(figsize=self.FIGURE_SIZE_IN)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(200, 200)
        layout.addWidget(self.canvas, stretch=1)

        button_row = QHBoxLayout()
        self.save_button = QPushButton("Save All Fits to Results File")
        self.save_button.clicked.connect(self._on_save)
        button_row.addWidget(self.save_button)
        button_row.addStretch()

        self.continue_button = QPushButton("Fit next file →")
        self.continue_button.clicked.connect(self.go_to_next_fit.emit)
        button_row.addWidget(self.continue_button)
        layout.addLayout(button_row)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(160)
        layout.addWidget(self.results_text)

    # ---------------------------------------------------------------
    def cont_button_to_export(self):
        # Change the visible label to indicate exporting to data export
        # and rewire the click handler to emit the `continue_to_export` signal.
        self.continue_button.setText("Continue to Data Export")
        try:
            # disconnect any existing clicked handlers to avoid duplicate actions
            self.continue_button.clicked.disconnect()
        except Exception:
            pass
        self.continue_button.clicked.connect(self.continue_to_export.emit)

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
    def refresh(self):
        """Called by main_window when InteractiveTab.fitting_complete
        fires. Rebuilds the full page list from whatever's in
        interactive_tab now and jumps to the first page."""
        it = self.interactive_tab
        self.results_text.setPlainText("\n\n".join(it._fit_log))
        self._panel_specs = self._build_panel_specs()
        self._page_index = 0
        self._draw_current_page()

    def _density_models(self):
        it = self.interactive_tab
        return [k for k in it.model_keys if k not in ("bi_power_law", "bi_rr_cdf")]

    def _build_panel_specs(self):
        it = self.interactive_tab
        specs = []
        density_keys = self._density_models()

        if density_keys:
            specs.append({"kind": "overlay", "model_keys": density_keys})
        for key in density_keys:
            specs.append({"kind": "density_single", "model_key": key})
        if "bi_power_law" in it.model_keys:
            specs.append({"kind": "power_law"})
        if "bi_rr_cdf" in it.model_keys:
            specs.append({"kind": "rr_cumulative"})

        return specs

    def _page_title_for(self, spec):
        kind = spec["kind"]
        if kind == "overlay":
            return "Overlay (all density models)"
        if kind == "density_single":
            return MODEL_LABELS.get(spec["model_key"], spec["model_key"])
        if kind == "power_law":
            return "Bi-power-law"
        if kind == "rr_cumulative":
            return "Bi-Rosin-Rammler (Cumulative Bi-Weibull) (mm + Φ)"
        return kind

    # ---------------------------------------------------------------
    def _go_prev(self):
        if self._page_index > 0:
            self._page_index -= 1
            self._draw_current_page()

    def _go_next(self):
        if self._page_index < len(self._panel_specs) - 1:
            self._page_index += 1
            self._draw_current_page()

    # ---------------------------------------------------------------
    def _draw_current_page(self):
        it = self.interactive_tab

        if not self._panel_specs or it.arrays is None:
            self.figure.clear()
            self._sync_figure_size_to_canvas()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No results yet.", ha='center', va='center')
            self.canvas.draw()
            self.canvas.repaint()
            self.page_label.setText("")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        self._page_index = max(0, min(self._page_index, len(self._panel_specs) - 1))
        spec = self._panel_specs[self._page_index]

        for ax in self.figure.axes:
            ax.set_yscale('linear')
        self.figure.clear()

        self._sync_figure_size_to_canvas()
        ax = self.figure.add_subplot(111)

        phi = it.arrays["phi"]
        weight_pct = it.arrays["weight_pct"]
        kind = spec["kind"]

        if kind == "overlay":
            density_keys_done = [k for k in self._density_models() if k in it._results_by_model]
            title = f"{it.dataset_label} -- ALL SELECTED PDF MODELS"
            self._render_density_panel(ax, it, phi, weight_pct, density_keys_done,
                                        title=title, is_overlay=True)
            if it.density_clicks:
                clicks = np.array(it.density_clicks)
                ax.plot(clicks[:, 0], clicks[:, 1], 'x', color='black', markersize=10,
                        markeredgewidth=2, zorder=5, label="Clicked peak positions")
            ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1.0),
                      borderaxespad=0.0)

        elif kind == "density_single":
            key = spec["model_key"]
            keys_here = [key] if key in it._results_by_model else []
            label = MODEL_LABELS.get(key, key)
            self._render_density_panel(ax, it, phi, weight_pct, keys_here, title=label)

        elif kind == "power_law":
            self._render_power_law_panel(ax, it, it._results_by_model)
            for cx, cy in it.power_law_clicks:
                ax.plot(cx, cy, 'x', color='black', markersize=10,
                        markeredgewidth=2, zorder=5)

        elif kind == "rr_cumulative":
            self._render_rr_cumulative(ax, it, it._results_by_model.get("bi_rr_cdf"))

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
        self.page_label.setText(f"Page {self._page_index + 1} / {n}  --  {self._page_title_for(spec)}")
        self.prev_button.setEnabled(self._page_index > 0)
        self.next_button.setEnabled(self._page_index < n - 1)

    # ---------------------------------------------------------------
    def _render_density_panel(self, ax, it, phi, weight_pct, model_keys_to_plot, title, is_overlay=False):
        bar_width = 0.90 * it.arrays.get("phi_bin_width", 1.0)
        ax.bar(phi, weight_pct, width=bar_width, color=self.CDATA, alpha=0.55,
               edgecolor='grey', linewidth=0.5, label='Data')
        ax.set_xlabel(r'Grain size ($\phi$)')
        ax.set_ylabel('Mass (wt.%)')
        ax.set_title(title, fontsize=10, fontweight='bold', pad=32)
        ax.set_xlim(phi.min() - 1, phi.max() + 1)
        ax.set_ylim(0, weight_pct.max() * 1.35)
        ax.grid(alpha=0.3)

        for model_key in model_keys_to_plot:
            result = it._results_by_model[model_key]
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

    def _render_power_law_panel(self, ax, it, results):
        result = results.get("bi_power_law")
        ax.set_xlabel(r'Grain size ($\phi$)')
        ax.set_ylabel(r'$N(\leq\phi)/N_0$')
        ax.set_title('Bi-power-law', fontsize=10, fontweight='bold', pad=32)
        phi = it.arrays["phi"]
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


            cd = results.get("cd_bi_power",None)
            if cd is not None:
                ax.semilogy(cd["cumulative_data"]["phi"], cd["cumulative_data"]["N_cum"], 'ob', markersize=5,
                            label='Constant Density Data', zorder=4)
                ax.semilogy(cd["phi_smooth"], cd["y_total"],'-', color='blue', lw=2,
                            label="Constant Density Fit")
            ax.legend(fontsize=7, loc='lower left', framealpha=0.85)
        else:
            ax.text(0.5, 0.5, "No fit yet.", ha='center', va='center',
                    transform=ax.transAxes, fontsize=9, color='grey')

        ax.invert_xaxis()
        return add_mm_twin_axis(ax)

    def _render_rr_cumulative(self, ax, it, result):
        ax.set_xlabel(r'Grain size ($\phi$)')
        ax.set_ylabel(r'$M(>l)/M_T$')
        ax.set_title('Bi-Rosin-Rammler (Cumulative)', fontsize=10, fontweight='bold', pad=32)
        ax.grid(alpha=0.3, which='both')
        if result is not None and "rr_cumulative" in result:
            cum = result["rr_cumulative"]
            params = result.get("params", {})
            ax.plot(cum["phi_data_sorted"], cum["M_gt_l_data"], 'o', color='k',
                    markersize=5, label='Data (empirical)', zorder=5)
            fit_label = (
                "Bi-Rosin-Rammler (fitted cumulative)\n"
                f"$d'_c$={params.get('sigma_coarse_mm', float('nan')):.3g} mm, "
                f"$k_c$={params.get('k_coarse', float('nan')):.2f}\n"
                f"$d'_f$={params.get('sigma_fine_mm', float('nan')):.3g} mm, "
                f"$k_f$={params.get('k_fine', float('nan')):.2f}"
            )
            ax.plot(cum["phi_fit_sorted"], cum["M_gt_l_fit"], '-', color='crimson',
                    lw=2, label=fit_label)
            ax.legend(fontsize=7, loc='upper right', framealpha=0.85)
        else:
            phi = it.arrays["phi"]
            weight_pct = it.arrays["weight_pct"]
            order = np.argsort(phi)
            phi_sorted = phi[order]
            mass_frac_sorted = weight_pct[order] / weight_pct.sum()
            M_gt_l_data = 1.0 - np.cumsum(mass_frac_sorted)
            M_gt_l_data = np.concatenate(([1.0], M_gt_l_data[:-1]))
            ax.plot(phi_sorted, M_gt_l_data, 'o', color='k',
                    markersize=5, label='Data (empirical)', zorder=5)
            ax.legend(fontsize=7, loc='upper right', framealpha=0.85)
            ax.set_xlim(phi.min() - 1, phi.max() + 1)
        return add_mm_twin_axis(ax)

    # ---------------------------------------------------------------
    def _on_save(self):
        it = self.interactive_tab
        if not it._results_by_model:
            return
        mass_frac = it.arrays["weight_pct"] / it.arrays["weight_pct"].sum()
        H, H_norm = entropy_of_info(mass_frac, bin_width=it.arrays["phi_bin_width"])

        saved, failed = [], []
        for model_key, result in it._results_by_model.items():
            try:
                save_fit_result(
                    dataset=it.dataset_label,
                    model=model_key,
                    params=result["params"],
                    rmse=result.get("rmse"),
                    entropy_bits=H,
                    entropy_norm=H_norm,
                    phi_bin_width=it.arrays["phi_bin_width"],
                    path=it.output_path,
                )
                saved.append(MODEL_LABELS.get(model_key, model_key))
            except Exception as e:
                failed.append(f"{MODEL_LABELS.get(model_key, model_key)}: {e}")

        msg = ""
        if saved:
            msg += f"Saved: {', '.join(saved)}\n\nFile: {it.output_path}"
        if failed:
            msg += "\n\nFailed to save:\n" + "\n".join(failed)
        QMessageBox.information(self, "Save results", msg or "Nothing was saved.")
