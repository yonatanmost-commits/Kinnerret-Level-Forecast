# tests/test_signal_harvest.py
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


# ── Feature list membership ──────────────────────────────────────────────────

def test_rbf_features_in_s1_features():
    from model_lib import S1_FEATURES
    for f in ["rbf_spring_equinox", "rbf_summer_solstice",
              "rbf_autumn_equinox", "rbf_winter_solstice"]:
        assert f in S1_FEATURES, f"{f} missing from S1_FEATURES"


def test_precip_intensity_in_s1_features():
    from model_lib import S1_FEATURES
    assert "precip_intensity_mm_hr" in S1_FEATURES


def test_rbf_features_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    for f in ["rbf_spring_equinox", "rbf_summer_solstice",
              "rbf_autumn_equinox", "rbf_winter_solstice"]:
        assert f in S2_DIRECT_FEATURES, f"{f} missing from S2_DIRECT_FEATURES"


def test_precip_intensity_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "precip_intensity_mm_hr" in S2_DIRECT_FEATURES


def test_outflow_lag1_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "outflow_lag1_m3" in S2_DIRECT_FEATURES


def test_dvol_lag2_anchor_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "dvol_lag2_anchor" in S2_DIRECT_FEATURES


def test_dvol_lag3_anchor_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "dvol_lag3_anchor" in S2_DIRECT_FEATURES


def test_s2_direct_no_inflow_still_subset():
    from model_lib import S2_DIRECT_FEATURES, S2_DIRECT_NO_INFLOW_FEATURES
    assert set(S2_DIRECT_NO_INFLOW_FEATURES) < set(S2_DIRECT_FEATURES)
    assert len(S2_DIRECT_NO_INFLOW_FEATURES) == len(S2_DIRECT_FEATURES) - 1


# ── build_direct_s2_data produces new anchor columns ─────────────────────────

def _make_s2_df(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "date":                pd.date_range("2020-01-01", periods=n),
        "inflow_obstacle_m3":  rng.uniform(1e5, 1e6, n),
        "volume_change_Mm3":   rng.uniform(-1.0, 1.0, n),
        "outflow_baptism_m3":  rng.uniform(0.1, 0.5, n),
        "level_m":             rng.uniform(-214, -208, n),
        **{c: rng.uniform(0.0, 1.0, n) for c in [
            "rainfall_mm", "rainfall_7d_mm", "rainfall_21d_mm",
            "temp_mean_C", "temp_max_C", "humidity_pct",
            "wind_speed_ms", "vpd_kPa", "et0_mm", "et0_7d_mm",
            "radiation_MJm2", "season_sin", "season_cos", "daylength_hrs",
            "rbf_spring_equinox", "rbf_summer_solstice",
            "rbf_autumn_equinox", "rbf_winter_solstice",
            "precip_intensity_mm_hr",
        ]},
    })


def test_build_direct_s2_data_has_outflow_lag1():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "outflow_lag1_m3" in result.columns


def test_build_direct_s2_data_has_dvol_lag2_anchor():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "dvol_lag2_anchor" in result.columns


def test_build_direct_s2_data_has_dvol_lag3_anchor():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "dvol_lag3_anchor" in result.columns


def test_outflow_lag1_is_shifted_by_one():
    """outflow_lag1_m3 at each anchor row t must equal outflow_baptism_m3 at t-1."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    df = _make_s2_df(20)
    result = m.build_direct_s2_data(df)
    # For anchor row at index 2 (date 2020-01-03) and horizon h=1:
    anchor_idx = 2
    h1_rows = result[result["date"] == df["date"].iloc[anchor_idx]]
    expected_outflow = df["outflow_baptism_m3"].shift(1).iloc[anchor_idx]
    actual_outflow = h1_rows["outflow_lag1_m3"].iloc[0]
    np.testing.assert_almost_equal(actual_outflow, expected_outflow)


# ── signed_log1p_transform applied in run_cv and train_final ─────────────────

def test_train_final_applies_s2_transform():
    """signed_log1p_transform must be called for Stage-2 fit in train_final."""
    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location(
        "_08e", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

    from model_lib import S1_FEATURES, S2_FEATURES, S1_TARGET, S2_TARGET
    rng = np.random.default_rng(1)
    dates = pd.date_range("2012-01-01", "2015-12-31", freq="D")  # short for speed
    n = len(dates)
    all_cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET, "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3", "outflow_baptism_m3",
    ]))
    df = pd.DataFrame({"date": dates, **{c: rng.uniform(0.1, 1.0, n) for c in all_cols}})
    oof = pd.Series(rng.uniform(0.1, 1.0, n), index=df.index)

    call_count = []
    orig = m.signed_log1p_transform
    def spy(y):
        call_count.append(1)
        return orig(y)

    with patch.object(m, "signed_log1p_transform", side_effect=spy):
        m.train_final(df, oof)

    assert len(call_count) >= 2, (
        f"signed_log1p_transform called {len(call_count)}x; expected >=2 (gb2 + gb2d)"
    )
