"""
fix_tym_silver.py
=================
One-shot repair for the TYM silver parquet and CSV.

ROOT CAUSE
----------
pipeline_shared.process_chunk() drops the `תאריך` column before returning.
When append_to_parquet() concatenates existing data (which has `תאריך`) with
new data (which doesn't), pandas fills NaN for the missing column.  The silver
CSV suffers an even worse column-shift bug: 23-column appended data is written
positionally into a 24-column file, shifting every sensor column left by one.

WHAT THIS SCRIPT DOES
---------------------
1. Reads the silver parquet with duckdb (or pyarrow as fallback).
2. Fills every NULL `תאריך` by converting the `Date&Time` JMP epoch to the
   existing string format  dd/mm/yyyy H:MM  (e.g. "16/04/2026 7:00").
3. Writes the fixed parquet back (sorted by Date&Time, de-duplicated).
4. Rebuilds the silver CSV from the fixed parquet — correct column order,
   correct תאריך for every row, Date&Time as human-readable string.
5. Prints a short summary of what was changed.

REQUIREMENTS
------------
  pip install duckdb pandas pyarrow   (pyarrow is needed to write parquet)
"""

from pathlib import Path
import pandas as pd
import duckdb

# ── paths ────────────────────────────────────────────────────────────────────
DATA_LAKE   = Path(r"C:\Users\yonatanm\ARW Group\TRIPLE T - Documents\(DL) Data Lake")
SILVER_DIR  = DATA_LAKE / "T1066P (TYM) - TAYA Monitoring Data" / "TYM_Silver"
PARQUET     = SILVER_DIR / "מערכת ניטור-דו_ח מפלסים_silver.parquet"
CSV_OUT     = SILVER_DIR / "מערכת ניטור-דו_ח מפלסים_silver.csv"

JMP_ORIGIN  = pd.Timestamp("1904-01-01")

# ── helpers ──────────────────────────────────────────────────────────────────
def jmp_to_tarich(epoch_series: pd.Series) -> pd.Series:
    """
    Convert JMP epoch (int64 seconds since 1904-01-01) to the silver
    תאריך string format: dd/mm/yyyy H:MM  (hour not zero-padded).
    """
    dt = JMP_ORIGIN + pd.to_timedelta(epoch_series.astype("int64"), unit="s")
    # Build string without zero-padded hour (matches existing values)
    date_part = dt.dt.strftime("%d/%m/%Y")
    time_part = dt.dt.hour.astype(str) + ":" + dt.dt.minute.astype(str).str.zfill(2)
    return date_part + " " + time_part


def jmp_to_dt_str(epoch_series: pd.Series) -> pd.Series:
    """JMP epoch → human-readable Date&Time string for the CSV column."""
    dt = JMP_ORIGIN + pd.to_timedelta(epoch_series.astype("int64"), unit="s")
    date_part = dt.dt.strftime("%d/%m/%Y")
    time_part = dt.dt.hour.astype(str) + ":" + dt.dt.minute.astype(str).str.zfill(2)
    return date_part + " " + time_part


# ── step 1: read parquet ─────────────────────────────────────────────────────
print("Reading parquet …")
con = duckdb.connect()
df  = con.execute(f"SELECT * FROM read_parquet('{PARQUET.as_posix()}')").df()
print(f"  Loaded {len(df):,} rows × {len(df.columns)} columns")

before_null = df["תאריך"].isna().sum()
print(f"  תאריך NULL before fix: {before_null:,} rows")

# ── step 2: fill NULL תאריך from Date&Time ──────────────────────────────────
print("Filling NULL תאריך values …")
null_mask = df["תאריך"].isna()
df.loc[null_mask, "תאריך"] = jmp_to_tarich(df.loc[null_mask, "Date&Time"])

after_null = df["תאריך"].isna().sum()
print(f"  תאריך NULL after fix:  {after_null:,} rows")

# ── step 3: sort & de-duplicate ──────────────────────────────────────────────
df["Date&Time"] = df["Date&Time"].astype("int64")
df = df.drop_duplicates(subset=["Date&Time"]).sort_values("Date&Time").reset_index(drop=True)
print(f"  Rows after de-dup + sort: {len(df):,}")

# ── step 4: write fixed parquet ──────────────────────────────────────────────
print(f"Writing parquet → {PARQUET.name} …")
# Ensure Date&Time is first column
cols = ["Date&Time"] + [c for c in df.columns if c != "Date&Time"]
df[cols].to_parquet(PARQUET, index=False, engine="pyarrow")
print("  Parquet written ✓")

# ── step 5: rebuild CSV from fixed parquet ───────────────────────────────────
print(f"Rebuilding CSV → {CSV_OUT.name} …")
csv_df = df[cols].copy()
csv_df["Date&Time"] = jmp_to_dt_str(csv_df["Date&Time"])

# Column order: Date&Time, תאריך, then all sensor columns
col_order = ["Date&Time", "תאריך"] + [c for c in cols if c not in ("Date&Time", "תאריך")]
csv_df = csv_df[col_order]

csv_df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
print(f"  CSV written ✓  ({len(csv_df):,} rows × {len(csv_df.columns)} columns)")

# ── summary ──────────────────────────────────────────────────────────────────
print()
print("=== SUMMARY ===")
print(f"  Rows fixed (תאריך was NULL): {before_null - after_null:,}")
print(f"  Date range: {csv_df['Date&Time'].iloc[0]}  →  {csv_df['Date&Time'].iloc[-1]}")
print(f"  Parquet: {PARQUET}")
print(f"  CSV:     {CSV_OUT}")
print()
print("Done. Re-run 04_silver_processor.py after applying the pipeline patch")
print("(patch_pipeline_shared.py) to prevent this issue on future appends.")
