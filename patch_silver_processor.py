"""
patch_silver_processor.py
=========================
Patches 04_silver_processor.py to fix the תאריך NaN bug.

ROOT CAUSE
----------
pipeline_shared.process_chunk() drops the raw datetime column (e.g. תאריך)
before returning.  When append_to_parquet() concatenates existing parquet rows
(which have תאריך) with new processed rows (which don't), pandas fills the
missing column with NaN for every newly-appended row.

THE FIX
-------
After the concat inside append_to_parquet(), detect any object-dtype column
(a datetime-source column like תאריך) that has NaN only in new rows, and
fill those NaN values by converting the Date&Time JMP epoch back to a datetime
string in the same dd/mm/yyyy H:MM format already used in existing rows.

HOW TO RUN
----------
    python patch_silver_processor.py

The script edits 04_silver_processor.py in-place and saves a .bak backup first.
"""

from pathlib import Path

AUTOMATION = Path(r"C:\Users\yonatanm\ARW Group\TRIPLE T - Documents\(DL) Data Lake\01_Automation")
TARGET = AUTOMATION / "04_silver_processor.py"

OLD_BLOCK = '''\
    if parquet_path.exists():
        try:
            existing_df = pd.read_parquet(parquet_path)
            existing_df["Date&Time"] = existing_df["Date&Time"].astype("int64")
            existing_clean = existing_df[
                ~existing_df["Date&Time"].isin(new_df["Date&Time"])
            ]
            combined = pd.concat([existing_clean, new_df], ignore_index=True)
        except Exception as exc:
            log.warning("  Could not read existing Parquet: %s -- writing fresh.", exc)
            combined = new_df
    else:
        combined = new_df

    combined = combined.sort_values("Date&Time")
    cols     = ["Date&Time"] + [c for c in combined.columns if c != "Date&Time"]
    combined = combined[cols]
    combined.to_parquet(parquet_path, index=False, engine="pyarrow")'''

NEW_BLOCK = '''\
    if parquet_path.exists():
        try:
            existing_df = pd.read_parquet(parquet_path)
            existing_df["Date&Time"] = existing_df["Date&Time"].astype("int64")
            existing_clean = existing_df[
                ~existing_df["Date&Time"].isin(new_df["Date&Time"])
            ]
            combined = pd.concat([existing_clean, new_df], ignore_index=True)
        except Exception as exc:
            log.warning("  Could not read existing Parquet: %s -- writing fresh.", exc)
            combined = new_df
    else:
        combined = new_df

    # ── Fill any datetime-source columns (e.g. תאריך) that are missing in new
    # rows but present in existing rows.  process_chunk() drops the raw datetime
    # column before returning, so a concat of old (has תאריך) + new (no תאריך)
    # leaves NaN in that column for every newly-appended row.  Derive it from
    # the Date&Time JMP epoch so the parquet stays fully populated.
    _jmp_origin = pd.Timestamp("1904-01-01")
    for col in combined.columns:
        if col == "Date&Time":
            continue
        null_mask = combined[col].isna()
        if not null_mask.any():
            continue
        # Only auto-fill if the column holds string values in existing rows
        # (i.e. it\'s a datetime-source column, not a numeric sensor column)
        non_null_sample = combined.loc[~null_mask, col]
        if non_null_sample.empty:
            continue
        if pd.api.types.is_object_dtype(non_null_sample) or non_null_sample.dtype == object:
            # Derive timestamp string from JMP epoch: dd/mm/yyyy H:MM (no zero-padded hour)
            dt = _jmp_origin + pd.to_timedelta(
                combined.loc[null_mask, "Date&Time"].astype("int64"), unit="s"
            )
            date_part = dt.dt.strftime("%d/%m/%Y")
            time_part = dt.dt.hour.astype(str) + ":" + dt.dt.minute.astype(str).str.zfill(2)
            combined.loc[null_mask, col] = date_part + " " + time_part
            log.info("  Filled %d NaN value(s) in column \'%s\' from Date&Time.", null_mask.sum(), col)

    combined = combined.sort_values("Date&Time")
    cols     = ["Date&Time"] + [c for c in combined.columns if c != "Date&Time"]
    combined = combined[cols]
    combined.to_parquet(parquet_path, index=False, engine="pyarrow")'''


def main():
    print(f"Reading {TARGET} …")
    source = TARGET.read_text(encoding="utf-8")

    if OLD_BLOCK not in source:
        if NEW_BLOCK in source:
            print("Patch already applied — nothing to do.")
        else:
            print("ERROR: Could not find the target block to patch.")
            print("The file may have changed since this patch was written.")
            print("Apply the change manually (see patch_silver_processor.py for details).")
        return

    # Backup
    backup = TARGET.with_suffix(".py.bak")
    backup.write_text(source, encoding="utf-8")
    print(f"Backup saved → {backup.name}")

    patched = source.replace(OLD_BLOCK, NEW_BLOCK, 1)
    TARGET.write_text(patched, encoding="utf-8")
    print("Patch applied successfully ✓")
    print()
    print("What changed: append_to_parquet() now detects string-typed columns")
    print("(like תאריך) that are NaN in newly-appended rows and fills them by")
    print("converting the Date&Time JMP epoch to  dd/mm/yyyy H:MM  format.")


if __name__ == "__main__":
    main()
