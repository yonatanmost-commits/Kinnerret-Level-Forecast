# -*- coding: utf-8 -*-
"""
01_ingest_met_data.py  -  Step 1 of 2 - Meteorological Data Pipeline

Reads all raw multi-station CSV files from Raw Data/Meteorological Data,
renames Hebrew columns to English slugs, maps station names to English,
and streams everything to a single long-format CSV.

All values are kept as strings at this stage (type conversion and
pivot are done in step 2) to keep this script fast (~15 seconds
on a typical machine).

Output
------
<temp_dir>/met_data_long.csv   (intermediate - consumed by step 2)
    Columns: station | datetime | 15 numeric params | wind_speed_max10min_time

Usage
-----
    python Automation/01_ingest_met_data.py
"""

import pathlib
import tempfile
import pandas as pd

BASE_DIR  = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR   = BASE_DIR / "Raw Data" / "Meteorological Data"
TEMP_DIR  = pathlib.Path(tempfile.gettempdir())
OUT_FILE  = TEMP_DIR / "met_data_long.csv"

# Hebrew column header  ->  English slug
COLUMN_MAP = {
    "תחנה":                                                      "station",
    "תאריך ושעה (שעון קיץ)":                                    "datetime",
    'קרינה גלובלית (וואט/מ"ר)':                                 "global_radiation_Wm2",
    "לחות יחסית (%)":                                            "relative_humidity_pct",
    "טמפרטורה (C°)":                                             "temperature_C",
    "טמפרטורת מקסימום (C°)":                                    "temperature_max_C",
    "טמפרטורת מינימום (C°)":                                    "temperature_min_C",
    "טמפרטורה ליד הקרקע (C°)":                                  "temperature_ground_C",
    "טמפרטורה לחה (C°)":                                        "temperature_wet_C",
    "כיוון הרוח (מעלות)":                                        "wind_dir_deg",
    "כיוון המשב העליון (מעלות)":                                 "wind_gust_dir_deg",
    "מהירות רוח (מטר לשניה)":                                   "wind_speed_ms",
    "מהירות רוח דקתית מקסימלית (מטר לשניה)":                   "wind_speed_max1min_ms",
    "מהירות רוח 10 דקתית מקסימלית (מטר לשניה)":                "wind_speed_max10min_ms",
    "זמן סיום מהירות רוח 10 דקתית מקסימלית  (hhmm)":           "wind_speed_max10min_time",
    "מהירות המשב העליון (מטר לשניה)":                           "wind_gust_speed_ms",
    "סטיית התקן של כיוון הרוח (מעלות)":                        "wind_dir_std_deg",
    'כמות גשם (מ"מ)':                                            "rainfall_mm",
}

# Hebrew station name  ->  English slug
STATION_MAP = {
    "לב כנרת":   "lev_kinneret",
    "כפר נחום":  "kfar_nachum",
    "טבריה":     "tiberias",
    "בית ציידה": "beit_tzaida",
    "צמח":       "tzamach",
}

COL_ORDER = [
    "station", "datetime",
    "global_radiation_Wm2", "relative_humidity_pct",
    "temperature_C", "temperature_max_C", "temperature_min_C",
    "temperature_ground_C", "temperature_wet_C",
    "wind_dir_deg", "wind_gust_dir_deg",
    "wind_speed_ms", "wind_speed_max1min_ms", "wind_speed_max10min_ms",
    "wind_gust_speed_ms", "wind_dir_std_deg", "rainfall_mm",
    "wind_speed_max10min_time",
]


def main():
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("No CSV files in " + str(RAW_DIR))

    print("Found %d source files" % len(csv_files))
    print("Writing long-format CSV to: " + str(OUT_FILE))
    total = 0

    with open(OUT_FILE, "w", encoding="utf-8-sig", newline="") as fout:
        header_done = False
        for f in csv_files:
            df = pd.read_csv(f, encoding="utf-8-sig", dtype=str,
                             na_values=[""], keep_default_na=False)
            df.columns = df.columns.str.strip()
            df = df.rename(columns=COLUMN_MAP)
            df["station"] = df["station"].map(STATION_MAP)
            df = df.dropna(subset=["station"])
            for col in COL_ORDER:
                if col not in df.columns:
                    df[col] = ""
            df[COL_ORDER].to_csv(fout, index=False, header=not header_done)
            header_done = True
            total += len(df)
            print("  ok  %-45s  %7d rows" % (f.name, len(df)))

    print("")
    print("-" * 60)
    print("Long-format CSV: " + str(OUT_FILE))
    print("Total rows     : %d" % total)
    print("-" * 60)
    print("Done. Run 02_pivot_wide_met_data.py next.")


if __name__ == "__main__":
    main()
