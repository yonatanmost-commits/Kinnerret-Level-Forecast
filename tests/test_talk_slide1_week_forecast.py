"""Slide 1's talk-day stop (11 Nov 2026) from the week model with the IMS forecast, when there is one
(decided 31 Oct; originator 5 Nov: "first slides animation still says if no rain falls, but it now
leans on the IMS forecast no?"). make_lake_animation.stops(week_fc) reads
docs/talk/data/slide1_week_forecast.json: {"from": last measured day, "made_on", "levels":
{date: level}} for every day after "from" up to 11 Nov. It is used only when made from the LAST
measured level; otherwise (missing or stale) the stop stays the no-rain projection, as before.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs" / "talk"))


@pytest.fixture(scope="module")
def m():
    import make_lake_animation as m
    return m


def _write(tmp_path, m, last_day, end_level=-213.60):
    days = pd.date_range(pd.Timestamp(last_day) + pd.Timedelta(days=1), "2026-11-11", freq="D")
    levels = {d.strftime("%Y-%m-%d"): -213.70 + (end_level + 213.70) * (i + 1) / len(days)
              for i, d in enumerate(days)}
    p = tmp_path / "fc.json"
    p.write_text(json.dumps({"from": str(last_day), "made_on": "2026-11-06", "levels": levels}))
    return p


def test_without_a_forecast_the_stop_is_the_no_rain_projection(m, tmp_path):
    S, path, info = m.stops(tmp_path / "missing.json")
    assert S[-1]["note"] == "if no rain falls"
    assert info["ahead_stamp"] == "projection, no rain"


def test_a_forecast_from_the_last_measured_day_sets_the_stop_and_the_path(m, tmp_path):
    _, _, base = m.stops(tmp_path / "missing.json")
    fc = _write(tmp_path, m, base["last_day"])
    S, path, info = m.stops(fc)
    assert S[-1]["level"] == pytest.approx(-213.60)
    assert S[-1]["projected"] and S[-1]["note"] == "forecast"
    assert path[pd.Timestamp("2026-11-11")] == pytest.approx(-213.60)
    assert info["ahead_stamp"] == "forecast, IMS weather"
    frames = m.timeline(S, path, info)
    ahead = [f for f in frames if f.kind == "years" and f.projected]
    assert ahead and all(f.ahead == "forecast, IMS weather" for f in ahead)


def test_a_stale_forecast_is_ignored(m, tmp_path):
    _, _, base = m.stops(tmp_path / "missing.json")
    fc = _write(tmp_path, m, base["last_day"] - pd.Timedelta(days=1))
    S, _, info = m.stops(fc)
    assert S[-1]["note"] == "if no rain falls"
    assert info["ahead_stamp"] == "projection, no rain"


def _gold(level_to, weather_to):
    days = pd.date_range("2026-10-01", weather_to, freq="D")
    g = pd.DataFrame({"date": days, "temp_max_C": 25.0, "temp_min_C": 15.0, "rainfall_mm": 0.0,
                      "humidity_pct": 60.0, "wind_speed_ms": 2.0, "radiation_MJm2": 15.0})
    g["level_m"] = [-213.7 if d <= pd.Timestamp(level_to) else None for d in days]
    g["volume_Mm3"] = [3500.0 if d <= pd.Timestamp(level_to) else None for d in days]
    return g


def _ims(first):
    days = pd.date_range(first, periods=7, freq="D")
    return pd.DataFrame({"date": days, "temp_max_C": 20.0, "temp_min_C": 14.0, "rainfall_mm": 3.0,
                         "humidity_pct": 75.0, "wind_speed_ms": 1.5, "radiation_MJm2": float("nan")})


def _producer():
    sys.path.insert(0, str(ROOT / "docs" / "talk" / "data"))
    import slide1_week_forecast as p
    return p


def test_producer_starts_at_the_last_measured_level_with_measured_weather_first():
    p = _producer()
    last, hist, w = p.inputs(_gold("2026-11-04", "2026-11-05"), _ims("2026-11-06"))
    assert last == pd.Timestamp("2026-11-04") and hist["date"].max() == last
    assert list(w["date"]) == list(pd.date_range("2026-11-05", "2026-11-11"))
    assert list(w["source"]) == ["measured"] + ["IMS"] * 6
    assert w.iloc[1]["rainfall_mm"] == 3.0


def test_producer_refuses_when_the_talk_day_is_beyond_a_week():
    p = _producer()
    with pytest.raises(SystemExit):
        p.inputs(_gold("2026-11-03", "2026-11-05"), _ims("2026-11-06"))
