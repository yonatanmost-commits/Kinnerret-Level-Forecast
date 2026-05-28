from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

FLOW_DEFAULT_FROM = date(2026, 4, 1)
_STATION_ID = "79"
_PAGE_URL = "https://hydro.water.gov.il/index.php/?page=hydro_obs&lang=he"
_OBS_URL = "https://hydro.water.gov.il/db_requests/get_hydro_observations_A7f3Q.php"

FLOW_COLS = [
    "Date",
    "JORDAN - BAPTISM SITE",
    "JORDAN - NEAR OLD BRIDGE",
    "JORDAN - OBSTACLE BRIDGE",
    "JORDAN - SEDE NEHEMYA",
    "YARMUQ - NAHARAYIM",
]


def _get_token(session: requests.Session) -> str:
    r = session.get(_PAGE_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.find("meta", {"name": "api-token"})
    if not meta:
        raise ValueError("api-token meta tag not found on hydro.water.gov.il")
    return meta["content"]


def _fetch_observations(session: requests.Session, token: str) -> dict:
    r = session.post(_OBS_URL, headers={"X-SESSION-TOKEN": token}, timeout=30)
    r.raise_for_status()
    return r.json()[0]


def _aggregate_daily(obs: dict, station_id: str = _STATION_ID) -> pd.DataFrame:
    records = []
    for ts_str, stations in obs.items():
        station_data = stations.get(station_id)
        if station_data is not None and station_data[0] is not None:
            records.append({
                "datetime": pd.Timestamp(ts_str),
                "flow_m3s": float(station_data[0]),
            })
    if not records:
        return pd.DataFrame(columns=["date", "JORDAN - OBSTACLE BRIDGE"])
    df_raw = pd.DataFrame(records)
    df_raw["date"] = df_raw["datetime"].dt.date
    daily = df_raw.groupby("date")["flow_m3s"].mean().reset_index()
    daily["JORDAN - OBSTACLE BRIDGE"] = daily["flow_m3s"] * 86400
    return daily.drop(columns=["flow_m3s"])


def fetch_new_flows(raw_csv_path: Path) -> pd.DataFrame:
    raw_csv_path = Path(raw_csv_path)
    if raw_csv_path.exists():
        df_existing = pd.read_csv(raw_csv_path, parse_dates=["Date"])
        max_ts = df_existing["Date"].max()
        last_date = FLOW_DEFAULT_FROM - timedelta(days=1) if pd.isna(max_ts) else max_ts.date()
    else:
        last_date = FLOW_DEFAULT_FROM - timedelta(days=1)

    if last_date >= date.today() - timedelta(days=1):
        return pd.DataFrame(columns=["date", "JORDAN - OBSTACLE BRIDGE"])

    session = requests.Session()
    token = _get_token(session)
    obs = _fetch_observations(session, token)
    df_daily = _aggregate_daily(obs)
    if df_daily.empty:
        return df_daily

    df_daily["date"] = pd.to_datetime(df_daily["date"]).dt.date
    df_daily = df_daily[df_daily["date"] < date.today()]
    df_daily = df_daily[df_daily["date"] > last_date]
    return df_daily


def append_to_flow_raw(df: pd.DataFrame, raw_csv_path: Path) -> int:
    if df.empty:
        return 0
    raw_csv_path = Path(raw_csv_path)
    raw_csv_path.parent.mkdir(parents=True, exist_ok=True)
    full = pd.DataFrame(index=range(len(df)), columns=FLOW_COLS)
    full["Date"] = df["date"].astype(str).values
    full["JORDAN - OBSTACLE BRIDGE"] = df["JORDAN - OBSTACLE BRIDGE"].values
    full.to_csv(raw_csv_path, mode="a", header=not raw_csv_path.exists(), index=False)
    return len(full)
