# tests/test_longrange_cordex_calibrate.py
import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def test_write_cordex_config_creates_required_keys(tmp_path, monkeypatch):
    """write_cordex_config must write cordex_config.json with all required keys."""
    import longrange_cordex_calibrate as cal

    # Stub out the heavy IO
    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(cal, "META_PATH", tmp_path / "model_metadata.json")
    monkeypatch.setattr(cal, "LEVEL_PATH", tmp_path / "kinneret_level.csv")

    # Write fake meta
    (tmp_path / "model_metadata.json").write_text(
        json.dumps({"bathy_vol2level_coeffs": [-3.83e-7, 0.00917, -241.44]})
    )
    # Write fake level file spanning 2006-2015 to cover both anchor and calib start
    dates = pd.date_range("2006-01-01", "2015-12-31", freq="D")
    pd.DataFrame({
        "date": dates,
        "kinneret_level": [-211.65] * len(dates),
    }).to_csv(tmp_path / "kinneret_level.csv", index=False)

    # Stub run_water_balance + load_cordex so no real CORDEX needed
    fake_dates = pd.date_range("2012-01-01", periods=30)
    fake_wb = pd.DataFrame({
        "date": list(fake_dates) * 2,
        "model": ["m"] * 60,
        "scenario": ["rcp45"] * 60,
        "level_m": [-211.5] * 60,
        "dv_Mm3": [0.1] * 60,
        "volume_Mm3": [3876.0] * 60,
        "lake_ET_Mm3": [0.2] * 60,
        "inflow_clim_Mm3": [1.0] * 60,
        "et0_lake_mm": [1.5] * 60,
        "et0_catch_mm": [1.2] * 60,
    })
    fake_cordex = pd.DataFrame({
        "date": fake_dates, "model": "m", "scenario": "rcp45",
        "site": "bet_zayda", "tmin": 8.0, "tmax": 20.0, "doy": 1,
    })

    import longrange_cordex_waterbalance as wb_mod
    import longrange_cordex_ingest as ing_mod
    monkeypatch.setattr(wb_mod, "GOLD_PATH", tmp_path / "kinneret_level.csv")  # won't be called
    monkeypatch.setattr(cal, "run_water_balance", lambda *a, **kw: fake_wb, raising=False)
    monkeypatch.setattr(cal, "load_cordex", lambda: fake_cordex, raising=False)

    result = cal.write_cordex_config()
    cfg = json.loads((tmp_path / "cordex_config.json").read_text())
    for key in ["bathy_vol2level_coeffs", "anchor_date", "anchor_level_m", "calibration_rmse_m"]:
        assert key in cfg, f"missing key: {key}"


def test_write_cordex_config_rmse_nonnegative(tmp_path, monkeypatch):
    """calibration_rmse_m must be a non-negative float."""
    import longrange_cordex_calibrate as cal

    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(cal, "META_PATH", tmp_path / "model_metadata.json")
    monkeypatch.setattr(cal, "LEVEL_PATH", tmp_path / "kinneret_level.csv")

    (tmp_path / "model_metadata.json").write_text(
        json.dumps({"bathy_vol2level_coeffs": [-3.83e-7, 0.00917, -241.44]})
    )
    # Write fake level file spanning 2006-2015 to cover both anchor and calib start
    dates = pd.date_range("2006-01-01", "2015-12-31", freq="D")
    pd.DataFrame({
        "date": dates,
        "kinneret_level": [-211.65] * len(dates),
    }).to_csv(tmp_path / "kinneret_level.csv", index=False)

    fake_dates = pd.date_range("2012-01-01", periods=30)
    fake_wb = pd.DataFrame({
        "date": list(fake_dates) * 2, "model": ["m"] * 60,
        "scenario": ["rcp45"] * 60, "level_m": [-211.5] * 60,
        "dv_Mm3": [0.1] * 60, "volume_Mm3": [3876.0] * 60,
        "lake_ET_Mm3": [0.2] * 60, "inflow_clim_Mm3": [1.0] * 60,
        "et0_lake_mm": [1.5] * 60, "et0_catch_mm": [1.2] * 60,
    })
    fake_cordex = pd.DataFrame({
        "date": fake_dates, "model": "m", "scenario": "rcp45",
        "site": "bet_zayda", "tmin": 8.0, "tmax": 20.0, "doy": 1,
    })

    monkeypatch.setattr(cal, "run_water_balance", lambda *a, **kw: fake_wb, raising=False)
    monkeypatch.setattr(cal, "load_cordex", lambda: fake_cordex, raising=False)

    cal.write_cordex_config()
    cfg = json.loads((tmp_path / "cordex_config.json").read_text())
    assert cfg["calibration_rmse_m"] >= 0.0
