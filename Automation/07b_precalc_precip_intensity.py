# -*- coding: utf-8 -*-
"""
07b_precalc_precip_intensity.py  -  Pre-compute daily precipitation intensity

Reads the 10-minute wide meteorological CSV (207 MB) and computes the peak
1-hour rainfall intensity for each day.  The result is cached as a small
daily CSV so that 07_build_gold_features.py does not need to reload the
large file on every run.

Peak 1-hour intensity: maximum of any rolling 6-slot (60-minute) window of
10-minute readings.  Uses lev_kinneret_rainfall_mm; falls back to the mean
of all available station rainfall columns where lev_kinneret is NaN.

Output
------
Silver Data/Meteorological/precip_intensity_daily.csv
    Columns: date (YYYY-MM-DD) | precip_intensity_mm_hr

Usage
-----
    python Automation/07b_precalc_precip_intensity.py
"""

import pathlib
import pandas as pd

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_MET = BASE_DIR / "Silver Data" / "Meteorological"
IN_WIDE    = SILVER_MET / "met_data_wide.csv"
OUT_FILE   = SILVER_MET / "precip_intensity_daily.csv"


def main():
    if not IN_WIDE.exists():
        raise FileNotFoundError(str(IN_WIDE) + " not found - run 02_pivot_wide_met_data.py first")

    print("Loading rainfall columns from " + IN_WIDE.name + " ...")
    wide = pd.read_csv(
        IN_WIDE, encoding="utf-8-sig", low_memory=False,
        usecols=lambda c: c == "datetime" or c.endswith("_rainfall_mm"),
    )
    wide["datetime"] = pd.to_datetime(wide["datetime"], errors="coerce")
    wide = wide.dropna(subset=["datetime"]).sort_values("datetime")
    wide["date"] = wide["datetime"].dt.strftime("%Y-%m-%d")

    rain_cols = [c for c in wide.columns if c.endswith("_rainfall_mm")]
    lev_col   = "lev_kinneret_rainfall_mm"
    if lev_col in rain_cols:
        wide["_rain"] = wide[lev_col].fillna(wide[rain_cols].mean(axis=1))
    else:
        wide["_rain"] = wide[rain_cols].mean(axis=1)

    # Peak 1-hour intensity: max rolling sum of 6 consecutive 10-min slots
    wide["_6slot"] = wide["_rain"].rolling(6, min_periods=6).sum()
    result = (
        wide.groupby("date")["_6slot"]
        .max()
        .rename("precip_intensity_mm_hr")
        .reset_index()
    )

    result.to_csv(OUT_FILE, index=False, encoding="utf-8")
    print("Saved " + str(OUT_FILE))
    print("Rows: %d  |  Non-null: %d" % (len(result), result["precip_intensity_mm_hr"].notna().sum()))
    print("Done.")


if __name__ == "__main__":
    main()
