# tests/test_tzemach_gold.py
"""Tzemach-first gold, extended back to 1998 with the IMS envista history.

Decision (2026-10-16, docs/experiments/ims_station_bias.md): gold takes every
weather column from Tzemach first, for every year, so the record never switches
station (Lev Kinneret's nights run +4.2 C warmer and its wind +1.1 m/s stronger,
and its gauge is empty before 2012). The pre-2012 history enters as IMS export
files and goes through pipeline steps 1-4 like every other export.

Acceptance:
  * consensus_col takes tzamach first and falls back to the mean of the others
  * gold starts 1998-02-01, where Tzemach rain starts
  * 1998-02 .. 2012-05 rows are filled: >= 95% of days for each weather input,
    >= 90% for radiation (and so ET0), which has a whole-month gap in 2006-09
  * the committed daily silver gained the pre-2012 rows and kept every later row as it was
"""
import importlib.util
import io
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "Gold Data" / "kinneret_gold_features.csv"
CLEAN = ROOT / "Silver Data" / "Meteorological" / "met_data_daily_clean.csv"
BASE_SHA = "42e5a4c"            # master before the backfill

_spec = importlib.util.spec_from_file_location("_07_gold", ROOT / "Automation" / "07_build_gold_features.py")
g07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g07)

WEATHER = ["temp_mean_C", "temp_max_C", "temp_min_C", "humidity_pct", "wind_speed_ms", "rainfall_mm"]


# ── the rule ────────────────────────────────────────────────────────────────────

def test_consensus_takes_tzemach_first():
    met = pd.DataFrame({"tzamach_x": [1.0, 1.0], "lev_kinneret_x": [9.0, 9.0], "kfar_nachum_x": [5.0, 5.0]})
    assert list(g07.consensus_col(met, "x")) == [1.0, 1.0]


def test_consensus_falls_back_to_mean_of_other_stations():
    met = pd.DataFrame({"tzamach_x": [np.nan], "lev_kinneret_x": [9.0], "kfar_nachum_x": [5.0]})
    assert g07.consensus_col(met, "x").iloc[0] == pytest.approx(7.0)


# ── the built gold ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def gold():
    return pd.read_csv(GOLD, parse_dates=["date"]).set_index("date")


def test_gold_starts_where_tzemach_rain_starts(gold):
    assert gold.index.min() == pd.Timestamp("1998-02-01")


@pytest.mark.parametrize("col", WEATHER)
def test_pre2012_weather_is_filled(gold, col):
    part = gold.loc["1998-02-01":"2012-05-31", col]
    assert part.notna().mean() >= 0.95, f"{col}: {part.notna().mean():.3f} of days filled"


@pytest.mark.parametrize("col", ["radiation_MJm2", "et0_mm"])
def test_pre2012_radiation_and_et0_are_filled(gold, col):
    part = gold.loc["1998-02-01":"2012-05-31", col]
    assert part.notna().mean() >= 0.90, f"{col}: {part.notna().mean():.3f} of days filled"


# ── the silver backfill ─────────────────────────────────────────────────────────

def test_daily_silver_starts_1994_and_keeps_every_later_row():
    new = pd.read_csv(CLEAN)
    old = pd.read_csv(io.StringIO(subprocess.run(
        ["git", "show", f"{BASE_SHA}:Silver Data/Meteorological/met_data_daily_clean.csv"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout))
    assert new["date"].min() <= "1994-01-31"
    later = new[new["date"] >= old["date"].min()].reset_index(drop=True)
    pd.testing.assert_frame_equal(later[old.columns], old, check_dtype=False)
