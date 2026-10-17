"""Acceptance tests for the monthly long-range fan (bug: the 6-month card value was a straight
line between the 130 d and 260 d forecasts, which cuts under the spring peak; for October
starts the real 182 d level averaged 0.42 m above that line, 2011-2025).

- the bench can forecast a monthly set of horizons (CFC_HORIZONS), the default set unchanged
- the card reads a horizon only where the model forecast it, never across a gap
- with monthly horizons the page shows 6-month numbers and a month-by-month table;
  with the old 130/260/365 file it shows no 6-month numbers
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))
sys.path.insert(0, str(ROOT / "kinneret_app"))
import fan_today  # noqa: E402

MONTHLY = [7, 13, 26, 30, 61, 91, 122, 130, 152, 182, 213, 243, 260, 274, 304, 335, 365]
OLD = [7, 13, 26, 130, 260, 365]
START = "2026-10-08"
PAGE = ROOT / "kinneret_app" / "pages" / "10_Days_to_Red_Line.py"


def bench_horizons(value=None):
    env = {k: v for k, v in os.environ.items() if k != "CFC_HORIZONS"}
    if value is not None:
        env["CFC_HORIZONS"] = value
    code = "import cfc_tournament as t; print(t.HORIZONS, t.HMAX)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "Automation", env=env,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_bench_default_horizons_unchanged():
    assert bench_horizons() == f"{OLD} 365"


def test_bench_monthly_horizons():
    assert bench_horizons("monthly") == f"{MONTHLY} 365"
    assert bench_horizons("7,30,182,365") == "[7, 30, 182, 365] 365"


def fan(hs):
    """A fan file whose median rises to a spring peak at 182 d, as the lake does."""
    peak = lambda H: -213.65 + 2.0 * np.sin(np.pi * min(H, 300) / 365)
    horizons = [{"H": H, "date": str((pd.Timestamp(START) + pd.Timedelta(days=H)).date()),
                 "median": peak(H), **{f"{s}_{k}": peak(H) + (w if s == "hi" else -w)
                                       for k, w in ((50, .3), (80, .6), (90, .8)) for s in ("lo", "hi")},
                 "p_red": round(0.1 + H / 2000, 3), "p_upper": 0.0} for H in hs]
    return {"made_on": "2026-10-17", "start": START, "level0": -213.65, "model": "test",
            "seasonal": {}, "lines": {"red": -213.0, "upper": -208.8}, "horizons": horizons,
            "scenarios": [{"kind": k, "winter": w, "path": [{"H": H, "level": -213.0} for H in hs]}
                          for k, w in (("wettest", "2018-19"), ("driest", "2024-25"))]}


def test_card_reads_only_forecast_horizons():
    import fan_card
    f = fan(MONTHLY)
    h182 = next(h for h in f["horizons"] if h["H"] == 182)
    assert fan_card._at(f, "median", 182) == h182["median"]
    assert fan_card._at(fan(OLD), "median", 182) is None          # no straight line across 130..260


def run_page(monkeypatch, tmp_path, f):
    from streamlit.testing.v1 import AppTest
    p = tmp_path / "fan.json"
    fan_today.write(f, p)
    monkeypatch.setenv("KINNERET_FAN_FILE", str(p))
    at = AppTest.from_file(str(PAGE), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def metric_labels(at):
    return [m.label for m in at.metric]


def test_page_shows_6_month_numbers_and_month_by_month_with_monthly_file(monkeypatch, tmp_path):
    f = fan(MONTHLY)
    at = run_page(monkeypatch, tmp_path, f)
    labels = metric_labels(at)
    assert any("6 months" in l for l in labels) and any("12 months" in l for l in labels)
    h182 = next(h for h in f["horizons"] if h["H"] == 182)
    assert f"{h182['median']:.2f} m" in [m.value for m in at.metric]
    tables = at.dataframe if len(at.dataframe) else at.table
    assert len(tables) == 1
    shown = tables[0].value
    assert len(shown) == 12                                       # one row per month, Nov .. Oct


def test_page_hides_6_month_numbers_with_the_old_file(monkeypatch, tmp_path):
    at = run_page(monkeypatch, tmp_path, fan(OLD))
    labels = metric_labels(at)
    assert not any("6 months" in l for l in labels)
    assert any("12 months" in l for l in labels)
