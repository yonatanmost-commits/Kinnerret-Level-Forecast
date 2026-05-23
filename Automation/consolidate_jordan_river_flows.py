"""
consolidate_jordan_river_flows.py  -  Step 1 - Jordan River Flow Ingestion

Reads all raw CSV *and* Excel (.xlsx) files from
Raw Data/Jordan River Stations Raw Data/, handles the zero/missing sentinel,
normalises station names, drops thin stations, and pivots to a single
wide-format CSV.

This script is intentionally ingestion-only -- no outlier removal, no gap
filling.  Those steps are handled by 05_clean_jordan_river_flow.py.

--- CSV files (headerless) ---
Their columns are:
    A - record id
    B - station code
    C - station name (Hebrew)
    D - station name (English)      <- used as the column header
    E - date (DD/MM/YYYY)            <- used as the Date column
    F - daily flow volume (m^3)      <- the value we want
    G - flow rate (m^3/s)            <- used to distinguish real zeros from missing data
    H - hydrological year

--- Excel files (.xlsx) ---
Exported from the Israeli Hydrological Service with 3 title/header rows then
data.  Columns (0-indexed):
    0 - empty
    1 - station code
    2 - station name (Hebrew only)  <- mapped to English via HEBREW_TO_ENGLISH_MAP
    3 - date (datetime)
    4 - daily flow volume (m^3)     <- the value we want
    5 - average flow rate (m^3/s)   <- used for the missing sentinel
    6 - hydrological year

Column G (index 6) is used as a missing sentinel: when both F == 0 AND G == "0",
the row has no real measurement and is treated as NaN.  A genuine zero flow (rare
but valid) has a non-zero G value and is kept as 0.

Steps applied:
  1. Zero vs missing  - Only nullify when col G == "0" AND flow == 0.
  2. Station names    - Normalised to "NAME - SUBNAME" (spaced dash) convention.
  3. Thin stations    - JORDAN - UPSTREAM FROM ARIK BRIDGE (120 readings / 4 months)
                        and JORDAN - DEGANYA (1902-day internal gap) are dropped.

Output is written to `Silver Data/Jordan River Silver/jordan_river_daily_flow.csv`.
Run 05_clean_jordan_river_flow.py next to apply QC and produce the clean file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR     = PROJECT_ROOT / "Raw Data" / "Jordan River Stations Raw Data"
OUTPUT_DIR  = PROJECT_ROOT / "Silver Data" / "Jordan River Silver"
OUTPUT_FILE = OUTPUT_DIR / "jordan_river_daily_flow.csv"

# ---------------------------------------------------------------------------
# Column layout of the raw files (0-indexed)
# ---------------------------------------------------------------------------
COL_STATION = 3   # column D - English station name
COL_DATE    = 4   # column E - date DD/MM/YYYY
COL_FLOW    = 5   # column F - daily flow volume (m3/day)
COL_RATE    = 6   # column G - flow rate (m3/s); raw "0" flags missing data

RAW_COLUMN_NAMES = [
    "id",
    "station_code",
    "station_name_he",
    "station_name_en",
    "date",
    "flow_m3",
    "flow_rate",
    "hydro_year",
]

# ---------------------------------------------------------------------------
# Data-quality parameters
# ---------------------------------------------------------------------------

# Stations with too few readings or unacceptably large internal gaps.
STATIONS_TO_DROP: set = {
    "JORDAN - UPSTREAM FROM ARIK BRIDGE",  # 120 readings over 4 months (2016)
    "JORDAN - DEGANYA",                    # 1902-day gap inside 1987-1996 window
    "HAELA - GAN YAVNE",                   # unrelated catchment (Mediterranean basin)
}

# Station-name normalisation: replace bare-dash names with spaced-dash convention.
# Applied after strip(). Value is the canonical form used in the output CSV.
STATION_NAME_MAP: dict = {
    "JORDAN-BAPTISM SITE":               "JORDAN - BAPTISM SITE",
    "JORDAN-NEAR OLD BRIDGE":            "JORDAN - NEAR OLD BRIDGE",
    "JORDAN-UPSTREAM FROM ARIK BRIDGE":  "JORDAN - UPSTREAM FROM ARIK BRIDGE",
}

# Hebrew → English station-name translation for .xlsx source files, which
# carry only Hebrew names.  After translation STATION_NAME_MAP is still
# applied so the result is guaranteed to be in the spaced-dash convention.
HEBREW_TO_ENGLISH_MAP: dict = {
    "ירדן - גשר הפקק":   "JORDAN - OBSTACLE BRIDGE",
    "ירדן-אתר הטבילה":   "JORDAN-BAPTISM SITE",      # normalised below by STATION_NAME_MAP
    "האלה - גן יבנה":    "HAELA - GAN YAVNE",
}


# ---------------------------------------------------------------------------
# Step 1 - Read raw files
# ---------------------------------------------------------------------------

def read_raw_file(path: Path) -> pd.DataFrame:
    """Read a single headerless raw CSV and return a tidy DataFrame."""
    df = pd.read_csv(
        path,
        header=None,
        names=RAW_COLUMN_NAMES,
        dtype=str,
        encoding="utf-8",
        on_bad_lines="skip",
    )

    tidy = df[[
        RAW_COLUMN_NAMES[COL_STATION],
        RAW_COLUMN_NAMES[COL_DATE],
        RAW_COLUMN_NAMES[COL_FLOW],
        RAW_COLUMN_NAMES[COL_RATE],
    ]].copy()
    tidy.columns = ["station", "date", "flow_m3", "flow_rate"]

    # Normalise station names before any further processing.
    tidy["station"] = (
        tidy["station"]
        .str.strip()
        .replace(STATION_NAME_MAP)
    )

    # Drop stations that are explicitly excluded.
    tidy = tidy[~tidy["station"].isin(STATIONS_TO_DROP)]

    # Parse types.
    tidy["date"]      = pd.to_datetime(tidy["date"],    format="%d/%m/%Y", errors="coerce")
    tidy["flow_m3"]   = pd.to_numeric(tidy["flow_m3"], errors="coerce")
    tidy["flow_rate"] = tidy["flow_rate"].str.strip()   # keep as str for sentinel check

    # ------------------------------------------------------------------
    # Zero vs missing logic
    # When flow_rate == "0" AND flow_m3 == 0, the row carries no real
    # measurement (the source system uses (0, 0) as a missing marker).
    # A genuine zero flow has a non-zero flow_rate and is kept as 0.
    # ------------------------------------------------------------------
    missing_mask = (tidy["flow_rate"] == "0") & (tidy["flow_m3"] == 0)
    tidy.loc[missing_mask, "flow_m3"] = np.nan

    # Drop rows where essentials could not be parsed.
    tidy = tidy.dropna(subset=["date", "station"])

    return tidy[["station", "date", "flow_m3"]]


def read_xlsx_file(path: Path) -> pd.DataFrame:
    """
    Read a single .xlsx file exported from the Israeli Hydrological Service.

    The workbook has 3 leading rows (title + blank + Hebrew header) before data
    begins.  Only Hebrew station names are present; they are translated to English
    via HEBREW_TO_ENGLISH_MAP, then normalised with STATION_NAME_MAP.

    Returns the same tidy schema as read_raw_file: station | date | flow_m3.
    """
    df = pd.read_excel(
        path,
        sheet_name=0,
        header=None,
        skiprows=3,          # skip title, blank, and header rows
        dtype={1: str},      # station_code as string
        engine="openpyxl",
    )

    # Align to the same column layout as the CSV files
    df.columns = range(len(df.columns))
    tidy = pd.DataFrame({
        "station":   df[2].astype(str).str.strip(),
        "date":      pd.to_datetime(df[3], errors="coerce"),
        "flow_m3":   pd.to_numeric(df[4], errors="coerce"),
        "flow_rate": pd.to_numeric(df[5], errors="coerce"),
    })

    # Translate Hebrew names → English, then normalise to spaced-dash convention.
    tidy["station"] = (
        tidy["station"]
        .replace(HEBREW_TO_ENGLISH_MAP)
        .replace(STATION_NAME_MAP)
    )

    # Drop explicitly excluded stations.
    tidy = tidy[~tidy["station"].isin(STATIONS_TO_DROP)]

    # Zero vs missing: when both flow_m3 == 0 and flow_rate == 0, treat as NaN.
    missing_mask = (tidy["flow_rate"] == 0) & (tidy["flow_m3"] == 0)
    tidy.loc[missing_mask, "flow_m3"] = np.nan

    # Drop rows where essentials could not be parsed.
    tidy = tidy.dropna(subset=["date", "station"])

    return tidy[["station", "date", "flow_m3"]]


def load_all_raw(raw_dir: Path) -> pd.DataFrame:
    """Read and concatenate every CSV and XLSX file in the raw folder."""
    csv_files  = sorted(raw_dir.glob("*.csv"))
    xlsx_files = sorted(raw_dir.glob("*.xlsx"))
    all_files  = csv_files + xlsx_files

    if not all_files:
        raise FileNotFoundError(f"No CSV or XLSX files found in {raw_dir}")

    frames = []
    for path in all_files:
        print(f"  Reading {path.name} ...", flush=True)
        if path.suffix.lower() == ".xlsx":
            frames.append(read_xlsx_file(path))
        else:
            frames.append(read_raw_file(path))

    combined = pd.concat(frames, ignore_index=True)
    print(f"  -> {len(combined):,} total rows from {len(all_files)} file(s) "
          f"({len(csv_files)} CSV, {len(xlsx_files)} XLSX).")
    return combined


# ---------------------------------------------------------------------------
# Step 2 - Pivot to wide format
# ---------------------------------------------------------------------------

def pivot_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot tidy rows (date, station, flow) into wide: Date + one col per station."""
    duplicates = df.duplicated(subset=["date", "station"]).sum()
    if duplicates:
        print(f"  Note: {duplicates:,} duplicate (date, station) rows - averaging.")

    wide = (
        df.groupby(["date", "station"], as_index=False)["flow_m3"]
        .mean()
        .pivot(index="date", columns="station", values="flow_m3")
        .sort_index()
    )

    # Drop any station columns that are entirely empty (no real readings).
    empty_cols = [c for c in wide.columns if wide[c].isna().all()]
    if empty_cols:
        print(f"  Dropping {len(empty_cols)} empty station column(s): {empty_cols}")
        wide = wide.drop(columns=empty_cols)

    wide.index.name   = "Date"
    wide.columns.name = None

    return wide


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Raw data folder : {RAW_DIR}")
    print(f"Output file     : {OUTPUT_FILE}")
    print()

    # 1. Load
    print("=== Loading raw files ===")
    tidy = load_all_raw(RAW_DIR)

    # 2. Pivot
    print("\n=== Pivoting to wide format ===")
    wide = pivot_to_wide(tidy)

    # 3. Write output
    wide_out = wide.reset_index()
    wide_out["Date"] = wide_out["Date"].dt.strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Write to a sibling temp file first, then shell-rename.
    # This sidesteps an ENOENT quirk on certain network (CIFS/OneDrive)
    # mounts where open(O_CREAT) fails but rename of an existing file works.
    import subprocess, tempfile, os
    tmp = OUTPUT_FILE.with_name("_tmp_flow.csv")
    wide_out.to_csv(str(tmp), index=False, encoding="utf-8")
    subprocess.run(["mv", "-f", str(tmp), str(OUTPUT_FILE)], check=True)

    station_cols = [c for c in wide_out.columns if c != "Date"]
    print(
        f"\nWrote {len(wide_out):,} rows x {len(station_cols)} station column(s) "
        f"to {OUTPUT_FILE.name}"
    )
    print("Stations (raw, pre-QC):")
    for s in station_cols:
        non_null = wide_out[s].notna().sum()
        print(f"  - {s}: {non_null:,} daily values")
    print("\nRun 05_clean_jordan_river_flow.py next to apply QC.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
