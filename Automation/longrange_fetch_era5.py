# Automation/longrange_fetch_era5.py
"""
longrange_fetch_era5.py - Deep ERA5 daily history for the Kinneret point via the
Open-Meteo archive API (ERA5-backed, 1940-present). Mirrors kinneret_app/met_update.py.

Writes Silver Data/Meteorological/era5_kinneret_daily.csv with tidy columns:
  date, temp_max_C, temp_min_C, rainfall_mm, radiation_MJm2, humidity_pct, wind_speed_ms
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests

_LAT = 32.7724    # Open-Meteo grid point (same as met_update.py)
_LON = 35.5458
_TZ = "Asia/Jerusalem"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_START = date(1960, 1, 1)

OUT_PATH = (Path(__file__).resolve().parent.parent
            / "Silver Data" / "Meteorological" / "era5_kinneret_daily.csv")

# Open-Meteo daily var -> (tidy column, unit factor)
_VAR_MAP = [
    ("temperature_2m_max",        "temp_max_C",     1.0),
    ("temperature_2m_min",        "temp_min_C",     1.0),
    ("precipitation_sum",         "rainfall_mm",    1.0),
    ("shortwave_radiation_sum",   "radiation_MJm2", 1.0),   # already MJ/m2
    ("relative_humidity_2m_mean", "humidity_pct",   1.0),
    ("wind_speed_10m_mean",       "wind_speed_ms",  1 / 3.6),  # km/h -> m/s
]


def fetch_era5_daily(from_date: date, to_date: date) -> pd.DataFrame:
    daily_vars = [v for v, _, _ in _VAR_MAP]
    r = requests.get(_ARCHIVE_URL, params={
        "latitude": _LAT, "longitude": _LON,
        "start_date": str(from_date), "end_date": str(to_date),
        "daily": ",".join(daily_vars), "timezone": _TZ,
    }, timeout=120)
    r.raise_for_status()
    data = r.json().get("daily", {})
    if not data or not data.get("time"):
        return pd.DataFrame()
    out = pd.DataFrame({"date": pd.to_datetime(data["time"]).date})
    for var, col, factor in _VAR_MAP:
        if var in data:
            out[col] = pd.to_numeric(pd.Series(data[var]), errors="coerce") * factor
    return out


def main():
    df = fetch_era5_daily(DEFAULT_START, date.today())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} rows ({df['date'].min()}..{df['date'].max()}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
