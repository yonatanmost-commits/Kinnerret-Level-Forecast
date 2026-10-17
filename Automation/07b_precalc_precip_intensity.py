# -*- coding: utf-8 -*-
"""
07b_precalc_precip_intensity.py  -  Pre-compute daily precipitation intensity

Reads the 10-minute wide meteorological CSV (207 MB) and computes the peak
1-hour rainfall intensity for each day.  The result is cached as a small
daily CSV so that 07_build_gold_features.py does not need to reload the
large file on every run.

Peak 1-hour intensity: maximum of any rolling 6-slot (60-minute) window of
10-minute readings, as defined in precip_intensity.daily_intensity (Tzemach's
gauge first, the mean of the other gauges where it is missing).

After that (whether or not the wide file is present), the days after the
cache's last value are filled from the IMS 10-minute feed through yesterday
(precip_intensity.update_cache). The wide file stopped growing on 2026-04-25,
when the manual exports ended.

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

from precip_intensity import daily_intensity, update_cache

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_MET = BASE_DIR / "Silver Data" / "Meteorological"
IN_WIDE    = SILVER_MET / "met_data_wide.csv"
OUT_FILE   = SILVER_MET / "precip_intensity_daily.csv"


def main():
    rebuild_from_wide()
    out = update_cache(OUT_FILE)
    print("Extended from IMS feed: last day %s  |  Rows: %d  |  Non-null: %d"
          % (out["date"].max(), len(out), out["precip_intensity_mm_hr"].notna().sum()))


def rebuild_from_wide():
    # met_data_wide.csv is 207 MB and is excluded from the repository, so it is
    # absent in CI and in any fresh clone. The daily agent never extends it either
    # - it appends to met_data_daily.csv - so a rebuild only recomputes the manual
    # export's era, and would overwrite the days update_cache has since fetched
    # from the IMS feed (it rolled the cache back to April on 2026-10-16). Rebuild
    # only when there is no cache at all; otherwise keep it, as CI always does.
    if OUT_FILE.exists():
        print("SKIP: keeping cached " + OUT_FILE.name + "; the IMS feed extends it.")
        return
    if not IN_WIDE.exists():
        raise FileNotFoundError(
            str(IN_WIDE) + " not found and no cached " + OUT_FILE.name
            + " to fall back on - run 02_pivot_wide_met_data.py first"
        )

    print("Loading rainfall columns from " + IN_WIDE.name + " ...")
    wide = pd.read_csv(
        IN_WIDE, encoding="utf-8-sig", low_memory=False,
        usecols=lambda c: c == "datetime" or c.endswith("_rainfall_mm"),
    )
    wide["datetime"] = pd.to_datetime(wide["datetime"], errors="coerce")
    wide = wide.dropna(subset=["datetime"]).drop_duplicates("datetime").set_index("datetime")
    rain10 = wide.rename(columns=lambda c: c.removesuffix("_rainfall_mm"))

    # the one definition, shared with the IMS-feed extension (precip_intensity.daily_intensity)
    result = daily_intensity(rain10).rename_axis("date").reset_index()

    result.to_csv(OUT_FILE, index=False, encoding="utf-8")
    print("Saved " + str(OUT_FILE))
    print("Rows: %d  |  Non-null: %d" % (len(result), result["precip_intensity_mm_hr"].notna().sum()))


if __name__ == "__main__":
    main()
