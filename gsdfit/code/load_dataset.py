"""
load_dataset.py
================
The single entry point scripts use to load a user's grain-size CSV.
This is the file that "asks the user all the info" -- scripts just
create a DatasetLoader and call .load(), which walks the user through
file selection, header confirmation, column mapping, and convention
confirmation via terminal prompts, then returns clean numpy arrays.
"""

from gsdfit.code.data_loading import (
    pick_csv_path,
    pick_header_row,
    load_raw_table,
    pick_column_mapping,
    pick_conventions,
    build_arrays,
    confirm_phi_bin_width,
)


class DatasetLoader:
    """
    Stateful helper that walks a terminal user through picking a CSV,
    confirming its header row, mapping its columns, and confirming
    its unit/phi conventions -- then returns clean numpy arrays.

    Call .load() for the whole flow in one go, or call the individual
    step methods yourself if you want to interleave other logic.
    """

    def __init__(self, need_size=False, need_weight=True):
        self.need_size = need_size
        self.need_weight = need_weight

        self.path = None
        self.header_row = None
        self.raw_df = None
        self.dataset_label = None
        self._mapping = None
        self._conventions = None
        self.data = None

    # -- Step 1 ----------------------------------------------------------
    def pick_file(self, pattern="*.csv"):
        """Prompt the user to choose a CSV (native dialog or typed path)."""
        self.path = pick_csv_path(pattern=pattern)
        return self.path

    # -- Step 2 ------------------------------------------------------------
    def confirm_header(self, n_preview_rows=15, default=0):
        """Preview the raw file and let the user confirm the header row.
        (Phi values are always treated as bin centers -- no shift is asked.)"""
        if not self.path:
            raise RuntimeError(
                "No file selected yet -- call pick_file() before this."
            )
        self.header_row = pick_header_row(
            self.path, n_preview_rows=n_preview_rows, default=default
        )
        return self.header_row

    # -- Step 3 ------------------------------------------------------------
    def map_columns(self):
        """Load the table with the confirmed header row, then prompt for
        column mapping and unit/convention choices."""
        self.dataset_label = (
            self.path.split("/")[-1].split("\\")[-1].rsplit(".", 1)[0]
        )
        self.raw_df = load_raw_table(self.path, self.header_row)
        self._mapping = pick_column_mapping(
            self.raw_df, need_size=self.need_size, need_weight=self.need_weight
        )
        self._conventions = pick_conventions()
        return self._mapping, self._conventions

    # -- Step 4 ------------------------------------------------------------
    def finalize(self):
        """Build and return the clean arrays once all selections are made."""
        self.data = build_arrays(
            self.raw_df, self._mapping, self._conventions, weight_is_pct=True
        )
        if self.need_size and self.data["size_mm"] is None:
            raise ValueError(
                "This script needs a physical size column (mm or \u00b5m) "
                "-- re-run and select one during column mapping."
            )
        if self.need_weight and self.data["weight_pct"] is None:
            raise ValueError(
                "No weight column was selected -- re-run and select one "
                "during column mapping."
            )
        # Confirm the phi sampling interval (e.g. 1.0 vs 0.5 phi) so
        # entropy is computed consistently and stays comparable across
        # datasets that were measured at different resolutions.
        self.data["phi_bin_width"] = confirm_phi_bin_width(
            self.data.get("phi_bin_width")
        )
        return self.data

    # -- Convenience: run the whole flow in one call ------------------------
    def load(self, pattern="*.csv", n_preview_rows=15, default_header=0):
        """
        Run the full pick -> confirm header -> map columns -> finalize
        flow in one blocking call. Returns the same dict as finalize().
        """
        self.pick_file(pattern=pattern)
        self.confirm_header(n_preview_rows=n_preview_rows, default=default_header)
        self.map_columns()
        return self.finalize()
