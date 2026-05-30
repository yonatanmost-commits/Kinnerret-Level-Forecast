# -*- coding: utf-8 -*-
"""
02_pivot_wide_met_data.py  -  Step 2 of 2 - Meteorological Data Pipeline

Loads the long-format CSV produced by step 1, cleans types (replace "-"
sentinel with NaN, parse datetimes, cast numerics), then pivots to a wide
table where every column is  {station}_{parameter}.

One row per 10-minute timestamp across all stations.  Stations not
operating during a period have NaN in their columns.  Duplicate
(datetime, station) pairs are resolved by keeping the first value.

Output
------
Silver Data/met_data_wide.csv
    - One row per 10-minute timestamp (2012-06-01 to present)
    - 67 columns: datetime + 66 station-parameter cols
    - Column naming: {station}_{parameter}
      stations : beit_tzaida, kfar_nachum, lev_kinneret, tiberias, tzamach
      parameters: global_radiation_Wm2, relative_humidity_pct, temperature_C,
                  temperature_max_C, temperature_min_C, temperature_ground_C,
                  temperature_wet_C, wind_dir_deg, wind_gust_dir_deg,
                  wind_speed_ms, wind_speed_max1min_ms, wind_speed_max10min_ms,
                  wind_gust_speed_ms, wind_dir_std_deg, rainfall_mm,
                  wind_speed_max10min_time

Usage
-----
    python Automation/02_pivot_wide_met_data.py
"""

import pathlib
import tempfile
import pandas as pd

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
SILVER_DIR = BASE_DIR / "Silver Data"
SILVER_DIR.mkdir(parents=True, exist_ok=True)
IN_FILE    = pathlib.Path(tempfile.gettempdir()) / "met_data_long.csv"
OUT_FILE   = SILVER_DIR / "met_data_wide.csv"

NUMERIC_COLS = [
    "global_radiation_Wm2", "relative_humidity_pct",
    "temperature_C", "temperature_max_C", "temperature_min_C",
    "temperature_ground_C", "temperature_wet_C",
    "wind_dir_deg", "wind_gust_dir_deg",
    "wind_speed_ms", "wind_speed_max1min_ms", "wind_speed_max10min_ms",
    "wind_gust_speed_ms", "wind_dir_std_deg", "rainfall_mm",
]
STRING_COLS = ["wind_speed_max10min_time"]
PARAM_ORDER = NUMERIC_COLS + STRING_COLS


def pivot_params(df, params):
    cols = [p for p in params if p in df.columns]
    wide = (df[["datetime", "station"] + cols]
            .pivot_table(index="datetime", columns="station",
                         values=cols, aggfunc="last"))
    # Flatten MultiIndex (param, station) -> station_param
    wide.columns = ["%s_%s" % (st, p) for p, st in wide.columns]
    return wide


def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(
            str(IN_FILE) + " not found.\nRun 01_ingest_met_data.py first."
        )

    print("Loading " + str(IN_FILE) + " ...")
    df = pd.read_csv(IN_FILE, encoding="utf-8-sig", dtype=str,
                     na_values=[""], keep_default_na=False)

    # Clean: replace "-" sentinel, parse datetime, cast numerics
    df = df.replace("-", pd.NA)
    df["datetime"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M", errors="coerce")
    df = df.dropna(subset=["datetime", "station"])
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    stations = sorted(df["station"].unique())
    print("  %d rows  |  stations: %s" % (len(df), stations))

    # Pivot to wide
    print("Pivoting ...")
    wide = pd.concat([pivot_params(df, NUMERIC_COLS),
                      pivot_params(df, STRING_COLS)], axis=1)

    # Order columns: station groups in alphabetical order, PARAM_ORDER within each
    ordered = []
    for st in stations:
        for p in PARAM_ORDER:
            col = "%s_%s" % (st, p)
            if col in wide.columns:
                ordered.append(col)
    ordered += [c for c in wide.columns if c not in ordered]
    wide = wide[ordered].reset_index().sort_values("datetime").reset_index(drop=True)

    print("Saving " + str(OUT_FILE) + " ...")
    wide.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    # Summary
    print("")
    print("-" * 60)
    print("Output : " + str(OUT_FILE))
    print("Rows   : %d  (10-min timestamps)" % len(wide))
    print("Columns: %d  (datetime + %d station-param cols)" % (len(wide.columns), len(wide.columns) - 1))
    print("Range  : %s  to  %s" % (wide["datetime"].min(), wide["datetime"].max()))
    print("")
    print("Station coverage:")
    for st in stations:
        cols = [c for c in wide.columns if c.startswith(st + "_")]
        pct  = wide[cols].notna().mean().mean() * 100
        print("  %-15s  %2d params  avg fill: %.1f%%" % (st, len(cols), pct))
    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
