import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_wb_result(catchment_scale=2.0, n=365):
    """Synthetic water balance output as if run with cs=1.0 (Q=0.5mm/day constant)."""
    dates = pd.date_range("2012-01-01", periods=n)
    Q_mm = 0.5     # mm/day runoff
    et_Mm3 = 0.2   # lake ET Mm3/day
    out_Mm3 = 0.4  # outflow Mm3/day
    # dv was computed with cs=1.0, so dv = Q*1 - et - out
    dv = Q_mm * 1.0 - et_Mm3 - out_Mm3
    vol = 3800.0 + np.cumsum(np.full(n, dv))
    coeffs = [-3.83e-7, 0.00917, -241.44]
    level = np.polyval(coeffs, vol)
    return pd.DataFrame({
        "date": dates, "model": "m1", "scenario": "rcp45",
        "dv_Mm3": dv, "volume_Mm3": vol, "level_m": level,
        "lake_ET_Mm3": et_Mm3, "P_est_mm": 1.0,
        "runoff_mm": Q_mm, "et0_lake_mm": 1.5, "et0_catch_mm": 1.2,
    })


def _make_obs_for_cs(true_cs, wb_df):
    """Make obs level that corresponds to running the water balance with true_cs."""
    rng = np.random.default_rng(42)
    # With cs=true_cs: vol = 3800 + cumsum(Q*cs - et - out) = 3800 + cumsum(0.5*cs - 0.6)
    Q_mm = 0.5
    et_Mm3 = 0.2
    out_Mm3 = 0.4
    dv_true = Q_mm * true_cs - et_Mm3 - out_Mm3
    vol_true = 3800.0 + np.cumsum(np.full(len(wb_df), dv_true))
    coeffs = [-3.83e-7, 0.00917, -241.44]
    level_true = np.polyval(coeffs, vol_true)
    return pd.DataFrame({
        "date": wb_df["date"],
        "kinneret_level": level_true + rng.normal(0, 0.01, len(wb_df)),
    })


def test_calibrate_recovers_true_scale(tmp_path, monkeypatch):
    """calibrate_catchment_scale must recover catchment_scale within 20%."""
    import longrange_cordex_calibrate as cal
    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")

    true_cs = 2.0
    wb = _make_wb_result()
    obs = _make_obs_for_cs(true_cs, wb)

    result = cal.calibrate_catchment_scale(
        wb_result=wb, obs_level=obs,
        bathy_coeffs=[-3.83e-7, 0.00917, -241.44],
        anchor_vol=3800.0,
    )
    assert abs(result["catchment_scale_Mm3_per_mm"] - true_cs) / true_cs < 0.20


def test_calibrate_writes_config(tmp_path, monkeypatch):
    """calibrate_catchment_scale must write cordex_config.json with required keys."""
    import longrange_cordex_calibrate as cal
    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")

    wb = _make_wb_result()
    obs = _make_obs_for_cs(2.0, wb)
    cal.calibrate_catchment_scale(
        wb_result=wb, obs_level=obs,
        bathy_coeffs=[-3.83e-7, 0.00917, -241.44],
        anchor_vol=3800.0,
    )
    cfg = json.loads((tmp_path / "cordex_config.json").read_text())
    for key in ["catchment_scale_Mm3_per_mm", "S_max_mm", "bathy_vol2level_coeffs",
                "anchor_date", "anchor_level_m", "calibration_rmse_m"]:
        assert key in cfg, f"missing key: {key}"
