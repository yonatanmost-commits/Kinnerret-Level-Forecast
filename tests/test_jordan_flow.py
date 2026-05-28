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

    def fake_obs(_session, _token):
        return {}

    monkeypatch.setattr(jf, "_get_token", fake_token)
    monkeypatch.setattr(jf, "_fetch_observations", fake_obs)
    fetch_new_flows(tmp_path / "nope.csv")
    assert captured[0] == "token"
