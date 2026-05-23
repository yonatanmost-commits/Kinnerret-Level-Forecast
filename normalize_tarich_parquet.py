"""
normalize_tarich_parquet.py
============================
One-time cleanup: normalizes the תאריך column in the TYM silver parquet
to a uniform dd/mm/yyyy H:MM format (e.g. "16/04/2026 7:00") derived from
the Date&Time JMP epoch, so April and May rows share the same format.

Run once after fix_tym_silver.py.
"""

from pathlib import Path
import pandas as pd

PARQUET = (
    Path(r"C:\Users\yonatanm\ARW Group\TRIPLE T - Documents\(DL) Data Lake")
    / "T1066P (TYM) - TAYA Monitoring Data" / "TYM_Silver"
    / "מערכת ניטור-דו_ח מפלסים_silver.parquet"
)
JMP_ORIGIN = pd.Timestamp("1904-01-01")

def jmp_to_tarich(epoch_series):
    dt = JMP_ORIGIN + pd.to_timedelta(epoch_series.astype("int64"), unit="s")
    return dt.dt.strftime("%d/%m/%Y") + " " + dt.dt.hour.astype(str) + ":" + dt.dt.minute.astype(str).str.zfill(2)

print("Reading parquet...")
df = pd.read_parquet(PARQUET)
print(f"  {len(df):,} rows")

df["תאריך"] = jmp_to_tarich(df["Date&Time"].astype("int64"))
print(f"  תאריך normalized: {df['תאריך'].iloc[0]!r} → {df['תאריך'].iloc[-1]!r}")

df.to_parquet(PARQUET, index=False, engine="pyarrow")
print("Done ✓")
