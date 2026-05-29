from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

MET_DEFAULT_FROM = date(2024, 1, 1)

_LAT = 32.7724
_LON = 35.5458
_TZ  = "Asia/Jerusalem"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo daily variable → (silver_columns, unit_factor)
# unit_factor converts Open-Meteo units to silver CSV units (wind: km/h → m/s = /3.6)
_VAR_MAP = [
    ("temperature_2m_max",          ["lev_kinneret_temperature_C_max", "lev_kinneret_temperature_max_C_max"],  1.0),
    ("temperature_2m_min",          ["lev_kinneret_temperature_C_min", "lev_kinneret_temperature_min_C_min"],  1.0),
    ("temperature_2m_mean",         ["lev_kinneret_temperature_C_mean"],                                        1.0),
    ("precipitation_sum",           ["lev_kinneret_rainfall_mm_sum"],                                           1.0),
    ("relative_humidity_2m_mean",   ["lev_kinneret_relative_humidity_pct_mean"],                                1.0),
    ("wind_speed_10m_mean",         ["lev_kinneret_wind_speed_ms_mean"],                                        1/3.6),
    ("wind_speed_10m_max",          ["lev_kinneret_wind_speed_ms_max", "lev_kinneret_wind_speed_max10min_ms_max"], 1/3.6),
    ("wind_gusts_10m_max",          ["lev_kinneret_wind_gust_speed_ms_max", "lev_kinneret_wind_speed_max1min_ms_max"], 1/3.6),
    ("wind_direction_10m_dominant", ["lev_kinneret_wind_dir_deg_mean", "lev_kinneret_wind_gust_dir_deg_mean"],  1.0),
]


def _fetch_openmeteo(from_date: date, to_date: date) -> pd.DataFrame:
    daily_vars = [v for v, _, _ in _VAR_MAP]
    r = requests.get(_ARCHIVE_URL, params={
        "latitude":  _LAT,
        "longitude": _LON,
        "start_date": str(from_date),
        "end_date":   str(to_date),
        "daily":     ",".join(daily_vars),
        "timezone":  _TZ,
    }, timeout=60)
    r.raise_for_status()
    data = r.json().get("daily", {})
    if not data or not data.get("time"):
        return pd.DataFrame()

    df = pd.DataFrame({"date": pd.to_datetime(data["time"]).date})
    for var, cols, factor in _VAR_MAP:
        if var in data:
            vals = pd.to_numeric(pd.Series(data[var]), errors="coerce") * factor
            for col in cols:
                df[col] = vals.values
    return df


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

    df = _fetch_openmeteo(from_date, to_date)
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
