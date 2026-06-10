"""
Write docs/cordex_config.json — bathy coefficients, anchor date/level.

The water balance uses a DOY inflow climatology from observed gold data, so
there is no parameter to optimize. This script just assembles the config that
the dashboard and hindcast scripts need, and computes a quick hindcast RMSE
on the 2012-2024 period as a sanity check.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT    = Path(__file__).resolve().parent.parent
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
META_PATH       = PROJECT_ROOT / "Models" / "model_metadata.json"
LEVEL_PATH      = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
ANCHOR_DATE     = "2006-01-01"

# Lazy imports — populated on first use or replaced by monkeypatch in tests
sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
try:
    from longrange_cordex_waterbalance import run_water_balance
    from longrange_cordex_ingest import load_cordex
except ImportError:
    run_water_balance = None  # type: ignore[assignment]
    load_cordex = None        # type: ignore[assignment]


def write_cordex_config() -> dict:
    """Write docs/cordex_config.json with bathy coeffs and anchor info.

    Returns the config dict.
    """
    import longrange_cordex_calibrate as _self
    _run_water_balance = _self.run_water_balance
    _load_cordex       = _self.load_cordex

    meta         = json.loads(META_PATH.read_text())
    bathy_coeffs = meta["bathy_vol2level_coeffs"]

    level_obs = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    anchor_row = level_obs[level_obs["date"] == pd.Timestamp(ANCHOR_DATE)]
    if anchor_row.empty:
        raise ValueError(f"No observed level on {ANCHOR_DATE}")
    anchor_level_m = float(anchor_row["kinneret_level"].iloc[0])

    # Quick hindcast RMSE on 2012-2024 (gold overlap)
    cordex = _load_cordex()
    mask_calib = (cordex["date"] >= pd.Timestamp("2012-01-01")) & \
                 (cordex["date"] <= pd.Timestamp("2024-12-31"))
    wb = _run_water_balance(
        cordex[mask_calib].copy(),
        anchor_level_m=float(
            level_obs[level_obs["date"] == pd.Timestamp("2012-01-01")]["kinneret_level"].iloc[0]
        ),
        anchor_date="2012-01-01",
    )
    med = wb.groupby("date")["level_m"].median().reset_index()
    merged = med.merge(
        level_obs.rename(columns={"kinneret_level": "obs"}),
        on="date", how="inner",
    ).dropna()
    rmse = float(np.sqrt(np.mean((merged["level_m"] - merged["obs"]) ** 2)))

    cfg = {
        "bathy_vol2level_coeffs": bathy_coeffs,
        "anchor_date":             ANCHOR_DATE,
        "anchor_level_m":          anchor_level_m,
        "calibration_rmse_m":      round(rmse, 4),
    }
    CORDEX_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORDEX_CFG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"Config written. Hindcast RMSE (2012-2024) = {rmse:.3f} m")
    return cfg


if __name__ == "__main__":
    write_cordex_config()
