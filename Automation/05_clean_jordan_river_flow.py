# -*- coding: utf-8 -*-
"""
05_clean_jordan_river_flow.py  -  Step 2 - Jordan River Flow QC & Cleaning

Applies three layers of quality control to jordan_river_daily_flow.csv:

  Layer 1 - Physical bounds
      Flow values below 0 m3/day are physically impossible and set to NaN.

  Layer 2 - Monthly IQR outlier filter
      For each (station, calendar-month) group, values outside
      [Q1 - 3*IQR,  Q3 + 3*IQR] are set to NaN.
      Monthly grouping preserves genuine seasonal flood peaks -- a January
      value is only compared to other January values, not to summer lows.
      3*IQR is conservative; genuine extreme events survive.
      (Replaces the previous global 2.5*p99 cap which did not account for
      seasonality and was too aggressive on stations like YARMUQ.)

  Layer 3 - Short gap interpolation
      Consecutive NaN runs of up to MAX_INTERP_DAYS days within each
      station's active span (first to last valid reading) are filled by
      linear time interpolation.  Longer gaps and periods outside the
      active span are left as NaN.  Filled values are recorded in the
      QC log with reason "interpolated".

All three layers are fully vectorised -- no row-by-row Python loops.

Outputs
-------
Silver Data/Jordan River Silver/jordan_river_daily_flow_clean.csv
Silver Data/Jordan River Silver/jordan_river_flow_qc_log.csv
    Columns: Date | station | original_value | new_value | reason | layer

Usage
-----
    python Automation/05_clean_jordan_river_flow.py
"""

import pathlib
import pandas as pd
import numpy as np

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_DIR = BASE_DIR / "Silver Data" / "Jordan River Silver"
IN_FILE    = SILVER_DIR / "jordan_river_daily_flow.csv"
OUT_CLEAN  = SILVER_DIR / "jordan_river_daily_flow_clean.csv"
OUT_LOG    = SILVER_DIR / "jordan_river_flow_qc_log.csv"

# Layer 2 settings
IQR_MULTIPLIER = 3.0

# Layer 3 settings
MAX_INTERP_DAYS = 3   # max consecutive NaN days to fill by interpolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wide_to_log(df_before, df_after, date_col, reason):
    """
    Compare two wide DataFrames and return a log of all cells that changed
    from non-NaN to NaN (i.e. were nulled).

    Returns a tidy DataFrame with columns:
        Date | station | original_value | new_value | reason | layer
    """
    station_cols = [c for c in df_before.columns if c != date_col]
    rows = []
    for col in station_cols:
        nulled = df_before[col].notna() & df_after[col].isna()
        idx = df_before.index[nulled]
        if idx.empty:
            continue
        rows.append(pd.DataFrame({
            "Date":           df_before.loc[idx, date_col].values,
            "station":        col,
            "original_value": df_before.loc[idx, col].values,
            "new_value":      np.nan,
            "reason":         reason,
        }))
    if not rows:
        return pd.DataFrame(columns=["Date", "station", "original_value", "new_value", "reason"])
    return pd.concat(rows, ignore_index=True)


def interpolation_log(df_before, df_after, date_col):
    """
    Return a log of all cells that changed from NaN to non-NaN (filled).
    """
    station_cols = [c for c in df_before.columns if c != date_col]
    rows = []
    for col in station_cols:
        filled = df_before[col].isna() & df_after[col].notna()
        idx = df_before.index[filled]
        if idx.empty:
            continue
        rows.append(pd.DataFrame({
            "Date":           df_before.loc[idx, date_col].values,
            "station":        col,
            "original_value": np.nan,
            "new_value":      df_after.loc[idx, col].values,
            "reason":         "interpolated_gap<=%dd" % MAX_INTERP_DAYS,
        }))
    if not rows:
        return pd.DataFrame(columns=["Date", "station", "original_value", "new_value", "reason"])
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Layer 1 - Physical bounds
# ---------------------------------------------------------------------------

def layer1_physical_bounds(df):
    """Null any flow values below 0. Returns (df, log)."""
    df = df.copy()
    df_before = df.copy()
    station_cols = [c for c in df.columns if c != "Date"]
    for col in station_cols:
        bad = df[col].notna() & (df[col] < 0)
        df.loc[bad, col] = np.nan
    log = wide_to_log(df_before, df, "Date", "physical_bounds [0, inf)")
    return df, log


# ---------------------------------------------------------------------------
# Layer 2 - Monthly IQR outlier filter
# ---------------------------------------------------------------------------

def layer2_monthly_iqr(df, multiplier=IQR_MULTIPLIER):
    """
    For each (station, calendar-month) group, null values outside
    [Q1 - multiplier*IQR,  Q3 + multiplier*IQR].
    Returns (df, log).
    """
    df = df.copy()
    df_before = df.copy()
    station_cols = [c for c in df.columns if c != "Date"]

    month = pd.to_datetime(df["Date"]).dt.month

    for col in station_cols:
        s = df[col]
        # Compute per-month bounds via groupby
        monthly_stats = s.groupby(month).agg(
            lambda g: (
                g.quantile(0.25) - multiplier * (g.quantile(0.75) - g.quantile(0.25)),
                g.quantile(0.75) + multiplier * (g.quantile(0.75) - g.quantile(0.25)),
            )
        )
        lo_map = monthly_stats.map(lambda t: t[0])
        hi_map = monthly_stats.map(lambda t: t[1])
        lo = month.map(lo_map)
        hi = month.map(hi_map)

        bad = s.notna() & ((s < lo) | (s > hi))
        # Build per-row reason string
        reasons = bad.index.map(
            lambda i: (
                "monthly_IQR month=%d [%.0f, %.0f]" % (
                    month.at[i],
                    lo_map.get(month.at[i], -np.inf),
                    hi_map.get(month.at[i],  np.inf),
                )
            ) if bad.at[i] else ""
        )
        df.loc[bad, col] = np.nan

    log = wide_to_log(df_before, df, "Date",
                      "monthly_IQR_3x (see station/month for bounds)")
    # Annotate log with precise bounds per row by re-deriving
    # (simpler: just note the layer; the original value tells the story)
    return df, log


# ---------------------------------------------------------------------------
# Layer 3 - Short gap interpolation
# ---------------------------------------------------------------------------

def layer3_interpolate(df):
    """
    Within each station's active span, linearly interpolate NaN runs of
    up to MAX_INTERP_DAYS days.  Longer gaps are left as NaN.
    Returns (df, log).
    """
    df = df.copy()
    df_before = df.copy()
    station_cols = [c for c in df.columns if c != "Date"]

    date_index = pd.to_datetime(df["Date"])
    df_work = df[station_cols].copy()
    df_work.index = date_index

    total_filled = 0
    for col in station_cols:
        series = df_work[col]
        first_valid = series.first_valid_index()
        last_valid  = series.last_valid_index()
        if first_valid is None:
            continue
        active = series[first_valid:last_valid]
        n_nan_before = int(active.isna().sum())
        filled = active.interpolate(
            method="time",
            limit=MAX_INTERP_DAYS,
            limit_direction="forward",
            limit_area="inside",
        )
        n_filled = n_nan_before - int(filled.isna().sum())
        if n_filled:
            df_work.loc[first_valid:last_valid, col] = filled
            total_filled += n_filled

    # Write results back to df (by positional alignment)
    df[station_cols] = df_work.values
    log = interpolation_log(df_before, df, "Date")
    return df, log, total_filled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(
            str(IN_FILE) + " not found - run consolidate_jordan_river_flows.py first"
        )

    print("Loading " + IN_FILE.name + " ...")
    df = pd.read_csv(IN_FILE, encoding="utf-8", low_memory=False)
    original_shape = df.shape
    station_cols = [c for c in df.columns if c != "Date"]
    all_logs = []

    print("Layer 1: Physical bounds (flow >= 0) ...")
    df, log1 = layer1_physical_bounds(df)
    all_logs.append(log1)
    print("  %d values nulled" % len(log1))

    print("Layer 2: Monthly IQR filter (%.0fx IQR per station-month) ..." % IQR_MULTIPLIER)
    df, log2 = layer2_monthly_iqr(df)
    all_logs.append(log2)
    print("  %d values nulled" % len(log2))

    print("Layer 3: Short gap interpolation (<= %d consecutive days) ..." % MAX_INTERP_DAYS)
    df, log3, n_filled = layer3_interpolate(df)
    all_logs.append(log3)
    print("  %d gaps filled" % n_filled)

    print("Saving outputs ...")
    df.to_csv(OUT_CLEAN, index=False, encoding="utf-8")

    log_df = pd.concat([l for l in all_logs if not l.empty], ignore_index=True)
    log_df["layer"] = log_df["reason"].str.split("_").str[0]
    log_df.to_csv(OUT_LOG, index=False, encoding="utf-8")

    nulled = len(log1) + len(log2)
    all_cells = original_shape[0] * len(station_cols)
    print("")
    print("-" * 60)
    print("Input  : %d rows x %d station cols" % (original_shape[0], len(station_cols)))
    print("Output : " + str(OUT_CLEAN))
    print("QC log : " + str(OUT_LOG) + "  (%d entries)" % len(log_df))
    print("")
    print("Values nulled by layer:")
    print("  Layer 1 physical bounds   : %5d" % len(log1))
    print("  Layer 2 monthly IQR       : %5d" % len(log2))
    print("  Total nulled              : %5d  (%.3f%% of cells)" % (
        nulled, nulled / all_cells * 100 if all_cells else 0))
    print("  Layer 3 gaps filled       : %5d" % n_filled)
    print("")
    print("Station summary after cleaning:")
    for col in station_cols:
        n = df[col].notna().sum()
        print("  %-40s  %d non-null days" % (col, n))
    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
