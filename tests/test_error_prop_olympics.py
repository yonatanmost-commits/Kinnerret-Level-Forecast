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


def test_run_cv_s1_direct_s2_anchor_returns_4_folds():
    from _08_train_forecast_model import run_cv_s1_direct_s2_anchor

    df = _make_cv_df()
    from model_lib import S1_DIRECT_FEATURES, S2_DIRECT_FEATURES
    rng = np.random.default_rng(1)
    for c in set(S1_DIRECT_FEATURES + S2_DIRECT_FEATURES):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    bathy = [0.0, 0.0, -208.0]
    results = run_cv_s1_direct_s2_anchor(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)
    assert all("s1_r2" in r for r in results)


def test_run_cv_single_stage_returns_4_folds():
    from _08_train_forecast_model import run_cv_single_stage
    from model_lib import S2_DIRECT_NO_INFLOW_FEATURES

    df = _make_cv_df()
    rng = np.random.default_rng(2)
    for c in S2_DIRECT_NO_INFLOW_FEATURES:
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    bathy = [0.0, 0.0, -208.0]
    results = run_cv_single_stage(df, bathy)
    assert len(results) == 4
    assert all(r["s1_r2"] is None for r in results)
    assert all("drift_m" in r for r in results)


def test_run_cv_s1_chain_s2_roll1_returns_4_folds():
    from _08_train_forecast_model import run_cv_s1_chain_s2_roll1

    df = _make_cv_df()
    bathy = [0.0, 0.0, -208.0]
    results = run_cv_s1_chain_s2_roll1(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)


def test_roll1_dvol_lag2_stays_fixed():
    """roll_dvol_only=True must not update dvol_lag2_fixed across steps."""
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(30)
    df["volume_change_Mm3"] = 0.999
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((10, len(S1_FEATURES))), np.ones(10))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((10, len(S2_FEATURES))), np.ones(10))

    anchor = pd.Timestamp("2020-01-10")
    rows_e = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=True)
    rows_a = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    assert len(rows_e) == 7
    assert len(rows_a) == 7


def test_train_final_gbr_s1_direct_s2_anchor_creates_pkls(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    df = _make_cv_df()
    from model_lib import S1_DIRECT_FEATURES, S2_DIRECT_FEATURES, S1_TARGET, S2_DIRECT_TARGET
    rng = np.random.default_rng(3)
    for c in set(S1_DIRECT_FEATURES + S2_DIRECT_FEATURES + [S1_TARGET, S2_DIRECT_TARGET]):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    m08.train_final_gbr_s1_direct_s2_anchor(df, _n_est=2)
    assert (tmp_path / "gbr_s1_direct.pkl").exists()
    assert (tmp_path / "gbr_s2_anchor.pkl").exists()


def test_train_final_gbr_single_stage_creates_pkl(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    df = _make_cv_df()
    from model_lib import S2_DIRECT_NO_INFLOW_FEATURES, S2_DIRECT_TARGET
    rng = np.random.default_rng(4)
    for c in set(S2_DIRECT_NO_INFLOW_FEATURES + [S2_DIRECT_TARGET]):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    m08.train_final_gbr_single_stage(df, _n_est=2)


def test_save_olympics_results_includes_new_architectures(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    dummy_cv = [{"fold": str(y), "n_test": 10, "s1_r2": 0.9,
                 "s2_r2": 0.7, "s2_mae": 0.5, "drift_m": 0.05}
                for y in range(2021, 2025)]
    baseline = {"cv_vol_r2_mean": 0.694, "cv_vol_r2_by_fold": {},
                "cv_vol_mae_mean": 0.667, "cv_7d_drift_mean_m": None,
                "cv_inflow_r2_mean": 0.920}

    import pandas as pd
    df = pd.DataFrame({"date": pd.to_datetime(["2024-12-31"])})

    m08.save_olympics_results(
        baseline,
        dummy_cv, dummy_cv, dummy_cv,   # xgb, lgb, gru
        dummy_cv, dummy_cv, dummy_cv, dummy_cv,   # A, C, D, E
        df)

    import json
    with open(tmp_path / "olympics_results.json") as f:
        data = json.load(f)
    assert "gbr_max_chain" in data["models"]
    assert "gbr_s1_direct_s2_anchor" in data["models"]
    assert "gbr_single_stage" in data["models"]
    assert "gbr_s1_chain_s2_roll1" in data["models"]
