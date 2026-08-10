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
import ipywidgets as widgets
from IPython.display import display
 
 
# ---------------------------------------------------------------------
# Step 1: let the user pick a CSV from ANYWHERE on their computer
# ---------------------------------------------------------------------

class CSVSelection:
    """
    Holds the result of whichever picking method the user used.
    Read .value after the user has made a selection (and, for the
    upload widget, after the upload has completed) -- same interface
    as reading .value on an ipywidgets.Dropdown.
    """
    def __init__(self):
        self.path = None
        self._upload_widget = None
 
    @property
    def value(self):
        if self._upload_widget is not None and len(self._upload_widget.value) > 0:
            return self._resolve_uploaded_path()
        return self.path
 
    def _resolve_uploaded_path(self):
        uploaded = self._upload_widget.value
        item = list(uploaded.values())[0] if isinstance(uploaded, dict) else uploaded[0]
        name = item["metadata"]["name"] if isinstance(uploaded, dict) else item["name"]
        content = item["content"]
        out_path = os.path.join(os.getcwd(), f"_uploaded_{name}")
        with open(out_path, "wb") as f:
            f.write(bytes(content))
        return out_path
 
 
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
 
 
def make_csv_picker(pattern="*.csv"):
    """
    Let the user choose a CSV from anywhere on their computer.
 
    Tries a native "Open File" dialog first (pops up a normal OS file
    browser window -- may appear behind your browser, check your
    taskbar/dock). If that's not usable in this environment, falls
    back to an upload button, and also lists any CSVs already in the
    current folder as a shortcut.
 
    Returns a CSVSelection object; read .value for the chosen path.
    """
    selection = CSVSelection()
 
    native_path = _try_native_file_dialog()
    if native_path:
        selection.path = native_path
        print(f"Selected file: {native_path}")
        return selection
 
    print("A native file browser wasn't available in this environment "
          "(common on remote/hosted Jupyter). Use ONE of the options below:\n")
 
    upload_widget = widgets.FileUpload(
        accept=".csv",
        multiple=False,
        description="Upload CSV",
    )
    selection._upload_widget = upload_widget
 
    local_files = sorted(glob.glob(pattern))
    widgets_to_show = [
        widgets.HTML("<b>Option A</b> — upload a file from your computer:"),
        upload_widget,
    ]
    if local_files:
        local_picker = widgets.Dropdown(
            options=local_files,
            description="...or pick from this folder:",
            style={"description_width": "initial"},
        )
 
        def _on_local_change(change):
            selection.path = change["new"]
 
        local_picker.observe(_on_local_change, names="value")
        selection.path = local_files[0]
        widgets_to_show += [
            widgets.HTML("<b>Option B</b> — a CSV already in this folder:"),
            local_picker,
        ]
 
    display(widgets.VBox(widgets_to_show))
    print("\nAfter choosing a file above, continue to the next cell.")
    return selection
 
 
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
 
 
def make_header_row_picker(path, n_preview_rows=15, default=0):
    """
    Let the user tell us which raw line number is the actual column
    header row (0-indexed). Everything above it gets skipped on load.
    """
    preview_csv(path, n_preview_rows=n_preview_rows)
    picker = widgets.Dropdown(
        options=list(range(n_preview_rows)),
        value=default,
        description="Header row is line #:",
        style={"description_width": "initial"},
    )
    display(picker)
    return picker

  
# ---------------------------------------------------------------------
# Step 2: column mapping — user tells us which column is which
# ---------------------------------------------------------------------
