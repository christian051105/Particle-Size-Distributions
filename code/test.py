import pandas as pd

def load(fname):
    print(f"Loading {fname}")
    return pd.read_csv(fname, header=1)