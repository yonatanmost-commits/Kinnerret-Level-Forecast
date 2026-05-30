# tests/test_met_update.py
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from met_update import (
    append_to_met_silver,
    fetch_new_met,
    MET_DEFAULT_FROM,
)


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


# ── fetch_new_met behavior (no network) ───────────────────────────────────────

def test_fetch_new_met_uptodate_returns_empty(tmp_path):
    today = date.today()
    p = tmp_path / "met_data_daily.csv"
    p.write_text(f"date,lev_kinneret_temperature_C_mean\n{today},22.5\n")
    df = fetch_new_met(p)
    assert df.empty
