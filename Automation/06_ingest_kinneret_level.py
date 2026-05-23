# -*- coding: utf-8 -*-
"""
06_ingest_kinneret_level.py  -  Kinneret Level Ingestion

Reads the raw Kinneret water-level survey CSV, standardises column names
and date format, and writes a clean silver file.

No QC or outlier removal is applied -- the source data is complete (zero
NaN values) and physically consistent across its full 1966-2026 range.
Large single-day rises (up to 0.23 m/day) occur during winter flood
events and are genuine signal, not recording errors.

Note on measurement frequency:
    1966-1989 : weekly surveys (median 7-day gap) -- gaps are structural
    1990-2026 : daily readings -- effectively continuous

Output columns:
    date            YYYY-MM-DD
    kinneret_level  Water level in metres below mean sea level (negative).
                    Historical range: -208.2 m (high) to -214.87 m (low).

Output
------
Silver Data/Kinneret Level/kinneret_level.csv

Usage
-----
    python Automation/06_ingest_kinneret_level.py
"""

import pathlib
import pandas as pd

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR    = BASE_DIR / "Raw Data" / "Kinneret_Level"
SILVER_DIR = BASE_DIR / "Silver Data" / "Kinneret Level"
OUT_FILE   = SILVER_DIR / "kinneret_level.csv"


def _read_level_file(path: pathlib.Path) -> pd.DataFrame:
    """
    Read a single raw level CSV and return a tidy (date, kinneret_level) frame.

    Handles two source formats:
      Format A  – columns: Survey_Date (DD/M/YYYY), Kinneret_Level
                  (legacy IHS export)
      Format B  – columns: Date (YYYY-MM-DD), Level
                  (Miflas / kineret.org.il export; may have a trailing
                  footer line beginning with whitespace)
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, skip_blank_lines=True)
    df.columns = df.columns.str.strip()

    # Drop pure-whitespace / footer rows (e.g. "Downloaded from: ...")
    df = df[df.iloc[:, 0].str.strip().ne("")]
    df = df[~df.iloc[:, 0].str.strip().str.startswith("Downloaded")]

    if "Survey_Date" in df.columns and "Kinneret_Level" in df.columns:
        # Format A
        date  = pd.to_datetime(df["Survey_Date"].str.strip(),
                               format="%d/%m/%Y", errors="coerce")
        level = pd.to_numeric(df["Kinneret_Level"].str.strip(), errors="coerce")
    elif "Date" in df.columns and "Level" in df.columns:
        # Format B
        date  = pd.to_datetime(df["Date"].str.strip(),
                               format="%Y-%m-%d", errors="coerce")
        level = pd.to_numeric(df["Level"].str.strip(), errors="coerce")
    else:
        # Not a level file (e.g. bathymetric curve) — return empty frame
        return pd.DataFrame(columns=["date", "kinneret_level"])

    out = pd.DataFrame({"date": date, "kinneret_level": level})
    return out


def main():
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("No CSV files found in " + str(RAW_DIR))

    frames = []
    for f in csv_files:
        print("  Reading " + f.name + " ...")
        frames.append(_read_level_file(f))

    raw = pd.concat(frames, ignore_index=True)

    # parse already done in _read_level_file; just ensure types are clean
    raw["date"]           = pd.to_datetime(raw["date"], errors="coerce")
    raw["kinneret_level"] = pd.to_numeric(raw["kinneret_level"], errors="coerce")

    # Drop rows that couldn't be parsed (should be none)
    n_bad = raw[["date", "kinneret_level"]].isna().any(axis=1).sum()
    if n_bad:
        print("  Warning: %d row(s) failed to parse and were dropped." % n_bad)
    raw = raw.dropna(subset=["date", "kinneret_level"])

    # Deduplicate: keep first reading per date
    dupes = raw.duplicated(subset=["date"]).sum()
    if dupes:
        print("  Note: %d duplicate date(s) found -- keeping first." % dupes)
    raw = raw.drop_duplicates(subset=["date"], keep="first")

    out = (
        raw[["date", "kinneret_level"]]
        .sort_values("date")
        .reset_index(drop=True)
    )
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_FILE, index=False, encoding="utf-8")

    print("")
    print("-" * 60)
    print("Output : " + str(OUT_FILE))
    print("Rows   : %d" % len(out))
    print("Range  : %s  to  %s" % (out["date"].min(), out["date"].max()))
    print("Level  : %.3f m  (min)  to  %.3f m  (max)" % (
        out["kinneret_level"].min(), out["kinneret_level"].max()))
    print("NaN    : %d" % out["kinneret_level"].isna().sum())
    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
