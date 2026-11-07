# tests/test_met_coverage_cache.py
"""Step 04's Layer 3 must keep blanking low-coverage days that the local 10-minute
wide file does not reach.

Bug (found 2026-11-07): the 18 Oct local refresh ran step 04 with the local
met_data_wide.csv present. That file starts 2012-06-01, while the committed
coverage cache had been backfilled to 1994. Step 04 recomputed coverage from
the wide file alone and overwrote the cache, so every pre-2012 row was lost and
partial days (e.g. Tzemach 2009-04-11, 36% of slots) flowed into gold.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def step04(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "_04_clean_daily_met_data", ROOT / "Automation" / "04_clean_daily_met_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, fname in (("IN_DAILY", "met_data_daily.csv"), ("IN_WIDE", "met_data_wide.csv"),
                        ("OUT_CLEAN", "met_data_daily_clean.csv"), ("OUT_LOG", "met_data_daily_qc_log.csv"),
                        ("COV_CACHE", "met_coverage_daily.csv")):
        monkeypatch.setattr(mod, name, tmp_path / fname)
    return mod


def _write_inputs(mod):
    days = ["2009-04-10", "2009-04-11", "2009-04-12", "2012-06-01", "2012-06-02", "2012-06-03"]
    pd.DataFrame({
        "date": days,
        "tzamach_temperature_C_mean": [18.6, 19.2, 21.5, 27.1, 26.6, 27.9],
        "tzamach_temperature_C_max": [24.7, 24.8, 28.4, 34.3, 31.9, 32.9],
    }).to_csv(mod.IN_DAILY, index=False, encoding="utf-8-sig")

    # the local 10-minute file only starts in 2012; 2012-06-02 has 20 of 144 slots
    slots = []
    for day, n in (("2012-06-01", 144), ("2012-06-02", 20), ("2012-06-03", 144)):
        t = pd.date_range(day, periods=144, freq="10min")
        v = np.full(144, np.nan)
        v[:n] = 25.0
        slots.append(pd.DataFrame({"datetime": t, "tzamach_temperature_C": v}))
    pd.concat(slots).to_csv(mod.IN_WIDE, index=False, encoding="utf-8-sig")

    # the committed cache reaches back before the wide file (backfilled history)
    pd.DataFrame({"date": ["2009-04-10", "2009-04-11", "2009-04-12"],
                  "tzamach": [1.0, 0.361111, 1.0]}).to_csv(mod.COV_CACHE, index=False)


def test_pre_wide_low_coverage_day_is_still_blanked(step04):
    _write_inputs(step04)
    step04.main()
    clean = pd.read_csv(step04.OUT_CLEAN, encoding="utf-8-sig").set_index("date")
    assert clean.loc["2009-04-11", ["tzamach_temperature_C_mean", "tzamach_temperature_C_max"]].isna().all()
    assert clean.loc["2012-06-02", ["tzamach_temperature_C_mean", "tzamach_temperature_C_max"]].isna().all()
    assert clean.loc["2009-04-10", "tzamach_temperature_C_mean"] == pytest.approx(18.6)
    assert clean.loc["2012-06-01", "tzamach_temperature_C_mean"] == pytest.approx(27.1)


def test_cache_keeps_rows_the_wide_file_does_not_reach(step04):
    _write_inputs(step04)
    step04.main()
    cov = pd.read_csv(step04.COV_CACHE).set_index("date")
    assert cov.loc["2009-04-11", "tzamach"] == pytest.approx(0.361111)
    assert cov.loc["2012-06-02", "tzamach"] == pytest.approx(20 / 144)
