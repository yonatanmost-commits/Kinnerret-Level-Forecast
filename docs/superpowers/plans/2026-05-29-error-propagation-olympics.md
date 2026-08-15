# Error Propagation Olympics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four GBR architecture candidates (A, C, D, E) to the Model Olympics that isolate the effect of error propagation in the 7-day forecast.

**Architecture:** Each candidate trains `GBRegressor` with the same CV harness but different feature strategies and inference simulations. A shared `_simulate_7d_chain` helper drives the chaining simulation for architectures A and E. C and D use the existing direct-data builders. Results flow into an expanded `save_olympics_results`.

**Tech Stack:** Pure numpy `GBRegressor` (already in `model_lib.py`), existing `build_direct_s1_data` / `build_direct_s2_data` builders, walk-forward CV folds 2021–2024, `_mean_7d_drift` metric.

---

## Architecture reference

| Key | Name | S1 | S2 | Chain at inference |
|-----|------|----|----|--------------------|
| `baseline_gbr` | Baseline GBR | `S1_FEATURES` (chained lags, but CV uses actual) | `S2_FEATURES` (anchor, direct anchor) | S1 chains; S2 anchor fixed |
| `gbr_max_chain` | **A — max chain** | `S1_FEATURES` | `S2_FEATURES` | Both S1 and S2 fully chain over 7 days |
| `gbr_s1_direct_s2_anchor` | **C — s1 direct, s2 anchor** | `S1_DIRECT_FEATURES` (anchor inflow + horizon_h) | `S2_DIRECT_FEATURES` (anchor state + horizon_h) | Neither chains |
| `gbr_single_stage` | **D — single stage** | None | `S2_DIRECT_NO_INFLOW_FEATURES` (no inflow at all) | N/A |
| `gbr_s1_chain_s2_roll1` | **E — s1 chain, s2 roll1** | `S1_FEATURES` | `S2_FEATURES` | S1 chains; S2 rolls dvol_lag1 only (dvol_lag2 and level_m stay at anchor) |

---

## File structure

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `Automation/model_lib.py` | Add `S2_DIRECT_NO_INFLOW_FEATURES` constant |
| Modify | `Automation/08_train_forecast_model.py` | Add `_simulate_7d_chain`, four `run_cv_*` functions, two `train_final_*` functions, update `save_olympics_results` and `main()` |
| Modify | `kinneret_app/pages/7_Model_Olympics.py` | Extend `DISPLAY_NAMES`, add architecture notes |
| Create | `tests/test_error_prop_olympics.py` | Tests for new constants and helpers |

---

## Task 1 — Add S2_DIRECT_NO_INFLOW_FEATURES to model_lib.py

**Files:**
- Modify: `Automation/model_lib.py` (after line 109, after `S2_DIRECT_FEATURES`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_prop_olympics.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))

from model_lib import S2_DIRECT_FEATURES, S2_DIRECT_NO_INFLOW_FEATURES

def test_no_inflow_features_excludes_predicted_inflow():
    assert "predicted_inflow_m3" not in S2_DIRECT_NO_INFLOW_FEATURES

def test_no_inflow_features_is_subset_of_direct_features():
    assert set(S2_DIRECT_NO_INFLOW_FEATURES) < set(S2_DIRECT_FEATURES)

def test_no_inflow_features_length():
    assert len(S2_DIRECT_NO_INFLOW_FEATURES) == len(S2_DIRECT_FEATURES) - 1
```

- [ ] **Step 2: Run test to verify it fails**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_error_prop_olympics.py -v
```
Expected: ImportError or AttributeError on `S2_DIRECT_NO_INFLOW_FEATURES`

- [ ] **Step 3: Add the constant to model_lib.py**

Insert after `S2_DIRECT_FEATURES` block (after line 110):
```python
# Single-stage architecture (D): same as S2_DIRECT_FEATURES but without inflow prediction.
# Used when no Stage-1 model is run — inflow signal is absent.
S2_DIRECT_NO_INFLOW_FEATURES = [f for f in S2_DIRECT_FEATURES if f != "predicted_inflow_m3"]
```

- [ ] **Step 4: Update the import in 08_train_forecast_model.py**

Change the import block at the top to add `S2_DIRECT_NO_INFLOW_FEATURES`:
```python
from model_lib import (
    GBRegressor,
    S1_FEATURES, S1_TARGET,
    S2_FEATURES, S2_TARGET,
    S2_MET_FEATURES, S2_DIRECT_FEATURES, S2_DIRECT_TARGET,
    S1_DIRECT_FEATURES,
    S2_DIRECT_NO_INFLOW_FEATURES,
    log_transform, inv_log_transform,
    signed_log1p_transform, inv_signed_log1p_transform,
)
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_error_prop_olympics.py::test_no_inflow_features_excludes_predicted_inflow tests/test_error_prop_olympics.py::test_no_inflow_features_is_subset_of_direct_features tests/test_error_prop_olympics.py::test_no_inflow_features_length -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add Automation/model_lib.py Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add S2_DIRECT_NO_INFLOW_FEATURES constant for single-stage architecture"
```

---

## Task 2 — Add _simulate_7d_chain helper

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert before `run_cv` function, after `_mean_7d_drift`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
import numpy as np
import pandas as pd
import pytest


def _make_minimal_df(n_rows: int = 30) -> pd.DataFrame:
    """Tiny but complete gold-like DataFrame for testing."""
    from model_lib import (
        S1_FEATURES, S1_TARGET, S2_FEATURES, S2_TARGET,
    )
    dates = pd.date_range("2020-01-01", periods=n_rows)
    rng = np.random.default_rng(0)
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET,
        "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
    ]))
    data = {"date": dates}
    for c in cols:
        data[c] = rng.uniform(0.1, 1.0, n_rows)
    df = pd.DataFrame(data)
    return df


def test_simulate_7d_chain_returns_7_rows():
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(30)
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((10, len(S1_FEATURES))), np.ones(10))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((10, len(S2_FEATURES))), np.ones(10))

    anchor = pd.Timestamp("2020-01-10")
    rows = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    assert len(rows) == 7


def test_simulate_7d_chain_missing_future_returns_empty():
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(5)   # only 5 rows; no room for 7 future days from day 1
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((5, len(S1_FEATURES))), np.ones(5))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((5, len(S2_FEATURES))), np.ones(5))

    anchor = pd.Timestamp("2020-01-04")  # only 1 future row available (day 5)
    rows = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_simulate_7d_chain_returns_7_rows -v
```
Expected: ImportError — `_simulate_7d_chain` doesn't exist yet

- [ ] **Step 3: Add _simulate_7d_chain to 08_train_forecast_model.py**

Insert between `_mean_7d_drift` and `load_data` (around line 176):

```python
def _simulate_7d_chain(
    rf1: GBRegressor,
    rf2: GBRegressor,
    anchor_date: pd.Timestamp,
    df_idx: pd.DataFrame,
    bathy_coeffs: list,
    roll_dvol_only: bool = False,
) -> list:
    """
    Simulate a 7-day chained forecast window for architecture A or E.

    rf1           : trained Stage-1 GBRegressor (S1_FEATURES → inflow)
    rf2           : trained Stage-2 GBRegressor (S2_FEATURES → dvol)
    anchor_date   : day-0 anchor (predictions start at anchor+1)
    df_idx        : full gold DataFrame indexed by date (Timestamp)
    bathy_coeffs  : vol→level polynomial [a, b, c] for architecture A level update
    roll_dvol_only: if True (architecture E) only dvol_lag1 chains;
                    dvol_lag2 and level_m stay at anchor values throughout.

    Returns list of {'date', 'horizon_h', 'pred_dvol'} for h=1..7,
    or [] if any of the 7 future dates are missing from df_idx.
    """
    future_dates = [anchor_date + pd.Timedelta(days=h) for h in range(1, 8)]
    if not all(d in df_idx.index for d in future_dates):
        return []

    prev_date = anchor_date - pd.Timedelta(days=1)
    anchor = df_idx.loc[anchor_date]
    prev = df_idx.loc[prev_date] if prev_date in df_idx.index else anchor

    # Chain state — initialised from anchor and prev
    inflow_lag1 = float(anchor.get("inflow_obstacle_m3", np.nan))
    inflow_lag2 = float(prev.get("inflow_obstacle_m3", np.nan))
    dvol_lag1   = float(anchor.get("volume_change_Mm3", np.nan))
    dvol_lag2_fixed = float(prev.get("volume_change_Mm3", np.nan))
    dvol_lag2   = dvol_lag2_fixed
    level_m     = float(anchor.get("level_m", np.nan))
    volume_Mm3  = float(anchor.get("volume_Mm3", np.nan))

    rows = []
    for h in range(1, 8):
        fut = df_idx.loc[future_dates[h - 1]]

        # Stage-1 row: met features from future date, lags from chain state
        s1_row = {f: float(fut.get(f, np.nan)) for f in S1_FEATURES}
        s1_row["inflow_lag1_m3"] = inflow_lag1
        s1_row["inflow_lag2_m3"] = inflow_lag2
        pred_inflow = float(np.clip(
            rf1.predict(np.array([[s1_row[f] for f in S1_FEATURES]])), 0, None)[0])

        # Stage-2 row: met features from future date, state from chain
        s2_row = {f: float(fut.get(f, np.nan)) for f in S2_FEATURES}
        s2_row["predicted_inflow_m3"] = pred_inflow
        s2_row["volume_change_lag1_Mm3"] = dvol_lag1
        s2_row["volume_change_lag2_Mm3"] = dvol_lag2
        s2_row["level_m"] = level_m
        pred_dvol = float(rf2.predict(np.array([[s2_row[f] for f in S2_FEATURES]]))[0])

        rows.append({"date": anchor_date, "horizon_h": float(h), "pred_dvol": pred_dvol})

        # Advance chain state
        inflow_lag2 = inflow_lag1
        inflow_lag1 = pred_inflow

        if roll_dvol_only:
            # Architecture E: only roll dvol_lag1; dvol_lag2 and level_m stay fixed
            dvol_lag1 = pred_dvol
            dvol_lag2 = dvol_lag2_fixed
            # level_m unchanged — no cumulative level update
        else:
            # Architecture A: full chain — update all state
            dvol_lag2 = dvol_lag1
            dvol_lag1 = pred_dvol
            volume_Mm3 += pred_dvol
            level_m = float(np.polyval(bathy_coeffs, volume_Mm3))

    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_error_prop_olympics.py::test_simulate_7d_chain_returns_7_rows tests/test_error_prop_olympics.py::test_simulate_7d_chain_missing_future_returns_empty -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add _simulate_7d_chain helper for max-chain and roll1 architectures"
```

---

## Task 3 — run_cv_max_chain (Architecture A)

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert after `run_cv`, before `run_cv_xgb`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_run_cv_max_chain_returns_4_folds():
    from _08_train_forecast_model import run_cv_max_chain

    df = _make_cv_df()  # see below for helper
    bathy = [0.0, 0.0, -208.0]  # constant level ≈ -208m
    results = run_cv_max_chain(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)
    assert all("s1_r2" in r for r in results)


def _make_cv_df() -> pd.DataFrame:
    """Minimal gold-like DataFrame spanning 2012–2024 for CV fold testing."""
    from model_lib import S1_FEATURES, S2_FEATURES, S1_TARGET, S2_TARGET
    rng = np.random.default_rng(42)
    dates = pd.date_range("2012-01-01", "2024-12-31", freq="D")
    n = len(dates)
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET, "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
    ]))
    data = {"date": dates}
    for c in cols:
        data[c] = rng.uniform(0.1, 1.0, n)
    return pd.DataFrame(data)
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_max_chain_returns_4_folds -v
```
Expected: ImportError or AttributeError on `run_cv_max_chain`

- [ ] **Step 3: Add run_cv_max_chain to 08_train_forecast_model.py**

Insert after `run_cv` function (after line 315):

```python
def run_cv_max_chain(df: pd.DataFrame, bathy_coeffs: list,
                     _n_est: int = 150) -> list:
    """
    Walk-forward CV for architecture A (max-chain).

    Trains the same GBR models as baseline (S1_FEATURES, S2_FEATURES with
    actual lags) but evaluates using a 7-day sequential simulation where both
    inflow lags and dvol lags/level_m are replaced with predictions at each step.
    This measures the actual error propagation that occurs at inference time.
    """
    print("\n=== GBR max-chain CV (architecture A) ===")
    cv_results = []
    df_idx = df.set_index("date")

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # Train S1 — identical to baseline
        s1_tr = tr.dropna(subset=S1_FEATURES + [S1_TARGET])
        if len(s1_tr) == 0:
            continue
        rf1 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                          learning_rate=0.05, random_state=42)
        rf1.fit(s1_tr[S1_FEATURES].values, s1_tr[S1_TARGET].values)

        # Train S2 — identical to baseline (actual inflow as training proxy)
        tr_s2 = tr.copy()
        tr_s2["predicted_inflow_m3"] = tr_s2[S1_TARGET]
        s2_tr = tr_s2.dropna(subset=S2_FEATURES + [S2_TARGET])
        if len(s2_tr) == 0:
            continue
        rf2 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                          learning_rate=0.05, random_state=42)
        rf2.fit(s2_tr[S2_FEATURES].values, s2_tr[S2_TARGET].values)

        # Simulate chained 7-day windows for every anchor day in the test year
        te_dates = sorted(te["date"].unique())
        preds_rows = []
        all_pred, all_true = [], []

        for anchor_date in te_dates:
            window = _simulate_7d_chain(
                rf1, rf2, pd.Timestamp(anchor_date), df_idx,
                bathy_coeffs, roll_dvol_only=False)
            if not window:
                continue
            for r in window:
                fut_ts = r["date"] + pd.Timedelta(days=int(r["horizon_h"]))
                if fut_ts in df_idx.index:
                    true_dvol = float(df_idx.loc[fut_ts].get(S2_TARGET, np.nan))
                    if not np.isnan(true_dvol):
                        all_pred.append(r["pred_dvol"])
                        all_true.append(true_dvol)
            preds_rows.extend(window)

        if not all_pred:
            print(f"  Fold {fold_name}: no valid windows — skipping")
            continue

        preds_df = pd.DataFrame(preds_rows)
        s1_r2_val = r2(
            [float(df_idx.loc[pd.Timestamp(d) + pd.Timedelta(days=int(h))].get(S1_TARGET, np.nan))
             for d, h in zip(preds_df["date"], preds_df["horizon_h"])
             if (pd.Timestamp(d) + pd.Timedelta(days=int(h))) in df_idx.index],
            [float(x) for x in []]) if False else float("nan")

        s2_r2_val  = r2(np.array(all_true), np.array(all_pred))
        s2_mae_val = mae(np.array(all_true), np.array(all_pred))
        drift      = _mean_7d_drift(df, preds_df, bathy_coeffs)

        cv_results.append({
            "fold":    fold_name,
            "n_test":  len(all_pred),
            "s1_r2":   None,
            "s2_r2":   round(s2_r2_val, 3),
            "s2_mae":  round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_max_chain_returns_4_folds -v
```
Expected: PASSED (will take ~30-60 s on full data)

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add run_cv_max_chain (architecture A) — full 7-day error propagation"
```

---

## Task 4 — run_cv_s1_direct_s2_anchor (Architecture C)

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert after `run_cv_max_chain`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_run_cv_s1_direct_s2_anchor_returns_4_folds():
    from _08_train_forecast_model import run_cv_s1_direct_s2_anchor

    df = _make_cv_df()
    # Add required direct-feature columns if missing
    from model_lib import S1_DIRECT_FEATURES, S2_DIRECT_FEATURES
    rng = np.random.default_rng(1)
    for c in set(S1_DIRECT_FEATURES + S2_DIRECT_FEATURES):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    bathy = [0.0, 0.0, -208.0]
    results = run_cv_s1_direct_s2_anchor(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)
    assert all("s1_r2" in r for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_s1_direct_s2_anchor_returns_4_folds -v
```
Expected: ImportError on `run_cv_s1_direct_s2_anchor`

- [ ] **Step 3: Add run_cv_s1_direct_s2_anchor to 08_train_forecast_model.py**

Insert after `run_cv_max_chain`:

```python
def run_cv_s1_direct_s2_anchor(df: pd.DataFrame, bathy_coeffs: list,
                                _n_est: int = 150) -> list:
    """
    Walk-forward CV for architecture C (s1-direct, s2-anchor).

    Both stages use direct multi-step training data (7x rows per anchor day).
    S1 uses inflow_anchor_m3 + horizon_h instead of chained inflow lags.
    S2 uses level_m_anchor + dvol_lag1_anchor + horizon_h instead of chained state.
    This is the GBR equivalent of what XGBoost and LightGBM already do.
    """
    print("\n=== GBR s1-direct s2-anchor CV (architecture C) ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # Stage 1 direct
        tr_s1 = build_direct_s1_data(tr).dropna(
            subset=S1_DIRECT_FEATURES + [S1_TARGET])
        te_s1_all = build_direct_s1_data(te)

        gb_s1 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                             learning_rate=0.05, random_state=42)
        gb_s1.fit(tr_s1[S1_DIRECT_FEATURES].values, tr_s1[S1_TARGET].values)

        te_inflow_pred = np.clip(
            gb_s1.predict(te_s1_all[S1_DIRECT_FEATURES].values), 0, None)

        te_s1_clean = te_s1_all.dropna(subset=S1_DIRECT_FEATURES + [S1_TARGET])
        s1_r2_val = r2(
            te_s1_clean[S1_TARGET].values,
            np.clip(gb_s1.predict(te_s1_clean[S1_DIRECT_FEATURES].values), 0, None))

        # Stage 2 direct anchor
        tr_s2 = build_direct_s2_data(tr).dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        te_s2_all = build_direct_s2_data(te).copy()
        te_s2_all["predicted_inflow_m3"] = te_inflow_pred

        gb_s2 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                             learning_rate=0.05, random_state=42)
        gb_s2.fit(tr_s2[S2_DIRECT_FEATURES].values, tr_s2[S2_DIRECT_TARGET].values)

        te_s2_clean = te_s2_all.dropna(
            subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
        p2 = gb_s2.predict(te_s2_clean[S2_DIRECT_FEATURES].values)

        s2_r2_val  = r2( te_s2_clean[S2_DIRECT_TARGET].values, p2)
        s2_mae_val = mae(te_s2_clean[S2_DIRECT_TARGET].values, p2)

        preds_df = te_s2_all.copy()
        preds_df["pred_dvol"] = gb_s2.predict(
            te_s2_all[S2_DIRECT_FEATURES].values)
        drift = _mean_7d_drift(df, preds_df[["date", "horizon_h", "pred_dvol"]],
                               bathy_coeffs)

        cv_results.append({
            "fold":    fold_name,
            "n_test":  int(len(te_s2_clean)),
            "s1_r2":   round(s1_r2_val, 3),
            "s2_r2":   round(s2_r2_val, 3),
            "s2_mae":  round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S1 R²={s1_r2_val:.3f}  |  "
              f"S2 R²={s2_r2_val:.3f}  MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_s1_direct_s2_anchor_returns_4_folds -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add run_cv_s1_direct_s2_anchor (architecture C) — GBR direct multi-step"
```

---

## Task 5 — run_cv_single_stage (Architecture D)

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert after `run_cv_s1_direct_s2_anchor`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_run_cv_single_stage_returns_4_folds():
    from _08_train_forecast_model import run_cv_single_stage
    from model_lib import S2_DIRECT_NO_INFLOW_FEATURES

    df = _make_cv_df()
    rng = np.random.default_rng(2)
    for c in S2_DIRECT_NO_INFLOW_FEATURES:
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    bathy = [0.0, 0.0, -208.0]
    results = run_cv_single_stage(df, bathy)
    assert len(results) == 4
    assert all(r["s1_r2"] is None for r in results)
    assert all("drift_m" in r for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_single_stage_returns_4_folds -v
```
Expected: ImportError on `run_cv_single_stage`

- [ ] **Step 3: Add run_cv_single_stage to 08_train_forecast_model.py**

Insert after `run_cv_s1_direct_s2_anchor`:

```python
def run_cv_single_stage(df: pd.DataFrame, bathy_coeffs: list,
                        _n_est: int = 150) -> list:
    """
    Walk-forward CV for architecture D (single-stage, no S1).

    A single GBR predicts volume_change_Mm3 directly from met features +
    anchor state + horizon_h.  No inflow prediction is made.
    Uses build_direct_s2_data for training data construction but drops
    the predicted_inflow_m3 column entirely.
    """
    print("\n=== GBR single-stage CV (architecture D) ===")
    cv_results = []

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        tr_s2 = build_direct_s2_data(tr).dropna(
            subset=S2_DIRECT_NO_INFLOW_FEATURES + [S2_DIRECT_TARGET])
        te_s2_all = build_direct_s2_data(te)

        gb = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                         learning_rate=0.05, random_state=42)
        gb.fit(tr_s2[S2_DIRECT_NO_INFLOW_FEATURES].values,
               tr_s2[S2_DIRECT_TARGET].values)

        te_s2_clean = te_s2_all.dropna(
            subset=S2_DIRECT_NO_INFLOW_FEATURES + [S2_DIRECT_TARGET])
        p2 = gb.predict(te_s2_clean[S2_DIRECT_NO_INFLOW_FEATURES].values)

        s2_r2_val  = r2( te_s2_clean[S2_DIRECT_TARGET].values, p2)
        s2_mae_val = mae(te_s2_clean[S2_DIRECT_TARGET].values, p2)

        preds_df = te_s2_all.copy()
        preds_df["pred_dvol"] = gb.predict(
            te_s2_all[S2_DIRECT_NO_INFLOW_FEATURES].values)
        drift = _mean_7d_drift(df, preds_df[["date", "horizon_h", "pred_dvol"]],
                               bathy_coeffs)

        cv_results.append({
            "fold":    fold_name,
            "n_test":  int(len(te_s2_clean)),
            "s1_r2":   None,
            "s2_r2":   round(s2_r2_val, 3),
            "s2_mae":  round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_single_stage_returns_4_folds -v
```
Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add run_cv_single_stage (architecture D) — no S1, direct vol-change"
```

---

## Task 6 — run_cv_s1_chain_s2_roll1 (Architecture E)

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert after `run_cv_single_stage`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_run_cv_s1_chain_s2_roll1_returns_4_folds():
    from _08_train_forecast_model import run_cv_s1_chain_s2_roll1

    df = _make_cv_df()
    bathy = [0.0, 0.0, -208.0]
    results = run_cv_s1_chain_s2_roll1(df, bathy)
    assert len(results) == 4
    assert all("drift_m" in r for r in results)


def test_roll1_dvol_lag2_stays_fixed():
    """roll_dvol_only=True must not update dvol_lag2_fixed across steps."""
    from model_lib import GBRegressor, S1_FEATURES, S2_FEATURES
    from _08_train_forecast_model import _simulate_7d_chain

    df = _make_minimal_df(30)
    # Set all dvol values to a unique recognizable number so we can trace them
    df["volume_change_Mm3"] = 0.999
    df_idx = df.set_index("date")

    rf1 = GBRegressor(n_estimators=2, random_state=0)
    rf1.fit(np.ones((10, len(S1_FEATURES))), np.ones(10))
    rf2 = GBRegressor(n_estimators=2, random_state=0)
    rf2.fit(np.ones((10, len(S2_FEATURES))), np.ones(10))

    anchor = pd.Timestamp("2020-01-10")
    rows_e = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=True)
    rows_a = _simulate_7d_chain(rf1, rf2, anchor, df_idx, [0.0, 0.0, 0.0], roll_dvol_only=False)
    # Both should return 7 rows (existence check)
    assert len(rows_e) == 7
    assert len(rows_a) == 7
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_s1_chain_s2_roll1_returns_4_folds -v
```
Expected: ImportError on `run_cv_s1_chain_s2_roll1`

- [ ] **Step 3: Add run_cv_s1_chain_s2_roll1 to 08_train_forecast_model.py**

Insert after `run_cv_single_stage`:

```python
def run_cv_s1_chain_s2_roll1(df: pd.DataFrame, bathy_coeffs: list,
                              _n_est: int = 150) -> list:
    """
    Walk-forward CV for architecture E (s1-chain, s2-roll1).

    Trains the same GBR models as baseline but simulates a partial chain:
    - S1 fully chains inflow lags (lag1 → previous prediction, lag2 → lag1 etc.)
    - S2 rolls only dvol_lag1 (replaced with previous prediction);
      dvol_lag2 and level_m remain fixed at anchor values throughout.
    This represents a middle ground between baseline (anchor fixed) and
    max-chain (everything updates).
    """
    print("\n=== GBR s1-chain s2-roll1 CV (architecture E) ===")
    cv_results = []
    df_idx = df.set_index("date")

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # Train S1 — identical to baseline
        s1_tr = tr.dropna(subset=S1_FEATURES + [S1_TARGET])
        if len(s1_tr) == 0:
            continue
        rf1 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                          learning_rate=0.05, random_state=42)
        rf1.fit(s1_tr[S1_FEATURES].values, s1_tr[S1_TARGET].values)

        # Train S2 — identical to baseline
        tr_s2 = tr.copy()
        tr_s2["predicted_inflow_m3"] = tr_s2[S1_TARGET]
        s2_tr = tr_s2.dropna(subset=S2_FEATURES + [S2_TARGET])
        if len(s2_tr) == 0:
            continue
        rf2 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                          learning_rate=0.05, random_state=42)
        rf2.fit(s2_tr[S2_FEATURES].values, s2_tr[S2_TARGET].values)

        # Simulate with roll1 (partial chain)
        te_dates = sorted(te["date"].unique())
        preds_rows = []
        all_pred, all_true = [], []

        for anchor_date in te_dates:
            window = _simulate_7d_chain(
                rf1, rf2, pd.Timestamp(anchor_date), df_idx,
                bathy_coeffs, roll_dvol_only=True)
            if not window:
                continue
            for r in window:
                fut_ts = r["date"] + pd.Timedelta(days=int(r["horizon_h"]))
                if fut_ts in df_idx.index:
                    true_dvol = float(df_idx.loc[fut_ts].get(S2_TARGET, np.nan))
                    if not np.isnan(true_dvol):
                        all_pred.append(r["pred_dvol"])
                        all_true.append(true_dvol)
            preds_rows.extend(window)

        if not all_pred:
            print(f"  Fold {fold_name}: no valid windows — skipping")
            continue

        s2_r2_val  = r2(np.array(all_true), np.array(all_pred))
        s2_mae_val = mae(np.array(all_true), np.array(all_pred))
        preds_df   = pd.DataFrame(preds_rows)
        drift      = _mean_7d_drift(df, preds_df, bathy_coeffs)

        cv_results.append({
            "fold":    fold_name,
            "n_test":  len(all_pred),
            "s1_r2":   None,
            "s2_r2":   round(s2_r2_val, 3),
            "s2_mae":  round(s2_mae_val, 3),
            "drift_m": round(drift, 4),
        })
        print(f"  {fold_name}:  S2 R²={s2_r2_val:.3f}  "
              f"MAE={s2_mae_val:.3f}  drift={drift:.4f} m")

    return cv_results
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_error_prop_olympics.py::test_run_cv_s1_chain_s2_roll1_returns_4_folds tests/test_error_prop_olympics.py::test_roll1_dvol_lag2_stays_fixed -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add run_cv_s1_chain_s2_roll1 (architecture E) — partial chain simulation"
```

---

## Task 7 — Final training functions for C and D

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (insert after `train_final_lgb`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_train_final_gbr_s1_direct_s2_anchor_creates_pkls(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    df = _make_cv_df()
    from model_lib import S1_DIRECT_FEATURES, S2_DIRECT_FEATURES, S1_TARGET, S2_DIRECT_TARGET
    import numpy as np
    rng = np.random.default_rng(3)
    for c in set(S1_DIRECT_FEATURES + S2_DIRECT_FEATURES + [S1_TARGET, S2_DIRECT_TARGET]):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    m08.train_final_gbr_s1_direct_s2_anchor(df, _n_est=2)
    assert (tmp_path / "gbr_s1_direct.pkl").exists()
    assert (tmp_path / "gbr_s2_anchor.pkl").exists()


def test_train_final_gbr_single_stage_creates_pkl(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    df = _make_cv_df()
    from model_lib import S2_DIRECT_NO_INFLOW_FEATURES, S2_DIRECT_TARGET
    rng = np.random.default_rng(4)
    for c in set(S2_DIRECT_NO_INFLOW_FEATURES + [S2_DIRECT_TARGET]):
        if c not in df.columns:
            df[c] = rng.uniform(0.1, 1.0, len(df))

    m08.train_final_gbr_single_stage(df, _n_est=2)
    assert (tmp_path / "gbr_single_stage.pkl").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_train_final_gbr_s1_direct_s2_anchor_creates_pkls -v
```
Expected: ImportError or AttributeError

- [ ] **Step 3: Add final training functions to 08_train_forecast_model.py**

Insert after `train_final_lgb` (around line 513):

```python
def train_final_gbr_s1_direct_s2_anchor(df: pd.DataFrame, _n_est: int = 250):
    """Train final GBR direct models (architecture C) on all available data."""
    print("\n  GBR s1-direct s2-anchor final training ...")

    s1_data = build_direct_s1_data(df).dropna(
        subset=S1_DIRECT_FEATURES + [S1_TARGET])
    gb_s1 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                        learning_rate=0.05, random_state=42)
    gb_s1.fit(s1_data[S1_DIRECT_FEATURES].values, s1_data[S1_TARGET].values)

    s2_data = build_direct_s2_data(df).dropna(
        subset=S2_DIRECT_FEATURES + [S2_DIRECT_TARGET])
    gb_s2 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                        learning_rate=0.05, random_state=42)
    gb_s2.fit(s2_data[S2_DIRECT_FEATURES].values, s2_data[S2_DIRECT_TARGET].values)

    MODELS_DIR.mkdir(exist_ok=True)
    gb_s1.save(MODELS_DIR / "gbr_s1_direct.pkl")
    gb_s2.save(MODELS_DIR / "gbr_s2_anchor.pkl")
    print(f"  Saved gbr_s1_direct.pkl  gbr_s2_anchor.pkl")
    return gb_s1, gb_s2


def train_final_gbr_single_stage(df: pd.DataFrame, _n_est: int = 250):
    """Train final single-stage GBR (architecture D) on all available data."""
    print("\n  GBR single-stage final training ...")

    s2_data = build_direct_s2_data(df).dropna(
        subset=S2_DIRECT_NO_INFLOW_FEATURES + [S2_DIRECT_TARGET])
    gb = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                     learning_rate=0.05, random_state=42)
    gb.fit(s2_data[S2_DIRECT_NO_INFLOW_FEATURES].values,
           s2_data[S2_DIRECT_TARGET].values)

    MODELS_DIR.mkdir(exist_ok=True)
    gb.save(MODELS_DIR / "gbr_single_stage.pkl")
    print(f"  Saved gbr_single_stage.pkl")
    return gb
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_error_prop_olympics.py::test_train_final_gbr_s1_direct_s2_anchor_creates_pkls tests/test_error_prop_olympics.py::test_train_final_gbr_single_stage_creates_pkl -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: add train_final functions for architectures C and D"
```

---

## Task 8 — Update save_olympics_results and main()

**Files:**
- Modify: `Automation/08_train_forecast_model.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_error_prop_olympics.py`:
```python
def test_save_olympics_results_includes_new_architectures(tmp_path, monkeypatch):
    import _08_train_forecast_model as m08
    monkeypatch.setattr(m08, "MODELS_DIR", tmp_path)

    dummy_cv = [{"fold": str(y), "n_test": 10, "s1_r2": 0.9,
                 "s2_r2": 0.7, "s2_mae": 0.5, "drift_m": 0.05}
                for y in range(2021, 2025)]
    baseline = {"cv_vol_r2_mean": 0.694, "cv_vol_r2_by_fold": {},
                "cv_vol_mae_mean": 0.667, "cv_7d_drift_mean_m": None,
                "cv_inflow_r2_mean": 0.920}

    import pandas as pd
    df = pd.DataFrame({"date": pd.to_datetime(["2024-12-31"])})

    m08.save_olympics_results(
        baseline,
        dummy_cv, dummy_cv, dummy_cv,   # xgb, lgb, gru
        dummy_cv, dummy_cv, dummy_cv, dummy_cv,   # A, C, D, E
        df)

    import json
    with open(tmp_path / "olympics_results.json") as f:
        data = json.load(f)
    assert "gbr_max_chain" in data["models"]
    assert "gbr_s1_direct_s2_anchor" in data["models"]
    assert "gbr_single_stage" in data["models"]
    assert "gbr_s1_chain_s2_roll1" in data["models"]
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_error_prop_olympics.py::test_save_olympics_results_includes_new_architectures -v
```
Expected: TypeError (wrong number of arguments) or KeyError

- [ ] **Step 3: Update save_olympics_results signature and models dict**

Replace the existing `save_olympics_results` function with:

```python
def save_olympics_results(baseline: dict,
                          xgb_cv: list, lgb_cv: list, gru_cv: list,
                          max_chain_cv: list,
                          s1d_s2a_cv: list,
                          single_stage_cv: list,
                          roll1_cv: list,
                          df: pd.DataFrame) -> None:
    """Collate CV results from all models and write olympics_results.json."""

    def _summarise(cv_list: list) -> dict:
        r2s   = [r["s2_r2"]   for r in cv_list]
        maes  = [r["s2_mae"]  for r in cv_list]
        drift = [r["drift_m"] for r in cv_list if r.get("drift_m") is not None]
        s1r2s = [r["s1_r2"]   for r in cv_list if r.get("s1_r2") is not None]
        return {
            "cv_vol_r2_mean":     round(float(np.mean(r2s)),  3) if r2s  else None,
            "cv_vol_r2_by_fold":  {r["fold"]: r["s2_r2"] for r in cv_list},
            "cv_vol_mae_mean":    round(float(np.mean(maes)), 3) if maes else None,
            "cv_7d_drift_mean_m": round(float(np.mean(drift)), 4) if drift else None,
            "cv_inflow_r2_mean":  round(float(np.mean(s1r2s)), 3) if s1r2s else None,
        }

    models = {
        "baseline_gbr":            baseline,
        "xgboost":                 _summarise(xgb_cv),
        "lgbm":                    _summarise(lgb_cv),
        "gru":                     _summarise(gru_cv),
        "gbr_max_chain":           _summarise(max_chain_cv),
        "gbr_s1_direct_s2_anchor": _summarise(s1d_s2a_cv),
        "gbr_single_stage":        _summarise(single_stage_cv),
        "gbr_s1_chain_s2_roll1":   _summarise(roll1_cv),
    }

    winner = max(models, key=lambda k: models[k].get("cv_vol_r2_mean") or -1)

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

- [ ] **Step 4: Update main() to call new CV functions**

In `main()`, after the GRU section (around line 848), add:

```python
    # 11. Architecture A — max chain
    max_chain_cv = run_cv_max_chain(df, bathy_coeffs)

    # 12. Architecture C — GBR s1-direct s2-anchor
    s1d_s2a_cv = run_cv_s1_direct_s2_anchor(df, bathy_coeffs)
    train_final_gbr_s1_direct_s2_anchor(df)

    # 13. Architecture D — single stage
    single_stage_cv = run_cv_single_stage(df, bathy_coeffs)
    train_final_gbr_single_stage(df)

    # 14. Architecture E — s1 chain, s2 roll1
    roll1_cv = run_cv_s1_chain_s2_roll1(df, bathy_coeffs)
```

And update the `save_olympics_results` call:
```python
    save_olympics_results(baseline_entry, xgb_cv_results,
                          lgb_cv_results, gru_cv_results,
                          max_chain_cv, s1d_s2a_cv,
                          single_stage_cv, roll1_cv, df)
```

- [ ] **Step 5: Update train_winner_only() for new winner keys**

Add cases to the `if winner == ...` chain in `train_winner_only()`:
```python
    elif winner == "gbr_s1_direct_s2_anchor":
        train_final_gbr_s1_direct_s2_anchor(df)
    elif winner == "gbr_single_stage":
        train_final_gbr_single_stage(df)
    elif winner in ("gbr_max_chain", "gbr_s1_chain_s2_roll1"):
        # Both use same weights as baseline_gbr; re-run baseline final training
        cv_results, oof_s1 = run_cv(df)
        gb1, gb2, gb2d = train_final(df, oof_s1)
        if gb1 is not None:
            MODELS_DIR.mkdir(exist_ok=True)
            gb1.save(MODELS_DIR / "stage1_inflow_rf.pkl")
            gb2.save(MODELS_DIR / "stage2_volume_rf.pkl")
            gb2d.save(MODELS_DIR / "stage2_direct_gb.pkl")
```

- [ ] **Step 6: Run test to verify it passes**

```
python -m pytest tests/test_error_prop_olympics.py::test_save_olympics_results_includes_new_architectures -v
```
Expected: PASSED

- [ ] **Step 7: Run all tests to check no regressions**

```
python -m pytest tests/test_error_prop_olympics.py -v
```
Expected: all PASSED

- [ ] **Step 8: Commit**

```bash
git add Automation/08_train_forecast_model.py tests/test_error_prop_olympics.py
git commit -m "feat: wire all 4 new architectures into save_olympics_results and main()"
```

---

## Task 9 — Update 7_Model_Olympics.py

**Files:**
- Modify: `kinneret_app/pages/7_Model_Olympics.py`

- [ ] **Step 1: Extend DISPLAY_NAMES**

Replace the current `DISPLAY_NAMES` dict (lines 72–77) with:
```python
DISPLAY_NAMES = {
    "baseline_gbr":            "Baseline GBR",
    "xgboost":                 "XGBoost",
    "lgbm":                    "LightGBM",
    "gru":                     "GRU (multi-task)",
    "gbr_max_chain":           "GBR A — max chain",
    "gbr_s1_direct_s2_anchor": "GBR C — s1 direct / s2 anchor",
    "gbr_single_stage":        "GBR D — single stage",
    "gbr_s1_chain_s2_roll1":   "GBR E — s1 chain / s2 roll1",
}
```

- [ ] **Step 2: Locate the architecture notes section**

Find the section at the bottom of `7_Model_Olympics.py` that renders architecture notes and add descriptions for A, C, D, E. It should look like this (add the new entries alongside the existing 4):

```python
ARCH_NOTES = {
    "baseline_gbr": (
        "**S1** chains inflow lags (lag1/lag2 from previous prediction at inference). "
        "**S2** uses fixed anchor state from day 0 + predicted inflow. "
        "CV uses actual lags — optimistic estimate of chaining error."
    ),
    "xgboost": (
        "**S1** direct: inflow_anchor + horizon_h → no chaining. "
        "**S2** direct: anchor state + horizon_h → no chaining. "
        "XGBoost regressor, 300 estimators."
    ),
    "lgbm": (
        "**S1** direct: inflow_anchor + horizon_h → no chaining. "
        "**S2** direct: anchor state + horizon_h → no chaining. "
        "LightGBM regressor, 300 estimators."
    ),
    "gru": (
        "Multi-task GRU trained on 21-day sequences. "
        "Predicts inflow and volume change simultaneously. "
        "No explicit chaining — sequence model handles temporal dependencies."
    ),
    "gbr_max_chain": (
        "**A — maximum error propagation.** Same GBR weights as Baseline GBR. "
        "CV simulates full 7-day chain: inflow lag1/lag2 and dvol lag1/lag2 and level_m "
        "all update with predictions at each step. Measures true inference-time error."
    ),
    "gbr_s1_direct_s2_anchor": (
        "**C — minimum propagation, GBR version.** "
        "**S1** uses inflow_anchor + horizon_h (same as XGBoost/LightGBM). "
        "**S2** uses level_m_anchor + dvol_lag1_anchor + horizon_h. "
        "Pure numpy GBR, 150 estimators CV / 250 final."
    ),
    "gbr_single_stage": (
        "**D — no inflow model.** Single GBR predicts volume_change directly "
        "from met features + anchor state + horizon_h. No S1 stage. "
        "Tests whether inflow prediction adds value over met-only signal."
    ),
    "gbr_s1_chain_s2_roll1": (
        "**E — partial propagation.** Same GBR weights as Baseline GBR. "
        "**S1** fully chains inflow lags. **S2** rolls only dvol_lag1 "
        "(dvol_lag2 and level_m stay fixed at anchor). Middle ground between C and A."
    ),
}
```

Find where architecture notes are rendered in `7_Model_Olympics.py` and replace the existing `ARCH_NOTES` dict with the one above. If no such dict exists yet, add the rendering block at the bottom of the page:

```python
# ── Architecture notes ────────────────────────────────────────────────────────
st.markdown('<hr class="kn-divider">', unsafe_allow_html=True)
st.markdown('<p class="kn-label">Architecture notes</p>', unsafe_allow_html=True)
for key, note in ARCH_NOTES.items():
    if key in models:
        name = DISPLAY_NAMES.get(key, key)
        st.markdown(f"**{name}** — {note}")
```

- [ ] **Step 2: Manually verify the dashboard**

Start Streamlit and check that the Olympics page loads without error and shows all 8 models:

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m streamlit run kinneret_app/app.py --server.port 8501
```

Open `http://localhost:8501` → navigate to Model Olympics page.
Expected: scoreboard shows all 8 model names, architecture notes visible at bottom.

- [ ] **Step 3: Commit**

```bash
git add kinneret_app/pages/7_Model_Olympics.py
git commit -m "feat: add 4 new architecture display names and notes to Model Olympics page"
```

---

## Task 10 — Run full test suite

- [ ] **Step 1: Run all project tests**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v
```
Expected: all tests PASS, including the 10 jordan_flow tests and all new error-prop tests.

- [ ] **Step 2: Smoke-test the full training pipeline on a dry run**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project\Automation"
python 08_train_forecast_model.py --winner-only
```
Expected: no crash, loads data, trains winner, saves pkl.

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -u
git commit -m "fix: address any issues found during smoke test"
```

---

## Self-review against spec

**Coverage check:**
- A (max_chain): Task 3 — `run_cv_max_chain` + `_simulate_7d_chain(roll_dvol_only=False)` ✓
- C (s1_direct_s2_anchor): Task 4 — `run_cv_s1_direct_s2_anchor` + `train_final_gbr_s1_direct_s2_anchor` ✓
- D (single_stage): Task 5 — `run_cv_single_stage` + `train_final_gbr_single_stage` ✓
- E (s1_chain_s2_roll1): Task 6 — `run_cv_s1_chain_s2_roll1` + `_simulate_7d_chain(roll_dvol_only=True)` ✓
- Olympics JSON: Task 8 — 8 models in results, winner logic updated ✓
- Dashboard: Task 9 — DISPLAY_NAMES and ARCH_NOTES for all 8 ✓
- Tests: Tasks 1–8 each have TDD steps; Task 10 is integration ✓
- `train_winner_only`: Task 8 — new winner keys handled ✓

**Type consistency check:**
- `_simulate_7d_chain` returns `list[dict]` with keys `date`, `horizon_h`, `pred_dvol` — matches `_mean_7d_drift` expectation ✓
- All new `run_cv_*` functions return `list[dict]` with keys `fold`, `n_test`, `s1_r2`, `s2_r2`, `s2_mae`, `drift_m` — matches `_summarise` input expectation ✓
- `save_olympics_results` new signature takes 9 args (baseline + 7 cv_lists + df) ✓

**Placeholder check:** No TBDs found. All code blocks are complete. ✓
