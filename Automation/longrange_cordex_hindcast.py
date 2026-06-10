# Automation/longrange_cordex_hindcast.py
"""
Run the calibrated water balance over 2006-2024 and record RMSE / correlation
vs observed Kinneret level. Results are appended to docs/cordex_config.json
and used by the dashboard hindcast tab.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT    = Path(__file__).resolve().parent.parent
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
LEVEL_PATH      = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
HINDCAST_CACHE  = PROJECT_ROOT / "Gold Data" / "cordex_hindcast.parquet"


def run_hindcast() -> dict:
    """Run calibrated water balance on 2006-2024, compare to observed.

    Writes hindcast_rmse_m and hindcast_corr back to docs/cordex_config.json.
    Caches the full hindcast DataFrame as Gold Data/cordex_hindcast.parquet.
    Returns the updated config dict.
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_ingest import load_cordex
    from longrange_cordex_waterbalance import run_water_balance

    # Load cordex_config.json for anchor info
    if not CORDEX_CFG_PATH.exists():
        raise FileNotFoundError(
            f"docs/cordex_config.json not found — run longrange_cordex_calibrate.py first"
        )
    cfg = json.loads(CORDEX_CFG_PATH.read_text())
    anchor_level_m = cfg["anchor_level_m"]
    anchor_date    = cfg["anchor_date"]

    # Run water balance over full CORDEX period (2006-2100)
    # but only evaluate hindcast on the observed overlap (2006-2024)
    cordex = load_cordex()
    wb = run_water_balance(
        cordex, anchor_level_m=anchor_level_m, anchor_date=anchor_date
    )

    hindcast = wb[wb["date"].dt.year <= 2024].copy()

    # Ensemble median level per date
    med = (
        hindcast.groupby("date")["level_m"]
        .median()
        .reset_index()
        .rename(columns={"level_m": "level_pred"})
    )

    obs = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    merged = med.merge(
        obs.rename(columns={"kinneret_level": "level_obs"}),
        on="date", how="inner"
    ).dropna()

    if merged.empty:
        raise ValueError("No overlap between hindcast dates and observed level")

    rmse = float(np.sqrt(np.mean((merged["level_pred"] - merged["level_obs"]) ** 2)))
    corr = float(merged["level_pred"].corr(merged["level_obs"]))

    # Append to cordex_config.json
    cfg["hindcast_rmse_m"]  = round(rmse, 4)
    cfg["hindcast_corr"]    = round(corr, 4)
    cfg["hindcast_n_days"]  = int(len(merged))
    CORDEX_CFG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"Hindcast 2006-2024: RMSE={rmse:.3f} m  corr={corr:.3f}  n={len(merged)}")

    hindcast.to_parquet(HINDCAST_CACHE, index=False)
    return cfg


if __name__ == "__main__":
    run_hindcast()
