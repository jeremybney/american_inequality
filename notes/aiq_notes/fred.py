"""Fetch FRED series without an API key (fredgraph CSV endpoint), cached in data/fred/."""
from io import StringIO
from pathlib import Path
import time
import pandas as pd
import subprocess

CACHE = Path(__file__).resolve().parent.parent / "data" / "fred"


def series(sid, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{sid}.csv"
    if refresh or not p.exists():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        for attempt in range(4):
            res = subprocess.run(["curl", "-sSf", "-m", "60", url], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.startswith("observation_date"):
                p.write_text(res.stdout)
                break
            time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"FRED fetch failed for {sid}: {res.stderr[:200]}")
    df = pd.read_csv(p)
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().set_index("date")["value"]
