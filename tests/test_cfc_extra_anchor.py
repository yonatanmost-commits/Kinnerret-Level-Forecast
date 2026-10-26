"""A forecast from the last measured day, so the fan can use a seasonal forecast published that week
(5 Nov update plan, D1 (a)).

Starts fall every 7th day of the year (cfc_tournament.anchors_for), and the November one is 5 Nov,
but SEAS5 counts as published only AFTER the 5th (seas5.init_for), so a 5 Nov start still reads
the October issue. CFC_ANCHOR=YYYY-MM-DD adds one start on that day, in its own year only, and
only on a day whose level was measured (never a filled-in day).
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("CFC_HORIZONS", "monthly")
sys.path.insert(0, str(ROOT / "Automation"))
import cfc_tournament as ct  # noqa: E402
import seas5  # noqa: E402


def base(missing=()):
    d = pd.DataFrame({"date": pd.date_range("2025-01-01", "2026-11-09")})
    d["level_m"] = -213.5
    d.loc[d["date"].isin(pd.to_datetime(list(missing))), "level_m"] = np.nan
    return d


def test_the_5_nov_start_still_reads_the_october_issue():
    assert seas5.init_for(pd.Timestamp("2026-11-05")) == pd.Timestamp("2026-10-01")
    assert seas5.init_for(pd.Timestamp("2026-11-08")) == pd.Timestamp("2026-11-01")


def test_no_extra_start_unless_asked(monkeypatch):
    monkeypatch.setattr(ct, "EXTRA_ANCHOR", None)
    b = base()
    days = b["date"].iloc[ct.anchors_for(b, 2026)]
    assert pd.Timestamp("2026-11-08") not in set(days)
    assert (days.dt.dayofyear % 7 == 1).all()                  # 1 Jan, 8 Jan ... 5 Nov


def test_the_extra_start_is_added_on_its_day(monkeypatch):
    monkeypatch.setattr(ct, "EXTRA_ANCHOR", "2026-11-08")
    b = base()
    a = ct.anchors_for(b, 2026)
    days = b["date"].iloc[a]
    assert days.iloc[-1] == pd.Timestamp("2026-11-08")         # the latest start
    assert list(a) == sorted(set(a))                           # sorted, no duplicates
    assert pd.Timestamp("2026-11-05") in set(days)             # the grid is kept


def test_the_extra_start_belongs_to_its_own_year(monkeypatch):
    monkeypatch.setattr(ct, "EXTRA_ANCHOR", "2026-11-08")
    b = base()
    assert pd.Timestamp("2026-11-08") not in set(b["date"].iloc[ct.anchors_for(b, 2025)])


def test_never_on_a_day_without_a_measured_level(monkeypatch):
    monkeypatch.setattr(ct, "EXTRA_ANCHOR", "2026-11-08")
    with pytest.raises(ValueError):
        ct.anchors_for(base(missing=["2026-11-08"]), 2026)
