"""
08_train_forecast_model.py  -  Train the Kinneret two-stage weekly forecast model.

Stage 1 : met features → Jordan River daily inflow  (m³/day)
Stage 2 : Stage-1 inflow + met features → Kinneret daily volume change (Mm³/day)

Walk-forward cross-validation uses four held-out years (2021-2024) so all
reported metrics are honest out-of-sample estimates.

Stage 2 is trained using out-of-fold Stage-1 predictions (stacking), so the
training distribution matches what Stage 2 sees at inference time.

Outputs
-------
  Models/stage1_inflow_rf.pkl       pickled RFRegressor
  Models/stage2_volume_rf.pkl       pickled RFRegressor
  Models/model_metadata.json        feature lists, CV scores, bathy polynomial
  forecast_input_template.csv       fill this in and pass to 09_weekly_forecast.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_lib import (
    GBRegressor,
    S1_FEATURES, S1_TARGET,
    S2_FEATURES, S2_TARGET,
    S2_MET_FEATURES, S2_DIRECT_FEATURES, S2_DIRECT_TARGET,
    S1_DIRECT_FEATURES,
    log_transform, inv_log_transform,
    signed_log1p_transform, inv_signed_log1p_transform,
)
import xgboost as xgb
import lightgbm as lgb
from gru_model import GRUTrainer

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
GOLD_FILE  = BASE_DIR / "Gold Data"  / "kinneret_gold_features.csv"
BATHY_FILE = BASE_DIR / "Raw Data"   / "Kinneret_Level" / \
             "Lake Kinneret Bathymetric and Hypsometric Curve.csv"
MODELS_DIR = BASE_DIR / "Models"


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def r2(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    ss_res  = np.sum((y - yhat) ** 2)
    ss_tot  = np.sum((y - y.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(yhat))))


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Direct multi-step training data builder
# ─────────────────────────────────────────────────────────────────────────────

def build_direct_s2_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build horizon-aware Stage-2 training data (7x rows).

    For each anchor row t and horizon h in 1..7:
      - S2_MET_FEATURES come from t+h (df shifted by -h)
      - predicted_inflow_m3 uses actual inflow at t+h as a training proxy
      - level_m_anchor, dvol_lag1_anchor stay fixed at t
      - horizon_h = h (tells the model how far ahead it predicts)
      - target = volume_change at t+h
    """
    pieces = []
    for h in range(1, 8):
        p = pd.DataFrame()
        p["date"] = df["date"]

        # Actual inflow at t+h as proxy for predicted_inflow
        p["predicted_inflow_m3"] = df["inflow_obstacle_m3"].shift(-h)

        # Remaining met features from t+h
        for col in [c for c in S2_MET_FEATURES if c != "predicted_inflow_m3"]:
            p[col] = df[col].shift(-h) if col in df.columns else np.nan

        # Target from t+h
        p[S2_DIRECT_TARGET] = df[S2_DIRECT_TARGET].shift(-h)

        # Anchor state from t  (never updated — this is what eliminates chaining error)
        p["level_m_anchor"]   = df["level_m"]
        p["dvol_lag1_anchor"] = df["volume_change_Mm3"]   # dvol at anchor = lag1 for h=1
        p["horizon_h"]        = float(h)
        pieces.append(p)

    return pd.concat(pieces, ignore_index=True)


def build_direct_s1_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build horizon-aware Stage-1 training data (7x rows).

    For each anchor row t and horizon h in 1..7:
      - Met/rain/seasonality features come from t+h (df shifted by -h)
      - inflow_anchor_m3 = actual inflow at t  (never updated — no chaining)
      - horizon_h = h
      - target (S1_TARGET) = inflow_obstacle_m3 at t+h
    """
    anchor_features = {"inflow_anchor_m3", "horizon_h"}
    met_cols = [c for c in S1_DIRECT_FEATURES if c not in anchor_features]

    pieces = []
    for h in range(1, 8):
        p = pd.DataFrame()
        p["date"] = df["date"]
        for col in met_cols:
            p[col] = df[col].shift(-h) if col in df.columns else np.nan
        p["inflow_anchor_m3"] = df["inflow_obstacle_m3"].values
        p["horizon_h"]        = float(h)
        p[S1_TARGET]          = df[S1_TARGET].shift(-h)
        pieces.append(p)

    return pd.concat(pieces, ignore_index=True)


def _mean_7d_drift(full_df: pd.DataFrame,
                   preds_df: pd.DataFrame,
                   bathy_coeffs: list) -> float:
    """
    Mean absolute lake-level error at the end of every 7-day forecast window.

    full_df   : complete gold DataFrame (needs 'date', 'volume_Mm3', 'level_m')
    preds_df  : DataFrame with columns:
                  'date'      — anchor date (pd.Timestamp)
                  'horizon_h' — 1..7 (float)
                  'pred_dvol' — predicted volume_change_Mm3
    bathy_coeffs : vol→level polynomial (from meta["bathy_vol2level_coeffs"])

    Returns mean drift in metres, or NaN if no complete 7-day windows found.
    """
    vol_map = full_df.set_index("date")["volume_Mm3"]
    lvl_map = full_df.set_index("date")["level_m"]

    drifts = []
    for anchor_date, grp in preds_df.groupby("date"):
        grp = grp.sort_values("horizon_h")
        if len(grp) < 7:
            continue
        anchor_ts  = pd.Timestamp(anchor_date)
        anchor_vol = vol_map.get(anchor_ts)
        if anchor_vol is None or np.isnan(float(anchor_vol)):
            continue
        pred_cum_dvol = float(grp["pred_dvol"].sum())
        pred_vol_7    = float(anchor_vol) + pred_cum_dvol
        pred_lvl_7    = float(np.polyval(bathy_coeffs, pred_vol_7))

        target_ts    = anchor_ts + pd.Timedelta(days=7)
        actual_lvl_7 = lvl_map.get(target_ts)
        if actual_lvl_7 is None or np.isnan(float(actual_lvl_7)):
            continue
        drifts.append(abs(pred_lvl_7 - float(actual_lvl_7)))

    return float(np.mean(drifts)) if drifts else float("nan")


def load_data() -> pd.DataFrame:
    """Load gold features and add rainfall lag columns required by Stage 1."""
    df = (
        pd.read_csv(GOLD_FILE, parse_dates=["date"])
        .sort_values("date")
        .reset_index(drop=True)
    )
    # Rainfall lags (Stage-1 feature: yesterday's and day-before-yesterday's rain)
    df["rainfall_lag1_mm"] = df["rainfall_mm"].shift(1)
    df["rainfall_lag2_mm"] = df["rainfall_mm"].shift(2)
    df["rainfall_lag3_mm"] = df["rainfall_mm"].shift(3)

    # Placeholder filled during CV / final training
    df["predicted_inflow_m3"] = np.nan
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Bathymetric polynomial:  volume (Mm³)  →  level (m MSL)
# Needed by the inference script to convert predicted volume back to level.
# ─────────────────────────────────────────────────────────────────────────────

def fit_vol2level_poly() -> list:
    """
    Fit degree-2 polynomial:  level_m = p(volume_Mm3).
    Returns coefficients as a plain list for JSON serialisation.
    """
    raw = pd.read_csv(BATHY_FILE, encoding="utf-8-sig")

    def _to_num(s):
        return pd.to_numeric(
            s.astype(str).str.replace("%", "").str.replace(",", "").str.strip(),
            errors="coerce",
        )

    v_mm3 = _to_num(raw["Volume (Mm3)"])
    v_pct = _to_num(raw["Volume (%)"])
    vol   = v_mm3 if v_mm3.max() > v_pct.max() else v_pct   # pick the Mm3 column
    lvl   = pd.to_numeric(raw["Water Level (m MSL)"], errors="coerce")

    mask   = vol.notna() & lvl.notna()
    coeffs = np.polyfit(vol[mask].values, lvl[mask].values, 2)   # volume → level
    fitted = np.polyval(coeffs, vol[mask].values)
    r2_val = 1 - np.sum((lvl[mask].values - fitted) ** 2) / \
                 np.sum((lvl[mask].values - lvl[mask].mean()) ** 2)
    print(f"  Bathy poly (vol->level) deg-2  R2={r2_val:.5f}")
    return coeffs.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Walk-forward cross-validation
# ─────────────────────────────────────────────────────────────────────────────

# Each fold: (label, years used for training, held-out test year)
CV_FOLDS = [
    ("2021", list(range(2012, 2021)), 2021),
    ("2022", list(range(2012, 2022)), 2022),
    ("2023", list(range(2012, 2023)), 2023),
    ("2024", list(range(2012, 2024)), 2024),
]


def run_cv(df: pd.DataFrame):
    """
    Walk-forward CV.

    For each fold:
      1. Fit Stage-1 on train → predict test inflow (OOF predictions).
      2. Fit Stage-2 on train (using actual inflow as proxy) →
         evaluate on test with Stage-1 predictions as input.

    Returns
    -------
    cv_results : list of dicts
    oof_s1     : Series of out-of-fold Stage-1 predictions (index = df.index)
    """
    print("\n=== Walk-forward cross-validation ===")
    oof_s1   = pd.Series(np.nan, index=df.index, dtype=float)
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # ── Stage 1 ──────────────────────────────────────────────────────────
        s1_tr = tr.dropna(subset=S1_FEATURES + [S1_TARGET])
        s1_te = te.dropna(subset=S1_FEATURES + [S1_TARGET])
        if len(s1_te) == 0:
            print(f"  Fold {fold_name}: no Stage-1 test rows — skipping")
            continue

        rf1 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
        rf1.fit(s1_tr[S1_FEATURES].values, s1_tr[S1_TARGET].values)
        p1 = rf1.predict(s1_te[S1_FEATURES].values)
        p1 = np.clip(p1, 0, None)
        oof_s1.loc[s1_te.index] = p1

        s1_r2_val  = r2(s1_te[S1_TARGET].values, p1)
        s1_mae_val = mae(s1_te[S1_TARGET].values, p1) / 1e6   # convert to Mm³/day

        # ── Stage 2 ──────────────────────────────────────────────────────────
        # Train with actual inflow (best proxy available in training set).
        # Evaluate with Stage-1 predicted inflow → honest end-to-end metric.
        tr_s2 = tr.copy()
        tr_s2["predicted_inflow_m3"] = tr_s2[S1_TARGET]    # actual as training proxy

        te_s2 = te.copy()
        te_s2["predicted_inflow_m3"] = np.nan
        te_s2.loc[s1_te.index, "predicted_inflow_m3"] = p1  # OOF from Stage-1

        s2_tr = tr_s2.dropna(subset=S2_FEATURES + [S2_TARGET])
        s2_te = te_s2.dropna(subset=S2_FEATURES + [S2_TARGET])
        if len(s2_te) == 0:
            print(f"  Fold {fold_name}: no Stage-2 test rows")
            continue

        rf2 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
        rf2.fit(s2_tr[S2_FEATURES].values, s2_tr[S2_TARGET].values)
        p2 = rf2.predict(s2_te[S2_FEATURES].values)

        s2_r2_val  = r2(s2_te[S2_TARGET].values, p2)
        s2_mae_val = mae(s2_te[S2_TARGET].values, p2)

        cv_results.append({
            "fold":        fold_name,
            "n_test":      int(len(s2_te)),
            "s1_r2":       round(s1_r2_val,  3),
            "s1_mae_Mm3":  round(s1_mae_val, 3),
            "s2_r2":       round(s2_r2_val,  3),
            "s2_mae_Mm3":  round(s2_mae_val, 3),
        })
        print(
            f"  {fold_name}:  "
            f"S1 R²={s1_r2_val:.3f}  MAE={s1_mae_val:.3f} Mm³/d  |  "
            f"S2 R²={s2_r2_val:.3f}  MAE={s2_mae_val:.3f} Mm³/d  "
            f"(n={len(s2_te)})"
        )

    return cv_results, oof_s1


def run_cv_xgb(df: pd.DataFrame, bathy_coeffs: list):
    """Walk-forward CV for the XGBoost direct multi-step challenger."""
    print("\n=== XGBoost CV ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # ── Stage 1 direct ───────────────────────────────────────────────
        tr_s1 = build_direct_s1_data(tr).dropna(
            subset=S1_DIRECT_FEATURES + [S1_TARGET])
        te_s1_all = build_direct_s1_data(te)   # keep all rows for alignment

        xgb_s1 = xgb.XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, verbosity=0,
            random_state=42)
        xgb_s1.fit(tr_s1[S1_DIRECT_FEATURES], tr_s1[S1_TARGET])

        # Predict on all te_s1 rows (XGBoost handles NaN natively)
        te_inflow_pred = np.clip(
            xgb_s1.predict(te_s1_all[S1_DIRECT_FEATURES].values), 0, None)

        te_s1_clean = te_s1_all.dropna(subset=S1_DIRECT_FEATURES + [S1_TARGET])
        s1_r2_val = r2(
            te_s1_clean[S1_TARGET].values,
            np.clip(xgb_s1.predict(te_s1_clean[S1_DIRECT_FEATURES].values), 0, None))

        # ── Stage 2 direct ───────────────────────────────────────────────
        tr_s2 = build_direct_s2_data(tr).dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        te_s2_all = build_direct_s2_data(te)

        # Inject XGB S1 predictions as predicted_inflow (1:1 row alignment)
        te_s2_all = te_s2_all.copy()
        te_s2_all["predicted_inflow_m3"] = te_inflow_pred

        xgb_s2 = xgb.XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, verbosity=0,
            random_state=42)
        xgb_s2.fit(tr_s2[S2_DIRECT_FEATURES], tr_s2[S2_DIRECT_TARGET])

        te_s2_clean = te_s2_all.dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        p2 = xgb_s2.predict(te_s2_clean[S2_DIRECT_FEATURES].values)

        s2_r2_val  = r2( te_s2_clean[S2_DIRECT_TARGET].values, p2)
        s2_mae_val = mae(te_s2_clean[S2_DIRECT_TARGET].values, p2)

        # ── 7-day drift ──────────────────────────────────────────────────
        preds_df = te_s2_all.copy()
        preds_df["pred_dvol"] = xgb_s2.predict(
            te_s2_all[S2_DIRECT_FEATURES].values)
        drift = _mean_7d_drift(df, preds_df[["date", "horizon_h", "pred_dvol"]],
                               bathy_coeffs)

        cv_results.append({
            "fold":        fold_name,
            "n_test":      int(len(te_s2_clean)),
            "s1_r2":       round(s1_r2_val, 3),
            "s2_r2":       round(s2_r2_val, 3),
            "s2_mae":      round(s2_mae_val, 3),
            "drift_m":     round(drift, 4),
        })
        print(f"  {fold_name}:  S1 R²={s1_r2_val:.3f}  |  "
              f"S2 R²={s2_r2_val:.3f}  MAE={s2_mae_val:.3f}  "
              f"drift={drift:.4f} m")

    return cv_results


def train_final_xgb(df: pd.DataFrame, oof_s1: pd.Series):
    """Train final XGBoost models on all available data."""
    print("\n  XGBoost final training ...")
    df2 = df.copy()
    df2["predicted_inflow_m3"] = oof_s1.combine_first(df[S1_TARGET])

    s1_data = build_direct_s1_data(df).dropna(
        subset=S1_DIRECT_FEATURES + [S1_TARGET])
    xgb_s1 = xgb.XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, verbosity=0, random_state=42)
    xgb_s1.fit(s1_data[S1_DIRECT_FEATURES], s1_data[S1_TARGET])

    s2_data = build_direct_s2_data(df2).dropna(
        subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
    xgb_s2 = xgb.XGBRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, verbosity=0, random_state=42)
    xgb_s2.fit(s2_data[S2_DIRECT_FEATURES], s2_data[S2_DIRECT_TARGET])

    import pickle
    MODELS_DIR.mkdir(exist_ok=True)
    with open(MODELS_DIR / "xgb_s1_direct.pkl", "wb") as f:
        pickle.dump(xgb_s1, f)
    with open(MODELS_DIR / "xgb_s2_direct.pkl", "wb") as f:
        pickle.dump(xgb_s2, f)
    print(f"  Saved xgb_s1_direct.pkl  xgb_s2_direct.pkl")
    return xgb_s1, xgb_s2


def run_cv_lgb(df: pd.DataFrame, bathy_coeffs: list):
    """Walk-forward CV for the LightGBM direct multi-step challenger."""
    print("\n=== LightGBM CV ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        tr_s1      = build_direct_s1_data(tr).dropna(
            subset=S1_DIRECT_FEATURES + [S1_TARGET])
        te_s1_all  = build_direct_s1_data(te)

        lgb_s1 = lgb.LGBMRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            verbosity=-1, random_state=42)
        lgb_s1.fit(tr_s1[S1_DIRECT_FEATURES], tr_s1[S1_TARGET])

        te_inflow_pred = np.clip(
            lgb_s1.predict(te_s1_all[S1_DIRECT_FEATURES].values), 0, None)

        te_s1_clean = te_s1_all.dropna(subset=S1_DIRECT_FEATURES + [S1_TARGET])
        s1_r2_val = r2(
            te_s1_clean[S1_TARGET].values,
            np.clip(lgb_s1.predict(te_s1_clean[S1_DIRECT_FEATURES].values), 0, None))

        tr_s2     = build_direct_s2_data(tr).dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        te_s2_all = build_direct_s2_data(te).copy()
        te_s2_all["predicted_inflow_m3"] = te_inflow_pred

        lgb_s2 = lgb.LGBMRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            verbosity=-1, random_state=42)
        lgb_s2.fit(tr_s2[S2_DIRECT_FEATURES], tr_s2[S2_DIRECT_TARGET])

        te_s2_clean = te_s2_all.dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        p2 = lgb_s2.predict(te_s2_clean[S2_DIRECT_FEATURES].values)

        s2_r2_val  = r2( te_s2_clean[S2_DIRECT_TARGET].values, p2)
        s2_mae_val = mae(te_s2_clean[S2_DIRECT_TARGET].values, p2)

        preds_df = te_s2_all.copy()
        preds_df["pred_dvol"] = lgb_s2.predict(
            te_s2_all[S2_DIRECT_FEATURES].values)
        drift = _mean_7d_drift(df, preds_df[["date", "horizon_h", "pred_dvol"]],
                               bathy_coeffs)

        cv_results.append({
            "fold": fold_name, "n_test": int(len(te_s2_clean)),
            "s1_r2": round(s1_r2_val, 3),
            "s2_r2": round(s2_r2_val, 3),
            "s2_mae": round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S1 R²={s1_r2_val:.3f}  |  "
              f"S2 R²={s2_r2_val:.3f}  MAE={s2_mae_val:.3f}  "
              f"drift={drift:.4f} m")

    return cv_results


def train_final_lgb(df: pd.DataFrame, oof_s1: pd.Series):
    """Train final LightGBM models on all available data."""
    print("\n  LightGBM final training ...")
    df2 = df.copy()
    df2["predicted_inflow_m3"] = oof_s1.combine_first(df[S1_TARGET])

    s1_data = build_direct_s1_data(df).dropna(
        subset=S1_DIRECT_FEATURES + [S1_TARGET])
    lgb_s1 = lgb.LGBMRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, verbosity=-1, random_state=42)
    lgb_s1.fit(s1_data[S1_DIRECT_FEATURES], s1_data[S1_TARGET])

    s2_data = build_direct_s2_data(df2).dropna(
        subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
    lgb_s2 = lgb.LGBMRegressor(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, verbosity=-1, random_state=42)
    lgb_s2.fit(s2_data[S2_DIRECT_FEATURES], s2_data[S2_DIRECT_TARGET])

    import pickle
    MODELS_DIR.mkdir(exist_ok=True)
    with open(MODELS_DIR / "lgb_s1_direct.pkl", "wb") as f:
        pickle.dump(lgb_s1, f)
    with open(MODELS_DIR / "lgb_s2_direct.pkl", "wb") as f:
        pickle.dump(lgb_s2, f)
    print(f"  Saved lgb_s1_direct.pkl  lgb_s2_direct.pkl")
    return lgb_s1, lgb_s2


def run_cv_gru(df: pd.DataFrame, bathy_coeffs: list):
    """
    Walk-forward CV for the GRU multi-task challenger.

    A new GRU is trained from scratch for each fold (~150 epochs × 4 folds).
    Sequences for test prediction are built from the FULL df so the 21-day
    history window can naturally span the train-test boundary.
    """
    print("\n=== GRU CV (4 folds × 150 epochs — expect ~15 min on CPU) ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()

        trainer = GRUTrainer(epochs=150, lr=1e-3, batch_size=64)
        trainer.fit(tr)

        # Collect predictions for all horizons in test year
        all_dvol_pred, all_dvol_true = [], []
        preds_rows = []

        for h in range(1, 8):
            p_inf, p_dv, anc_dates, dv_true = trainer.predict_horizon(
                df, horizon=h, test_year=test_yr)
            if len(p_dv) == 0:
                continue

            all_dvol_pred.extend(p_dv.tolist())
            all_dvol_true.extend(dv_true.tolist())

            for i, ad in enumerate(anc_dates):
                preds_rows.append({
                    "date":      pd.Timestamp(ad),
                    "horizon_h": float(h),
                    "pred_dvol": float(p_dv[i]),
                })

        s2_r2_val  = r2( np.array(all_dvol_true), np.array(all_dvol_pred))
        s2_mae_val = mae(np.array(all_dvol_true), np.array(all_dvol_pred))

        preds_df = pd.DataFrame(preds_rows)
        drift = _mean_7d_drift(df, preds_df, bathy_coeffs)

        cv_results.append({
            "fold": fold_name, "n_test": int(len(all_dvol_true)),
            "s1_r2": None,
            "s2_r2": round(s2_r2_val, 3),
            "s2_mae": round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results


def train_final_gru(df: pd.DataFrame):
    """Train final GRU on all available data and save."""
    print("\n  GRU final training (150 epochs on full dataset) ...")
    trainer = GRUTrainer(epochs=150, lr=1e-3, batch_size=64)
    trainer.fit(df)
    MODELS_DIR.mkdir(exist_ok=True)
    trainer.save(MODELS_DIR / "gru_multitask.pt")
    print(f"  Saved gru_multitask.pt")
    return trainer


# ─────────────────────────────────────────────────────────────────────────────
# Final model training
# ─────────────────────────────────────────────────────────────────────────────

def train_final(df: pd.DataFrame, oof_s1: pd.Series):
    """
    Train final Stage-1 and Stage-2 models on all available data.

    Stage-2 uses OOF Stage-1 predictions where available (from CV), falling
    back to actual inflow for rows outside all CV test windows.  This keeps
    the training distribution aligned with inference.
    """
    print("\n=== Training final models on all data ===")

    # Stage 1
    s1_data = df.dropna(subset=S1_FEATURES + [S1_TARGET])
    print(f"  Stage 1: {len(s1_data):,} training rows")
    gb1 = GBRegressor(n_estimators=250, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
    gb1.fit(s1_data[S1_FEATURES].values, s1_data[S1_TARGET].values,
            feature_names=S1_FEATURES)

    # Stage 2: prefer OOF predictions; fall back to actual inflow for
    # rows not covered by any CV test window (earliest historical years).
    df2 = df.copy()
    df2["predicted_inflow_m3"] = oof_s1.combine_first(df[S1_TARGET])
    s2_data = df2.dropna(subset=S2_FEATURES + [S2_TARGET])
    print(f"  Stage 2: {len(s2_data):,} training rows")
    gb2 = GBRegressor(n_estimators=250, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
    gb2.fit(s2_data[S2_FEATURES].values, s2_data[S2_TARGET].values,
            feature_names=S2_FEATURES)

    # Stage 2 direct (horizon-aware, anchor state)
    print("  Stage 2 direct: building 7x horizon data ...")
    direct_data = build_direct_s2_data(df2)
    direct_data = direct_data.dropna(subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
    print(f"  Stage 2 direct: {len(direct_data):,} training rows ({len(direct_data)//7:,} anchors x 7 horizons)")
    gb2d = GBRegressor(n_estimators=250, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
    gb2d.fit(direct_data[S2_DIRECT_FEATURES].values, direct_data[S2_DIRECT_TARGET].values,
             feature_names=S2_DIRECT_FEATURES)

    return gb1, gb2, gb2d


def _read_baseline_from_meta() -> dict:
    """
    Read baseline CV metrics from the existing model_metadata.json.
    Returns a dict in the same shape used for challenger entries.
    """
    meta_path = MODELS_DIR / "model_metadata.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    folds = {r["fold"]: r["s2_r2"] for r in meta.get("cv_results", [])}
    maes  = [r["s2_mae_Mm3"] for r in meta.get("cv_results", [])]
    return {
        "cv_vol_r2_mean":    round(float(meta.get("cv_s2_mean_r2", 0.0)), 3),
        "cv_vol_r2_by_fold": folds,
        "cv_vol_mae_mean":   round(float(np.mean(maes)) if maes else 0.0, 3),
        "cv_7d_drift_mean_m": None,
        "cv_inflow_r2_mean": None,
    }


def save_olympics_results(baseline: dict,
                          xgb_cv: list, lgb_cv: list, gru_cv: list,
                          df: pd.DataFrame) -> None:
    """Collate CV results from all models and write olympics_results.json."""

    def _summarise(cv_list: list) -> dict:
        r2s   = [r["s2_r2"]   for r in cv_list]
        maes  = [r["s2_mae"]  for r in cv_list]
        drift = [r["drift_m"] for r in cv_list if r.get("drift_m") is not None]
        s1r2s = [r["s1_r2"]   for r in cv_list if r.get("s1_r2") is not None]
        return {
            "cv_vol_r2_mean":    round(float(np.mean(r2s)),  3) if r2s  else None,
            "cv_vol_r2_by_fold": {r["fold"]: r["s2_r2"] for r in cv_list},
            "cv_vol_mae_mean":   round(float(np.mean(maes)), 3) if maes else None,
            "cv_7d_drift_mean_m": round(float(np.mean(drift)), 4) if drift else None,
            "cv_inflow_r2_mean": round(float(np.mean(s1r2s)), 3) if s1r2s else None,
        }

    models = {
        "baseline_gbr": baseline,
        "xgboost":      _summarise(xgb_cv),
        "lgbm":         _summarise(lgb_cv),
        "gru":          _summarise(gru_cv),
    }

    # Declare winner by highest mean CV R² on volume change
    winner = max(models, key=lambda k: models[k].get("cv_vol_r2_mean", -1))

    results = {
        "generated_at": str(df["date"].max().date()),
        "winner":       winner,
        "models":       models,
    }

    out = MODELS_DIR / "olympics_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved: {out}")
    print(f"  WINNER: {winner}  "
          f"(R²={models[winner]['cv_vol_r2_mean']:.3f}  "
          f"MAE={models[winner]['cv_vol_mae_mean']:.3f})")


# ─────────────────────────────────────────────────────────────────────────────
# Forecast template
# ─────────────────────────────────────────────────────────────────────────────

def create_forecast_template(df: pd.DataFrame) -> Path:
    """Write a blank 7-day forecast CSV starting the day after the last data row."""
    last_date = df["date"].max()
    dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=7)
    template = pd.DataFrame({
        "date":           dates.strftime("%Y-%m-%d"),
        "temp_max_C":     "",
        "temp_min_C":     "",
        "rainfall_mm":    "",
        "humidity_pct":   "",
        "wind_speed_ms":  "",
        "radiation_MJm2": "",    # optional — leave blank if unavailable
    })
    out = BASE_DIR / "forecast_input_template.csv"
    template.to_csv(out, index=False)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Kinneret forecast model — training pipeline")
    print("=" * 60)

    # 1. Load data
    print("\nLoading gold features ...")
    df = load_data()
    print(f"  {len(df):,} rows  ({df['date'].min().date()} to {df['date'].max().date()})")

    # 2. Bathymetric polynomial
    print("\nFitting bathymetric polynomial (volume -> level) ...")
    bathy_coeffs = fit_vol2level_poly()

    # 3. Walk-forward CV
    cv_results, oof_s1 = run_cv(df)

    # 4. CV summary
    if cv_results:
        print("\n=== CV Summary ===")
        s1_r2s  = [r["s1_r2"]     for r in cv_results]
        s1_maes = [r["s1_mae_Mm3"] for r in cv_results]
        s2_r2s  = [r["s2_r2"]     for r in cv_results]
        s2_maes = [r["s2_mae_Mm3"] for r in cv_results]
        print(f"  Stage 1 (inflow)   R² = {np.mean(s1_r2s):.3f} ± {np.std(s1_r2s):.3f}  |  "
              f"MAE = {np.mean(s1_maes):.3f} Mm³/day")
        print(f"  Stage 2 (volume Δ) R² = {np.mean(s2_r2s):.3f} ± {np.std(s2_r2s):.3f}  |  "
              f"MAE = {np.mean(s2_maes):.3f} Mm³/day")

    # 5. Train final models
    gb1, gb2, gb2d = train_final(df, oof_s1)

    # 6. Save models
    MODELS_DIR.mkdir(exist_ok=True)
    gb1.save(MODELS_DIR / "stage1_inflow_rf.pkl")
    gb2.save(MODELS_DIR / "stage2_volume_rf.pkl")
    gb2d.save(MODELS_DIR / "stage2_direct_gb.pkl")
    print(f"\n  Saved: {MODELS_DIR / 'stage1_inflow_rf.pkl'}")
    print(f"  Saved: {MODELS_DIR / 'stage2_volume_rf.pkl'}")
    print(f"  Saved: {MODELS_DIR / 'stage2_direct_gb.pkl'}")

    # 7. Save metadata
    metadata = {
        "trained_through":       str(df["date"].max().date()),
        "n_rows_total":          int(len(df)),
        "s1_features":           S1_FEATURES,
        "s1_target":             S1_TARGET,
        "s2_features":           S2_FEATURES,
        "s2_target":             S2_TARGET,
        "bathy_vol2level_coeffs": bathy_coeffs,    # level = poly2(volume)
        "cv_results":            cv_results,
        "cv_s2_mean_r2":  round(float(np.mean(s2_r2s)),  3) if cv_results else None,
        "cv_s2_mean_mae": round(float(np.mean(s2_maes)), 3) if cv_results else None,
        "cv_s1_mean_r2":  round(float(np.mean(s1_r2s)),  3) if cv_results else None,
        "target_transforms": {"s1": "none", "s2": "none"},
        "s2_direct": True,
    }
    meta_path = MODELS_DIR / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved: {meta_path}")

    # 8. Forecast template
    tmpl = create_forecast_template(df)
    print(f"\nForecast template: {tmpl}")
    print("  Fill in the weather forecast values and run:")
    print("  python Automation/09_weekly_forecast.py --forecast forecast_input_template.csv")

    # ── Challenger models ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Model Olympics — training challengers")
    print("=" * 60)

    # 6. Read baseline metrics
    baseline_entry = _read_baseline_from_meta()

    # 7. XGBoost
    xgb_cv_results = run_cv_xgb(df, bathy_coeffs)
    train_final_xgb(df, oof_s1)

    # 8. LightGBM
    lgb_cv_results = run_cv_lgb(df, bathy_coeffs)
    train_final_lgb(df, oof_s1)

    # 9. GRU
    gru_cv_results = run_cv_gru(df, bathy_coeffs)
    train_final_gru(df)

    # 10. Save combined results
    save_olympics_results(baseline_entry, xgb_cv_results,
                          lgb_cv_results, gru_cv_results, df)

    print("\nDone.")

    # 9. Restart Streamlit so the dashboard picks up the new data and models
    restart_streamlit()


def restart_streamlit():
    """Kill any Streamlit processes on port 8501 and start a fresh instance."""
    import subprocess
    import time

    print("\nRestarting Streamlit dashboard ...")
    try:
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        pids = {
            line.strip().split()[-1]
            for line in result.stdout.splitlines()
            if ":8501 " in line and "LISTENING" in line
        }
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            print(f"  Killed PID {pid}")
        if pids:
            time.sleep(1)
    except Exception as e:
        print(f"  Warning: could not kill old processes: {e}")

    app_path = BASE_DIR / "kinneret_app" / "app.py"
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app_path),
         "--server.port", "8501", "--server.headless", "true"],
        cwd=str(BASE_DIR),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
    print("  Streamlit restarted — http://localhost:8501")


if __name__ == "__main__":
    main()
