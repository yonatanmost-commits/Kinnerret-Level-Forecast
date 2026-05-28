import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

MET_DEFAULT_FROM = date(2024, 1, 1)
_STATION_ID = "115"
_ARCHIVE_URL = (
    "https://ims.gov.il/he/archive_data/T-10/{sid}/7/{from_h}/{to_h}/1/"
)
_CKAN_BASE = "http://eapi.data.gov.il/api/action/datastore_search"
_CHANNELS = ["1", "2", "4", "5", "6", "7", "8", "9", "10", "12", "13"]

# (channel_id, aggregation, output_column_name)
CHANNEL_AGG = [
    ("1",  "sum",  "lev_kinneret_rainfall_mm_sum"),
    ("2",  "max",  "lev_kinneret_wind_gust_speed_ms_max"),
    ("4",  "mean", "lev_kinneret_wind_speed_ms_mean"),
    ("4",  "max",  "lev_kinneret_wind_speed_ms_max"),
    ("5",  "mean", "lev_kinneret_wind_dir_deg_mean"),
    ("6",  "mean", "lev_kinneret_wind_dir_std_deg_mean"),
    ("7",  "mean", "lev_kinneret_temperature_C_mean"),
    ("8",  "mean", "lev_kinneret_relative_humidity_pct_mean"),
    ("9",  "max",  "lev_kinneret_temperature_C_max"),
    ("9",  "max",  "lev_kinneret_temperature_max_C_max"),
    ("10", "min",  "lev_kinneret_temperature_C_min"),
    ("10", "min",  "lev_kinneret_temperature_min_C_min"),
    ("12", "max",  "lev_kinneret_wind_speed_max1min_ms_max"),
    ("13", "max",  "lev_kinneret_wind_speed_max10min_ms_max"),
]


def _discover_resource_id(cache_path: Path) -> str:
    cache_path = Path(cache_path)
    if cache_path.exists():
        return json.loads(cache_path.read_text())["resource_id"]

    today_str = date.today().strftime("%Y%m%d")
    url = _ARCHIVE_URL.format(
        sid=_STATION_ID,
        from_h=f"{today_str}00",
        to_h=f"{today_str}23",
    )
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    data = r.json()

    resource_id = data.get("resource_id") or data.get("resourceId")
    if not resource_id:
        basic_url = data.get("basic_url", "")
        m = re.search(r"resource_id=([a-f0-9\-]{10,})", basic_url)
        if m:
            resource_id = m.group(1)

    if not resource_id:
        raise ValueError(
            "Could not auto-discover IMS resource_id. "
            f"Inspect response at: {url}\n"
            f"Then create {cache_path} manually: "
            '{"resource_id": "YOUR_ID_HERE"}'
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"resource_id": resource_id}))
    return resource_id


def _fetch_channel_data(resource_id: str, from_date: date, to_date: date) -> pd.DataFrame:
    days = pd.date_range(from_date, to_date, freq="D")
    filters = json.dumps({
        "year":    sorted({str(d.year)  for d in days}),
        "month":   sorted({str(d.month) for d in days}, key=int),
        "day":     sorted({str(d.day)   for d in days}, key=int),
        "stn_num": [_STATION_ID],
    })
    params = {
        "resource_id": resource_id,
        "limit": 150000,
        "fields": "stn_num,time_obs," + ",".join(_CHANNELS),
        "filters": filters,
        "sort": "time_obs, stn_num",
    }
    r = requests.get(_CKAN_BASE, params=params, timeout=60)
    r.raise_for_status()
    records = r.json().get("result", {}).get("records", [])
    return pd.DataFrame(records) if records else pd.DataFrame()


def _aggregate_daily(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        return pd.DataFrame()
    raw_df = raw_df.copy()
    raw_df["date"] = pd.to_datetime(raw_df["time_obs"]).dt.date
    rows = []
    for day_date, day_df in raw_df.groupby("date"):
        row = {"date": day_date}
        for ch, agg, col in CHANNEL_AGG:
            if ch in day_df.columns:
                vals = pd.to_numeric(day_df[ch], errors="coerce")
                if agg == "sum":
                    row[col] = vals.sum()
                elif agg == "max":
                    row[col] = vals.max()
                elif agg == "min":
                    row[col] = vals.min()
                elif agg == "mean":
                    row[col] = vals.mean()
        rows.append(row)
    return pd.DataFrame(rows)


def fetch_new_met(silver_csv_path: Path) -> pd.DataFrame:
    silver_csv_path = Path(silver_csv_path)
    if silver_csv_path.exists():
        df_tail = pd.read_csv(silver_csv_path, encoding="utf-8-sig", parse_dates=["date"])
        max_ts = df_tail["date"].max()
        last_date = MET_DEFAULT_FROM - timedelta(days=1) if pd.isna(max_ts) else max_ts.date()
    else:
        last_date = MET_DEFAULT_FROM - timedelta(days=1)

    from_date = last_date + timedelta(days=1)
    to_date = date.today() - timedelta(days=1)
    if from_date > to_date:
        return pd.DataFrame()

    cache = Path(__file__).resolve().parent.parent / "Models" / "ims_resource_id.json"
    resource_id = _discover_resource_id(cache)
    raw_df = _fetch_channel_data(resource_id, from_date, to_date)
    df = _aggregate_daily(raw_df)
    if df.empty:
        return df
    df = df[df["date"] > last_date]
    df = df[df["date"] <= to_date]
    return df


def append_to_met_silver(df: pd.DataFrame, silver_csv_path: Path) -> int:
    if df.empty:
        return 0
    silver_csv_path = Path(silver_csv_path)
    silver_csv_path.parent.mkdir(parents=True, exist_ok=True)

    if silver_csv_path.exists():
        cols = list(pd.read_csv(silver_csv_path, encoding="utf-8-sig", nrows=0).columns)
    else:
        df.to_csv(silver_csv_path, index=False)
        return len(df)

    full = pd.DataFrame(index=range(len(df)), columns=cols)
    full["date"] = df["date"].astype(str).values
    for col in df.columns:
        if col in cols:
            full[col] = df[col].values

    full.to_csv(silver_csv_path, mode="a", header=False, index=False)
    return len(full)
