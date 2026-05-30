# tests/test_error_prop_olympics.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))

from model_lib import S2_DIRECT_FEATURES, S2_DIRECT_NO_INFLOW_FEATURES


def test_no_inflow_features_excludes_predicted_inflow():
    assert "predicted_inflow_m3" not in S2_DIRECT_NO_INFLOW_FEATURES


def test_no_inflow_features_is_subset_of_direct_features():
    assert set(S2_DIRECT_NO_INFLOW_FEATURES) < set(S2_DIRECT_FEATURES)


def test_no_inflow_features_length():
    assert len(S2_DIRECT_NO_INFLOW_FEATURES) == len(S2_DIRECT_FEATURES) - 1


import numpy as np
import pandas as pd
import pytest


def _make_minimal_df(n_rows: int = 30) -> pd.DataFrame:
    """Tiny but complete gold-like DataFrame for testing."""
    from model_lib import (
        S1_FEATURES, S1_TARGET, S2_FEATURES, S2_TARGET,
    )
    dates = pd.date_range("2020-01-01", periods=n_rows)
    rng = np.random.default_rng(0)
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET,
        "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
    ]))
    data = {"date": dates}
    for c in cols:
        data[c] = rng.uniform(0.1, 1.0, n_rows)
    df = pd.DataFrame(data)
    return df


def test_simulate_7d_chain_returns_7_rows():
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(30)
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((10, len(S1_FEATURES))), np.ones(10))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((10, len(S2_FEATURES))), np.ones(10))

    anchor = pd.Timestamp("2020-01-10")
    rows = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    assert len(rows) == 7


def test_simulate_7d_chain_missing_future_returns_empty():
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(5)   # only 5 rows; no room for 7 future days from day 1
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((5, len(S1_FEATURES))), np.ones(5))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((5, len(S2_FEATURES))), np.ones(5))

    anchor = pd.Timestamp("2020-01-04")  # only 1 future row available (day 5)
    rows = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    assert rows == []


def _make_cv_df() -> pd.DataFrame:
    """Minimal gold-like DataFrame spanning 2012–2024 for CV fold testing."""
    from model_lib import S1_FEATURES, S2_FEATURES, S1_TARGET, S2_TARGET
    rng = np.random.default_rng(42)
    dates = pd.date_range("2012-01-01", "2024-12-31", freq="D")
    n = len(dates)
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET, "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
    ]))
    data = {"date": dates}
    for c in cols:
        data[c] = rng.uniform(0.1, 1.0, n)
    return pd.DataFrame(data)


def test_run_cv_max_chain_returns_4_folds():
    from _08_train_forecast_model import run_cv_max_chain

    df = _make_cv_df()
    bathy = [0.0, 0.0, -208.0]  # constant level ≈ -208m
    results = run_cv_max_chain(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)
    assert all("s1_r2" in r for r in results)
