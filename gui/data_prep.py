"""
data_prep.py
============
These functions take arguments and return values or raise exceptions,
so Settings tab widgets can drive them directly.
"""

import numpy as np
import pandas as pd


def preview_csv_lines(path, n_preview_rows=20):
    """Return the first n_preview_rows non-empty raw lines of a file, for display
    in a list/table widget so the user can pick the header row."""
    lines = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            cleaned = line.rstrip("\n")
            if cleaned.strip():
                lines.append(cleaned)
            if len(lines) >= n_preview_rows:
                break
    return lines


def load_raw_table(path, header_row):
    """Read the CSV using the user-confirmed header row index."""
    df = pd.read_csv(path, skiprows=header_row, header=0)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed")]
    return df


def detect_phi_bin_width(phi):
    """Auto-detect the phi sampling interval via the median gap between
    consecutive sorted phi values. Returns None if not enough points."""
    phi = np.asarray(phi, dtype=float)
    phi = np.sort(phi[~np.isnan(phi)])
    if len(phi) < 2:
        return None
    gaps = np.diff(phi)
    gaps = gaps[gaps > 1e-9]
    if len(gaps) == 0:
        return None
    return float(np.median(gaps))


def suggest_bin_width(detected_width):
    """Snap a detected width to the nearest common value, for
    pre-selecting a sensible default in a Settings tab widget."""
    common_widths = [0.25, 0.5, 1.0, 2.0]
    if detected_width is None:
        return 1.0
    return min(common_widths, key=lambda w: abs(w - detected_width))


def build_arrays(df, mapping, conventions=None, phi_bin_width=None):
    """
    Turn a column-mapping dict into clean numpy arrays.
    Returns dict with keys: phi, size_mm, weight_pct, phi_bin_width, density.
    phi_bin_width: if None, detected from the edges and snapped to a common
    value; Settings passes the user-confirmed value to override it.
    """
    size_col = mapping["size"]
    size_type = mapping.get("size_type", "phi")
    size_raw = pd.to_numeric(df[size_col], errors="coerce").to_numpy(dtype=float)

    if size_type == "phi":
        phi_edge = size_raw
    elif size_type == "mm":
        with np.errstate(divide="ignore", invalid="ignore"):
            phi_edge = -np.log2(size_raw)
    elif size_type == "\u00b5m":
        with np.errstate(divide="ignore", invalid="ignore"):
            phi_edge = -np.log2(size_raw / 1000.0)
    else:
        raise ValueError(f"Unknown size_type '{size_type}'.")

    # weights
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

    # density: always an array the same length as the table, so the
    # validity mask and sort below apply to it like every other column
    density_header = mapping.get("density")
    if density_header in (None, "Constant"):
        density = np.ones(len(df))
    else:
        density = pd.to_numeric(df[density_header], errors="coerce").to_numpy(dtype=float)

    # drop invalid rows BEFORE anything else
    valid = np.isfinite(phi_edge)
    phi_edge = phi_edge[valid]
    density = density[valid]
    if weight_pct is not None:
        weight_pct = weight_pct[valid]

    order = np.argsort(phi_edge)
    phi_edge = phi_edge[order]
    density = density[order]
    if weight_pct is not None:
        weight_pct = weight_pct[order]

    # bin width from the EDGES, then use it for the edge -> centre shift
    if phi_bin_width is None:
        phi_bin_width = suggest_bin_width(detect_phi_bin_width(phi_edge))

    phi = phi_edge - phi_bin_width / 2.0
    size_mm = 2.0 ** (-phi)

    return {
        "phi": phi, "size_mm": size_mm, "weight_pct": weight_pct,
        "phi_bin_width": phi_bin_width, "density": density,
        "n_points": len(phi),
    }
