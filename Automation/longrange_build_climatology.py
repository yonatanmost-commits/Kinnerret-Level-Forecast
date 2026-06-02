# Automation/longrange_build_climatology.py
"""
longrange_build_climatology.py - Build the per-day-of-year normals table used by
the long-range model. Meteorological normals come from the deep (bias-corrected)
record; outflow climatology comes from the MODERN record only (2012+), because
pumping policy is non-stationary (Group 9).

Writes Gold Data/longrange_climatology.csv keyed by doy (1..366).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from longrange_climatology import (fit_harmonic, eval_harmonic, fit_rain_climatology,
                                    clearsky_dtr_by_doy)

ROOT = Path(__file__).resolve().parent.parent
DEEP_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily_corrected.csv"
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
OUT_PATH = ROOT / "Gold Data" / "longrange_climatology.csv"
MODERN_START = "2012-01-01"


def build_climatology(deep_df: pd.DataFrame, modern_df: pd.DataFrame) -> pd.DataFrame:
    deep = deep_df.copy()
    deep["date"] = pd.to_datetime(deep["date"])
    doy = deep["date"].dt.dayofyear.values
    dtr = (deep["temp_max_C"] - deep["temp_min_C"]).values

    tmax_c = fit_harmonic(doy, deep["temp_max_C"].values)
    tmin_c = fit_harmonic(doy, deep["temp_min_C"].values)
    dtr_c = fit_harmonic(doy, dtr)
    dtr_cs_c = clearsky_dtr_by_doy(doy, dtr)
    et0_c = fit_harmonic(doy, deep["et0_mm"].values) if "et0_mm" in deep else None
    pwet_c, amt_c = fit_rain_climatology(doy, deep["rainfall_mm"].values)

    modern = modern_df.copy()
    modern["date"] = pd.to_datetime(modern["date"])
    modern = modern[modern["date"] >= MODERN_START]
    mdoy = modern["date"].dt.dayofyear.values
    outflow_c = fit_harmonic(mdoy, modern["outflow_baptism_m3"].values)

    grid = np.arange(1, 367, dtype=float)
    out = pd.DataFrame({
        "doy": grid.astype(int),
        "temp_max_clim": eval_harmonic(grid, tmax_c),
        "temp_min_clim": eval_harmonic(grid, tmin_c),
        "dtr_clim": eval_harmonic(grid, dtr_c),
        "dtr_clearsky": eval_harmonic(grid, dtr_cs_c),
        "et0_clim": eval_harmonic(grid, et0_c) if et0_c is not None else np.nan,
        "p_wet_clim": np.clip(eval_harmonic(grid, pwet_c), 0, 1),
        "amount_clim": np.clip(eval_harmonic(grid, amt_c), 0, None),
        "outflow_clim": eval_harmonic(grid, outflow_c),
    })
    return out


def main():
    deep = pd.read_csv(DEEP_PATH, encoding="utf-8-sig")
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    out = build_climatology(deep, gold)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote climatology ({len(out)} DOY rows) to {OUT_PATH}")


if __name__ == "__main__":
    main()
