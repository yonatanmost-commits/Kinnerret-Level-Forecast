# -*- coding: utf-8 -*-
"""
03_aggregate_daily_met_data.py  -  Step 3 (optional) - Daily Aggregation

Reads the wide 10-minute CSV (met_data_wide.csv) and collapses it to one
row per calendar day using meteorologically correct aggregation methods:

    Temperature (C)      : mean, daily_max, daily_min
    Relative humidity (%) : mean
    Global radiation (W/m2): mean intensity, daily_energy_MJm2
                             (energy = sum * 600s / 1e6,  i.e. sum * 0.0006)
    Rainfall (mm)         : daily_sum  (must be summed, never averaged)
    Wind speed (m/s)      : mean, max
    Max gust speed (m/s)  : max
    Wind direction (deg)  : mean  (arithmetic approx - fine for daily data)

Output
------
Silver Data/Meteorological/met_data_daily.csv
    ~5,000 rows (one per calendar day, 2012-06-01 to present)
    Columns: date | {station}_{param}_{agg} ...

Usage
-----
    python Automation/03_aggregate_daily_met_data.py
"""

import pathlib
import pandas as pd

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_DIR = BASE_DIR / "Silver Data"
MET_DIR    = SILVER_DIR / "Meteorological"
IN_FILE    = SILVER_DIR / "met_data_wide.csv"
OUT_FILE   = MET_DIR / "met_data_daily.csv"

# Map each parameter to the aggregation(s) to apply.
# Key   = parameter suffix in the wide column name
# Value = dict of  output_suffix -> pandas_agg_function
PARAM_AGGS = {
    "temperature_C":          {"mean": "mean", "max": "max", "min": "min"},
    "temperature_max_C":      {"max": "max"},       # rolling-window daily high
    "temperature_min_C":      {"min": "min"},       # rolling-window daily low
    "temperature_ground_C":   {"mean": "mean"},
    "temperature_wet_C":      {"mean": "mean"},
    "relative_humidity_pct":  {"mean": "mean"},
    "global_radiation_Wm2":   {"mean": "mean",
                                "sum": "sum"},      # sum -> MJm2 below
    "rainfall_mm":            {"sum": "sum"},       # NEVER average rainfall
    "wind_speed_ms":          {"mean": "mean", "max": "max"},
    "wind_speed_max1min_ms":  {"max": "max"},
    "wind_speed_max10min_ms": {"max": "max"},
    "wind_gust_speed_ms":     {"max": "max"},
    "wind_dir_deg":           {"mean": "mean"},
    "wind_gust_dir_deg":      {"mean": "mean"},
    "wind_dir_std_deg":       {"mean": "mean"},
}

# Conversion: W/m2 averaged over 10-min intervals -> MJ/m2/day
# Energy per interval = W/m2 * 600 s = J/m2
# Sum of all intervals / 1e6 = MJ/m2
RAD_J_PER_INTERVAL = 600        # seconds in 10 minutes
RAD_J_TO_MJ        = 1_000_000


def build_agg_map(columns):
    """
    Given a list of wide column names, return:
      agg_map : { wide_col: {out_suffix: agg_func} }
      rename  : { (wide_col, agg_func): out_col }
    """
    agg_map = {}
    for col in columns:
        if col == "datetime":
            continue
        # col format: {station}_{param}  e.g. beit_tzaida_temperature_C
        # Find which param it ends with (longest match wins)
        matched_param = None
        for param in sorted(PARAM_AGGS.keys(), key=len, reverse=True):
            if col.endswith("_" + param):
                matched_param = param
                break
        if matched_param is None:
            continue
        station = col[: -(len(matched_param) + 1)]
        agg_map[col] = {
            "%s_%s_%s" % (station, matched_param, out_sfx): agg_fn
            for out_sfx, agg_fn in PARAM_AGGS[matched_param].items()
        }
    return agg_map


def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(str(IN_FILE) + " not found - run 02_pivot_wide_met_data.py first")

    print("Loading " + IN_FILE.name + " ...")
    df = pd.read_csv(IN_FILE, encoding="utf-8-sig", low_memory=False)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    df["date"] = df["datetime"].dt.date

    stations = sorted({c.split("_")[0] for c in df.columns if c != "datetime" and c != "date"})
    print("  %d rows  |  stations: %s" % (len(df), stations))

    # Build per-column aggregation instructions
    agg_map = build_agg_map(df.columns)

    # Construct the pandas groupby agg dict
    # { wide_col: [agg_fn, ...] }
    gb_agg = {}
    for wide_col, out_map in agg_map.items():
        fns = list(out_map.values())
        gb_agg[wide_col] = fns

    print("Aggregating to daily ...")
    grouped = df.groupby("date").agg(gb_agg)

    # Flatten MultiIndex columns: (wide_col, agg_fn) -> out_col
    # Build reverse lookup from (wide_col, agg_fn) -> desired output name
    rename_lookup = {}
    for wide_col, out_map in agg_map.items():
        for out_sfx, agg_fn in out_map.items():
            rename_lookup[(wide_col, agg_fn)] = out_sfx  # out_sfx already includes station+param+agg

    flat_cols = []
    for wide_col, agg_fn in grouped.columns:
        flat_cols.append(rename_lookup.get((wide_col, agg_fn),
                                           "%s_%s" % (wide_col, agg_fn)))
    grouped.columns = flat_cols
    grouped = grouped.reset_index()

    # Fix: pandas sum() returns 0 for all-NaN groups; restore to NaN for rainfall
    # so that consensus_col in gold builder can fall back to neighbouring stations.
    for wide_col in [c for c in df.columns if c.endswith("_rainfall_mm")]:
        out_col = wide_col + "_sum"
        if out_col in grouped.columns:
            count_by_date = df.groupby("date")[wide_col].count()
            no_data = set(count_by_date[count_by_date == 0].index)
            grouped.loc[grouped["date"].isin(no_data), out_col] = float("nan")

    # Add daily radiation energy column: MJ/m2
    # = sum_col (W/m2 readings summed) * 600s / 1e6
    for wide_col in [c for c in df.columns if c.endswith("_global_radiation_Wm2")]:
        sum_col = wide_col + "_sum"
        if sum_col in grouped.columns:
            energy_col = wide_col.replace("_global_radiation_Wm2", "_global_radiation_MJm2")
            grouped[energy_col] = (grouped[sum_col] * RAD_J_PER_INTERVAL / RAD_J_TO_MJ).round(3)

    # Sort columns: date first, then grouped by station
    def col_sort_key(c):
        if c == "date":
            return (0, "", "")
        parts = c.split("_", 1)
        return (1, parts[0], parts[1] if len(parts) > 1 else "")

    grouped = grouped.reindex(sorted(grouped.columns, key=col_sort_key), axis=1)
    grouped = grouped.sort_values("date").reset_index(drop=True)

    print("Saving " + OUT_FILE.name + " ...")
    grouped.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    import os
    size_mb = os.path.getsize(OUT_FILE) / 1e6
    print("")
    print("-" * 60)
    print("Output : " + str(OUT_FILE))
    print("Rows   : %d  (calendar days)" % len(grouped))
    print("Columns: %d" % len(grouped.columns))
    print("Range  : %s  to  %s" % (grouped["date"].min(), grouped["date"].max()))
    print("Size   : %.1f MB" % size_mb)
    print("")
    print("Sample columns:")
    for c in list(grouped.columns)[1:12]:
        non_null = grouped[c].notna().sum()
        print("  %-45s  %d non-null days" % (c, non_null))
    print("-" * 60)
    print("Done.")



if __name__ == "__main__":
    main()
