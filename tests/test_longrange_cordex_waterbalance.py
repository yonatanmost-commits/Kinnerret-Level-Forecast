import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_cordex_long(n_days=30):
    """Minimal long-frame CORDEX fixture: 1 model × 1 scenario × 2 sites × n days."""
    dates = pd.date_range("2006-01-01", periods=n_days)
    rows = []
    for site in ["bet_zayda", "zemah"]:
        for d in dates:
            rows.append({
                "date": d, "model": "cnrm_cclm", "scenario": "rcp45",
                "site": site, "tmin": 8.0, "tmax": 20.0,
                "doy": d.day_of_year,
            })
    return pd.DataFrame(rows)


def _make_clim(tmp_path):
    """Write a minimal climatology CSV (all DOYs, constant values)."""
    doys = list(range(1, 367))
    df = pd.DataFrame({
        "doy": doys,
        "temp_max_clim": [20.0] * 366,
        "temp_min_clim": [8.0] * 366,
        "dtr_clim": [12.0] * 366,
        "dtr_clearsky": [15.0] * 366,
        "et0_clim": [3.0] * 366,
        "p_wet_clim": [0.2] * 366,
        "amount_clim": [10.0] * 366,
        "outflow_clim": [400000.0] * 366,   # m³/day
    })
    p = tmp_path / "longrange_climatology.csv"
    df.to_csv(p, index=False)
    return p


def _make_configs(tmp_path):
    """Write minimal longrange_config.json and cordex_config.json."""
    cfg = {"hargreaves_calibration": {"slope": 1.0, "intercept": 0.0}}
    (tmp_path / "longrange_config.json").write_text(json.dumps(cfg))
    ccfg = {"catchment_scale_Mm3_per_mm": 1.0, "S_max_mm": 150.0,
            "bathy_vol2level_coeffs": [-3.83e-7, 0.00917, -241.44]}
    (tmp_path / "cordex_config.json").write_text(json.dumps(ccfg))
    return tmp_path / "longrange_config.json", tmp_path / "cordex_config.json"


def test_level_from_volume_round_trip():
    """level_from_volume and volume_from_level must be mutual inverses."""
    import longrange_cordex_waterbalance as wb
    coeffs = [-3.83e-7, 0.00917, -241.44]
    for vol in [3400.0, 3800.0, 4200.0]:
        level = wb.level_from_volume(vol, coeffs)
        vol_back = wb.volume_from_level(level, coeffs)
        assert abs(vol_back - vol) < 0.1, f"round-trip failed at vol={vol}"


def test_run_water_balance_output_schema(tmp_path, monkeypatch):
    """run_water_balance must return required columns for every (model, scenario) pair."""
    import longrange_cordex_waterbalance as wb
    monkeypatch.setattr(wb, "CFG_PATH", tmp_path / "longrange_config.json")
    monkeypatch.setattr(wb, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(wb, "CLIM_PATH", tmp_path / "longrange_climatology.csv")
    _make_configs(tmp_path)
    _make_clim(tmp_path)
    cordex = _make_cordex_long(n_days=30)
    result = wb.run_water_balance(cordex, anchor_level_m=-211.65, anchor_date="2006-01-01")
    for col in ["date", "model", "scenario", "dv_Mm3", "volume_Mm3", "level_m",
                "lake_ET_Mm3", "P_est_mm", "runoff_mm", "et0_lake_mm", "et0_catch_mm"]:
        assert col in result.columns, f"missing column: {col}"


def test_volume_integrates_from_anchor(tmp_path, monkeypatch):
    """volume_Mm3 on anchor_date must equal the anchor volume (within 0.5 Mm³)."""
    import longrange_cordex_waterbalance as wb
    monkeypatch.setattr(wb, "CFG_PATH", tmp_path / "longrange_config.json")
    monkeypatch.setattr(wb, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(wb, "CLIM_PATH", tmp_path / "longrange_climatology.csv")
    _make_configs(tmp_path)
    _make_clim(tmp_path)
    cordex = _make_cordex_long(n_days=30)
    result = wb.run_water_balance(cordex, anchor_level_m=-211.65, anchor_date="2006-01-01")
    anchor_row = result[result["date"] == pd.Timestamp("2006-01-01")]
    expected_vol = wb.volume_from_level(-211.65, [-3.83e-7, 0.00917, -241.44])
    assert abs(anchor_row["volume_Mm3"].iloc[0] - expected_vol) < 0.5
