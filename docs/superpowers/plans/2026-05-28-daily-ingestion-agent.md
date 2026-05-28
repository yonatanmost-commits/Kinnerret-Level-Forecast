# Daily Ingestion Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate daily data ingestion (kinneret level, river flow, met), gold pipeline, and champion-only model retraining via a single orchestrator that runs from Task Scheduler, CLI, and a dashboard button.

**Architecture:** Six independent units follow the same pattern as the existing `kinneret_level.py` fetcher: pure-Python modules in `kinneret_app/`, imported by an orchestrator in `Automation/`. Each fetcher reads the silver CSV tail date, fetches only missing days, appends to raw silver, then the orchestrator runs the relevant clean script. Training uses a new `--winner-only` flag that reads `olympics_results.json` and trains only the champion model.

**Tech Stack:** `requests`, `beautifulsoup4`, `pandas`, `subprocess`, `pathlib`, `streamlit`, `pytest`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tests/test_train_winner.py` | Tests for `train_winner_only` dispatch |
| Modify | `Automation/08_train_forecast_model.py` | Add `train_winner_only()` + `--winner-only` CLI flag |
| Create | `tests/test_jordan_flow.py` | Tests for `jordan_flow` module |
| Create | `kinneret_app/jordan_flow.py` | hydro.water.gov.il river flow fetcher |
| Create | `tests/test_met_update.py` | Tests for `met_update` module |
| Create | `kinneret_app/met_update.py` | IMS Envista station 115 met fetcher |
| Create | `tests/test_daily_agent.py` | Tests for orchestrator health/report logic |
| Create | `Automation/daily_agent.py` | Orchestrator + health check + report |
| Create | `Automation/run_daily_agent.ps1` | Task Scheduler PowerShell wrapper |
| Modify | `kinneret_app/pages/2_Pipeline.py` | Add "Run Daily Refresh" button |

`tests/conftest.py` already adds `kinneret_app/` to sys.path.

---

## Task 1: `--winner-only` training flag

**Files:**
- Create: `tests/test_train_winner.py`
- Modify: `Automation/08_train_forecast_model.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_train_winner.py`**

```python
# tests/test_train_winner.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))
import importlib.util, types

# Import without executing __main__ block
_spec = importlib.util.spec_from_file_location(
    "train_08",
    Path(__file__).resolve().parent.parent / "Automation" / "08_train_forecast_model.py",
)
train_08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_08)


def test_train_winner_only_raises_when_json_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        train_08.train_winner_only()


def test_train_winner_only_raises_on_unknown_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    (tmp_path / "olympics_results.json").write_text(
        json.dumps({"winner": "unknown_model", "models": {}})
    )
    monkeypatch.setattr(train_08, "load_data", lambda: __import__("pandas").DataFrame())
    with pytest.raises(ValueError, match="unknown_model"):
        train_08.train_winner_only()


def test_train_winner_only_dispatches_correct_trainer(tmp_path, monkeypatch):
    monkeypatch.setattr(train_08, "MODELS_DIR", tmp_path)
    (tmp_path / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "models": {}})
    )
    import pandas as pd, numpy as np
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=10)})
    monkeypatch.setattr(train_08, "load_data", lambda: df)
    called = []
    monkeypatch.setattr(train_08, "run_cv", lambda df: ([], pd.Series(np.nan, index=df.index)))
    monkeypatch.setattr(train_08, "train_final", lambda df, oof: called.append("gbr") or (None, None, None))
    train_08.train_winner_only()
    assert called == ["gbr"]
```

- [ ] **Run tests — verify they fail**

```
python -m pytest tests/test_train_winner.py -v
```

Expected: `AttributeError` or `ImportError` (function doesn't exist yet)

---

### Step 2: Implement `train_winner_only` and `--winner-only` flag

- [ ] **Add `train_winner_only()` to `Automation/08_train_forecast_model.py`**

Insert this block immediately before the `main()` function (before line 717):

```python
def train_winner_only():
    """Read olympics_results.json and retrain only the winning model."""
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    olympics_path = MODELS_DIR / "olympics_results.json"
    if not olympics_path.exists():
        raise FileNotFoundError(f"Not found: {olympics_path}")
    with open(olympics_path, encoding="utf-8") as f:
        winner = json.load(f)["winner"]

    print(f"Loading data ...")
    df = load_data()
    print(f"  {len(df):,} rows  ({df['date'].min().date()} to {df['date'].max().date()})")

    if winner == "baseline_gbr":
        cv_results, oof_s1 = run_cv(df)
        gb1, gb2, gb2d = train_final(df, oof_s1)
        MODELS_DIR.mkdir(exist_ok=True)
        gb1.save(MODELS_DIR / "stage1_inflow_rf.pkl")
        gb2.save(MODELS_DIR / "stage2_volume_rf.pkl")
        gb2d.save(MODELS_DIR / "stage2_direct_gb.pkl")
    elif winner == "xgboost":
        import pandas as _pd
        oof_s1 = df[S1_TARGET]
        train_final_xgb(df, oof_s1)
    elif winner == "lgbm":
        oof_s1 = df[S1_TARGET]
        train_final_lgb(df, oof_s1)
    elif winner == "gru":
        train_final_gru(df)
    else:
        raise ValueError(f"Unknown winner in olympics_results.json: {winner!r}")

    print(f"Winner '{winner}' trained and saved.")
```

- [ ] **Add `--winner-only` check at the top of `main()`**

The existing `main()` starts at line 717. Replace:
```python
def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
```
With:
```python
def main():
    if "--winner-only" in sys.argv:
        train_winner_only()
        return
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
```

---

### Step 3: Run tests — verify they pass

- [ ] **Run tests**

```
python -m pytest tests/test_train_winner.py -v
```

Expected: 3 tests PASSED

---

### Step 4: Commit

- [ ] **Commit**

```
git add tests/test_train_winner.py Automation/08_train_forecast_model.py
git commit -m "feat: add train_winner_only and --winner-only flag to 08_train"
```

---

## Task 2: `kinneret_app/jordan_flow.py`

**Files:**
- Create: `tests/test_jordan_flow.py`
- Create: `kinneret_app/jordan_flow.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_jordan_flow.py`**

```python
# tests/test_jordan_flow.py
from datetime import date

import pandas as pd
import pytest

from jordan_flow import (
    _aggregate_daily,
    append_to_flow_raw,
    fetch_new_flows,
    FLOW_DEFAULT_FROM,
)

# 3 readings for 2026-05-27, 2 for 2026-05-28
FIXTURE_OBS = {
    "2026-05-27 06:00:00": {"79": [15.5, 2.1]},
    "2026-05-27 06:10:00": {"79": [15.8, 2.1]},
    "2026-05-27 06:20:00": {"79": [15.3, 2.1]},
    "2026-05-28 06:00:00": {"79": [16.0, 2.2]},
    "2026-05-28 06:10:00": {"79": [16.2, 2.2]},
}


# ── _aggregate_daily ───────────────────────────────────────────────────────────

def test_aggregate_daily_count():
    result = _aggregate_daily(FIXTURE_OBS)
    assert len(result) == 2


def test_aggregate_daily_m3_conversion():
    result = _aggregate_daily(FIXTURE_OBS)
    day = result[pd.to_datetime(result["date"]).dt.date == date(2026, 5, 27)].iloc[0]
    expected_mean = (15.5 + 15.8 + 15.3) / 3
    assert day["JORDAN - OBSTACLE BRIDGE"] == pytest.approx(expected_mean * 86400)


def test_aggregate_daily_ignores_missing_station():
    obs = {
        "2026-05-27 06:00:00": {"99": [5.0, 1.0]},  # wrong station
    }
    result = _aggregate_daily(obs)
    assert result.empty


# ── append_to_flow_raw ─────────────────────────────────────────────────────────

@pytest.fixture
def raw_flow_csv(tmp_path):
    p = tmp_path / "jordan_river_daily_flow.csv"
    p.write_text(
        "Date,JORDAN - BAPTISM SITE,JORDAN - NEAR OLD BRIDGE,"
        "JORDAN - OBSTACLE BRIDGE,JORDAN - SEDE NEHEMYA,YARMUQ - NAHARAYIM\n"
        "2026-04-08,,, 1473729.48,,\n"
    )
    return p


def test_append_to_flow_raw_count(raw_flow_csv):
    df = pd.DataFrame({
        "date": [date(2026, 4, 9)],
        "JORDAN - OBSTACLE BRIDGE": [1400000.0],
    })
    assert append_to_flow_raw(df, raw_flow_csv) == 1


def test_append_to_flow_raw_row_written(raw_flow_csv):
    df = pd.DataFrame({
        "date": [date(2026, 4, 9)],
        "JORDAN - OBSTACLE BRIDGE": [1400000.0],
    })
    append_to_flow_raw(df, raw_flow_csv)
    result = pd.read_csv(raw_flow_csv)
    assert len(result) == 2
    assert str(result.iloc[1]["Date"]) == "2026-04-09"
    assert result.iloc[1]["JORDAN - OBSTACLE BRIDGE"] == pytest.approx(1400000.0)


def test_append_to_flow_raw_noop_on_empty(raw_flow_csv):
    df = pd.DataFrame(columns=["date", "JORDAN - OBSTACLE BRIDGE"])
    assert append_to_flow_raw(df, raw_flow_csv) == 0
    assert len(pd.read_csv(raw_flow_csv)) == 1


# ── fetch_new_flows behavior (no network) ─────────────────────────────────────

def test_fetch_new_flows_uptodate_returns_empty(tmp_path, monkeypatch):
    import jordan_flow as jf
    today = date.today()
    p = tmp_path / "jordan_river_daily_flow.csv"
    p.write_text(
        "Date,JORDAN - BAPTISM SITE,JORDAN - NEAR OLD BRIDGE,"
        "JORDAN - OBSTACLE BRIDGE,JORDAN - SEDE NEHEMYA,YARMUQ - NAHARAYIM\n"
        f"{today},,,1400000.0,,\n"
    )
    called = []
    monkeypatch.setattr(jf, "_get_token", lambda s: called.append(1) or "tok")
    df = fetch_new_flows(p)
    assert df.empty
    assert called == []


def test_fetch_new_flows_missing_csv_uses_default(tmp_path, monkeypatch):
    import jordan_flow as jf
    captured = []

    def fake_token(session):
        captured.append("token")
        return "tok"

    def fake_obs(session, token):
        return {}

    monkeypatch.setattr(jf, "_get_token", fake_token)
    monkeypatch.setattr(jf, "_fetch_observations", fake_obs)
    fetch_new_flows(tmp_path / "nope.csv")
    assert captured[0] == "token"
```

- [ ] **Run tests — verify they fail with ModuleNotFoundError**

```
python -m pytest tests/test_jordan_flow.py -v
```

Expected: `ModuleNotFoundError: No module named 'jordan_flow'`

---

### Step 2: Implement `kinneret_app/jordan_flow.py`

- [ ] **Create `kinneret_app/jordan_flow.py`**

```python
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
```

- [ ] **Run tests — verify all pass**

```
python -m pytest tests/test_jordan_flow.py -v
```

Expected: 8 tests PASSED

---

### Step 3: Commit

- [ ] **Commit**

```
git add tests/test_jordan_flow.py kinneret_app/jordan_flow.py
git commit -m "feat: add jordan_flow module for hydro.water.gov.il river flow fetch"
```

---

## Task 3: `kinneret_app/met_update.py`

**Files:**
- Create: `tests/test_met_update.py`
- Create: `kinneret_app/met_update.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_met_update.py`**

```python
# tests/test_met_update.py
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from met_update import (
    _aggregate_daily,
    _discover_resource_id,
    append_to_met_silver,
    fetch_new_met,
    MET_DEFAULT_FROM,
)

# 3 10-minute readings for 2026-05-20
FIXTURE_RECORDS = [
    {"stn_num": "115", "time_obs": "2026-05-20 06:00:00",
     "1": "0.0", "7": "22.5", "8": "70.0", "9": "25.0", "10": "18.0"},
    {"stn_num": "115", "time_obs": "2026-05-20 06:10:00",
     "1": "0.1", "7": "22.8", "8": "71.0", "9": "25.5", "10": "18.2"},
    {"stn_num": "115", "time_obs": "2026-05-20 06:20:00",
     "1": "0.0", "7": "23.0", "8": "72.0", "9": "26.0", "10": "18.4"},
]


# ── _aggregate_daily ───────────────────────────────────────────────────────────

def test_aggregate_daily_rain_is_sum():
    raw_df = pd.DataFrame(FIXTURE_RECORDS)
    result = _aggregate_daily(raw_df)
    assert result.iloc[0]["lev_kinneret_rainfall_mm_sum"] == pytest.approx(0.1)


def test_aggregate_daily_temperature_mean():
    raw_df = pd.DataFrame(FIXTURE_RECORDS)
    result = _aggregate_daily(raw_df)
    expected = (22.5 + 22.8 + 23.0) / 3
    assert result.iloc[0]["lev_kinneret_temperature_C_mean"] == pytest.approx(expected)


def test_aggregate_daily_temperature_max():
    raw_df = pd.DataFrame(FIXTURE_RECORDS)
    result = _aggregate_daily(raw_df)
    assert result.iloc[0]["lev_kinneret_temperature_C_max"] == pytest.approx(26.0)


def test_aggregate_daily_temperature_min():
    raw_df = pd.DataFrame(FIXTURE_RECORDS)
    result = _aggregate_daily(raw_df)
    assert result.iloc[0]["lev_kinneret_temperature_C_min"] == pytest.approx(18.0)


def test_aggregate_daily_empty():
    result = _aggregate_daily(pd.DataFrame())
    assert result.empty


# ── append_to_met_silver ───────────────────────────────────────────────────────

@pytest.fixture
def met_silver_csv(tmp_path):
    p = tmp_path / "met_data_daily.csv"
    p.write_text(
        "date,lev_kinneret_temperature_C_mean,other_station_col\n"
        "2026-05-19,22.5,1.0\n"
    )
    return p


def test_append_to_met_silver_count(met_silver_csv):
    df = pd.DataFrame({
        "date": [date(2026, 5, 20)],
        "lev_kinneret_temperature_C_mean": [23.0],
    })
    assert append_to_met_silver(df, met_silver_csv) == 1


def test_append_to_met_silver_preserves_other_cols_as_nan(met_silver_csv):
    df = pd.DataFrame({
        "date": [date(2026, 5, 20)],
        "lev_kinneret_temperature_C_mean": [23.0],
    })
    append_to_met_silver(df, met_silver_csv)
    result = pd.read_csv(met_silver_csv)
    assert len(result) == 2
    assert pd.isna(result.iloc[1]["other_station_col"])
    assert result.iloc[1]["lev_kinneret_temperature_C_mean"] == pytest.approx(23.0)


# ── _discover_resource_id ──────────────────────────────────────────────────────

def test_discover_resource_id_reads_cache(tmp_path):
    cache = tmp_path / "ims_resource_id.json"
    cache.write_text(json.dumps({"resource_id": "abc-123"}))
    assert _discover_resource_id(cache) == "abc-123"


# ── fetch_new_met behavior (no network) ───────────────────────────────────────

def test_fetch_new_met_uptodate_returns_empty(tmp_path, monkeypatch):
    import met_update as mu
    today = date.today()
    p = tmp_path / "met_data_daily.csv"
    p.write_text(f"date,lev_kinneret_temperature_C_mean\n{today},22.5\n")
    called = []
    monkeypatch.setattr(mu, "_discover_resource_id", lambda c: called.append(1) or "x")
    df = fetch_new_met(p)
    assert df.empty
    assert called == []
```

- [ ] **Run tests — verify they fail with ModuleNotFoundError**

```
python -m pytest tests/test_met_update.py -v
```

Expected: `ModuleNotFoundError: No module named 'met_update'`

---

### Step 2: Implement `kinneret_app/met_update.py`

- [ ] **Create `kinneret_app/met_update.py`**

```python
import json
import re
import urllib.parse
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
    df["date"] = pd.to_datetime(df["date"]).dt.date
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
```

- [ ] **Run tests — verify all pass**

```
python -m pytest tests/test_met_update.py -v
```

Expected: 10 tests PASSED

---

### Step 3: Commit

- [ ] **Commit**

```
git add tests/test_met_update.py kinneret_app/met_update.py
git commit -m "feat: add met_update module for IMS Envista station 115 met fetch"
```

---

## Task 4: `Automation/daily_agent.py`

**Files:**
- Create: `tests/test_daily_agent.py`
- Create: `Automation/daily_agent.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_daily_agent.py`**

```python
# tests/test_daily_agent.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "daily_agent",
    Path(__file__).resolve().parent.parent / "Automation" / "daily_agent.py",
)
daily_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily_agent)


# ── health_check ───────────────────────────────────────────────────────────────

def test_health_check_fails_on_missing_olympics_json(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    (tmp_path / "Models").mkdir()
    issues = daily_agent.health_check()
    assert any("olympics_results.json" in i and "REQUIRED" in i for i in issues)


def test_health_check_fails_on_missing_winner_key(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "olympics_results.json").write_text(json.dumps({"models": {}}))
    issues = daily_agent.health_check()
    assert any("winner" in i and "REQUIRED" in i for i in issues)


def test_health_check_passes_with_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "PROJECT_ROOT", tmp_path)
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "olympics_results.json").write_text(
        json.dumps({"winner": "baseline_gbr", "models": {}})
    )
    issues = daily_agent.health_check()
    required_failures = [i for i in issues if "REQUIRED" in i]
    assert required_failures == []


# ── _write_report ──────────────────────────────────────────────────────────────

def test_write_report_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_agent, "REPORTS_DIR", tmp_path / "Reports")
    results = {
        "kinneret_level": {"status": "ok", "rows_added": 1, "detail": "(2026-05-28)"},
        "river_flow":     {"status": "failed", "rows_added": 0, "detail": "timeout"},
        "build_gold":     {"status": "ok", "detail": None},
        "train_winner":   {"status": "ok", "detail": None},
    }
    path = daily_agent._write_report(results, [], "2026-05-28")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "kinneret_level" in text
    assert "FAILED" in text
    assert "2026-05-28" in text


# ── _run_script ────────────────────────────────────────────────────────────────

def test_run_script_captures_failure(tmp_path):
    bad_script = tmp_path / "bad.py"
    bad_script.write_text("import sys; sys.exit(1)\n")
    result = daily_agent._run_script_path(bad_script)
    assert result["status"] == "failed"
```

- [ ] **Run tests — verify they fail**

```
python -m pytest tests/test_daily_agent.py -v
```

Expected: `ModuleNotFoundError` or `AttributeError` (module doesn't exist yet)

---

### Step 2: Implement `Automation/daily_agent.py`

- [ ] **Create `Automation/daily_agent.py`**

```python
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

AUTOMATION   = Path(__file__).resolve().parent
PROJECT_ROOT = AUTOMATION.parent
REPORTS_DIR  = PROJECT_ROOT / "Reports"

sys.path.insert(0, str(PROJECT_ROOT / "kinneret_app"))

from kinneret_level import append_to_silver, fetch_new_levels
from jordan_flow    import append_to_flow_raw, fetch_new_flows
from met_update     import append_to_met_silver, fetch_new_met

KINNERET_LEVEL_SILVER = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
FLOW_RAW_SILVER       = PROJECT_ROOT / "Silver Data" / "Jordan River Silver" / "jordan_river_daily_flow.csv"
MET_SILVER            = PROJECT_ROOT / "Silver Data" / "Meteorological" / "met_data_daily.csv"


def health_check() -> list:
    issues = []
    olympics_path = PROJECT_ROOT / "Models" / "olympics_results.json"
    if not olympics_path.exists():
        issues.append("REQUIRED: Models/olympics_results.json missing")
    else:
        try:
            with open(olympics_path, encoding="utf-8") as f:
                data = json.load(f)
            if "winner" not in data:
                issues.append("REQUIRED: olympics_results.json has no 'winner' key")
        except Exception as e:
            issues.append(f"REQUIRED: olympics_results.json unreadable: {e}")

    for path, label in [
        (PROJECT_ROOT / "Gold Data" / "kinneret_gold_features.csv", "Gold Data/kinneret_gold_features.csv"),
        (PROJECT_ROOT / "Models" / "stage1_inflow_rf.pkl", "Models/stage1_inflow_rf.pkl"),
        (PROJECT_ROOT / "Models" / "stage2_volume_rf.pkl", "Models/stage2_volume_rf.pkl"),
    ]:
        if not path.exists():
            issues.append(f"WARN: {label} missing")

    return issues


def _run_script_path(script_path: Path, *args: str) -> dict:
    cmd = [sys.executable, str(script_path)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output")[:500]
        return {"status": "failed", "detail": detail}
    return {"status": "ok", "detail": None}


def _run_script(script_name: str, *args: str) -> dict:
    return _run_script_path(AUTOMATION / script_name, *args)


def _write_report(results: dict, health_issues: list, today: str) -> Path:
    lines = [f"=== Daily Agent Report - {today} ===", ""]

    lines += ["HEALTH"]
    if not health_issues:
        lines.append("  All checks passed.")
    else:
        for issue in health_issues:
            lines.append(f"  {issue}")

    lines += ["", "DATA FETCH"]
    for key in ["kinneret_level", "river_flow", "met"]:
        r = results.get(key)
        if r is None:
            continue
        n = r.get("rows_added", 0) or 0
        detail = r.get("detail") or ""
        if r["status"] == "ok":
            lines.append(f"  {key:<16} : ok        +{n} rows  {detail}")
        else:
            lines.append(f"  {key:<16} : FAILED    {detail}")

    lines += ["", "PIPELINE"]
    for key in ["05_clean_flow", "04_clean_met", "build_gold", "07b_precip", "train_winner"]:
        r = results.get(key)
        if r is None:
            continue
        if r["status"] == "ok":
            lines.append(f"  {key:<16} : ok")
        elif r["status"] == "skipped":
            lines.append(f"  {key:<16} : skipped   {r.get('detail','')}")
        else:
            lines.append(f"  {key:<16} : FAILED    {r.get('detail','')}")

    report_text = "\n".join(lines)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"daily_agent_{today}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def run() -> dict:
    results = {}

    # Step 1: Kinneret level
    try:
        df = fetch_new_levels(KINNERET_LEVEL_SILVER)
        n = append_to_silver(df, KINNERET_LEVEL_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["kinneret_level"] = {"status": "ok", "rows_added": n, "detail": detail}
    except Exception as e:
        results["kinneret_level"] = {"status": "failed", "rows_added": 0, "detail": str(e)}

    # Step 2: River flow
    try:
        df = fetch_new_flows(FLOW_RAW_SILVER)
        n = append_to_flow_raw(df, FLOW_RAW_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["river_flow"] = {"status": "ok", "rows_added": n, "detail": detail}
        results["05_clean_flow"] = _run_script("05_clean_jordan_river_flow.py")
    except Exception as e:
        results["river_flow"] = {"status": "failed", "rows_added": 0, "detail": str(e)}
        results["05_clean_flow"] = {"status": "skipped", "detail": "river_flow failed"}

    # Step 3: Met data
    try:
        df = fetch_new_met(MET_SILVER)
        n = append_to_met_silver(df, MET_SILVER)
        detail = f"({df['date'].min()} to {df['date'].max()})" if n else "(up to date)"
        results["met"] = {"status": "ok", "rows_added": n, "detail": detail}
        results["04_clean_met"] = _run_script("04_clean_daily_met_data.py")
    except Exception as e:
        results["met"] = {"status": "failed", "rows_added": 0, "detail": str(e)}
        results["04_clean_met"] = {"status": "skipped", "detail": "met failed"}

    # Step 4: Build gold (always attempt)
    results["build_gold"] = _run_script("07_build_gold_features.py")

    # Step 4b: Precipitation intensity feature (runs after 07, updates gold in place)
    if results["build_gold"]["status"] == "ok":
        results["07b_precip"] = _run_script("07b_precalc_precip_intensity.py")
    else:
        results["07b_precip"] = {"status": "skipped", "detail": "build_gold failed"}

    # Step 5: Train winner (only if gold + 07b succeeded)
    if results["build_gold"]["status"] == "ok" and results["07b_precip"]["status"] == "ok":
        results["train_winner"] = _run_script(
            "08_train_forecast_model.py", "--winner-only"
        )
    else:
        results["train_winner"] = {
            "status": "skipped", "detail": "build_gold or 07b_precip failed"
        }

    return results


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    today = str(date.today())

    health_issues = health_check()
    required_failures = [i for i in health_issues if i.startswith("REQUIRED")]

    if required_failures:
        report_path = _write_report({}, health_issues, today)
        print(f"HEALTH FAILED. See: {report_path}")
        print("\n".join(required_failures))
        sys.exit(1)

    results = run()
    report_path = _write_report(results, health_issues, today)

    print(open(report_path, encoding="utf-8").read())
    print(f"\nReport saved: {report_path}")

    if any(v["status"] == "failed" for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Run tests — verify all pass**

```
python -m pytest tests/test_daily_agent.py -v
```

Expected: 5 tests PASSED

---

### Step 3: Run full test suite

- [ ] **Run all tests**

```
python -m pytest tests/ -v
```

Expected: all tests pass (previous tests + new tests)

---

### Step 4: Commit

- [ ] **Commit**

```
git add tests/test_daily_agent.py Automation/daily_agent.py
git commit -m "feat: add daily_agent orchestrator with health check and report"
```

---

## Task 5: `Automation/run_daily_agent.ps1`

**Files:**
- Create: `Automation/run_daily_agent.ps1`

No tests — this is a one-line PowerShell wrapper.

- [ ] **Create `Automation/run_daily_agent.ps1`**

```powershell
# run_daily_agent.ps1 — Windows Task Scheduler entry point
# Schedule: Daily at 06:00
# Action: powershell.exe -NonInteractive -File "C:\...\Automation\run_daily_agent.ps1"

$python = (Get-Command python).Source
& $python "$PSScriptRoot\daily_agent.py"
exit $LASTEXITCODE
```

- [ ] **Test manually**

```
powershell -NonInteractive -File "Automation\run_daily_agent.ps1"
```

Expected: agent runs, prints report to console, exits 0 (or 1 if any step fails).

- [ ] **Commit**

```
git add Automation/run_daily_agent.ps1
git commit -m "feat: add run_daily_agent.ps1 Task Scheduler wrapper"
```

---

## Task 6: "Run Daily Refresh" button on `kinneret_app/pages/2_Pipeline.py`

**Files:**
- Modify: `kinneret_app/pages/2_Pipeline.py`

No unit tests — UI change, verify visually in browser.

### Step 1: Add the button section

- [ ] **Append at the very end of `kinneret_app/pages/2_Pipeline.py`** (after the closing of `with tab_gold:`)

```python

# ── Daily Refresh ──────────────────────────────────────────────────────────────
st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
st.subheader("Daily Data Refresh")
st.markdown(
    '<div class="kn-label">Fetch new data from all sources, rebuild gold, retrain champion</div>',
    unsafe_allow_html=True,
)

if st.button("Run Daily Refresh", key="daily_refresh"):
    agent_script = AUTOMATION / "daily_agent.py"
    with st.spinner("Running daily agent (may take a few minutes)..."):
        result = subprocess.run(
            [sys.executable, str(agent_script)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
    if result.returncode == 0:
        st.success("Daily agent completed successfully.")
    else:
        st.error("Daily agent finished with errors.")
    if result.stdout:
        st.code(result.stdout, language="text")
    if result.stderr:
        st.expander("stderr").code(result.stderr, language="text")
```

- [ ] **Add `import subprocess` at the top of `2_Pipeline.py`** (after the existing imports, around line 6)

Current imports end at:
```python
from app_utils import load_gold, PROJECT_ROOT, COLOURS
```

Add `import subprocess` on the line after `import sys` (line 1).

---

### Step 2: Verify in browser

- [ ] **Start the app**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project\kinneret_app"
streamlit run Home.py
```

Navigate to page 2 (Data Pipeline). Scroll to the bottom. Confirm the "Run Daily Refresh" button appears below the tabs. Click it and verify it runs the agent and shows the report output.

---

### Step 3: Commit

- [ ] **Commit**

```
git add kinneret_app/pages/2_Pipeline.py
git commit -m "feat: add Run Daily Refresh button to Pipeline page"
```

---

## Final check

- [ ] **Run full test suite**

```
python -m pytest tests/ -v
```

Expected: all tests PASSED (existing + new)

- [ ] **Run agent once end-to-end**

```
python Automation/daily_agent.py
```

Expected: report printed to console and saved to `Reports/daily_agent_YYYY-MM-DD.txt`
