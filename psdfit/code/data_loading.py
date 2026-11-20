"""
data_loading.py
================
Building-block functions for getting a user's grain-size CSV -- from
anywhere on their computer, in any column layout -- into clean numpy
arrays (phi, size_mm, weight_pct).
"""

import glob
import os
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Small terminal-prompt helpers
# ---------------------------------------------------------------------

def _prompt_choice(prompt_text, options, default_index=0):
    """
    Print a numbered list of options and ask the user to pick one by
    number. Returns the chosen option's VALUE (not its label) if
    options are (label, value) tuples, else the chosen string itself.
    Pressing Enter with no input accepts default_index.
    """
    print(f"\n{prompt_text}")
    for i, opt in enumerate(options):
        label = opt[0] if isinstance(opt, tuple) else str(opt)
        marker = " (default)" if i == default_index else ""
        print(f"  [{i}] {label}{marker}")

    while True:
        raw = input(f"Enter a number [0-{len(options) - 1}], "
                     f"or press Enter for default: ").strip()
        if raw == "":
            chosen = options[default_index]
            break
        try:
            idx = int(raw)
            if 0 <= idx < len(options):
                chosen = options[idx]
                break
        except ValueError:
            pass
        print(f"  Please enter a number between 0 and {len(options) - 1}.")

    return chosen[1] if isinstance(chosen, tuple) else chosen


def _prompt_int(prompt_text, default=0, min_value=0, max_value=None):
    """Ask for an integer, with a default if the user just presses Enter."""
    while True:
        suffix = f" (0-{max_value})" if max_value is not None else ""
        raw = input(f"{prompt_text}{suffix} [default {default}]: ").strip()
        if raw == "":
            return default
        try:
            val = int(raw)
            if val < min_value or (max_value is not None and val > max_value):
                print(f"  Please enter a value between {min_value} and {max_value}.")
                continue
            return val
        except ValueError:
            print("  Please enter a whole number.")


# ---------------------------------------------------------------------
# Step 1: let the user pick a CSV from ANYWHERE on their computer
# ---------------------------------------------------------------------
#
# Two ways to get a path, tried in order of convenience:
#   1. A native OS "Open File" dialog (works whenever a display is
#      available) via tkinter, which ships with standard Python -- no
#      extra install needed.
#   2. If that's not available (e.g. a headless/remote terminal), a
#      typed-path prompt, with a numbered list of any CSVs sitting in
#      the current folder offered as a shortcut.

def _try_native_file_dialog():
    """
    Attempt to open a native OS file-picker dialog via tkinter.
    Returns the chosen path (str) or None if unavailable/cancelled/failed.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Select your grain-size CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


def pick_csv_path(pattern="*.csv"):
    """
    Let the user choose a CSV from anywhere on their computer.
    """
    native_path = _try_native_file_dialog()
    if native_path:
        print(f"Selected file: {native_path}")
        return native_path

    print("A native file browser wasn't available in this environment "
          "(common on remote/headless terminals).")

    local_files = sorted(glob.glob(pattern))
    if local_files:
        options = [(f, f) for f in local_files] + [("Type a path manually", None)]
        choice = _prompt_choice(
            "Choose a CSV file already in this folder, or type a path:",
            options, default_index=0,
        )
        if choice is not None:
            print(f"Selected file: {choice}")
            return choice

    while True:
        path = input("Enter the full path to your CSV file: ").strip().strip('"').strip("'")
        if path and os.path.isfile(path):
            print(f"Selected file: {path}")
            return path
        print(f"  Could not find a file at '{path}'. Try again.")


def preview_csv(path, n_preview_rows=15):
    """
    Show the raw, un-parsed top of the file so the user can see for
    themselves where the real header row and data start.
    """
    with open(path, "r", errors="replace") as f:
        lines = [next(f, "") for _ in range(n_preview_rows)]
    print(f"--- First {n_preview_rows} raw lines of {path} ---")
    for i, line in enumerate(lines):
        print(f"{i:>3}: {line.rstrip()}")
    print("---")
    return lines


def pick_header_row(path, n_preview_rows=15, default=0):
    """
    Let the user tell us which raw line number is the actual column
    header row (0-indexed). Everything above it gets skipped on load.
    Returns the chosen row number (int).
    """
    preview_csv(path, n_preview_rows=n_preview_rows)
    return _prompt_int(
        "Which line number above is the column header row?",
        default=default, min_value=0, max_value=n_preview_rows - 1,
    )


# ---------------------------------------------------------------------
# Step 2: column mapping — user tells us which column is which
# ---------------------------------------------------------------------

def load_raw_table(path, header_row):
    """Read the CSV using the user-confirmed header row index."""
    df = pd.read_csv(path, skiprows=header_row, header=0)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    return df


def pick_column_mapping(df, need_size=True, need_weight=True):
    """
    Ask the user, via terminal prompts, which real column names map
    onto the roles a model needs: phi, (optionally) a physical size
    column, and (optionally) a weight/mass column.

    Returns a dict of chosen column names (str), keyed by role.
    A role that the user leaves as "(none)" maps to None.
    """
    cols = list(df.columns)
    none_opt = "(none)"
    options_other = [none_opt] + cols

    print("\nPreview of loaded columns:")
    print(df.head().to_string())

    mapping = {}

    mapping["phi"] = _prompt_choice(
        "Which column is Φ (phi)?", [(c, c) for c in cols], default_index=0,
    )

    if need_size:
        size_options = [(c, c) for c in options_other]
        chosen = _prompt_choice(
            "Which column is physical size (mm/µm), if present?",
            size_options, default_index=0,
        )
        mapping["size"] = None if chosen == none_opt else chosen

    if need_weight:
        weight_options = [(c, c) for c in options_other]
        chosen = _prompt_choice(
            "Which column is weight/mass?",
            weight_options, default_index=0,
        )
        mapping["weight"] = None if chosen == none_opt else chosen

    return mapping


def pick_conventions():
    """
    Ask the user, via terminal prompts, to confirm the conventions
    their data follows: what unit the size column is in (if provided).

    Phi values are always assumed to already be bin centres.
    """
    size_unit = _prompt_choice(
        "Size column unit:",
        [("mm", "mm"), ("µm", "µm"), ("already in phi units", "already in phi units")],
        default_index=0,
    )
    return {"size_unit": size_unit}


# ---------------------------------------------------------------------
# Step 3: build clean arrays from the user's mapping + conventions
# ---------------------------------------------------------------------

def build_arrays(df, mapping, conventions=None, weight_is_pct=True):
    """
    Turn the user's column-mapping choices into clean numpy arrays.
    """
    phi_col = mapping["phi"]
    phi_raw = pd.to_numeric(df[phi_col], errors="coerce").to_numpy(dtype=float)
    phi = phi_raw - 0.5

    size_mm = None
    if mapping.get("size") is not None:
        size_col = mapping["size"]
        size_raw = pd.to_numeric(df[size_col], errors="coerce").to_numpy(dtype=float)
        unit = conventions["size_unit"] if conventions is not None else "mm"
        if unit == "mm":
            size_mm = size_raw
        elif unit == "µm":
            size_mm = size_raw / 1000.0
        elif unit == "already in phi units":
            size_mm = 2.0 ** (-size_raw)

    weight_pct = None
    if mapping.get("weight") is not None:
        weight_col = mapping["weight"]
        w_raw = pd.to_numeric(df[weight_col], errors="coerce").to_numpy(dtype=float)
        w_raw = np.nan_to_num(w_raw, nan=0.0)
        total = w_raw.sum()
        if total <= 0:
            raise ValueError(
                f"Weight column '{weight_col}' sums to zero or less; "
                "check the column mapping."
            )
        weight_pct = w_raw / total * 100.0

    valid = ~np.isnan(phi)
    phi = phi[valid]
    if size_mm is not None:
        size_mm = size_mm[valid]
    if weight_pct is not None:
        weight_pct = weight_pct[valid]

    order = np.argsort(phi)
    phi = phi[order]
    if size_mm is not None:
        size_mm = size_mm[order]
    if weight_pct is not None:
        weight_pct = weight_pct[order]

    if len(phi):
        print(f"Loaded {len(phi)} valid points. "
              f"Phi range [{phi.min():.2f}, {phi.max():.2f}]")
    else:
        print("No valid rows found -- check your column mapping.")

    phi_bin_width = detect_phi_bin_width(phi)

    return {
        "phi": phi, "size_mm": size_mm, "weight_pct": weight_pct,
        "phi_bin_width": phi_bin_width,
    }


def detect_phi_bin_width(phi):
    """
    Auto-detect the phi sampling interval from the data itself (e.g.
    1.0 for whole-phi steps, 0.5 for half-phi steps), using the median
    gap between consecutive sorted phi values.
    """
    phi = np.asarray(phi, dtype=float)
    phi = np.sort(phi[~np.isnan(phi)])
    if len(phi) < 2:
        return None
    gaps = np.diff(phi)
    gaps = gaps[gaps > 1e-9]  # drop exact duplicates
    if len(gaps) == 0:
        return None
    return float(np.median(gaps))


def confirm_phi_bin_width(detected_width):
    """
    Show the auto-detected phi bin width and let the user confirm or
    override it via a terminal prompt. 
    """
    if detected_width is None:
        print("\nCould not auto-detect the phi sampling interval "
              "(not enough points).")
        default = 1.0
    else:
        # snap to the nearest common interval for a friendlier default
        common_widths = [0.25, 0.5, 1.0, 2.0]
        default = min(common_widths, key=lambda w: abs(w - detected_width))
        print(f"\nDetected phi sampling interval: ~{detected_width:.3f} "
              f"(closest common value: {default})")

    options = [
        (f"{w} phi" + (" (detected)" if detected_width is not None
                        and abs(w - default) < 1e-9 else ""), w)
        for w in [0.25, 0.5, 1.0, 2.0]
    ] + [("Other (type a custom value)", None)]

    default_index = next(
        (i for i, (_, w) in enumerate(options) if w == default), 0
    )
    chosen = _prompt_choice(
        "Confirm the phi bin width for this dataset "
        "(needed so entropy is comparable across datasets):",
        options, default_index=default_index,
    )

    if chosen is None:
        while True:
            raw = input("Enter the phi bin width as a number "
                         "(e.g. 0.5): ").strip()
            try:
                chosen = float(raw)
                if chosen > 0:
                    break
            except ValueError:
                pass
            print("  Please enter a positive number.")

    print(f"Using phi bin width = {chosen}")
    return chosen
