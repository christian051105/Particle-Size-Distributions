from test import load
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

fname = "TGSD_HEL1980_02.csv"


df = load(DATA_DIR / fname)