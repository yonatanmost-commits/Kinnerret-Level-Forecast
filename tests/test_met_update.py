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
