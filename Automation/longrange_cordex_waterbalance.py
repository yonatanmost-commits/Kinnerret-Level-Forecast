# Automation/longrange_cordex_waterbalance.py
"""
Physics-based water balance over the CORDEX ensemble.

Chain per (model, scenario):
  bet-zayda tmin/tmax -> Hargreaves ET0 (catchment)
  zemah     tmin/tmax -> Hargreaves ET0 (lake surface) -> open-water evaporation
  inflow held at DOY climatology derived from gold observed data (2012-2024)
  ΔV = inflow_clim - lake_ET - outflow_clim
  V_t = V_{t-1} + ΔV_t, anchored at first observed level

Outputs cached as Gold Data/cordex_waterbalance.parquet.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CFG_PATH        = PROJECT_ROOT / "docs" / "longrange_config.json"
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
CLIM_PATH       = PROJECT_ROOT / "Gold Data" / "longrange_climatology.csv"
GOLD_PATH       = PROJECT_ROOT / "Gold Data" / "kinneret_gold_features.csv"
LEVEL_PATH      = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
CACHE_PATH      = PROJECT_ROOT / "Gold Data" / "cordex_waterbalance.parquet"
LAKE_AREA_KM2   = 166.0   # km²; 1 mm × 166 km² × 0.001 = 0.166 Mm³


def level_from_volume(volume_Mm3, bathy_coeffs):
    """np.polyval(bathy_coeffs, volume) -> level_m (below sea level, negative)."""
    return np.polyval(bathy_coeffs, np.asarray(volume_Mm3, dtype=float))


def volume_from_level(level_m, bathy_coeffs):
    """Invert level_from_volume via quadratic formula; returns scalar Mm³."""
    a, b, c = bathy_coeffs
    # a*v^2 + b*v + (c - level) = 0
    disc = b**2 - 4 * a * (c - float(level_m))
    v1 = (-b + np.sqrt(disc)) / (2 * a)
    v2 = (-b - np.sqrt(disc)) / (2 * a)
    # pick root in hydrological range 2000-6000 Mm³
    for v in (v1, v2):
        if 2000 <= v <= 6000:
            return float(v)
    raise ValueError(f"No valid volume root for level={level_m}")


def _load_configs():
    cfg = json.loads(CFG_PATH.read_text())
    slope     = cfg["hargreaves_calibration"]["slope"]
    intercept = cfg["hargreaves_calibration"]["intercept"]
    ccfg = json.loads(CORDEX_CFG_PATH.read_text()) if CORDEX_CFG_PATH.exists() else {}
    catchment_scale = ccfg.get("catchment_scale_Mm3_per_mm", 1.0)
    S_max           = ccfg.get("S_max_mm", 150.0)
    bathy_coeffs    = ccfg.get("bathy_vol2level_coeffs",
                                [-3.829620769045569e-07, 0.009169651006627259, -241.43908960277244])
    return slope, intercept, catchment_scale, S_max, bathy_coeffs


def _build_inflow_clim() -> np.ndarray:
    """DOY climatology of observed inflow (Mm³/day) from gold 2012-2024.

    inflow = ΔV + lake_ET + outflow  (water balance identity)
    Returns array indexed 0..365 (doy 1..366).
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_climatology import fit_harmonic, eval_harmonic
    gold = pd.read_csv(GOLD_PATH, parse_dates=["date"])
    gold = gold.dropna(subset=["volume_change_Mm3", "et0_mm", "outflow_baptism_m3"])
    gold["inflow_Mm3"] = (
        gold["volume_change_Mm3"]
        + gold["et0_mm"] * LAKE_AREA_KM2 * 0.001
        + gold["outflow_baptism_m3"] / 1e6
    )
    gold["doy"] = gold["date"].dt.day_of_year
    coeffs = fit_harmonic(gold["doy"].values, gold["inflow_Mm3"].values, K=3)
    doys = np.arange(1, 367)
    return eval_harmonic(doys, coeffs)  # shape (366,), index 0 = DOY 1


def run_water_balance(
    cordex_long: pd.DataFrame,
    anchor_level_m: float,
    anchor_date: str,
) -> pd.DataFrame:
    """Run physics chain for every (model, scenario) pair in cordex_long.

    cordex_long: output of load_cordex() with both sites.
    Returns DataFrame with columns:
        date, model, scenario, dv_Mm3, volume_Mm3, level_m,
        lake_ET_Mm3, inflow_clim_Mm3, et0_lake_mm, et0_catch_mm
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_meteo import hargreaves_et0

    slope, intercept, catchment_scale, S_max, bathy_coeffs = _load_configs()
    anchor_vol = volume_from_level(anchor_level_m, bathy_coeffs)

    clim = pd.read_csv(CLIM_PATH).set_index("doy")
    anchor_ts = pd.Timestamp(anchor_date)

    bz = cordex_long[cordex_long["site"] == "bet_zayda"].copy()
    zm = cordex_long[cordex_long["site"] == "zemah"].copy()

    results = []
    pairs = bz.groupby(["model", "scenario"])
    for (model, scenario), bz_grp in pairs:
        zm_grp = zm[(zm["model"] == model) & (zm["scenario"] == scenario)].copy()
        bz_grp = bz_grp.sort_values("date").reset_index(drop=True)
        zm_grp = zm_grp.sort_values("date").reset_index(drop=True)

        # Alignment guard between bz_grp and zm_grp
        if len(bz_grp) != len(zm_grp):
            raise ValueError(
                f"Site length mismatch for {model}/{scenario}: "
                f"bet_zayda={len(bz_grp)} rows, zemah={len(zm_grp)} rows"
            )
        if not (bz_grp["date"].values == zm_grp["date"].values).all():
            raise ValueError(f"Site date mismatch for {model}/{scenario}")

        doy = bz_grp["doy"].values

        # Hargreaves ET0 (calibrated): ET0_cal = slope * ET0_HS + intercept
        et0_catch = np.clip(
            slope * hargreaves_et0(bz_grp["tmax"].values, bz_grp["tmin"].values, doy) + intercept,
            0, None)
        et0_lake = np.clip(
            slope * hargreaves_et0(zm_grp["tmax"].values, zm_grp["tmin"].values, doy) + intercept,
            0, None)
        lake_ET_Mm3 = et0_lake * LAKE_AREA_KM2 * 0.001

        # Inflow held at modern-period DOY climatology derived from gold observed data (2012-2024)
        inflow_clim_arr = _build_inflow_clim()
        inflow_Mm3 = inflow_clim_arr[doy - 1]  # doy is 1-based, array is 0-indexed

        # Outflow climatology (m³ → Mm³)
        outflow_Mm3 = clim.loc[doy, "outflow_clim"].values / 1e6

        dv = inflow_Mm3 - lake_ET_Mm3 - outflow_Mm3

        # Integrate volume from anchor date.
        # vol[anchor_idx] = anchor_vol (the observed state at the anchor date).
        # For subsequent days: vol[i] = vol[i-1] + dv[i].
        n = len(bz_grp)
        vol = np.empty(n)
        vol[:] = np.nan
        anchor_mask = bz_grp["date"] >= anchor_ts
        if anchor_mask.any():
            anchor_idx = int(anchor_mask.idxmax())
            vol[anchor_idx] = anchor_vol
            v = anchor_vol
            for i in range(anchor_idx + 1, n):
                v += dv[i]
                v = float(np.clip(v, 0, None))
                vol[i] = v

        level_arr = np.where(np.isnan(vol), np.nan, level_from_volume(vol, bathy_coeffs))

        results.append(pd.DataFrame({
            "date":             bz_grp["date"].values,
            "model":            model,
            "scenario":         scenario,
            "dv_Mm3":           dv,
            "volume_Mm3":       vol,
            "level_m":          level_arr,
            "lake_ET_Mm3":      lake_ET_Mm3,
            "inflow_clim_Mm3":  inflow_Mm3,
            "et0_lake_mm":      et0_lake,
            "et0_catch_mm":     et0_catch,
        }))

    return pd.concat(results, ignore_index=True)


def cache_water_balance(force: bool = False) -> pd.DataFrame:
    """Run water balance for the full CORDEX ensemble and cache as parquet.

    Reads anchor level from the observed level file (2006-01-01).
    """
    if not force and CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_ingest import load_cordex
    cordex = load_cordex()

    # Anchor: observed level on 2006-01-01 (start of CORDEX period)
    level_obs = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    anchor_row = level_obs[level_obs["date"] == pd.Timestamp("2006-01-01")]
    if anchor_row.empty:
        raise ValueError("Observed level for 2006-01-01 not found in kinneret_level.csv")
    anchor_level_m = float(anchor_row["kinneret_level"].iloc[0])

    result = run_water_balance(cordex, anchor_level_m=anchor_level_m, anchor_date="2006-01-01")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(CACHE_PATH, index=False)
    print(f"Cached {len(result):,} rows to {CACHE_PATH}")
    return result


if __name__ == "__main__":
    df = cache_water_balance(force=True)
    print(df.groupby(["model", "scenario"])["level_m"].agg(["min", "max", "mean"]).round(2))
