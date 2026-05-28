import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kinneret_app"))

import pandas as pd
from kinneret_level import append_to_silver, fetch_new_levels

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SILVER_CSV = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"


def main():
    if SILVER_CSV.exists():
        _max = pd.read_csv(SILVER_CSV, parse_dates=["date"])["date"].max()
        last = None if pd.isna(_max) else _max.date()
        if last:
            print(f"Fetching Kinneret levels since {last} ...")
        else:
            print("Fetching Kinneret levels (silver CSV empty, fetching from 2024-01-01) ...")
    else:
        last = None
        print("Fetching Kinneret levels (silver CSV not found, fetching from 2024-01-01) ...")

    df = fetch_new_levels(SILVER_CSV)

    if df.empty:
        print(f"  Already up to date (last: {last}). Nothing to fetch.")
        return

    n = append_to_silver(df, SILVER_CSV)
    d_min = df["date"].min()
    d_max = df["date"].max()
    print(f"  Added {n} new readings ({d_min} to {d_max})")
    print(f"  Silver CSV updated: Silver Data/Kinneret Level/kinneret_level.csv")


if __name__ == "__main__":
    main()
