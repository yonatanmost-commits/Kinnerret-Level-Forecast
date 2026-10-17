"""
backfill_pre2012_met_silver.py  -  put the pre-2012 IMS history in front of the daily met silver

The committed daily silver (met_data_daily*.csv, met_coverage_daily.csv, the QC log)
starts 2012-06-01, and from 2026-04-26 on it holds rows the daily agent appended from
the IMS feed, which no raw file reproduces. Rebuilding it from raw would drop those, so
the history is added instead of rebuilt:

  1. envista_to_ims_export.py writes the 1994-2012 history as IMS export files into an
     otherwise empty Raw Data/Meteorological Data (a fresh worktree has none).
  2. Steps 01-04 run on them as on any export; their outputs now hold only pre-2012 days.
  3. This script keeps those days (before 2012-06-01) and appends the committed file,
     taken from git at <ref>, unchanged.

Run:  python Automation/backfill_pre2012_met_silver.py [ref]      (default ref HEAD)
"""
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MET = Path("Silver Data") / "Meteorological"
FILES = ["met_data_daily.csv", "met_data_daily_clean.csv", "met_data_daily_qc_log.csv", "met_coverage_daily.csv"]
CUTOFF = "2012-06-01"


def committed(rel: Path, ref: str):
    """The committed file at ref, and whether it starts with a UTF-8 BOM (steps 03-04 write one)."""
    out = subprocess.run(["git", "show", f"{ref}:{rel.as_posix()}"], cwd=ROOT,
                         capture_output=True, text=True, check=True, encoding="utf-8").stdout
    bom = out.startswith("﻿")
    return pd.read_csv(io.StringIO(out.lstrip("﻿")), dtype=str, keep_default_na=False), bom


def backfill(name: str, ref: str) -> str:
    rel = MET / name
    old, bom = committed(rel, ref)
    new = pd.read_csv(ROOT / rel, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if new["date"].min() >= old["date"].min():
        raise RuntimeError(f"{name}: the step outputs hold no history before {old['date'].min()}"
                           " - run steps 01-04 on the envista exports first")
    pre = new[new["date"] < min(CUTOFF, old["date"].min())]
    cols = list(old.columns) + [c for c in pre.columns if c not in old.columns]
    out = pd.concat([pre.reindex(columns=cols, fill_value=""), old.reindex(columns=cols, fill_value="")],
                    ignore_index=True)
    out.to_csv(ROOT / rel, index=False, encoding="utf-8-sig" if bom else "utf-8")
    return f"{name}: {len(pre)} rows before {old['date'].min()} + {len(old)} committed rows"


if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    for f in FILES:
        print(backfill(f, ref))
