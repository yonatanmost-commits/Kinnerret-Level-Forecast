# Automation/longrange_bias_correct.py
"""
longrange_bias_correct.py - Group 8 monthly empirical quantile mapping of the deep
ERA5 record onto the IMS gold distribution, calibrated on the 2012-2024 overlap.
Without this the model would learn a fake discontinuity at the splice.

Temperature columns use quantile mapping (handles mean + variance bias). Run as a
script to produce era5_kinneret_daily_corrected.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ERA5_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily.csv"
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
OUT_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily_corrected.csv"

OVERLAP_START = "2012-01-01"
OVERLAP_END = "2024-12-31"
# ERA5 tidy column -> gold reference column
CORRECT_COLS = {
    "temp_max_C": "temp_max_C",
    "temp_min_C": "temp_min_C",
    "rainfall_mm": "rainfall_mm",
}


def quantile_map(src, ref):
    """Empirical quantile mapping: map each src value to the ref value at the same
    empirical rank. Returns array same shape as src."""
    src = np.asarray(src, dtype=float)
    ref = np.asarray(ref, dtype=float)
    ref = ref[~np.isnan(ref)]
    ref_sorted = np.sort(ref)
    n = ref_sorted.size
    ref_q = (np.arange(n) + 0.5) / n
    src_sorted = np.sort(src[~np.isnan(src)])
    m = src_sorted.size
    # empirical CDF rank of each src value within the src distribution
    ranks = (np.searchsorted(src_sorted, src, side="right") - 0.5) / max(m, 1)
    ranks = np.clip(ranks, 0, 1)
    return np.interp(ranks, ref_q, ref_sorted)


def correct_dataframe(era5: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    era5 = era5.copy()
    era5["date"] = pd.to_datetime(era5["date"])
    gold = gold.copy()
    gold["date"] = pd.to_datetime(gold["date"])
    overlap = gold[(gold["date"] >= OVERLAP_START) & (gold["date"] <= OVERLAP_END)]
    era5["month"] = era5["date"].dt.month
    overlap = overlap.assign(month=overlap["date"].dt.month)
    era5_ov = era5[(era5["date"] >= OVERLAP_START) & (era5["date"] <= OVERLAP_END)]

    for ecol, gcol in CORRECT_COLS.items():
        if ecol not in era5.columns or gcol not in gold.columns:
            continue
        for m in range(1, 13):
            ref = overlap.loc[overlap["month"] == m, gcol].values
            src_overlap = era5_ov.loc[era5_ov["month"] == m, ecol].values
            if ref.size < 30 or src_overlap.size < 30:
                continue   # not enough overlap to calibrate this month
            mask = era5["month"] == m
            era5.loc[mask, ecol] = quantile_map(era5.loc[mask, ecol].values, ref)
    return era5.drop(columns="month")


def main():
    era5 = pd.read_csv(ERA5_PATH, encoding="utf-8-sig")
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    out = correct_dataframe(era5, gold)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote bias-corrected ERA5 ({len(out)} rows) to {OUT_PATH}")


if __name__ == "__main__":
    main()
