# Model Olympics — Design Spec
**Date:** 2026-05-27  
**Status:** Approved

---

## Overview

Train three challenger models (XGBoost, LightGBM, GRU) alongside the existing GBRegressor baseline, benchmark all four with walk-forward cross-validation, and display the results in a new Streamlit comparison page that declares a winner. The live forecast pipeline is unchanged — promotion of a winner to production is a deliberate second step.

---

## Background & Motivation

The current Stage-2 model achieves **R² = 0.688, MAE = 0.655 Mm³/day** on volume change prediction (walk-forward CV, held-out years 2021–2024). The Stage-2 direct multi-step architecture already eliminates volume/level chaining error by fixing the anchor state at day 0. However, Stage-1 inflow prediction still uses chained lags — each day's predicted inflow becomes the next day's `inflow_lag1_m3` — which is a real source of error propagation. All three challengers eliminate this by applying the same direct multi-step approach to inflow prediction as well.

---

## Model Field

| Model | Inflow prediction | Volume Δ prediction | Chaining |
|---|---|---|---|
| **Baseline GBR** | chained lags | direct multi-step | Stage 1 only |
| **XGBoost** | direct multi-step | direct multi-step | none |
| **LightGBM** | direct multi-step | direct multi-step | none |
| **GRU (multi-task)** | joint output head | joint output head | none |

---

## Training Pipeline

### Changes to `Automation/08_train_forecast_model.py`

- Baseline GBR training is **unchanged**. All existing model files and `model_metadata.json` are preserved.
- After baseline training, three challenger training blocks are appended.
- A new helper `build_direct_s1_data(df)` mirrors the existing `build_direct_s2_data()` — it builds horizon-aware Stage-1 training data using a new constant `S1_DIRECT_FEATURES` (all of `S1_FEATURES` except `inflow_lag1_m3` and `inflow_lag2_m3`, plus `inflow_obstacle_m3` as anchor at day 0 and `horizon_h`). Target = `inflow_obstacle_m3` at t+h.
- Walk-forward CV runs for all four models on the same four folds (held-out years 2021, 2022, 2023, 2024).
- All results saved to `Models/olympics_results.json`.

### New file: `Automation/gru_model.py`

Kept separate from `model_lib.py` to avoid forcing a PyTorch import on every dashboard page load.

---

## Model Architectures

### XGBoost

Two independent direct models:

- `xgb_s1_direct`: features = `S1_DIRECT_FEATURES` (see Training Pipeline). Target = `inflow_obstacle_m3` at t+h.
- `xgb_s2_direct`: features = `S2_DIRECT_FEATURES`. Target = `volume_change_Mm3` at t+h.

Saved as `Models/xgb_s1_direct.pkl`, `Models/xgb_s2_direct.pkl`.  
Hyperparameters: `n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8` (sensible defaults, no grid search).

### LightGBM

Same structure as XGBoost — two independent direct models.  
Saved as `Models/lgb_s1_direct.pkl`, `Models/lgb_s2_direct.pkl`.  
Hyperparameters: `n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, verbosity=-1`.

### GRU (multi-task)

**Framework:** PyTorch (pip install torch).

**Input:**
- Sequence: last 21 days of daily features — 14 features per timestep:
  - Met: `temp_mean_C`, `temp_max_C`, `temp_min_C`, `rainfall_mm`, `humidity_pct`, `wind_speed_ms`, `et0_mm`, `rainfall_7d_mm`
  - Lake state: `level_m`, `volume_change_Mm3`, `inflow_obstacle_m3`
  - Seasonality: `season_sin`, `season_cos`, `daylength_hrs`
- Scalar: `horizon_h` (1–7), concatenated to GRU final hidden state

**Architecture:**
```
GRU layer:      input_size=14, hidden_size=64, num_layers=1, dropout=0.2
                → final hidden state [batch, 64]

Concat:         [hidden_state | horizon_h]  → [batch, 65]

Shared dense:   Linear(65→64), ReLU, Linear(64→32), ReLU

Output heads:
  inflow_head:  Linear(32→1)  → clipped ≥ 0 at inference
  dvol_head:    Linear(32→1)
```

**Training:**
- Targets z-score normalized per training fold (denormalized for metric reporting)
- Loss: joint MSE = `MSE(inflow_pred_norm, inflow_true_norm) + MSE(dvol_pred_norm, dvol_true_norm)`
- Optimizer: Adam, lr=1e-3
- Epochs: 150, batch size=64
- Saved as `Models/gru_multitask.pt` (torch.save)

**Data formatting:**  
For each anchor row t and horizon h, the 21-day sequence ends at t. Rows with fewer than 21 prior days are zero-padded. Sequences constructed in `gru_model.py` via `build_gru_sequences(df, horizon)`.

---

## Cross-Validation

- **Folds:** 4 walk-forward folds, held-out years 2021–2024 (same as baseline)
- **Baseline CV results** are read from the existing `model_metadata.json` — no re-training of the baseline. Inflow R² is `null` for the baseline by design (it chains predictions, no per-horizon inflow output).
- **GRU CV cost:** a new GRU is trained from scratch per fold (4 models × 150 epochs). Expect ~10–20 min total on CPU. The final production GRU trains on all data after CV.
- All metrics computed on original Mm³ scale (GRU targets denormalized before scoring)

---

## Metrics

| Metric | Description | Winner criterion |
|---|---|---|
| **R² — volume change** | Primary. CV mean across 4 folds. | Highest = winner |
| **MAE — volume change (Mm³/day)** | Scale-interpretable. Current baseline: 0.655. | Tiebreaker |
| **Cumulative 7-day level drift (m)** | Mean absolute difference between predicted and actual lake level at end of each 7-day CV forecast window. The metric users feel. | Diagnostic only |
| **R² — inflow** | Challengers only (baseline N/A — uses chained predictions, not direct). | Diagnostic only |

Winner declared by highest mean CV R² on volume change. All metrics saved to `Models/olympics_results.json`.

---

## `Models/olympics_results.json` Schema

```json
{
  "generated_at": "YYYY-MM-DD",
  "winner": "lgbm",
  "models": {
    "baseline_gbr": {
      "cv_vol_r2_mean": 0.688,
      "cv_vol_r2_by_fold": {"2021": ..., "2022": ..., "2023": ..., "2024": ...},
      "cv_vol_mae_mean": 0.655,
      "cv_7d_drift_mean_m": ...,
      "cv_inflow_r2_mean": null
    },
    "xgboost": { ... },
    "lgbm": { ... },
    "gru": { ... }
  }
}
```

---

## Dashboard Page

**File:** `kinneret_app/pages/7_Model_Olympics.py`

Follows existing CSS design system (`.kn-label`, `.kn-divider`, dark theme `bg=#0F1117`, accent `#1E90FF`, Syne/DM Mono fonts).

**Layout (top to bottom):**

1. **Scoreboard table** — all four models × all four metrics. Current baseline row highlighted. Winner row rendered with gold accent (`#FFD700`).

2. **Winner announcement** — prominent callout showing: model name, R² and MAE, delta vs baseline (e.g. `+0.042 R²`, `−0.089 MAE`).

3. **Cumulative drift chart** — line chart of predicted vs actual lake level across all CV test windows, one line per model. Makes error accumulation visually concrete.

4. **Per-fold R² bar chart** — R² by held-out year (2021–2024) per model. Shows consistency vs. single-fold luck.

5. **Architecture notes** — one paragraph per challenger, plain language. Explains what is structurally different from the baseline.

**Graceful degradation:** if `Models/olympics_results.json` does not exist, the page shows:
> "Models not yet trained. Run `python Automation/08_train_forecast_model.py` to generate results."

---

## Dependencies

```
pip install xgboost lightgbm torch
```

PyTorch CPU-only wheel recommended unless GPU is available:
```
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

---

## Files Created / Modified

| File | Action |
|---|---|
| `Automation/08_train_forecast_model.py` | Modified — add challenger training + extended CV |
| `Automation/gru_model.py` | New — PyTorch GRU class + sequence builder |
| `Models/xgb_s1_direct.pkl` | New (generated at training time) |
| `Models/xgb_s2_direct.pkl` | New (generated at training time) |
| `Models/lgb_s1_direct.pkl` | New (generated at training time) |
| `Models/lgb_s2_direct.pkl` | New (generated at training time) |
| `Models/gru_multitask.pt` | New (generated at training time) |
| `Models/olympics_results.json` | New (generated at training time) |
| `kinneret_app/pages/7_Model_Olympics.py` | New — dashboard comparison page |

**Unchanged:** `model_lib.py`, `app_utils.py`, `09_weekly_forecast.py`, `model_metadata.json`, all existing model `.pkl` files, pages 1–6.
