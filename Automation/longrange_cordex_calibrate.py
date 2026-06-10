"""
Fit catchment_scale (Mm³/mm) on the 2006-2024 observed level record and write
docs/cordex_config.json.

Volume is linear in catchment_scale:
    V(cs) = V_base(t) + cs * cumQ(t)
where cumQ = cumsum(runoff_mm) and V_base = V0 + cumsum(-lake_ET - outflow).
scipy.optimize.minimize_scalar finds optimal cs in <1s.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

PROJECT_ROOT    = Path(__file__).resolve().parent.parent
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
LEVEL_PATH      = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
ANCHOR_DATE     = "2006-01-01"
ANCHOR_LEVEL_M  = -211.65
S_MAX_DEFAULT   = 150.0


def calibrate_catchment_scale(
    wb_result: pd.DataFrame,
    obs_level: pd.DataFrame,
    bathy_coeffs: list,
    anchor_vol: float,
) -> dict:
    """Fit catchment_scale by minimising annual-mean-level RMSE on the overlap.

    wb_result: output of run_water_balance(...) with cs=1.0 over the calib period.
               Must have columns: date, runoff_mm, lake_ET_Mm3, dv_Mm3.
    obs_level: DataFrame with columns date (datetime64 or str), kinneret_level (float).
    bathy_coeffs: [a, b, c] for np.polyval(bathy_coeffs, volume_Mm3) -> level_m.
    anchor_vol: Mm³ at first date (V0).

    Returns and writes the full cordex_config dict.
    """
    # Use ensemble median across all model/scenario pairs
    med = (
        wb_result.groupby("date")[["runoff_mm", "lake_ET_Mm3", "dv_Mm3"]]
        .median()
        .reset_index()
        .sort_values("date")
    )

    Q_arr   = med["runoff_mm"].values           # mm/day
    et_arr  = med["lake_ET_Mm3"].values         # Mm³/day
    # outflow = Q*1.0 - et - dv  (wb was run with cs=1.0; dv = Q*1 - et - outflow)
    out_arr = Q_arr - et_arr - med["dv_Mm3"].values  # Mm³/day

    cumQ    = np.cumsum(Q_arr)                  # cumulative runoff, mm
    V_base  = anchor_vol + np.cumsum(-et_arr - out_arr)  # Mm³, cs-independent part

    # Align with observed
    obs = (
        obs_level.copy()
        .rename(columns={"kinneret_level": "obs_level"})
        .assign(date=lambda d: pd.to_datetime(d["date"]))
        .set_index("date")
    )
    med = med.set_index("date")
    overlap = med.index.intersection(obs.index)
    if len(overlap) < 30:
        raise ValueError(f"Only {len(overlap)} overlapping dates — need ≥30")

    idx = [list(med.index).index(d) for d in overlap]
    obs_vals  = obs.loc[overlap, "obs_level"].values
    V_base_ov = V_base[idx]
    cumQ_ov   = cumQ[idx]

    def rmse(cs):
        vol_pred = V_base_ov + cs * cumQ_ov
        lev_pred = np.polyval(bathy_coeffs, vol_pred)
        return float(np.sqrt(np.mean((lev_pred - obs_vals) ** 2)))

    res = minimize_scalar(rmse, bounds=(0.05, 20.0), method="bounded")
    cs_opt   = float(res.x)
    cal_rmse = float(res.fun)

    cfg = {
        "catchment_scale_Mm3_per_mm":  round(cs_opt, 6),
        "S_max_mm":                    S_MAX_DEFAULT,
        "bathy_vol2level_coeffs":      bathy_coeffs,
        "anchor_date":                 ANCHOR_DATE,
        "anchor_level_m":              ANCHOR_LEVEL_M,
        "calibration_rmse_m":          round(cal_rmse, 4),
    }
    CORDEX_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORDEX_CFG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"catchment_scale={cs_opt:.4f} Mm³/mm  calibration RMSE={cal_rmse:.3f} m")
    return cfg


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_waterbalance import run_water_balance, volume_from_level
    from longrange_cordex_ingest import load_cordex
    import json as _json

    meta = _json.loads((PROJECT_ROOT / "Models" / "model_metadata.json").read_text())
    bathy = meta["bathy_vol2level_coeffs"]

    obs_all = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    anchor_row = obs_all[obs_all["date"] == pd.Timestamp(ANCHOR_DATE)]
    if anchor_row.empty:
        raise SystemExit(f"No observed level on {ANCHOR_DATE}")
    anchor_vol = volume_from_level(float(anchor_row["kinneret_level"].iloc[0]), bathy)

    cordex = load_cordex()
    # Use only the calibration period (2006-2024)
    mask = cordex["date"] <= pd.Timestamp("2024-12-31")
    wb = run_water_balance(cordex[mask].copy(),
                           anchor_level_m=float(anchor_row["kinneret_level"].iloc[0]),
                           anchor_date=ANCHOR_DATE)
    calibrate_catchment_scale(wb, obs_all, bathy, anchor_vol)
