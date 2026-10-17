"""cfc_tournament --no-humidity: drop every input derived from humidity (humidity, VPD, ET0
and its sums), for the check that the 2012-13 humidity step in the IMS stations does not
steer the models. Applies to B (CfC, GRU, LSTM) and to the relay (A, A1, G)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))
GONE = ("humidity", "vpd", "et0", "moisture_balance")


def fresh():
    spec = importlib.util.spec_from_file_location("ct_fresh", ROOT / "Automation" / "cfc_tournament.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_daily_weather_and_window_summaries_lose_humidity_inputs():
    ct = fresh()
    ct.drop_humidity()
    assert not any(c.startswith(GONE) for c in ct.DM)
    W = np.ones((2, 400, len(ct.DM)))
    S = ct.window_summaries(W)
    per_window = len(ct.SUM_COLS) + len(ct.MEAN_COLS)
    assert per_window == 4 and S.shape == (2, len(ct.HORIZONS) * per_window)
    assert not np.isnan(S).any()


def test_relay_features_lose_humidity_inputs():
    ct = fresh()
    ct.drop_humidity()
    feats = ["rainfall_mm", "humidity_pct", "vpd_kPa", "et0_mm", "et0_7d_mm",
             "moisture_balance_7d_mm", "temp_mean_C", "level_m"]
    assert ct.relay_features(feats) == ["rainfall_mm", "temp_mean_C", "level_m"]


def test_default_keeps_everything():
    ct = fresh()
    assert "humidity_pct" in ct.DM
    assert ct.relay_features(["humidity_pct", "et0_mm"]) == ["humidity_pct", "et0_mm"]
