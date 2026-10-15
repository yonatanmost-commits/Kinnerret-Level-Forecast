# tests/test_precip_intensity.py
"""Peak 1-hour rain intensity, extended from the IMS 10-minute feed.

Acceptance (the fix for the silent freeze at 2026-04-25):
  * the committed cache has a value for every day 2026-01-01 .. 2026-10-14
  * every value on or before 2026-04-25 is unchanged from the frozen cache
    (commit 9e99eff), because the IMS feed reproduces the manual export exactly
  * the daily agent refreshes intensity BEFORE it builds gold, so gold reads today's cache
"""
import io
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import precip_intensity as pi

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "Silver Data" / "Meteorological" / "precip_intensity_daily.csv"
FROZEN_SHA = "9e99eff"


# ── acceptance ──────────────────────────────────────────────────────────────────

def _cache():
    return pd.read_csv(CACHE).set_index("date")["precip_intensity_mm_hr"]


def test_cache_has_no_gap_through_2026_10_14():
    c = _cache()
    days = pd.date_range("2026-01-01", "2026-10-14").strftime("%Y-%m-%d")
    missing = [d for d in days if d not in c.index or pd.isna(c[d])]
    assert not missing, f"{len(missing)} days without intensity, first {missing[:5]}"


def test_history_unchanged_from_frozen_cache():
    old = pd.read_csv(io.StringIO(subprocess.run(
        ["git", "show", f"{FROZEN_SHA}:Silver Data/Meteorological/precip_intensity_daily.csv"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    ).set_index("date")["precip_intensity_mm_hr"].dropna()
    old = old[old.index <= "2026-04-25"]
    new = _cache().reindex(old.index)
    assert np.allclose(new.to_numpy(), old.to_numpy(), atol=1e-9, equal_nan=False)


def test_agent_refreshes_intensity_before_building_gold():
    src = (ROOT / "Automation" / "daily_agent.py").read_text(encoding="utf-8")
    assert src.index('"07b_precalc_precip_intensity.py"') < src.index('"07_build_gold_features.py"')


# ── the calculation ─────────────────────────────────────────────────────────────

def _grid(start, n):
    return pd.date_range(start, periods=n, freq="10min")


def test_peak_hour_is_six_slot_sum_and_belongs_to_the_day_it_ends():
    idx = _grid("2026-03-01 23:00", 18)                 # 23:00 .. 01:50
    rain = pd.Series(0.0, index=idx)
    rain["2026-03-01 23:30":"2026-03-02 00:20"] = 1.0   # six wet slots straddling midnight
    out = pi.daily_intensity(pd.DataFrame({"lev_kinneret": rain}))
    assert out["2026-03-02"] == pytest.approx(6.0)
    assert out["2026-03-01"] == pytest.approx(3.0)      # 23:30..23:50 is all day 1 sees


def test_dead_lev_kinneret_falls_back_to_mean_of_other_gauges():
    idx = _grid("2026-03-01 00:00", 6)
    df = pd.DataFrame({"lev_kinneret": np.nan, "tzamach": 1.0, "tiberias": 3.0}, index=idx)
    assert pi.daily_intensity(df)["2026-03-01"] == pytest.approx(12.0)


def test_live_lev_kinneret_wins_over_the_others():
    idx = _grid("2026-03-01 00:00", 6)
    df = pd.DataFrame({"lev_kinneret": 0.5, "tzamach": 9.0}, index=idx)
    assert pi.daily_intensity(df)["2026-03-01"] == pytest.approx(3.0)


def test_one_minute_rain_sums_into_slot_labelled_by_its_end():
    one = pd.Series(0.1, index=pd.date_range("2026-03-01 00:01", periods=10, freq="1min"))
    ten = pi.one_minute_to_ten(one)
    assert ten[pd.Timestamp("2026-03-01 00:10")] == pytest.approx(1.0)
    assert len(ten) == 1


# ── fetching ────────────────────────────────────────────────────────────────────

def _reply(channel, recs):
    return json.dumps({"data": {"records": [
        {"date": d, "orig_winter_date": d, channel: v} for d, v in recs]}}).encode()


def test_fetch_retries_an_empty_reply(monkeypatch):
    replies = iter([_reply("Rain", []), _reply("Rain", [("01/03/2026 00:10", 0.2)])])
    monkeypatch.setattr(pi, "_get", lambda url: next(replies))
    monkeypatch.setattr(pi.time, "sleep", lambda s: None)
    s = pi.fetch_channel(233, "Rain", pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-02"))
    assert s[pd.Timestamp("2026-03-01 00:10")] == pytest.approx(0.2)


def test_fetch_raises_when_feed_stays_empty(monkeypatch):
    monkeypatch.setattr(pi, "_get", lambda url: _reply("Rain", []))
    monkeypatch.setattr(pi.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="IMS"):
        pi.fetch_channel(233, "Rain", pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-02"))


def test_dash_means_missing_not_zero(monkeypatch):
    monkeypatch.setattr(pi, "_get", lambda url: _reply("Rain", [("01/03/2026 00:10", "-")]))
    monkeypatch.setattr(pi.time, "sleep", lambda s: None)
    s = pi.fetch_channel(115, "Rain", pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-02"))
    assert s.isna().all()


# ── the cache update ────────────────────────────────────────────────────────────

def test_update_keeps_history_extends_and_skips_today(tmp_path):
    cache = tmp_path / "pi.csv"
    pd.DataFrame({"date": ["2026-05-01", "2026-05-02", "2026-05-03"],
                  "precip_intensity_mm_hr": [7.0, np.nan, np.nan]}).to_csv(cache, index=False)
    asked = {}

    def fake_fetch(start, end):
        asked["start"] = start
        idx = pd.date_range(start, end, freq="10min", inclusive="left")
        return pd.DataFrame({"tzamach": 0.5}, index=idx)

    pi.update_cache(cache, fetch=fake_fetch, today=pd.Timestamp("2026-05-05"))
    out = pd.read_csv(cache).set_index("date")["precip_intensity_mm_hr"]
    assert asked["start"] == pd.Timestamp("2026-04-30")         # a day of warm-up before the last good day
    assert out["2026-05-01"] == 7.0                              # history untouched
    assert out[["2026-05-02", "2026-05-03", "2026-05-04"]].tolist() == [3.0, 3.0, 3.0]
    assert "2026-05-05" not in out.index                         # today is not complete yet
