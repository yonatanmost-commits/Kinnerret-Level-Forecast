"""The fan slide's data is rebuilt by one script (5 Nov update plan, step 0).

docs/talk/data/slide11_fan_build.py must make ALL FOUR files chart_fan.py reads. The dots and
the crossings were made by hand on 19 Oct; the script must reproduce them from the same inputs:
  dots(run, backtest, fan)   <- docs/experiments/cfc_today_monthly, cfc_monthly, Models/longrange_fan.json
  crossings(fan_table, dots) <- the committed slide11_fan.csv and slide11_dots.csv
(The fan table itself is not replayed: its wet/normal/dry thirds read the gold table, whose rain
history was rebuilt on 18 Oct, a day after the run the slide shows.)
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "talk" / "data"


@pytest.fixture(scope="module")
def build():
    os.environ.setdefault("CFC_HORIZONS", "monthly")
    sys.path.insert(0, str(ROOT / "Automation"))
    spec = importlib.util.spec_from_file_location("slide11_fan_build", DATA / "slide11_fan_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # importing must not build anything
    return mod


def test_the_monthly_dots_are_rebuilt(build):
    import cfc_tournament_report as r
    run = r.load(ROOT / "docs" / "experiments" / "cfc_today_monthly")
    back = r.load(ROOT / "docs" / "experiments" / "cfc_monthly")
    fan = json.loads((ROOT / "Models" / "longrange_fan.json").read_text(encoding="utf-8"))
    new, old = build.dots(run, back, fan), pd.read_csv(DATA / "slide11_dots.csv")
    assert list(new.columns) == list(old.columns)
    assert new["date"].astype(str).tolist() == old["date"].tolist()
    num = [c for c in old.columns if c != "date"]
    pd.testing.assert_frame_equal(new[num].reset_index(drop=True), old[num], check_dtype=False, atol=0.0015)


def test_the_red_line_crossings_and_peaks_are_rebuilt(build):
    fan_table = pd.read_csv(DATA / "slide11_fan.csv")
    dots = pd.read_csv(DATA / "slide11_dots.csv")
    old = json.loads((DATA / "slide11_crossings.json").read_text(encoding="utf-8"))
    assert build.crossings(fan_table, dots) == old
