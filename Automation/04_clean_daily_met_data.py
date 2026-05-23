# -*- coding: utf-8 -*-
"""
04_clean_daily_met_data.py  -  Step 4 - Daily Data QC & Cleaning

Applies four layers of quality control to met_data_daily.csv:

  Layer 1 - Hard physical bounds
      Values outside physically possible ranges for the Sea of Galilee
      region are set to NaN.

  Layer 2 - Monthly IQR outlier filter
      For each (station, parameter, calendar-month) group, values outside
      [Q1 - 3*IQR,  Q3 + 3*IQR] are set to NaN.
      Monthly grouping preserves real seasonal extremes.
      3*IQR is conservative -- genuine extreme events survive.

  Layer 3 - Daily coverage filter
      Uses met_data_wide.csv to count how many valid 10-min readings
      each station reported per day.  Days where a station delivered
      fewer than COVERAGE_THRESHOLD (default 70%) of the 144 expected
      slots have all their daily aggregates set to NaN.

  Layer 4 - Persistence check
      For sensor-type columns (temperature, humidity, wind speed mean),
      runs of PERSISTENCE_MIN_RUN or more consecutive identical daily
      values are set to NaN.  A stuck sensor produces an implausibly flat
      signal that passes Layers 1-3 undetected.
      Rainfall and wind direction are excluded (genuine zero-rain streaks
      and sustained directional flow are meteorologically plausible).

All four layers are fully vectorised -- no row-by-row Python loops.

Outputs
-------
Silver Data/Meteorological/met_data_daily_clean.csv   -- cleaned daily data
Silver Data/Meteorological/met_data_daily_qc_log.csv  -- every change: date,
                                                          column, original
                                                          value, reason

Usage
-----
    python Automation/04_clean_daily_met_data.py
"""

import pathlib
import pandas as pd
import numpy as np

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_DIR = BASE_DIR / "Silver Data" / "Meteorological"
IN_DAILY   = SILVER_DIR / "met_data_daily.csv"
IN_WIDE    = SILVER_DIR / "met_data_wide.csv"
OUT_CLEAN  = SILVER_DIR / "met_data_daily_clean.csv"
OUT_LOG    = SILVER_DIR / "met_data_daily_qc_log.csv"

# ---------------------------------------------------------------------------
# Layer 1 - Physical bounds  (column_suffix: (min, max))
# ---------------------------------------------------------------------------
PHYSICAL_BOUNDS = {
    "temperature_C_mean":        (-10,  55),
    "temperature_C_max":         ( -5,  57),
    "temperature_C_min":         (-15,  45),
    "temperature_max_C_max":     ( -5,  57),
    "temperature_min_C_min":     (-15,  45),
    "temperature_ground_C_mean": (-10,  60),
    "temperature_wet_C_mean":    (-10,  40),
    "relative_humidity_pct_mean":(   0, 100),
    "rainfall_mm_sum":           (   0, 300),
    "wind_speed_ms_mean":        (   0,  25),
    "wind_speed_ms_max":         (   0,  40),
    "wind_speed_max1min_ms_max": (   0,  45),
    "wind_speed_max10min_ms_max":(   0,  40),
    "wind_gust_speed_ms_max":    (   0,  50),
    "global_radiation_Wm2_mean": (   0, 900),
    "global_radiation_Wm2_sum":  (   0, 900 * 144),
    "global_radiation_MJm2":     (   0,  40),
}

# Layer 3 settings
COVERAGE_THRESHOLD = 0.70    # minimum fraction of 10-min slots required
SLOTS_PER_DAY      = 144     # 24h * 6 per hour

# Parameters to blank when coverage is insufficient (skip string/hhmm cols)
COVERAGE_PARAMS = [
    "temperature_C", "temperature_max_C", "temperature_min_C",
    "temperature_ground_C", "temperature_wet_C",
    "relative_humidity_pct", "rainfall_mm",
    "wind_speed_ms", "wind_speed_max1min_ms", "wind_speed_max10min_ms",
    "wind_gust_speed_ms", "wind_dir_deg", "wind_gust_dir_deg",
    "wind_dir_std_deg", "global_radiation_Wm2",
]

# Layer 4 settings - persistence check
# Suffixes to check for stuck-sensor runs (skip rainfall, wind direction,
# radiation sum - legitimate constant runs occur in those parameters)
PERSISTENCE_SUFFIXES = [
    "temperature_C_mean", "temperature_C_max", "temperature_C_min",
    "temperature_max_C_max", "temperature_min_C_min",
    "temperature_ground_C_mean", "temperature_wet_C_mean",
    "relative_humidity_pct_mean",
    "wind_speed_ms_mean",
]
PERSISTENCE_MIN_RUN = 4   # flag runs of >= this many consecutive identical days


# ---------------------------------------------------------------------------
# Helpers - all vectorised
# ---------------------------------------------------------------------------

def collect_changes(df_before, df_after, reason_col):
    """
    Given two DataFrames of the same shape where df_after may have new NaNs
    compared to df_before, return a tidy log DataFrame of what changed.
    reason_col: Series aligned with df_before index giving the reason string.
    """
    changed_mask = df_before.notna() & df_after.isna()
    rows = []
    for col in changed_mask.columns:
        idx = changed_mask.index[changed_mask[col]]
        if idx.empty:
            continue
        sub = pd.DataFrame({
            "date":           df_before.loc[idx, "date"].values,
            "column":         col,
            "original_value": df_before.loc[idx, col].values,
            "reason":         reason_col.loc[idx].values,
        })
        rows.append(sub)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["date", "column", "original_value", "reason"])


def layer1_physical_bounds(df):
    """Null values outside physical ranges. Returns (df, log)."""
    df = df.copy()
    reason_series = pd.Series("", index=df.index)
    df_before = df.copy()

    for suffix, (lo, hi) in PHYSICAL_BOUNDS.items():
        for col in [c for c in df.columns if c.endswith("_" + suffix)]:
            bad = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
            reason_series.loc[bad] = "physical_bounds [%g, %g]" % (lo, hi)
            df.loc[bad, col] = np.nan

    log = collect_changes(df_before, df, reason_series)
    return df, log


def layer2_monthly_iqr(df, multiplier=3.0):
    """
    Null per-station-parameter values outside monthly Q1-3*IQR / Q3+3*IQR.
    Skips summed columns (rainfall, radiation sum) -- physical bounds suffice.
    Returns (df, log).
    """
    df = df.copy()
    df["_month"] = pd.to_datetime(df["date"]).dt.month

    numeric_cols = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if not c.startswith("_") and not c.endswith("_sum")
    ]

    reason_series = pd.Series("", index=df.index)
    df_before = df.drop(columns=["_month"]).copy()

    for col in numeric_cols:
        monthly = df.groupby("_month")[col].agg(
            lambda g: (g.quantile(0.25) - multiplier * (g.quantile(0.75) - g.quantile(0.25)),
                       g.quantile(0.75) + multiplier * (g.quantile(0.75) - g.quantile(0.25)))
        )
        lo_map = monthly.map(lambda t: t[0])
        hi_map = monthly.map(lambda t: t[1])
        lo_col = df["_month"].map(lo_map)
        hi_col = df["_month"].map(hi_map)

        bad = df[col].notna() & ((df[col] < lo_col) | (df[col] > hi_col))
        reason_series.loc[bad] = bad.loc[bad].index.map(
            lambda i: "monthly_IQR month=%d [%.2f, %.2f]" % (
                df.at[i, "_month"],
                lo_map.get(df.at[i, "_month"], -np.inf),
                hi_map.get(df.at[i, "_month"],  np.inf),
            )
        )
        df.loc[bad, col] = np.nan

    df.drop(columns=["_month"], inplace=True)
    log = collect_changes(df_before, df, reason_series)
    return df, log


def layer3_coverage(df, wide_path):
    """
    Blank daily values for station-days with < COVERAGE_THRESHOLD coverage.
    Returns (df, log).
    """
    df = df.copy()
    df_before = df.copy()

    wide = pd.read_csv(
        wide_path, encoding="utf-8-sig", low_memory=False,
        usecols=lambda c: c == "datetime" or c.endswith("_temperature_C"),
    )
    wide["datetime"] = pd.to_datetime(wide["datetime"], errors="coerce")
    wide = wide.dropna(subset=["datetime"])
    wide["date"] = wide["datetime"].dt.date.astype(str)

    station_temp_cols = {
        col.replace("_temperature_C", ""): col
        for col in wide.columns if col.endswith("_temperature_C")
    }

    cov_dict = {}
    for station, col in station_temp_cols.items():
        cov_dict[station] = (
            wide.groupby("date")[col]
            .apply(lambda x: x.notna().sum() / SLOTS_PER_DAY)
        )
    coverage = pd.DataFrame(cov_dict)

    df["_date_str"] = df["date"].astype(str)
    df = df.set_index("_date_str")

    reason_series = pd.Series("", index=df.index)

    for station in coverage.columns:
        low_mask = coverage[station] < COVERAGE_THRESHOLD
        low_dates = coverage.index[low_mask]
        if low_dates.empty:
            continue

        st_cols = [
            c for c in df.columns
            if c.startswith(station + "_")
            and any(p in c for p in COVERAGE_PARAMS)
        ]

        for date_str in low_dates:
            if date_str not in df.index:
                continue
            pct = coverage.at[date_str, station]
            reason_series.at[date_str] = (
                "coverage %.0f%% < %.0f%%" % (pct * 100, COVERAGE_THRESHOLD * 100)
            )
            df.loc[date_str, st_cols] = np.nan

    df = df.reset_index(drop=True)
    df_before = df_before.set_index(df_before["date"].astype(str)).reindex(
        df.index if "_date_str" not in df_before.columns else df_before["date"].astype(str)
    ).reset_index(drop=True)

    log = collect_changes(df_before, df, reason_series.reset_index(drop=True))
    return df, log


def layer4_persistence(df):
    """
    Null runs of PERSISTENCE_MIN_RUN or more consecutive identical daily values
    for sensor-type columns (temperature, humidity, wind speed mean).

    A sensor stuck at a fixed value produces an implausibly flat signal that
    survives Layers 1-3.  Physical bounds, IQR, and coverage filters all pass
    a constant 25.0 C for 7 days straight -- this layer catches it.

    Rainfall and wind direction are deliberately excluded: genuine zero-rain
    streaks and sustained directional flow are meteorologically plausible.

    Vectorised via run-length grouping (no Python loops over rows).
    """
    df = df.copy()
    df_before = df.copy()
    reason_series = pd.Series("", index=df.index)

    for suffix in PERSISTENCE_SUFFIXES:
        for col in [c for c in df.columns if c.endswith("_" + suffix)]:
            s = df[col]
            # New group whenever value changes OR either side is NaN.
            # This prevents a NaN from silently merging two adjacent identical runs.
            prev = s.shift()
            boundary = (s != prev) | s.isna() | prev.isna()
            groups = boundary.cumsum()

            # Map each non-NaN group to its run length
            valid_groups = groups.where(s.notna())
            run_len = valid_groups.map(valid_groups.value_counts())

            bad = s.notna() & (run_len >= PERSISTENCE_MIN_RUN)
            reason_series.loc[bad] = (
                "persistence_%d_days_identical" % PERSISTENCE_MIN_RUN
            )
            df.loc[bad, col] = np.nan

    log = collect_changes(df_before, df, reason_series)
    return df, log


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not IN_DAILY.exists():
        raise FileNotFoundError(str(IN_DAILY) + " not found - run 03_aggregate_daily_met_data.py first")

    print("Loading " + IN_DAILY.name + " ...")
    df = pd.read_csv(IN_DAILY, encoding="utf-8-sig", low_memory=False)
    original_shape = df.shape
    all_logs = []

    print("Layer 1: Physical bounds ...")
    df, log1 = layer1_physical_bounds(df)
    all_logs.append(log1)
    print("  %d values nulled" % len(log1))

    print("Layer 2: Monthly IQR filter (3x IQR per station-month) ...")
    df, log2 = layer2_monthly_iqr(df)
    all_logs.append(log2)
    print("  %d values nulled" % len(log2))

    if IN_WIDE.exists():
        print("Layer 3: Coverage filter (<%d%% of daily 10-min slots) ..." % int(COVERAGE_THRESHOLD * 100))
        df, log3 = layer3_coverage(df, IN_WIDE)
        all_logs.append(log3)
        print("  %d values nulled" % len(log3))
    else:
        print("Layer 3: SKIPPED (met_data_wide.csv not found in Silver Data)")
        log3 = pd.DataFrame(columns=["date", "column", "original_value", "reason"])

    print("Layer 4: Persistence check (>=%d consecutive identical days) ..." % PERSISTENCE_MIN_RUN)
    df, log4 = layer4_persistence(df)
    all_logs.append(log4)
    print("  %d values nulled" % len(log4))

    print("Saving outputs ...")
    df.to_csv(OUT_CLEAN, index=False, encoding="utf-8-sig")

    log_df = pd.concat([l for l in all_logs if not l.empty], ignore_index=True)
    log_df["layer"] = log_df["reason"].str.split("_").str[0]
    log_df.to_csv(OUT_LOG, index=False, encoding="utf-8-sig")

    total = len(log_df)
    all_cells = original_shape[0] * (original_shape[1] - 1)
    print("")
    print("-" * 60)
    print("Input  : %d rows x %d cols" % original_shape)
    print("Output : " + str(OUT_CLEAN))
    print("QC log : " + str(OUT_LOG) + "  (%d entries)" % total)
    print("")
    print("Values nulled by layer:")
    print("  Layer 1 physical bounds           : %5d" % len(log1))
    print("  Layer 2 monthly IQR               : %5d" % len(log2))
    print("  Layer 3 coverage <70%%            : %5d" % len(log3))
    print("  Layer 4 persistence (>=%dd run)   : %5d" % (PERSISTENCE_MIN_RUN, len(log4)))
    print("  Total                             : %5d  (%.3f%% of cells)" % (
        total, total / all_cells * 100 if all_cells else 0))
    if total:
        print("")
        print("Most affected columns:")
        for col, cnt in log_df["column"].value_counts().head(8).items():
            print("  %-45s  %d" % (col, cnt))
    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
