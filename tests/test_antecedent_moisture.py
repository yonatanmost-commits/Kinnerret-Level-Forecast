# tests/test_antecedent_moisture.py
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


# ── Feature list membership ───────────────────────────────────────────────────

def test_rainfall_30d_in_s1_features():
    from model_lib import S1_FEATURES
    assert "rainfall_30d_mm" in S1_FEATURES, "rainfall_30d_mm missing from S1_FEATURES"


def test_rainfall_45d_in_s1_features():
    from model_lib import S1_FEATURES
    assert "rainfall_45d_mm" in S1_FEATURES, "rainfall_45d_mm missing from S1_FEATURES"


def test_rainfall_30d_in_s2_met_features():
    from model_lib import S2_MET_FEATURES
    assert "rainfall_30d_mm" in S2_MET_FEATURES


def test_rainfall_45d_in_s2_met_features():
    from model_lib import S2_MET_FEATURES
    assert "rainfall_45d_mm" in S2_MET_FEATURES


def test_rainfall_30d_in_s2_direct_features():
    """S2_MET_FEATURES is included in S2_DIRECT_FEATURES, so this must propagate."""
    from model_lib import S2_DIRECT_FEATURES
    assert "rainfall_30d_mm" in S2_DIRECT_FEATURES


def test_rainfall_30d_in_s2_features():
    from model_lib import S2_FEATURES
    assert "rainfall_30d_mm" in S2_FEATURES


# ── build_feature_rows produces rolling windows from history ──────────────────

def _make_history_and_forecast():
    """50 days history (enough for 45d rolling) + 7 day forecast."""
    rng = np.random.default_rng(42)
    hist_dates = pd.date_range("2024-01-01", periods=50)
    history = pd.DataFrame({
        "date":           hist_dates,
        "rainfall_mm":    rng.uniform(0, 5, 50),
        "et0_mm":         rng.uniform(2, 8, 50),
        "level_m":        rng.uniform(-214, -208, 50),
        "volume_Mm3":     rng.uniform(2000, 4200, 50),
        "volume_change_Mm3": rng.uniform(-1, 1, 50),
        "outflow_baptism_m3": rng.uniform(0.2e6, 0.6e6, 50),
        "inflow_obstacle_m3": rng.uniform(1e5, 1e6, 50),
        **{c: rng.uniform(0, 1, 50) for c in [
            "temp_max_C", "temp_min_C", "humidity_pct",
            "wind_speed_ms", "radiation_MJm2",
        ]},
    })
    fc_dates = pd.date_range("2024-02-20", periods=7)
    forecast = pd.DataFrame({
        "date":           fc_dates,
        "temp_max_C":     rng.uniform(15, 25, 7),
        "temp_min_C":     rng.uniform(5, 15, 7),
        "rainfall_mm":    rng.uniform(0, 3, 7),
        "humidity_pct":   rng.uniform(40, 80, 7),
        "wind_speed_ms":  rng.uniform(2, 8, 7),
        "radiation_MJm2": rng.uniform(10, 25, 7),
    })
    return history, forecast


def test_build_feature_rows_produces_rainfall_30d():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_09", Path(__file__).parent.parent / "Automation" / "09_weekly_forecast.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    history, forecast = _make_history_and_forecast()
    result = m.build_feature_rows(forecast, history)
    assert "rainfall_30d_mm" in result.columns, "build_feature_rows must produce rainfall_30d_mm"
    assert "rainfall_45d_mm" in result.columns, "build_feature_rows must produce rainfall_45d_mm"


def test_build_feature_rows_rainfall_30d_uses_history():
    """Day-1 rainfall_30d_mm must reflect the 30-day window that spans history, not just forecast."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_09b", Path(__file__).parent.parent / "Automation" / "09_weekly_forecast.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    history, forecast = _make_history_and_forecast()

    # Manually compute what the 30d rolling sum should be for forecast day 1:
    # history has 50 days, forecast day 1 is day 51.
    # The 30-day window ending on day 51 = sum of days 22..51.
    all_rain = pd.concat([
        history[["date", "rainfall_mm"]],
        forecast[["date", "rainfall_mm"]],
    ]).sort_values("date").reset_index(drop=True)
    expected_day1 = float(all_rain["rainfall_mm"].rolling(30, min_periods=10).sum().iloc[50])

    result = m.build_feature_rows(forecast, history)
    actual_day1 = float(result["rainfall_30d_mm"].iloc[0])
    np.testing.assert_almost_equal(actual_day1, expected_day1, decimal=6)
