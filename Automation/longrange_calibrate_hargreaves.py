# Automation/longrange_calibrate_hargreaves.py
"""
longrange_calibrate_hargreaves.py - Calibrate temp-only Hargreaves ET0 to the
model's trained Penman-Monteith et0_mm scale (Group 2 calibration note).

Fits et0_pm ~ a*et0_hs + b over the gold record (where both exist) and writes the
linear calibration to docs/longrange_config.json so downstream code reproduces the
ET0 scale the existing model was trained on.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from longrange_meteo import hargreaves_et0

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
CONFIG_PATH = ROOT / "docs" / "longrange_config.json"


def fit_linear_calibration(et0_hs, et0_pm):
    """Least-squares fit et0_pm = a*et0_hs + b. Returns (a, b). Drops NaN rows."""
    x = np.asarray(et0_hs, dtype=float)
    y = np.asarray(et0_pm, dtype=float)
    ok = ~np.isnan(x) & ~np.isnan(y)
    A = np.column_stack([x[ok], np.ones(ok.sum())])
    (a, b), *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    return float(a), float(b)


def main():
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    gold["date"] = pd.to_datetime(gold["date"])
    doy = gold["date"].dt.dayofyear.values
    et0_hs = hargreaves_et0(gold["temp_max_C"].values, gold["temp_min_C"].values, doy)
    a, b = fit_linear_calibration(et0_hs, gold["et0_mm"].values)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(
        {"hargreaves_calibration": {"slope": a, "intercept": b,
         "note": "et0_pm ~= slope*et0_hs + intercept, fit on gold"}}, indent=2))
    print(f"Hargreaves calibration: slope={a:.4f} intercept={b:.4f} -> {CONFIG_PATH}")


if __name__ == "__main__":
    main()
