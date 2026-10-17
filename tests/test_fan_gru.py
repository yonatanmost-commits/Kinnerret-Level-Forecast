"""Acceptance tests for the swap of the app's long-range fan from the CfC to the GRU
(user, 2026-10-17: "lets swap to GRU"; final run cfc_monthly, the two tie, the GRU trains in a third
of the time).

- the fan is made from the GRU unless told otherwise, and says so in its model label
- the shipped app file is the GRU's
- the track record scores the GRU's fan backtest
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))
sys.path.insert(0, str(ROOT / "tests"))
import cfc_track_record  # noqa: E402
import fan_today  # noqa: E402


def test_fan_is_made_from_the_gru_by_default():
    assert fan_today.METHOD == "B14gru"
    assert "GRU" in fan_today.MODELS["B14gru"] and "CfC" in fan_today.MODELS["B14"]


def test_fan_label_follows_the_method():
    import pandas as pd
    from test_fan_today import errors, members        # the fan_today tests' small synthetic inputs
    m = members()
    w = pd.Series(1.0, index=m.index)
    assert fan_today.build(m, errors(), w, m["start"].iloc[0], {})["model"] == fan_today.MODELS["B14gru"]
    assert fan_today.build(m, errors(), w, m["start"].iloc[0], {}, method="B14")["model"] == fan_today.MODELS["B14"]


def test_shipped_app_fan_is_the_gru():
    fan = json.loads((ROOT / "Models" / "longrange_fan.json").read_text(encoding="utf-8"))
    assert "GRU" in fan["model"]
    assert 182 in [h["H"] for h in fan["horizons"]]


def test_track_record_scores_the_gru_fan():
    assert cfc_track_record.FAN.name == "fan_monthly_B14gru_seas5.csv"
