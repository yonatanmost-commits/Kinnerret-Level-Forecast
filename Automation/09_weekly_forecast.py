"""
09_weekly_forecast.py  -  Kinneret Two-Stage Weekly Volume Forecast

Usage
-----
    python Automation/09_weekly_forecast.py
    python Automation/09_weekly_forecast.py --forecast my_forecast.csv

The script reads a 7-row CSV containing the weekly weather forecast and
produces daily + cumulative predictions for Kinneret volume change and level.

Forecast CSV columns
--------------------
  date            YYYY-MM-DD  (7 consecutive days)
  temp_max_C      maximum daily temperature  (°C)
  temp_min_C      minimum daily temperature  (°C)
  rainfall_mm     expected daily rainfall    (mm)
  humidity_pct    mean relative humidity     (%)
  wind_speed_ms   mean wind speed            (m/s)
  radiation_MJm2  global solar radiation     (MJ/m² — optional, leave blank if unknown)

Run 08_train_forecast_model.py once to train the models before using this script.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_lib import (
    GBRegressor,
    S1_FEATURES,
    S2_DIRECT_FEATURES,
    enrich_forecast_df,
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
GOLD_FILE  = BASE_DIR / "Gold Data" / "kinneret_gold_features.csv"
MODELS_DIR = BASE_DIR / "Models"
META_FILE  = MODELS_DIR / "model_metadata.json"
TEMPLATE   = BASE_DIR / "forecast_input_template.csv"

# Days of actual history loaded to compute rainfall lags and rolling sums
HISTORY_DAYS = 21


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_recent_history(before_date=None) -> pd.DataFrame:
    """
    Return up to HISTORY_DAYS rows of the gold feature table ending on or
    before *before_date*.  When before_date is None the most recent rows are
    returned (original behaviour).
    """
    df = (
        pd.read_csv(GOLD_FILE, parse_dates=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )
    if before_date is not None:
        cutoff = pd.Timestamp(before_date)
        df = df[df["date"] <= cutoff]
    return df.tail(HISTORY_DAYS).reset_index(drop=True)


def read_forecast_csv(path: str) -> pd.DataFrame:
    """Read and validate the user's forecast CSV."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    required = ["date", "temp_max_C", "temp_min_C", "rainfall_mm",
                "humidity_pct", "wind_speed_ms"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Forecast CSV is missing required columns: {missing}")

    # Convert all numeric columns — blank cells become NaN
    for col in ["temp_max_C", "temp_min_C", "rainfall_mm",
                "humidity_pct", "wind_speed_ms", "radiation_MJm2"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    n_blank = df[required[1:]].isna().any(axis=1).sum()
    if n_blank:
        print(f"  Warning: {n_blank} forecast day(s) have missing required values "
              f"(model will impute with training medians).")
    return df


def build_feature_rows(forecast_df: pd.DataFrame,
                       history_df:  pd.DataFrame) -> pd.DataFrame:
    """
    Combine recent history + forecast into a feature DataFrame.

    Rainfall rolling sums/lags and ET0 rolling sums span BOTH history and
    forecast so that antecedent-moisture features are correctly computed for
    Day 1 of the forecast.

    Returns a DataFrame with exactly len(forecast_df) rows in forecast-date order.
    """
    # ── Rainfall rolling windows and lags ────────────────────────────────────
    rain_hist = history_df[["date", "rainfall_mm"]].copy()
    rain_fore = forecast_df[["date", "rainfall_mm"]].copy()
    rain_all  = (
        pd.concat([rain_hist, rain_fore], ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )
    rain_all["rolling7"]  = rain_all["rainfall_mm"].rolling(7,  min_periods=1).sum()
    rain_all["rolling14"] = rain_all["rainfall_mm"].rolling(14, min_periods=1).sum()
    rain_all["rolling21"] = rain_all["rainfall_mm"].rolling(21, min_periods=1).sum()
    rain_all["lag1"]      = rain_all["rainfall_mm"].shift(1)
    rain_all["lag2"]      = rain_all["rainfall_mm"].shift(2)
    rain_all["lag3"]      = rain_all["rainfall_mm"].shift(3)

    fore_mask  = rain_all["date"].isin(forecast_df["date"])
    rain_feats = rain_all[fore_mask].reset_index(drop=True)

    # ── Enrich forecast with VPD, ET0, seasonality (single-day values) ───────
    fc = enrich_forecast_df(forecast_df)

    # ── ET0 rolling windows (history + enriched forecast) ────────────────────
    et0_hist = history_df[["date"]].copy()
    et0_hist["et0_mm"] = (
        history_df["et0_mm"].values
        if "et0_mm" in history_df.columns
        else np.nan
    )
    et0_fore = fc[["date", "et0_mm"]].copy()
    et0_all  = (
        pd.concat([et0_hist, et0_fore], ignore_index=True)
        .sort_values("date")
        .reset_index(drop=True)
    )
    et0_all["et0_rolling7"]  = et0_all["et0_mm"].rolling(7,  min_periods=3).sum()
    et0_all["et0_rolling14"] = et0_all["et0_mm"].rolling(14, min_periods=5).sum()
    et0_mask  = et0_all["date"].isin(forecast_df["date"])
    et0_feats = et0_all[et0_mask].reset_index(drop=True)

    # ── Attach all rolling / lag features ────────────────────────────────────
    fc["rainfall_7d_mm"]   = rain_feats["rolling7"].values
    fc["rainfall_14d_mm"]  = rain_feats["rolling14"].values
    fc["rainfall_21d_mm"]  = rain_feats["rolling21"].values
    fc["rainfall_lag1_mm"] = rain_feats["lag1"].values
    fc["rainfall_lag2_mm"] = rain_feats["lag2"].values
    fc["rainfall_lag3_mm"] = rain_feats["lag3"].values

    fc["et0_7d_mm"]               = et0_feats["et0_rolling7"].values
    fc["moisture_balance_7d_mm"]  = fc["rainfall_7d_mm"]  - fc["et0_7d_mm"]
    fc["moisture_balance_14d_mm"] = fc["rainfall_14d_mm"] - et0_feats["et0_rolling14"].values

    return fc


def vol_to_level(volume_Mm3: float, coeffs: list) -> float:
    """Convert volume (Mm³) to level (m MSL) using the bathymetric polynomial."""
    return float(np.polyval(coeffs, volume_Mm3))


# ─────────────────────────────────────────────────────────────────────────────
# Two-stage forecast loop  (direct multi-step Stage 2)
# ─────────────────────────────────────────────────────────────────────────────

def run_forecast(forecast_df: pd.DataFrame,
                 history_df:  pd.DataFrame,
                 gb1:         GBRegressor,
                 gb2_direct:  GBRegressor,
                 meta:        dict):
    """
    Run the two-stage prediction day by day for the 7-day forecast window.

    Stage 1  (met → inflow)  uses chained inflow lags — each day's predicted
    inflow becomes the lag-1 for the following day.

    Stage 2  (met + inflow + state → volume change)  uses the DIRECT model:
    the anchor state (level and dvol at day 0, i.e. the last historical day)
    is fixed for the entire week.  The model receives horizon_h (1-7) as an
    explicit feature so it has learned how uncertainty grows with the horizon.
    This eliminates cumulative chaining errors in the lake-state features.

    current_volume and current_level are still updated each day for output
    display (cumulative sums) but are NOT fed back as model features.

    Returns (results list, start_level, start_volume, end_level, end_volume).
    """
    bathy = meta["bathy_vol2level_coeffs"]

    # ── Starting state: last row with valid level/volume data ─────────────────
    valid_state = history_df.dropna(subset=["level_m", "volume_Mm3"])
    if len(valid_state) == 0:
        full_df     = pd.read_csv(GOLD_FILE, parse_dates=["date"]).sort_values("date")
        valid_state = full_df.dropna(subset=["level_m", "volume_Mm3"])
    last           = valid_state.iloc[-1]
    current_level  = float(last["level_m"])
    current_volume = float(last["volume_Mm3"])
    start_level    = current_level
    start_volume   = current_volume
    print(f"  Starting state from {last['date'].date()}: "
          f"Level = {current_level:+.3f} m  Volume = {current_volume:,.1f} Mm³")

    # ── Initialise inflow lag state from history (Stage 1 — chained) ─────────
    hist_inflow = (history_df.dropna(subset=["inflow_obstacle_m3"])
                   if "inflow_obstacle_m3" in history_df.columns else pd.DataFrame())
    if len(hist_inflow) >= 2:
        inflow_lag1 = float(hist_inflow.iloc[-1]["inflow_obstacle_m3"])
        inflow_lag2 = float(hist_inflow.iloc[-2]["inflow_obstacle_m3"])
    elif len(hist_inflow) == 1:
        inflow_lag1 = float(hist_inflow.iloc[-1]["inflow_obstacle_m3"])
        inflow_lag2 = np.nan
    else:
        inflow_lag1 = inflow_lag2 = np.nan

    # ── Anchor state for Stage 2 direct model (fixed at day 0 — never updated) ─
    hist_dvol = (history_df.dropna(subset=["volume_change_Mm3"])
                 if "volume_change_Mm3" in history_df.columns else pd.DataFrame())
    if len(hist_dvol) >= 1:
        anchor_dvol = float(hist_dvol.iloc[-1]["volume_change_Mm3"])
    else:
        anchor_dvol = np.nan

    anchor_level = current_level   # fixed for the whole week
    print(f"  Anchor state:  level_m_anchor = {anchor_level:+.3f} m  |  "
          f"dvol_lag1_anchor = {anchor_dvol:+.4f} Mm³")

    fc      = build_feature_rows(forecast_df, history_df)
    results = []
    cum_vol = 0.0

    for i in range(len(fc)):
        row      = fc.iloc[i]
        horizon  = i + 1   # 1 … 7

        # ── Stage 1: met → inflow  (chained lags) ────────────────────────────
        s1_vals = {f: row.get(f, np.nan) for f in S1_FEATURES}
        s1_vals["inflow_lag1_m3"] = inflow_lag1
        s1_vals["inflow_lag2_m3"] = inflow_lag2
        s1_x        = np.array([[s1_vals.get(f, np.nan) for f in S1_FEATURES]], dtype=float)
        pred_inflow = float(gb1.predict(s1_x)[0])
        pred_inflow = max(0.0, pred_inflow)    # physical constraint: inflow >= 0

        # ── Stage 2 direct: anchor state + horizon → volume change ───────────
        s2_vals = {f: row.get(f, np.nan) for f in S2_DIRECT_FEATURES}
        s2_vals["predicted_inflow_m3"] = pred_inflow
        s2_vals["level_m_anchor"]      = anchor_level   # fixed (day 0)
        s2_vals["dvol_lag1_anchor"]    = anchor_dvol    # fixed (day 0)
        s2_vals["horizon_h"]           = float(horizon)
        s2_x      = np.array([[s2_vals.get(f, np.nan) for f in S2_DIRECT_FEATURES]], dtype=float)
        pred_dvol = float(gb2_direct.predict(s2_x)[0])

        # ── Update cumulative state (display only — NOT fed back to S2) ───────
        new_vol  = current_volume + pred_dvol if not np.isnan(current_volume) else np.nan
        new_lvl  = vol_to_level(new_vol, bathy) if not np.isnan(new_vol) else np.nan
        cum_vol += pred_dvol

        results.append({
            "day":             i + 1,
            "date":            row["date"].strftime("%Y-%m-%d"),
            "rain_mm":         float(row.get("rainfall_mm", np.nan)),
            "temp_mean_C":     float(row.get("temp_mean_C",  np.nan)),
            "pred_inflow_Mm3": pred_inflow / 1e6,
            "pred_dvol_Mm3":   pred_dvol,
            "cum_dvol_Mm3":    cum_vol,
            "pred_level_m":    new_lvl,
            "pred_volume_Mm3": new_vol,
        })

        # ── Advance Stage-1 inflow lags for next day ──────────────────────────
        inflow_lag2 = inflow_lag1
        inflow_lag1 = pred_inflow

        # Update display state (level/volume for output, not S2 features)
        current_level  = new_lvl
        current_volume = new_vol

    return results, start_level, start_volume, current_level, current_volume


# ─────────────────────────────────────────────────────────────────────────────
# Output formatting
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(val, fmt_str, fallback="  N/A"):
    try:
        return format(val, fmt_str) if not np.isnan(float(val)) else fallback
    except Exception:
        return fallback


def print_forecast(results, start_level, start_volume,
                   end_level, end_volume, meta):
    w = 78
    print()
    print("=" * w)
    print("  KINNERET WEEKLY FORECAST   (Gradient Boosting — direct multi-step)")
    cv_r2  = meta.get("cv_s2_mean_r2")
    cv_mae = meta.get("cv_s2_mean_mae")
    if cv_r2 is not None:
        print(f"  Model trained through {meta['trained_through']}  |  "
              f"CV R² = {cv_r2:.3f}  |  CV MAE = {cv_mae:.3f} Mm³/day")
    print("=" * w)
    print(f"  Starting state:  Level = {_fmt(start_level, '+.3f')} m MSL  |  "
          f"Volume = {_fmt(start_volume, ',.1f')} Mm³")
    print()

    # Table header
    hdr  = (f"{'Day':>3}  {'Date':<11} {'Rain':>5} {'Temp':>5} "
            f"{'Inflow':>8} {'ΔVol':>7} {'ΣΔVol':>7} {'Level':>8}  {'Volume':>8}")
    unit = (f"{'':3}  {'':11} {'mm':>5} {'°C':>5} "
            f"{'Mm³/d':>8} {'Mm³':>7} {'Mm³':>7} {'m MSL':>8}  {'Mm³':>8}")
    sep  = "-" * w
    print(hdr)
    print(unit)
    print(sep)

    for r in results:
        sgn  = "+" if r["pred_dvol_Mm3"]  >= 0 else ""
        csgn = "+" if r["cum_dvol_Mm3"]   >= 0 else ""
        lvl  = _fmt(r["pred_level_m"],   "+.3f")
        vol  = _fmt(r["pred_volume_Mm3"], ",.1f")
        print(
            f"  {r['day']:>1}  {r['date']:<11}"
            f" {_fmt(r['rain_mm'],    '5.1f')}"
            f" {_fmt(r['temp_mean_C'],'5.1f')}"
            f" {_fmt(r['pred_inflow_Mm3'], '8.3f')}"
            f" {sgn}{r['pred_dvol_Mm3']:>6.3f}"
            f" {csgn}{r['cum_dvol_Mm3']:>6.3f}"
            f" {lvl:>9}"
            f"  {vol:>8}"
        )

    print(sep)

    # Weekly summary
    total_dvol  = results[-1]["cum_dvol_Mm3"]
    delta_level = (end_level - start_level) if (
        not np.isnan(end_level) and not np.isnan(start_level)) else np.nan

    print(f"  End-of-week:     Level = {_fmt(end_level, '+.3f')} m MSL  |  "
          f"Volume = {_fmt(end_volume, ',.1f')} Mm³")
    print(f"  Weekly Δ volume: {'+' if total_dvol >= 0 else ''}{total_dvol:.3f} Mm³  |  "
          f"Level change: {_fmt(delta_level, '+.3f')} m")

    if not np.isnan(delta_level):
        if   delta_level >  0.01: trend = "▲  RISING"
        elif delta_level < -0.01: trend = "▼  FALLING"
        else:                     trend = "—  STABLE"
        print(f"  Trend: {trend}")

    print("=" * w)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Kinneret two-stage weekly volume/level forecast"
    )
    parser.add_argument(
        "--forecast", "-f",
        default=str(TEMPLATE),
        help=(f"Path to 7-day forecast CSV "
              f"(default: {TEMPLATE.name} in project root)"),
    )
    args = parser.parse_args()

    # Check models exist
    m1 = MODELS_DIR / "stage1_inflow_rf.pkl"
    m2d = MODELS_DIR / "stage2_direct_gb.pkl"
    missing_models = [str(p) for p in [m1, m2d] if not p.exists()]
    if missing_models:
        print("ERROR: Trained models not found:")
        for p in missing_models:
            print(f"  {p}")
        print("  Run:  python Automation/08_train_forecast_model.py")
        sys.exit(1)

    # Load
    print("Loading models ...")
    gb1        = GBRegressor.load(m1)
    gb2_direct = GBRegressor.load(m2d)
    with open(META_FILE, encoding="utf-8") as f:
        meta = json.load(f)

    fpath = Path(args.forecast)
    if not fpath.exists():
        print(f"ERROR: Forecast file not found: {fpath}")
        print(f"  Run 08_train_forecast_model.py to generate the template, then fill it in.")
        sys.exit(1)

    print(f"Reading forecast: {fpath.name} ...")
    forecast = read_forecast_csv(str(fpath))

    # Use history ending the day before the first forecast date so the
    # starting state is anchored to the period just before the forecast window,
    # even when gold data extends further into the future.
    first_fc_date  = forecast["date"].min()
    history_cutoff = first_fc_date - pd.Timedelta(days=1)

    print("Loading recent history ...")
    history = load_recent_history(before_date=history_cutoff)
    print(f"  History through {history['date'].max().date()}")

    print(f"  {len(forecast)} forecast days: "
          f"{forecast['date'].min().date()} → {forecast['date'].max().date()}")

    # Run two-stage prediction
    results, s_lvl, s_vol, e_lvl, e_vol = run_forecast(
        forecast, history, gb1, gb2_direct, meta
    )

    # Print results
    print_forecast(results, s_lvl, s_vol, e_lvl, e_vol, meta)


if __name__ == "__main__":
    main()
