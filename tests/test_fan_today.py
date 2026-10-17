"""Acceptance tests for the long-range fan on the app.

Automation/fan_today.py turns a past-winters ensemble from today into Models/longrange_fan.json;
kinneret_app/fan_card.py draws it on page 10 (Days to Red Line).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))
import cfc_bands as cb  # noqa: E402
import fan_today  # noqa: E402

START = "2026-10-08"
HS = (7, 130, 260, 365)
RED = {"red": -213.0, "upper": -208.8}


def members(start=START, winters=range(2002, 2026), level0=-213.65):
    """One scenario per past winter: winter Y's rise grows with Y's wetness (index)."""
    rng = np.random.default_rng(1)
    wet = {Y: rng.normal() for Y in winters}
    rows = [{"method": "B14", "weather": f"ens|{Y}", "year": 2026, "start": start, "H": H,
             "level0": level0, "pred": level0 + H / 365 * (1.0 + 1.5 * wet[Y]), "obs": None}
            for Y in winters for H in HS]
    return pd.DataFrame(rows)


def errors():
    """Earlier forecasts with the actual weather, starting near 8 Oct, outcomes known."""
    rng = np.random.default_rng(2)
    rows = [{"method": "B14", "weather": "obs", "year": y, "start": f"{y}-10-{d:02d}", "H": H,
             "level0": -212.0, "pred": -212.0, "obs": -212.0 + rng.normal(0, 0.05 + H / 1000)}
            for y in range(2011, 2026) for d in (1, 8, 15) for H in HS if y + H / 365 < 2026.7]
    return pd.DataFrame(rows)


def weights(m):
    return pd.Series(np.linspace(0.5, 1.5, len(m)), index=m.index)


def made():
    m = members()
    return fan_today.build(m, errors(), weights(m), START,
                           seasonal={"source": "ECMWF SEAS5", "init": "2026-10", "season_ratio": 1.06,
                                     "rank": 25, "of": 34}), m


def test_each_horizon_has_nested_ranges_and_odds():
    f, _ = made()
    assert [h["H"] for h in f["horizons"]] == list(HS)
    for h in f["horizons"]:
        assert h["lo_90"] <= h["lo_80"] <= h["lo_50"] <= h["median"] <= h["hi_50"] <= h["hi_80"] <= h["hi_90"]
        assert 0 <= h["p_red"] <= 1 and 0 <= h["p_upper"] <= 1
        assert h["date"] == str((pd.Timestamp(START) + pd.Timedelta(days=h["H"])).date())


def test_numbers_are_the_weighted_bands_of_the_bench():
    f, m = made()
    ref = cb.bands(m.assign(weight=weights(m)), levels=(0.5, 0.8, 0.9), errors=errors(),
                   thresholds=RED).set_index("H")
    for h in f["horizons"]:
        r = ref.loc[h["H"]]
        assert abs(h["median"] - r.pred) < 1e-9 and abs(h["hi_80"] - r.hi_80) < 1e-9
        assert abs(h["p_red"] - r.p_red) < 1e-9


def test_header_says_where_it_starts_and_what_drives_it():
    f, _ = made()
    assert f["start"] == START and abs(f["level0"] - (-213.65)) < 1e-9
    assert f["lines"] == {"red": -213.0, "upper": -208.8}
    assert f["seasonal"]["source"] == "ECMWF SEAS5" and f["seasonal"]["init"] == "2026-10"
    assert pd.Timestamp(f["made_on"]) >= pd.Timestamp(START)


def test_wettest_and_driest_winter_paths_are_the_extreme_scenarios():
    f, m = made()
    end = m[m.H == 365].set_index("weather")["pred"]
    sc = {s["kind"]: s for s in f["scenarios"]}
    assert sc["wettest"]["winter"].startswith(end.idxmax().split("|")[1])
    assert sc["driest"]["winter"].startswith(end.idxmin().split("|")[1])
    assert [p["H"] for p in sc["wettest"]["path"]] == list(HS)


def test_only_the_requested_start_is_used():
    m = pd.concat([members(), members(start="2026-10-01", level0=-200.0)], ignore_index=True)
    f = fan_today.build(m, errors(), pd.Series(1.0, index=m.index), START, seasonal={})
    assert abs(f["level0"] - (-213.65)) < 1e-9 and all(h["median"] < -205 for h in f["horizons"])


def test_written_file_is_plain_json(tmp_path):
    f, _ = made()
    p = tmp_path / "fan.json"
    fan_today.write(f, p)
    assert json.loads(p.read_text(encoding="utf-8"))["start"] == START


# ── the page ────────────────────────────────────────────────────────────────

PAGE = ROOT / "kinneret_app" / "pages" / "10_Days_to_Red_Line.py"


def run_page(monkeypatch, fan_path):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("KINNERET_FAN_FILE", str(fan_path))
    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.run()
    return at


def text(at):
    return "\n".join(m.value for m in at.markdown) + "\n".join(c.value for c in at.caption)


def test_page_shows_the_fan_and_the_12_month_odds(monkeypatch, tmp_path):
    f, _ = made()
    p = tmp_path / "fan.json"
    fan_today.write(f, p)
    at = run_page(monkeypatch, p)
    assert not at.exception, at.exception
    t = text(at)
    h365 = next(h for h in f["horizons"] if h["H"] == 365)
    assert f"{h365['p_red']:.0%}" in t                     # chance still below -213 in 12 months
    assert "8 Oct 2026" in t                               # the start it was made from
    without = run_page(monkeypatch, tmp_path / "missing.json")
    assert len(at.get("plotly_chart")) == len(without.get("plotly_chart")) + 1   # the fan chart


def test_page_without_the_file_still_renders(monkeypatch, tmp_path):
    at = run_page(monkeypatch, tmp_path / "missing.json")
    assert not at.exception, at.exception
    assert "not available" in text(at).lower()
