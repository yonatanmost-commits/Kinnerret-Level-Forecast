"""cfc_tournament keeps forecasts whose outcome is not known yet only when asked
(CFC_FUTURE / --keep-future): a real forecast from today, not a backtest."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))


def fresh():
    spec = importlib.util.spec_from_file_location("ct_future", ROOT / "Automation" / "cfc_tournament.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def table(n=30):
    return pd.DataFrame({"date": pd.date_range("2026-10-01", periods=n), "level_m": -213.0 + np.arange(n) * 0.001})


def test_backtest_drops_unknown_outcomes():
    ct = fresh()
    base = table()
    P = np.full((1, ct.HMAX), -212.0)
    rows = ct.records("B14", 2026, base, np.array([20]), {"clim": P})
    assert {r["H"] for r in rows} == {7}                      # 20 + 13 is past the table


def test_keep_future_keeps_them_with_no_outcome():
    ct = fresh()
    ct.KEEP_FUTURE = True
    base = table()
    P = np.full((1, ct.HMAX), -212.0)
    rows = ct.records("B14", 2026, base, np.array([20]), {"clim": P})
    assert {r["H"] for r in rows} == set(ct.HORIZONS)
    future = [r for r in rows if r["H"] > 7]
    assert all(r["obs"] is None for r in future) and all(r["pred"] == -212.0 for r in future)
