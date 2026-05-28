import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

SILVER_DEFAULT_FROM = date(2024, 1, 1)
_URL = "https://kineret.org.il/miflasim/?fromdate={}&todate={}&Frequency=daily"
_PATTERN = re.compile(
    r'new Date\((\d{4}),\s*(\d+),\s*(\d+)\);\r?\ndata\.addRow\(\[date,\s*([-\d.]+)'
)


def _fetch_html(from_date: date, to_date: date) -> str:
    r = requests.get(
        _URL.format(from_date, to_date),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    return r.text


def _parse_levels(html: str) -> list:
    return [
        (date(int(yr), int(mo) + 1, int(dy)), float(lvl))
        for yr, mo, dy, lvl in _PATTERN.findall(html)
    ]


def fetch_new_levels(silver_csv_path: Path) -> pd.DataFrame:
    silver_csv_path = Path(silver_csv_path)
    if silver_csv_path.exists():
        df_existing = pd.read_csv(silver_csv_path, parse_dates=["date"])
        max_ts = df_existing["date"].max()
        if pd.isna(max_ts):
            last_date = SILVER_DEFAULT_FROM - timedelta(days=1)
        else:
            last_date = max_ts.date()
    else:
        last_date = SILVER_DEFAULT_FROM - timedelta(days=1)

    from_date = last_date + timedelta(days=1)
    if from_date > date.today():
        return pd.DataFrame(columns=["date", "kinneret_level"])

    html = _fetch_html(from_date, date.today())
    pairs = _parse_levels(html)
    if not pairs:
        return pd.DataFrame(columns=["date", "kinneret_level"])
    df = pd.DataFrame(pairs, columns=["date", "kinneret_level"])
    df = df[df["date"] > last_date]
    return df


def append_to_silver(df: pd.DataFrame, silver_csv_path: Path) -> int:
    if df.empty:
        return 0
    silver_csv_path = Path(silver_csv_path)
    silver_csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(silver_csv_path, mode="a", header=not silver_csv_path.exists(), index=False)
    return len(df)
