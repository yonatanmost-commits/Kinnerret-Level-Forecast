# Model Olympics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train XGBoost, LightGBM, and GRU challengers alongside the existing GBRegressor baseline, benchmark all four with walk-forward CV, save results to `Models/olympics_results.json`, and display a comparison page (`7_Model_Olympics.py`) that crowns a winner.

**Architecture:** All challengers fix the Stage-1 chaining problem by using a direct multi-step inflow model (anchor inflow at day 0 + `horizon_h` as features, no chained predictions). XGBoost and LightGBM are two independent direct models each. The GRU is a single multi-task network with a shared 21-day sequence backbone and two output heads (inflow + volume change). Baseline CV metrics are carried forward from `model_metadata.json` — the existing pipeline is not modified.

**Tech Stack:** Python 3.14, PyTorch (CPU), xgboost, lightgbm, Streamlit, pure numpy (existing).

---

## File Map

| File | Role |
|---|---|
| `Automation/model_lib.py` | Add `S1_DIRECT_FEATURES` constant |
| `Automation/gru_model.py` | **New.** `KinneretGRU` nn.Module + `build_gru_sequences()` + `GRUTrainer` |
| `Automation/08_train_forecast_model.py` | Add helpers + CV + training for all three challengers; save `olympics_results.json` |
| `Models/olympics_results.json` | Generated at training time — CV scores + winner |
| `kinneret_app/pages/7_Model_Olympics.py` | **New.** Streamlit comparison page |

**Unchanged:** `model_lib.py` (except one constant), `app_utils.py`, `09_weekly_forecast.py`, `model_metadata.json`, pages 1–6, all existing `.pkl` files.

---

## Task 1: Install and Verify Dependencies

**Files:** none

- [ ] **Step 1: Install libraries**

```powershell
pip install xgboost lightgbm
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

- [ ] **Step 2: Verify imports**

```powershell
python -c "import xgboost; import lightgbm; import torch; print('xgb', xgboost.__version__, 'lgb', lightgbm.__version__, 'torch', torch.__version__)"
```

Expected: three version strings printed, no ImportError.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "chore: install xgboost, lightgbm, torch for model olympics"
```

---

## Task 2: Add S1_DIRECT_FEATURES to model_lib.py

**Files:**
- Modify: `Automation/model_lib.py` (after the `S2_DIRECT_TARGET` line, around line 110)

- [ ] **Step 1: Add constant**

Insert immediately after the line `S2_DIRECT_TARGET = "volume_change_Mm3"`:

```python
# Direct multi-step Stage-1 feature set.
# Replaces chained inflow lags with a fixed anchor inflow at day 0.
S1_DIRECT_FEATURES = [
    "rainfall_mm",
    "rainfall_lag1_mm",
    "rainfall_lag2_mm",
    "rainfall_lag3_mm",
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    "moisture_balance_7d_mm",
    "moisture_balance_14d_mm",
    "temp_mean_C",
    "temp_min_C",
    "humidity_pct",
    "vpd_kPa",
    "et0_mm",
    "inflow_anchor_m3",   # actual inflow at anchor day (day 0); never chained
    "horizon_h",          # 1 … 7 (which forecast day)
    "season_sin",
    "season_cos",
]
# S1_DIRECT_TARGET is the same as S1_TARGET = "inflow_obstacle_m3"
```

- [ ] **Step 2: Verify**

```powershell
python -c "from model_lib import S1_DIRECT_FEATURES; print(len(S1_DIRECT_FEATURES), 'features')"
```

Expected: `18 features`

- [ ] **Step 3: Commit**

```bash
git add Automation/model_lib.py
git commit -m "feat: add S1_DIRECT_FEATURES for direct multi-step inflow prediction"
```

---

## Task 3: Create gru_model.py

**Files:**
- Create: `Automation/gru_model.py`

- [ ] **Step 1: Write the file**

```python
"""
gru_model.py  -  PyTorch GRU multi-task model for Kinneret forecasting.

Predicts Jordan River inflow (m³/day) and lake volume change (Mm³/day)
jointly from a 21-day sequence window + per-horizon scalar.

Kept separate from model_lib.py so PyTorch is not imported on every
dashboard page load.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

SEQUENCE_LEN = 21

GRU_SEQ_FEATURES = [
    "temp_mean_C", "temp_max_C", "temp_min_C",
    "rainfall_mm", "humidity_pct", "wind_speed_ms", "et0_mm", "rainfall_7d_mm",
    "level_m", "volume_change_Mm3", "inflow_obstacle_m3",
    "season_sin", "season_cos", "daylength_hrs",
]
N_SEQ_FEATURES = len(GRU_SEQ_FEATURES)   # 14


# ─────────────────────────────────────────────────────────────────────────────
# Neural network
# ─────────────────────────────────────────────────────────────────────────────

class KinneretGRU(nn.Module):
    """
    GRU backbone with two output heads.

    Forward args
    ------------
    seq      : FloatTensor [batch, 21, 14]  — daily feature sequence
    horizon  : FloatTensor [batch, 1]       — forecast horizon (1-7)

    Returns
    -------
    inflow_pred : FloatTensor [batch]  (raw, denormalize externally)
    dvol_pred   : FloatTensor [batch]
    """

    def __init__(self, input_size: int = N_SEQ_FEATURES,
                 hidden_size: int = 64, dropout: float = 0.2):
        super().__init__()
        # num_layers=1: PyTorch dropout only fires between layers,
        # so we apply it in the dense block instead.
        self.gru = nn.GRU(input_size, hidden_size,
                          num_layers=1, batch_first=True)
        self.shared = nn.Sequential(
            nn.Linear(hidden_size + 1, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
        )
        self.inflow_head = nn.Linear(32, 1)
        self.dvol_head   = nn.Linear(32, 1)

    def forward(self, seq: torch.Tensor,
                horizon: torch.Tensor):
        _, h_n      = self.gru(seq)          # h_n: [1, B, H]
        h           = h_n.squeeze(0)         # [B, H]
        x           = torch.cat([h, horizon], dim=1)   # [B, H+1]
        shared      = self.shared(x)         # [B, 32]
        inflow_pred = self.inflow_head(shared).squeeze(1)
        dvol_pred   = self.dvol_head(shared).squeeze(1)
        return inflow_pred, dvol_pred


# ─────────────────────────────────────────────────────────────────────────────
# Sequence builder
# ─────────────────────────────────────────────────────────────────────────────

def build_gru_sequences(df: pd.DataFrame, horizon: int):
    """
    Build fixed-length (SEQUENCE_LEN) input sequences for one forecast horizon.

    For each anchor row t where targets at t+horizon are valid:
      - sequence   = df[GRU_SEQ_FEATURES] rows [t-20 : t+1], zero-padded if needed
      - horizon_h  = [[float(horizon)]]
      - inflow_tgt = inflow_obstacle_m3 at t+horizon
      - dvol_tgt   = volume_change_Mm3  at t+horizon
      - anchor_idx = integer row index t in df

    Returns five arrays (all float32):
      sequences     [N, 21, 14]
      horizons      [N, 1]
      inflow_tgts   [N]
      dvol_tgts     [N]
      anchor_indices [N]  — int64 row indices into df
    """
    df   = df.reset_index(drop=True)
    n    = len(df)
    feat = np.nan_to_num(
        df[GRU_SEQ_FEATURES].values.astype(np.float32), nan=0.0
    )
    inflow_col = df["inflow_obstacle_m3"].values.astype(np.float32)
    dvol_col   = df["volume_change_Mm3"].values.astype(np.float32)

    sequences, horizons_out, inflow_tgts, dvol_tgts, anc_idx = [], [], [], [], []

    for t in range(n - horizon):
        ti = float(inflow_col[t + horizon])
        td = float(dvol_col[t + horizon])
        if np.isnan(ti) or np.isnan(td):
            continue

        start = t - SEQUENCE_LEN + 1
        if start >= 0:
            seq = feat[start: t + 1].copy()
        else:
            pad = np.zeros((-start, N_SEQ_FEATURES), dtype=np.float32)
            seq = np.vstack([pad, feat[: t + 1]])

        sequences.append(seq)
        horizons_out.append([float(horizon)])
        inflow_tgts.append(ti)
        dvol_tgts.append(td)
        anc_idx.append(t)

    return (
        np.array(sequences,    dtype=np.float32),
        np.array(horizons_out, dtype=np.float32),
        np.array(inflow_tgts,  dtype=np.float32),
        np.array(dvol_tgts,    dtype=np.float32),
        np.array(anc_idx,      dtype=np.int64),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trainer  (fit / predict / save / load)
# ─────────────────────────────────────────────────────────────────────────────

class GRUTrainer:
    """
    Wraps KinneretGRU with a sklearn-style fit/predict API.
    Handles z-score normalisation of both targets internally.
    """

    def __init__(self, epochs: int = 150, lr: float = 1e-3,
                 batch_size: int = 64):
        self.epochs     = epochs
        self.lr         = lr
        self.batch_size = batch_size
        self.device     = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: KinneretGRU | None = None
        self.inflow_mean = self.inflow_std = None
        self.dvol_mean   = self.dvol_std   = None

    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "GRUTrainer":
        """Train on df (builds sequences for all horizons 1-7 internally)."""
        all_seqs, all_h, all_inf, all_dv = [], [], [], []
        for h in range(1, 8):
            s, hs, inf, dv, _ = build_gru_sequences(df, h)
            all_seqs.append(s);  all_h.append(hs)
            all_inf.append(inf); all_dv.append(dv)

        seqs    = np.concatenate(all_seqs)
        hs      = np.concatenate(all_h)
        inflows = np.concatenate(all_inf)
        dvols   = np.concatenate(all_dv)

        self.inflow_mean = float(np.nanmean(inflows))
        self.inflow_std  = max(float(np.nanstd(inflows)), 1e-8)
        self.dvol_mean   = float(np.nanmean(dvols))
        self.dvol_std    = max(float(np.nanstd(dvols)), 1e-8)

        inf_n = (inflows - self.inflow_mean) / self.inflow_std
        dv_n  = (dvols   - self.dvol_mean)   / self.dvol_std

        dev    = self.device
        X_seq  = torch.tensor(seqs,  device=dev)
        X_h    = torch.tensor(hs,    device=dev)
        y_inf  = torch.tensor(inf_n, device=dev)
        y_dv   = torch.tensor(dv_n,  device=dev)

        self.model = KinneretGRU().to(dev)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        n = len(seqs)
        for epoch in range(self.epochs):
            self.model.train()
            perm       = torch.randperm(n, device=dev)
            epoch_loss = 0.0
            n_batches  = 0
            for start in range(0, n, self.batch_size):
                idx = perm[start: start + self.batch_size]
                opt.zero_grad()
                p_inf, p_dv = self.model(X_seq[idx], X_h[idx])
                loss = (F.mse_loss(p_inf, y_inf[idx]) +
                        F.mse_loss(p_dv,  y_dv[idx]))
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
                n_batches  += 1
            if (epoch + 1) % 30 == 0:
                print(f"    GRU epoch {epoch+1}/{self.epochs}  "
                      f"loss={epoch_loss / n_batches:.4f}", flush=True)
        return self

    # ------------------------------------------------------------------
    def predict_horizon(self, full_df: pd.DataFrame,
                        horizon: int, test_year: int | None = None):
        """
        Predict inflow and dvol for one horizon.

        full_df   : gold DataFrame (may span multiple years; sequences use
                    history across the train-test boundary — correct behaviour)
        horizon   : 1-7
        test_year : if given, return only rows where anchor is in that year

        Returns (inflow_pred, dvol_pred, anchor_dates, dvol_actuals) — all
        aligned arrays (float32 / datetime64).
        """
        seqs, hs, inf_tgts, dv_tgts, anc_idx = build_gru_sequences(full_df, horizon)
        if len(seqs) == 0:
            empty = np.array([], dtype=np.float32)
            return empty, empty, np.array([]), empty

        if test_year is not None:
            mask    = full_df.iloc[anc_idx]["date"].dt.year.values == test_year
            seqs    = seqs[mask];    hs       = hs[mask]
            inf_tgts = inf_tgts[mask]; dv_tgts = dv_tgts[mask]
            anc_idx  = anc_idx[mask]

        self.model.eval()
        dev = self.device
        with torch.no_grad():
            p_inf, p_dv = self.model(
                torch.tensor(seqs, device=dev),
                torch.tensor(hs,   device=dev),
            )
        p_inf = p_inf.cpu().numpy() * self.inflow_std + self.inflow_mean
        p_dv  = p_dv.cpu().numpy()  * self.dvol_std   + self.dvol_mean
        p_inf = np.clip(p_inf, 0, None)

        anchor_dates = full_df.iloc[anc_idx]["date"].values
        return p_inf, p_dv, anchor_dates, dv_tgts

    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state": self.model.state_dict(),
            "inflow_mean": self.inflow_mean, "inflow_std": self.inflow_std,
            "dvol_mean":   self.dvol_mean,   "dvol_std":   self.dvol_std,
            "epochs": self.epochs, "lr": self.lr,
        }, path)

    @classmethod
    def load(cls, path: str | Path) -> "GRUTrainer":
        ckpt    = torch.load(path, map_location="cpu", weights_only=False)
        trainer = cls(epochs=ckpt["epochs"], lr=ckpt["lr"])
        trainer.model = KinneretGRU()
        trainer.model.load_state_dict(ckpt["model_state"])
        trainer.model.eval()
        trainer.inflow_mean = ckpt["inflow_mean"]
        trainer.inflow_std  = ckpt["inflow_std"]
        trainer.dvol_mean   = ckpt["dvol_mean"]
        trainer.dvol_std    = ckpt["dvol_std"]
        return trainer
```

- [ ] **Step 2: Smoke test**

```powershell
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -c "
import sys; sys.path.insert(0, 'Automation')
import numpy as np, pandas as pd
from gru_model import GRUTrainer, build_gru_sequences, GRU_SEQ_FEATURES

# Minimal synthetic df
n = 60
df = pd.DataFrame({col: np.random.randn(n) for col in GRU_SEQ_FEATURES})
df['date'] = pd.date_range('2020-01-01', periods=n)
df['inflow_obstacle_m3'] = np.abs(np.random.randn(n)) * 1e6
df['volume_change_Mm3']  = np.random.randn(n)

seqs, hs, inf, dv, idx = build_gru_sequences(df, horizon=3)
print('sequences shape:', seqs.shape)   # expect (N, 21, 14)
print('anchor idx sample:', idx[:3])

trainer = GRUTrainer(epochs=2)
trainer.fit(df)
p_inf, p_dv, dates, actuals = trainer.predict_horizon(df, horizon=3)
print('predict shapes:', p_inf.shape, p_dv.shape)
print('smoke test PASSED')
"
```

Expected:
```
sequences shape: (57, 21, 14)
anchor idx sample: [0 1 2]
GRU epoch 2/2  loss=...
predict shapes: (57,) (57,)
smoke test PASSED
```

- [ ] **Step 3: Commit**

```bash
git add Automation/gru_model.py
git commit -m "feat: add GRUTrainer multi-task model with 21-day sequence window"
```

---

## Task 4: Add Helpers to 08_train_forecast_model.py

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

Add two helpers and update the import line. These are shared by all three challenger CV functions.

- [ ] **Step 1: Update imports at top of file**

Change the existing `from model_lib import (...)` block to also import `S1_DIRECT_FEATURES`:

```python
from model_lib import (
    GBRegressor,
    S1_FEATURES, S1_TARGET,
    S2_FEATURES, S2_TARGET,
    S2_MET_FEATURES, S2_DIRECT_FEATURES, S2_DIRECT_TARGET,
    S1_DIRECT_FEATURES,
    log_transform, inv_log_transform,
    signed_log1p_transform, inv_signed_log1p_transform,
)
```

- [ ] **Step 2: Add `build_direct_s1_data()` after `build_direct_s2_data()`**

```python
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
```

- [ ] **Step 3: Add `_mean_7d_drift()` helper after `build_direct_s1_data()`**

```python
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
```

- [ ] **Step 4: Verify helpers are importable**

```powershell
python -c "
import sys; sys.path.insert(0, 'Automation')
from model_lib import S1_DIRECT_FEATURES
print('S1_DIRECT_FEATURES OK:', len(S1_DIRECT_FEATURES))
"
```

Expected: `S1_DIRECT_FEATURES OK: 18`

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py Automation/model_lib.py
git commit -m "feat: add build_direct_s1_data and _mean_7d_drift helpers"
```

---

## Task 5: XGBoost CV + Final Training

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

Add `run_cv_xgb()` and `train_final_xgb()`. Do NOT call them from `main()` yet — that happens in Task 8.

- [ ] **Step 1: Add imports at top of file (after existing imports)**

```python
import xgboost as xgb
```

- [ ] **Step 2: Add `run_cv_xgb()` after `run_cv()`**

```python
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
```

- [ ] **Step 3: Add `train_final_xgb()` after `run_cv_xgb()`**

```python
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
```

- [ ] **Step 4: Commit**

```bash
git add Automation/08_train_forecast_model.py
git commit -m "feat: add XGBoost direct multi-step CV and final training"
```

---

## Task 6: LightGBM CV + Final Training

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

- [ ] **Step 1: Add LightGBM import**

```python
import lightgbm as lgb
```

- [ ] **Step 2: Add `run_cv_lgb()` — identical structure to `run_cv_xgb()`, only model lines differ**

```python
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
```

- [ ] **Step 3: Add `train_final_lgb()`**

```python
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
```

- [ ] **Step 4: Commit**

```bash
git add Automation/08_train_forecast_model.py
git commit -m "feat: add LightGBM direct multi-step CV and final training"
```

---

## Task 7: GRU CV + Final Training

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

- [ ] **Step 1: Add GRU import (after existing imports)**

```python
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from gru_model import GRUTrainer
```

Note: the `sys.path.insert` for `Automation/` is already at the top of the file. Import `GRUTrainer` alongside the other model imports.

Actually: add this line to the existing imports block at the top of the file:

```python
from gru_model import GRUTrainer
```

(The `sys.path.insert(0, str(Path(__file__).resolve().parent))` is already present from the existing imports.)

- [ ] **Step 2: Add `run_cv_gru()` function**

```python
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
            "s1_r2": None,   # GRU predicts inflow jointly; separate metric complex to isolate
            "s2_r2": round(s2_r2_val, 3),
            "s2_mae": round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results
```

- [ ] **Step 3: Add `train_final_gru()`**

```python
def train_final_gru(df: pd.DataFrame):
    """Train final GRU on all available data and save."""
    print("\n  GRU final training (150 epochs on full dataset) ...")
    trainer = GRUTrainer(epochs=150, lr=1e-3, batch_size=64)
    trainer.fit(df)
    MODELS_DIR.mkdir(exist_ok=True)
    trainer.save(MODELS_DIR / "gru_multitask.pt")
    print(f"  Saved gru_multitask.pt")
    return trainer
```

- [ ] **Step 4: Commit**

```bash
git add Automation/08_train_forecast_model.py
git commit -m "feat: add GRU multi-task CV and final training"
```

---

## Task 8: Wire Everything Into main() and Save olympics_results.json

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

- [ ] **Step 1: Add `_read_baseline_from_meta()` helper**

```python
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
```

- [ ] **Step 2: Add `save_olympics_results()` helper**

```python
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
            "cv_vol_r2_mean":    round(float(np.mean(r2s)),  3),
            "cv_vol_r2_by_fold": {r["fold"]: r["s2_r2"] for r in cv_list},
            "cv_vol_mae_mean":   round(float(np.mean(maes)), 3),
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
```

- [ ] **Step 3: Update `main()` to call all challenger blocks before `restart_streamlit()`**

Find the existing `main()` body. After step 5 (`train_final(df, oof_s1)`) and saving metadata, add:

```python
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
```

- [ ] **Step 4: Verify the script is syntactically valid**

```powershell
python -c "
import ast, pathlib
src = pathlib.Path('Automation/08_train_forecast_model.py').read_text(encoding='utf-8')
ast.parse(src)
print('syntax OK')
"
```

Expected: `syntax OK`

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py
git commit -m "feat: wire challenger training into main() and save olympics_results.json"
```

---

## Task 9: Create 7_Model_Olympics.py Dashboard Page

**Files:**
- Create: `kinneret_app/pages/7_Model_Olympics.py`

- [ ] **Step 1: Write the file**

```python
"""
7_Model_Olympics.py  —  Model Benchmark Comparison

Loads Models/olympics_results.json and displays a four-model scorecard,
winner announcement, per-fold R² chart, and architecture notes.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys_path_added = False
try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_utils import PROJECT_ROOT, COLOURS
    sys_path_added = True
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RESULTS_FILE = PROJECT_ROOT / "Models" / "olympics_results.json"

st.set_page_config(page_title="Model Olympics", page_icon="🏅", layout="wide")

# ── CSS (matches project design system) ───────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700&family=DM+Mono&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif; }
.kn-label {
    font-size:0.78rem; color:#7BA3D4; text-transform:uppercase;
    letter-spacing:0.08em; font-family:'DM Mono',monospace; margin-bottom:4px;
}
.kn-divider {
    border:none; border-top:1px solid rgba(30,144,255,0.22); margin:1.2rem 0;
}
.winner-box {
    background:rgba(255,215,0,0.08); border:1px solid #FFD700;
    border-radius:8px; padding:1rem 1.4rem; margin:0.8rem 0;
}
.winner-name { font-family:'Syne',sans-serif; font-size:1.4rem;
               color:#FFD700; font-weight:700; }
.delta-pos { color:#66BB6A; font-weight:600; }
.delta-neg { color:#EF5350; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🏅 Model Olympics</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#7BA3D4;font-size:0.72rem;">'
    'Walk-forward CV benchmark — held-out years 2021–2024'
    '</p>', unsafe_allow_html=True)
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)

# ── Load results ──────────────────────────────────────────────────────────────
if not RESULTS_FILE.exists():
    st.warning(
        "Results not found. Run `python Automation/08_train_forecast_model.py` "
        "to train all models and generate the benchmark."
    )
    st.stop()

with open(RESULTS_FILE, encoding="utf-8") as f:
    results = json.load(f)

models   = results["models"]
winner   = results["winner"]
gen_date = results.get("generated_at", "unknown")

DISPLAY_NAMES = {
    "baseline_gbr": "Baseline GBR",
    "xgboost":      "XGBoost",
    "lgbm":         "LightGBM",
    "gru":          "GRU (multi-task)",
}

# ── 1. Scoreboard ─────────────────────────────────────────────────────────────
st.markdown('<p class="kn-label">Scoreboard</p>', unsafe_allow_html=True)

rows = []
for key, entry in models.items():
    rows.append({
        "Model":          DISPLAY_NAMES.get(key, key),
        "CV R² (vol Δ)":  entry.get("cv_vol_r2_mean"),
        "CV MAE (Mm³/d)": entry.get("cv_vol_mae_mean"),
        "7-day drift (m)":entry.get("cv_7d_drift_mean_m"),
        "Inflow R²":      entry.get("cv_inflow_r2_mean"),
        "_key":           key,
        "_is_winner":     key == winner,
    })

score_df = pd.DataFrame(rows)

def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.3f}"

# Build styled HTML table
def _row_html(row):
    bg    = "rgba(255,215,0,0.10)" if row["_is_winner"] else "transparent"
    color = "#FFD700" if row["_is_winner"] else "#E0E0E0"
    crown = " 🏅" if row["_is_winner"] else ""
    cells = [
        f'<td style="color:{color}">{row["Model"]}{crown}</td>',
        f'<td style="color:{color};text-align:right">{_fmt(row["CV R² (vol Δ)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["CV MAE (Mm³/d)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["7-day drift (m)"])}</td>',
        f'<td style="text-align:right">{_fmt(row["Inflow R²"])}</td>',
    ]
    return f'<tr style="background:{bg}">{"".join(cells)}</tr>'

header = "<tr>" + "".join(
    f'<th style="color:#7BA3D4;text-align:{"right" if i else "left"}">{h}</th>'
    for i, h in enumerate(["Model", "CV R² (vol Δ)", "CV MAE (Mm³/d)",
                            "7-day drift (m)", "Inflow R²"])
) + "</tr>"

table_html = (
    '<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;'
    'font-size:0.85rem">'
    f"<thead>{header}</thead><tbody>"
    + "".join(_row_html(r) for r in rows)
    + "</tbody></table>"
)
st.markdown(table_html, unsafe_allow_html=True)
st.markdown(f'<p style="color:#7BA3D4;font-size:0.7rem;margin-top:4px">'
            f'Generated: {gen_date}</p>', unsafe_allow_html=True)

# ── 2. Winner announcement ────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Champion</p>', unsafe_allow_html=True)

win_entry  = models[winner]
base_entry = models.get("baseline_gbr", {})
r2_delta   = (win_entry.get("cv_vol_r2_mean") or 0) - (base_entry.get("cv_vol_r2_mean") or 0)
mae_delta  = (win_entry.get("cv_vol_mae_mean") or 0) - (base_entry.get("cv_vol_mae_mean") or 0)

r2_sign    = "+" if r2_delta >= 0 else ""
mae_sign   = "+" if mae_delta >= 0 else ""
r2_class   = "delta-pos" if r2_delta >= 0 else "delta-neg"
mae_class  = "delta-neg" if mae_delta >= 0 else "delta-pos"

if winner != "baseline_gbr":
    st.markdown(f"""
    <div class="winner-box">
      <div class="winner-name">{DISPLAY_NAMES.get(winner, winner)}</div>
      <div style="margin-top:0.5rem;font-size:0.9rem;color:#E0E0E0">
        R² = <strong>{win_entry.get("cv_vol_r2_mean"):.3f}</strong>
        &nbsp;|&nbsp;
        MAE = <strong>{win_entry.get("cv_vol_mae_mean"):.3f} Mm³/day</strong>
        &nbsp;|&nbsp;
        vs baseline:
        <span class="{r2_class}">{r2_sign}{r2_delta:.3f} R²</span>
        &nbsp;
        <span class="{mae_class}">{mae_sign}{mae_delta:.3f} MAE</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="winner-box">
      <div class="winner-name">Baseline GBR holds the crown 🏆</div>
      <div style="margin-top:0.5rem;font-size:0.9rem;color:#E0E0E0">
        No challenger improved on the baseline R².
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── 3. Per-fold R² bar chart ──────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Per-fold R² (volume change)</p>',
            unsafe_allow_html=True)

fold_rows = []
for key, entry in models.items():
    by_fold = entry.get("cv_vol_r2_by_fold") or {}
    for fold, val in by_fold.items():
        if val is not None:
            fold_rows.append({
                "Year":  fold,
                "Model": DISPLAY_NAMES.get(key, key),
                "R²":    val,
            })

if fold_rows:
    fold_df = pd.DataFrame(fold_rows)
    # Pivot for grouped display
    pivot = fold_df.pivot(index="Year", columns="Model", values="R²")
    pivot = pivot[[DISPLAY_NAMES[k] for k in models if DISPLAY_NAMES[k] in pivot.columns]]
    st.bar_chart(pivot)

# ── 4. Architecture notes ─────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Architecture Notes</p>', unsafe_allow_html=True)

notes = {
    "Baseline GBR": (
        "The current production model. Stage 1 predicts Jordan River inflow using chained "
        "inflow lags — each day's predicted inflow feeds the next day as lag-1. Stage 2 uses "
        "a direct multi-step design with a fixed anchor state, but Stage 1 chaining remains "
        "a source of cumulative error over the 7-day window."
    ),
    "XGBoost": (
        "Two independent direct models (S1 for inflow, S2 for volume change), each trained "
        "with horizon_h as an explicit feature and a fixed anchor inflow at day 0. Eliminates "
        "Stage 1 chaining entirely. XGBoost's L1/L2 regularisation and column subsampling "
        "typically improve on gradient boosting baselines on tabular data."
    ),
    "LightGBM": (
        "Same two-model direct architecture as XGBoost. LightGBM's leaf-wise tree growth "
        "strategy often yields better performance on smaller datasets with skewed targets — "
        "relevant here because volume change has a heavy positive tail during flood events."
    ),
    "GRU (multi-task)": (
        "A single neural network with a shared 21-day GRU backbone. For each forecast day, "
        "the network receives a 21-day sequence of 14 daily features plus the target horizon "
        "(1-7) as input, and simultaneously predicts both inflow and volume change. The joint "
        "objective allows the network to learn physical co-variance between river flow and lake "
        "response that independent models cannot exploit."
    ),
}

for model_name, text in notes.items():
    if any(DISPLAY_NAMES[k] == model_name for k in models):
        st.markdown(f'<p style="color:#7BA3D4;font-size:0.78rem;margin-top:0.8rem">'
                    f'{model_name}</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:0.82rem;color:#C0C0C0">{text}</p>',
                    unsafe_allow_html=True)
```

- [ ] **Step 2: Verify Streamlit syntax**

```powershell
python -c "
import ast, pathlib
src = pathlib.Path('kinneret_app/pages/7_Model_Olympics.py').read_text(encoding='utf-8')
ast.parse(src)
print('syntax OK')
"
```

Expected: `syntax OK`

- [ ] **Step 3: Verify page loads without the results file**

```powershell
python -c "
import sys; sys.path.insert(0, 'kinneret_app')
# Confirm the page won't crash on import (no st.run context, just syntax check)
print('import check skipped — run dashboard to test graceful degradation')
"
```

To fully test the page, start Streamlit and navigate to page 7. It should display the "results not found" warning (since training hasn't been run yet).

- [ ] **Step 4: Commit**

```bash
git add kinneret_app/pages/7_Model_Olympics.py
git commit -m "feat: add Model Olympics dashboard page (7_Model_Olympics.py)"
```

---

## Task 10: End-to-End Validation

**Files:** none (read-only + run commands)

- [ ] **Step 1: Run the full training pipeline**

```powershell
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/08_train_forecast_model.py
```

Expected output (abbreviated):
```
=== Walk-forward cross-validation ===
  2021: ...
  ...
=== Model Olympics — training challengers ===
=== XGBoost CV ===
  2021:  S1 R²=...  |  S2 R²=...  MAE=...  drift=... m
  ...
=== LightGBM CV ===
  ...
=== GRU CV (4 folds × 150 epochs — expect ~15 min on CPU) ===
  ...
  Saved: Models/olympics_results.json
  WINNER: <model_name>  (R²=...  MAE=...)
  Streamlit restarted — http://localhost:8501
```

- [ ] **Step 2: Verify results file**

```powershell
python -c "
import json
with open('Models/olympics_results.json') as f:
    r = json.load(f)
print('Winner:', r['winner'])
for name, entry in r['models'].items():
    print(f'  {name}: R²={entry[\"cv_vol_r2_mean\"]}  MAE={entry[\"cv_vol_mae_mean\"]}')
"
```

Expected: four entries printed, winner declared.

- [ ] **Step 3: Check page 7 in browser**

Open `http://localhost:8501` → navigate to **Model Olympics**. Verify:
- Scoreboard table shows all 4 models
- Winner row highlighted in gold
- Champion callout visible with delta vs baseline
- Per-fold bar chart renders
- Architecture notes displayed

- [ ] **Step 4: Final commit**

```bash
git add Models/olympics_results.json
git commit -m "feat: run model olympics — results and winner saved"
```
