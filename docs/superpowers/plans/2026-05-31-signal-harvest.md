# Signal Harvest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply all six diagnostic findings from "Meteo Models Expert Notes.md" directly into the baseline GBR pipeline — no Olympic-style experiments, just straight improvements to the deployed model.

**Architecture:** The deployed model uses `S1_FEATURES` (chained inflow lags) → `stage1_inflow_rf.pkl` and `S2_DIRECT_FEATURES` (anchor state + horizon) → `stage2_direct_gb.pkl`. All six findings are implemented as changes to these feature lists, the training loop, and the inference script. No new model architectures are added.

**Tech Stack:** Python 3.x, numpy, pandas, `Automation/model_lib.py`, `Automation/08_train_forecast_model.py`, `Automation/09_weekly_forecast.py`, pytest (tests in `tests/`)

**Findings being implemented:**
- Finding 1 — Apply `signed_log1p_transform` to S2 target (already defined, never called)
- Finding 2 — Add `outflow_lag1_m3` to S2 features (corr=0.606 with dvol, 92.4% fill)
- Finding 3 — Add `dvol_lag2_anchor` + `dvol_lag3_anchor` to S2 features (autocorr 0.67, 0.61)
- Finding 4 — Add `rbf_*` seasonality to both S1 and S2 features (already in gold table)
- Finding 5 — Add `precip_intensity_mm_hr` to both S1 and S2 (corr=0.31, 99.3% fill)
- Finding 6 — Tune GBR hyperparameters: n_estimators 150→300 (CV), 250→500 (final); lr 0.05→0.03

---

## File Map

| File | What changes |
|------|-------------|
| `Automation/model_lib.py` | Add 5 features to `S1_FEATURES`; add 5 features to `S2_MET_FEATURES`; add `outflow_lag1_m3`, `dvol_lag2_anchor`, `dvol_lag3_anchor` to `S2_DIRECT_FEATURES`; add same 5 to `S1_DIRECT_FEATURES` |
| `Automation/08_train_forecast_model.py` | Add `GBR_CV_PARAMS`/`GBR_FINAL_PARAMS` constants; apply `signed_log1p_transform` in `run_cv()` and `train_final()`; add 3 new columns in `build_direct_s2_data()`; update `metadata["target_transforms"]`; update `_make_cv_df()` helper |
| `Automation/09_weekly_forecast.py` | Import `inv_signed_log1p_transform`; load 3 new anchor values from history in `run_forecast()`; apply inverse transform after S2 `predict()` |
| `tests/test_signal_harvest.py` | New test file covering all planned changes |

---

## Task 1: Feature list + anchor data (Findings 2, 3, 4, 5)

These four findings are coupled: the feature lists (model_lib.py) and the data builder (08_train_forecast_model.py) must be updated atomically so the named features actually exist in the training rows.

**Files:**
- Modify: `Automation/model_lib.py:36-135`
- Modify: `Automation/08_train_forecast_model.py:76-108` (build_direct_s2_data)
- Create: `tests/test_signal_harvest.py`

- [ ] **Step 1.1: Write failing tests**

Create `tests/test_signal_harvest.py`:

```python
# tests/test_signal_harvest.py
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


# ── Feature list membership ──────────────────────────────────────────────────

def test_rbf_features_in_s1_features():
    from model_lib import S1_FEATURES
    for f in ["rbf_spring_equinox", "rbf_summer_solstice",
              "rbf_autumn_equinox", "rbf_winter_solstice"]:
        assert f in S1_FEATURES, f"{f} missing from S1_FEATURES"


def test_precip_intensity_in_s1_features():
    from model_lib import S1_FEATURES
    assert "precip_intensity_mm_hr" in S1_FEATURES


def test_rbf_features_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    for f in ["rbf_spring_equinox", "rbf_summer_solstice",
              "rbf_autumn_equinox", "rbf_winter_solstice"]:
        assert f in S2_DIRECT_FEATURES, f"{f} missing from S2_DIRECT_FEATURES"


def test_precip_intensity_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "precip_intensity_mm_hr" in S2_DIRECT_FEATURES


def test_outflow_lag1_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "outflow_lag1_m3" in S2_DIRECT_FEATURES


def test_dvol_lag2_anchor_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "dvol_lag2_anchor" in S2_DIRECT_FEATURES


def test_dvol_lag3_anchor_in_s2_direct_features():
    from model_lib import S2_DIRECT_FEATURES
    assert "dvol_lag3_anchor" in S2_DIRECT_FEATURES


def test_s2_direct_no_inflow_still_subset():
    from model_lib import S2_DIRECT_FEATURES, S2_DIRECT_NO_INFLOW_FEATURES
    assert set(S2_DIRECT_NO_INFLOW_FEATURES) < set(S2_DIRECT_FEATURES)
    assert len(S2_DIRECT_NO_INFLOW_FEATURES) == len(S2_DIRECT_FEATURES) - 1


# ── build_direct_s2_data produces new anchor columns ─────────────────────────

def _make_s2_df(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "date":                pd.date_range("2020-01-01", periods=n),
        "inflow_obstacle_m3":  rng.uniform(1e5, 1e6, n),
        "volume_change_Mm3":   rng.uniform(-1.0, 1.0, n),
        "outflow_baptism_m3":  rng.uniform(0.1, 0.5, n),
        "level_m":             rng.uniform(-214, -208, n),
        **{c: rng.uniform(0.0, 1.0, n) for c in [
            "rainfall_mm", "rainfall_7d_mm", "rainfall_21d_mm",
            "temp_mean_C", "temp_max_C", "humidity_pct",
            "wind_speed_ms", "vpd_kPa", "et0_mm", "et0_7d_mm",
            "radiation_MJm2", "season_sin", "season_cos", "daylength_hrs",
            "rbf_spring_equinox", "rbf_summer_solstice",
            "rbf_autumn_equinox", "rbf_winter_solstice",
            "precip_intensity_mm_hr",
        ]},
    })


def test_build_direct_s2_data_has_outflow_lag1():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "outflow_lag1_m3" in result.columns


def test_build_direct_s2_data_has_dvol_lag2_anchor():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "dvol_lag2_anchor" in result.columns


def test_build_direct_s2_data_has_dvol_lag3_anchor():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    result = m.build_direct_s2_data(_make_s2_df())
    assert "dvol_lag3_anchor" in result.columns


def test_outflow_lag1_is_shifted_by_one():
    """outflow_lag1_m3 at each anchor row t must equal outflow_baptism_m3 at t-1."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_08", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    df = _make_s2_df(20)
    result = m.build_direct_s2_data(df)
    # For anchor row at index 2 (date 2020-01-03) and horizon h=1:
    anchor_idx = 2
    h1_rows = result[result["date"] == df["date"].iloc[anchor_idx]]
    expected_outflow = df["outflow_baptism_m3"].shift(1).iloc[anchor_idx]
    actual_outflow = h1_rows["outflow_lag1_m3"].iloc[0]
    np.testing.assert_almost_equal(actual_outflow, expected_outflow)
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py -v 2>&1 | head -60
```

Expected: all tests FAIL with `AssertionError` (features not yet in lists, columns not yet in data).

- [ ] **Step 1.3: Update S1_FEATURES in model_lib.py**

In `Automation/model_lib.py` at line ~59 (end of `S1_FEATURES` list, before the closing `]`), add after `"season_cos"`:

```python
    # RBF seasonality (localised seasonal bumps — wet-season onset vs. summer peak)
    "rbf_spring_equinox",
    "rbf_summer_solstice",
    "rbf_autumn_equinox",
    "rbf_winter_solstice",
    # Precipitation intensity (flash-flood signal; imputed at inference, 99.3% fill)
    "precip_intensity_mm_hr",
```

Result: S1_FEATURES grows from 18 → 23 entries.

- [ ] **Step 1.4: Update S2_MET_FEATURES in model_lib.py**

At line ~102 (end of `S2_MET_FEATURES` list, before the closing `]`), add after `"daylength_hrs"`:

```python
    # RBF seasonality
    "rbf_spring_equinox",
    "rbf_summer_solstice",
    "rbf_autumn_equinox",
    "rbf_winter_solstice",
    # Precipitation intensity
    "precip_intensity_mm_hr",
```

Result: S2_MET_FEATURES grows from 12 → 17. S2_DIRECT_FEATURES automatically grows from 15 → 20 (since `S2_DIRECT_FEATURES = S2_MET_FEATURES + [...]`).

- [ ] **Step 1.5: Add anchor features to S2_DIRECT_FEATURES in model_lib.py**

At line ~105, change the `S2_DIRECT_FEATURES` definition from:

```python
S2_DIRECT_FEATURES = S2_MET_FEATURES + [
    "level_m_anchor",       # actual level at anchor day
    "dvol_lag1_anchor",     # actual volume change at anchor day (lag1 for day 1)
    "horizon_h",            # 1 … 7 (which day of the forecast week)
]
```

to:

```python
S2_DIRECT_FEATURES = S2_MET_FEATURES + [
    "level_m_anchor",       # actual level at anchor day
    "dvol_lag1_anchor",     # actual volume change at anchor day (lag1 for day 1)
    "dvol_lag2_anchor",     # volume change at anchor-1 day (autocorr=0.67)
    "dvol_lag3_anchor",     # volume change at anchor-2 day (autocorr=0.61)
    "outflow_lag1_m3",      # yesterday's pump outflow (corr=0.606 with dvol, 92.4% fill)
    "horizon_h",            # 1 … 7 (which day of the forecast week)
]
```

Result: S2_DIRECT_FEATURES grows from 20 → 23.

- [ ] **Step 1.6: Update S1_DIRECT_FEATURES in model_lib.py**

At line ~133 (end of `S1_DIRECT_FEATURES`, before closing `]`), add after `"season_cos"`:

```python
    # RBF seasonality
    "rbf_spring_equinox",
    "rbf_summer_solstice",
    "rbf_autumn_equinox",
    "rbf_winter_solstice",
    # Precipitation intensity
    "precip_intensity_mm_hr",
```

Result: S1_DIRECT_FEATURES grows from 18 → 23.

- [ ] **Step 1.7: Update S2_FEATURES in model_lib.py (chained path, used in run_cv)**

At line ~86 (end of `S2_FEATURES`, before closing `]`), add after `"daylength_hrs"` and before the lake-state block:

```python
    # RBF seasonality
    "rbf_spring_equinox",
    "rbf_summer_solstice",
    "rbf_autumn_equinox",
    "rbf_winter_solstice",
    # Precipitation intensity
    "precip_intensity_mm_hr",
```

Result: S2_FEATURES grows from 17 → 22.

- [ ] **Step 1.8: Update build_direct_s2_data() in 08_train_forecast_model.py**

Find the block that sets `p["dvol_lag1_anchor"]` (around line 104) and add three lines after it:

```python
        p["dvol_lag1_anchor"] = df["volume_change_Mm3"]   # dvol at anchor = lag1 for h=1
        p["dvol_lag2_anchor"] = df["volume_change_Mm3"].shift(1)  # anchor-1 day
        p["dvol_lag3_anchor"] = df["volume_change_Mm3"].shift(2)  # anchor-2 day
        p["outflow_lag1_m3"]  = df["outflow_baptism_m3"].shift(1)  # yesterday's outflow
        p["horizon_h"]        = float(h)
```

- [ ] **Step 1.9: Update _make_cv_df() test helper in test_error_prop_olympics.py**

Find `_make_cv_df()` (around line 80) and add `"outflow_baptism_m3"` to the extra columns list:

```python
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET,
        "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
        "outflow_baptism_m3",     # required by build_direct_s2_data()
    ]))
```

Also update `_make_minimal_df()` (around line 26) the same way:

```python
    cols = list(set(S1_FEATURES + S2_FEATURES + [
        S1_TARGET, S2_TARGET,
        "volume_Mm3", "predicted_inflow_m3",
        "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
        "level_m", "volume_change_Mm3",
        "outflow_baptism_m3",
    ]))
```

- [ ] **Step 1.10: Run all tests to confirm signal harvest tests pass and no regressions**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py tests/test_error_prop_olympics.py -v 2>&1 | tail -30
```

Expected: all `test_signal_harvest.py` tests PASS; all `test_error_prop_olympics.py` tests PASS.

- [ ] **Step 1.11: Commit**

```
git add Automation/model_lib.py Automation/08_train_forecast_model.py tests/test_signal_harvest.py tests/test_error_prop_olympics.py
git commit -m "feat: add RBF, precip_intensity, outflow/dvol anchors to feature lists (Findings 2-5)"
```

---

## Task 2: Apply signed_log1p_transform to S2 target (Finding 1)

The functions `signed_log1p_transform` and `inv_signed_log1p_transform` already exist in `model_lib.py` but are never used in `run_cv` or `train_final`. This task wires them in.

**Files:**
- Modify: `Automation/08_train_forecast_model.py:319-395` (run_cv), `:989-1025` (train_final)
- Modify: `Automation/09_weekly_forecast.py:33-38` (imports), `:259` (predict call)
- Modify: `tests/test_signal_harvest.py` (add tests)

- [ ] **Step 2.1: Add transform tests to test_signal_harvest.py**

Append to `tests/test_signal_harvest.py`:

```python
# ── signed_log1p_transform applied in run_cv ─────────────────────────────────

def test_run_cv_s2_predictions_not_in_log_space():
    """
    After the transform fix, predicted values from run_cv must be in Mm³ space
    (order of magnitude ~1), NOT log space (which would be ~0.0–3.0).
    We verify by checking that MAE is in a physically plausible range.
    """
    from model_lib import (
        S1_FEATURES, S2_FEATURES, S1_DIRECT_FEATURES, S2_DIRECT_FEATURES,
        S1_TARGET, S2_TARGET,
    )
    spec = importlib.util.spec_from_file_location(
        "_08b", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

    rng = np.random.default_rng(42)
    dates = pd.date_range("2012-01-01", "2024-12-31", freq="D")
    n = len(dates)
    all_cols = list(set(
        S1_FEATURES + S2_FEATURES + S1_DIRECT_FEATURES + S2_DIRECT_FEATURES + [
            S1_TARGET, S2_TARGET, "volume_Mm3", "predicted_inflow_m3",
            "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
            "level_m", "volume_change_Mm3", "outflow_baptism_m3",
        ]
    ))
    df = pd.DataFrame({"date": dates, **{c: rng.uniform(0.0, 1.0, n) for c in all_cols}})
    # S2_TARGET has correct scale: volume change in Mm³ (−5 to +5)
    df[S2_TARGET] = rng.uniform(-3.0, 3.0, n)

    cv_results, _ = m.run_cv(df)
    assert len(cv_results) == 4
    for r in cv_results:
        # MAE in Mm³ should be < 10 (would be ~0.01–3 range, not 100s which log-space would give)
        assert r["s2_mae_Mm3"] < 10.0, f"MAE={r['s2_mae_Mm3']} looks like log-space leak"


def test_train_final_writes_transform_to_metadata(tmp_path, monkeypatch):
    """model_metadata.json must record s2 target_transform = signed_log1p."""
    from model_lib import (
        S1_FEATURES, S2_FEATURES, S1_DIRECT_FEATURES, S2_DIRECT_FEATURES,
        S1_TARGET, S2_TARGET,
    )
    spec = importlib.util.spec_from_file_location(
        "_08c", Path(__file__).parent.parent / "Automation" / "08_train_forecast_model.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    monkeypatch.setattr(m, "MODELS_DIR", tmp_path)

    rng = np.random.default_rng(1)
    dates = pd.date_range("2012-01-01", "2024-12-31", freq="D")
    n = len(dates)
    all_cols = list(set(
        S1_FEATURES + S2_FEATURES + S1_DIRECT_FEATURES + S2_DIRECT_FEATURES + [
            S1_TARGET, S2_TARGET, "volume_Mm3", "predicted_inflow_m3",
            "rainfall_lag1_mm", "rainfall_lag2_mm", "rainfall_lag3_mm",
            "level_m", "volume_change_Mm3", "outflow_baptism_m3",
        ]
    ))
    df = pd.DataFrame({"date": dates, **{c: rng.uniform(0.1, 1.0, n) for c in all_cols}})

    oof = pd.Series(rng.uniform(0.1, 1.0, n), index=df.index)
    m.train_final(df, oof)

    import json
    meta = json.loads((tmp_path / "model_metadata.json").read_text())
    assert meta["target_transforms"]["s2"] == "signed_log1p"
```

- [ ] **Step 2.2: Run new tests to confirm they fail**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py::test_train_final_writes_transform_to_metadata -v
```

Expected: FAIL (`s2` is `"none"` in current metadata).

- [ ] **Step 2.3: Apply transform in run_cv() — S2 fit and predict**

In `Automation/08_train_forecast_model.py`, find `run_cv()` (line ~372–375) where Stage 2 is fitted:

Replace:
```python
        rf2 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
        rf2.fit(s2_tr[S2_FEATURES].values, s2_tr[S2_TARGET].values)
        p2 = rf2.predict(s2_te[S2_FEATURES].values)
```

With:
```python
        rf2 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
        rf2.fit(s2_tr[S2_FEATURES].values,
                signed_log1p_transform(s2_tr[S2_TARGET].values))
        p2 = inv_signed_log1p_transform(rf2.predict(s2_te[S2_FEATURES].values))
```

- [ ] **Step 2.4: Apply transform in train_final() — gb2 and gb2d**

In `train_final()` (line ~1001–1024):

For `gb2` (chained Stage 2), change:
```python
    gb2.fit(s2_data[S2_FEATURES].values, s2_data[S2_TARGET].values,
            feature_names=S2_FEATURES)
```
to:
```python
    gb2.fit(s2_data[S2_FEATURES].values,
            signed_log1p_transform(s2_data[S2_TARGET].values),
            feature_names=S2_FEATURES)
```

For `gb2d` (direct Stage 2), change:
```python
    gb2d.fit(direct_data[S2_DIRECT_FEATURES].values, direct_data[S2_DIRECT_TARGET].values,
             feature_names=S2_DIRECT_FEATURES)
```
to:
```python
    gb2d.fit(direct_data[S2_DIRECT_FEATURES].values,
             signed_log1p_transform(direct_data[S2_DIRECT_TARGET].values),
             feature_names=S2_DIRECT_FEATURES)
```

- [ ] **Step 2.5: Update metadata target_transforms in main()**

Find in `main()` (line ~1224):
```python
        "target_transforms": {"s1": "none", "s2": "none"},
```
Change to:
```python
        "target_transforms": {"s1": "none", "s2": "signed_log1p"},
```

- [ ] **Step 2.6: Apply inverse transform in 09_weekly_forecast.py**

Add `inv_signed_log1p_transform` to the import in `09_weekly_forecast.py` (line ~33):

```python
from model_lib import (
    GBRegressor,
    S1_FEATURES,
    S2_DIRECT_FEATURES,
    enrich_forecast_df,
    inv_signed_log1p_transform,
)
```

Find the S2 predict call in `run_forecast()` (line ~259):
```python
        pred_dvol = float(gb2_direct.predict(s2_x)[0])
```
Replace with:
```python
        pred_dvol = float(inv_signed_log1p_transform(gb2_direct.predict(s2_x))[0])
```

- [ ] **Step 2.7: Run tests**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py -v -k "transform" 2>&1 | tail -20
```

Expected: all transform tests PASS.

- [ ] **Step 2.8: Run full test suite (no regressions)**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 2.9: Commit**

```
git add Automation/08_train_forecast_model.py Automation/09_weekly_forecast.py tests/test_signal_harvest.py
git commit -m "feat: apply signed_log1p_transform to S2 target in run_cv and train_final (Finding 1)"
```

---

## Task 3: Inject new anchor state at inference time (Findings 2, 3)

The training data now has `outflow_lag1_m3`, `dvol_lag2_anchor`, `dvol_lag3_anchor` (from Task 1). The inference script must load these from history at forecast time and inject them as fixed anchor values.

**Files:**
- Modify: `Automation/09_weekly_forecast.py:198-260` (run_forecast)
- Modify: `tests/test_signal_harvest.py` (add inference test)

- [ ] **Step 3.1: Add inference anchor test to test_signal_harvest.py**

Append to `tests/test_signal_harvest.py`:

```python
# ── Inference anchor injection ────────────────────────────────────────────────

def test_run_forecast_injects_new_anchors(tmp_path, monkeypatch):
    """run_forecast must pass outflow_lag1, dvol_lag2/lag3 to S2 model."""
    import importlib.util, json
    sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))
    spec09 = importlib.util.spec_from_file_location(
        "_09", Path(__file__).parent.parent / "Automation" / "09_weekly_forecast.py")
    m09 = importlib.util.module_from_spec(spec09); spec09.loader.exec_module(m09)

    from model_lib import S2_DIRECT_FEATURES

    captured_s2_rows = []

    class SpyGBR:
        median_ = np.zeros(len(S2_DIRECT_FEATURES))
        def predict(self, X):
            captured_s2_rows.append(X.copy())
            return np.zeros(len(X))

    class DummyS1GBR:
        median_ = np.zeros(1)
        def predict(self, X): return np.ones(len(X)) * 1e5

    # Minimal meta with bathy poly and feature lists
    meta = {
        "bathy_vol2level_coeffs": [0.0, 0.0, -208.0],
        "cv_s2_mean_r2": 0.7,
        "cv_s2_mean_mae": 0.5,
        "trained_through": "2024-12-31",
    }

    rng = np.random.default_rng(7)
    hist_dates = pd.date_range("2024-01-01", periods=25)
    history = pd.DataFrame({
        "date":                 hist_dates,
        "level_m":              rng.uniform(-214, -208, 25),
        "volume_Mm3":           rng.uniform(2000, 4200, 25),
        "volume_change_Mm3":    rng.uniform(-1.0, 1.0, 25),
        "outflow_baptism_m3":   rng.uniform(0.2e6, 0.6e6, 25),
        "inflow_obstacle_m3":   rng.uniform(1e5, 1e6, 25),
        "et0_mm":               rng.uniform(2, 8, 25),
        "rainfall_mm":          rng.uniform(0, 5, 25),
        **{c: rng.uniform(0.0, 1.0, 25) for c in [
            "temp_max_C", "temp_min_C", "humidity_pct",
            "wind_speed_ms", "radiation_MJm2",
            "rainfall_7d_mm", "rainfall_21d_mm",
        ]},
    })

    fc_dates = pd.date_range("2024-01-26", periods=7)
    forecast = pd.DataFrame({
        "date":           fc_dates,
        "temp_max_C":     rng.uniform(15, 25, 7),
        "temp_min_C":     rng.uniform(5, 15, 7),
        "rainfall_mm":    rng.uniform(0, 3, 7),
        "humidity_pct":   rng.uniform(40, 80, 7),
        "wind_speed_ms":  rng.uniform(2, 8, 7),
        "radiation_MJm2": rng.uniform(10, 25, 7),
    })

    m09.run_forecast(forecast, history, DummyS1GBR(), SpyGBR(), meta)

    assert len(captured_s2_rows) == 7, "Expected 7 S2 predict calls"
    feat_idx = {f: i for i, f in enumerate(S2_DIRECT_FEATURES)}

    # Verify outflow_lag1_m3 is consistently the same anchor value for all 7 days
    outflow_idx = feat_idx.get("outflow_lag1_m3")
    assert outflow_idx is not None, "outflow_lag1_m3 not in S2_DIRECT_FEATURES"
    outflow_vals = [float(row[0, outflow_idx]) for row in captured_s2_rows]
    assert len(set(outflow_vals)) == 1, "outflow_lag1_m3 must be constant (anchor)"
    assert not np.isnan(outflow_vals[0]), "outflow_lag1_m3 anchor must not be NaN"

    # Verify dvol_lag2_anchor and dvol_lag3_anchor are present and constant
    for col in ["dvol_lag2_anchor", "dvol_lag3_anchor"]:
        idx = feat_idx.get(col)
        assert idx is not None, f"{col} not in S2_DIRECT_FEATURES"
        vals = [float(row[0, idx]) for row in captured_s2_rows]
        assert len(set(vals)) == 1, f"{col} must be constant (anchor)"
```

- [ ] **Step 3.2: Run to confirm test fails**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py::test_run_forecast_injects_new_anchors -v
```

Expected: FAIL (new anchors not yet injected at inference).

- [ ] **Step 3.3: Update run_forecast() to load and inject new anchors**

In `Automation/09_weekly_forecast.py`, find the anchor state block (around line 225–234):

```python
    hist_dvol = (history_df.dropna(subset=["volume_change_Mm3"])
                 if "volume_change_Mm3" in history_df.columns else pd.DataFrame())
    if len(hist_dvol) >= 1:
        anchor_dvol = float(hist_dvol.iloc[-1]["volume_change_Mm3"])
    else:
        anchor_dvol = np.nan

    anchor_level = current_level   # fixed for the whole week
```

Replace with:

```python
    hist_dvol = (history_df.dropna(subset=["volume_change_Mm3"])
                 if "volume_change_Mm3" in history_df.columns else pd.DataFrame())
    anchor_dvol      = float(hist_dvol.iloc[-1]["volume_change_Mm3"]) if len(hist_dvol) >= 1 else np.nan
    anchor_dvol_lag2 = float(hist_dvol.iloc[-2]["volume_change_Mm3"]) if len(hist_dvol) >= 2 else np.nan
    anchor_dvol_lag3 = float(hist_dvol.iloc[-3]["volume_change_Mm3"]) if len(hist_dvol) >= 3 else np.nan

    hist_outflow = (history_df.dropna(subset=["outflow_baptism_m3"])
                    if "outflow_baptism_m3" in history_df.columns else pd.DataFrame())
    outflow_lag1_anchor = float(hist_outflow.iloc[-1]["outflow_baptism_m3"]) if len(hist_outflow) >= 1 else np.nan

    anchor_level = current_level   # fixed for the whole week
```

- [ ] **Step 3.4: Update the print statement to show new anchor values**

Find the print after anchor state:
```python
    print(f"  Anchor state:  level_m_anchor = {anchor_level:+.3f} m  |  "
          f"dvol_lag1_anchor = {anchor_dvol:+.4f} Mm³")
```
Replace with:
```python
    print(f"  Anchor state:  level_m_anchor={anchor_level:+.3f} m  "
          f"dvol_lag1={anchor_dvol:+.4f}  dvol_lag2={anchor_dvol_lag2:+.4f}  "
          f"dvol_lag3={anchor_dvol_lag3:+.4f} Mm³  "
          f"outflow_lag1={outflow_lag1_anchor/1e6:.3f} Mm³")
```

- [ ] **Step 3.5: Inject new anchors into s2_vals in the forecast loop**

Find the anchor injection block (around line 254–258):
```python
        s2_vals["predicted_inflow_m3"] = pred_inflow
        s2_vals["level_m_anchor"]      = anchor_level   # fixed (day 0)
        s2_vals["dvol_lag1_anchor"]    = anchor_dvol    # fixed (day 0)
        s2_vals["horizon_h"]           = float(horizon)
```

Replace with:
```python
        s2_vals["predicted_inflow_m3"] = pred_inflow
        s2_vals["level_m_anchor"]      = anchor_level        # fixed (day 0)
        s2_vals["dvol_lag1_anchor"]    = anchor_dvol         # fixed (day 0)
        s2_vals["dvol_lag2_anchor"]    = anchor_dvol_lag2    # fixed (day 0)
        s2_vals["dvol_lag3_anchor"]    = anchor_dvol_lag3    # fixed (day 0)
        s2_vals["outflow_lag1_m3"]     = outflow_lag1_anchor # fixed (day 0)
        s2_vals["horizon_h"]           = float(horizon)
```

- [ ] **Step 3.6: Run inference anchor test**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_signal_harvest.py::test_run_forecast_injects_new_anchors -v
```

Expected: PASS.

- [ ] **Step 3.7: Run full test suite**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS.

- [ ] **Step 3.8: Commit**

```
git add Automation/09_weekly_forecast.py tests/test_signal_harvest.py
git commit -m "feat: inject outflow_lag1 and dvol_lag2/lag3 anchors in forecast inference (Findings 2, 3)"
```

---

## Task 4: Hyperparameter tuning (Finding 6)

Replace hardcoded GBR hyperparameters with named constants and tune them: n_estimators 150→300 (CV), 250→500 (final); learning_rate 0.05→0.03.

**Files:**
- Modify: `Automation/08_train_forecast_model.py` (multiple call sites)

- [ ] **Step 4.1: Add GBR_CV_PARAMS and GBR_FINAL_PARAMS constants near the top of 08_train_forecast_model.py**

After the imports (around line 42), add:

```python
# ─────────────────────────────────────────────────────────────────────────────
# GBR hyperparameter constants  (single source of truth)
# ─────────────────────────────────────────────────────────────────────────────
GBR_CV_PARAMS = dict(
    n_estimators=300, max_depth=4, min_leaf=10,
    learning_rate=0.03, random_state=42,
)
GBR_FINAL_PARAMS = dict(
    n_estimators=500, max_depth=4, min_leaf=10,
    learning_rate=0.03, random_state=42,
)
```

- [ ] **Step 4.2: Replace GBRegressor instantiations in run_cv()**

Find:
```python
        rf1 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
```
Replace with:
```python
        rf1 = GBRegressor(**GBR_CV_PARAMS)
```

Find:
```python
        rf2 = GBRegressor(n_estimators=150, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
```
Replace with:
```python
        rf2 = GBRegressor(**GBR_CV_PARAMS)
```

- [ ] **Step 4.3: Replace GBRegressor instantiations in run_cv_max_chain(), run_cv_s1_chain_s2_roll1()**

Both functions have a `_n_est` override parameter for tests. Keep the override but default to GBR_CV_PARAMS:

Example for `run_cv_max_chain` (around line 419–421):
```python
        rf1 = GBRegressor(n_estimators=_n_est, max_depth=4, min_leaf=10,
                          learning_rate=0.05, random_state=42)
```
Replace with:
```python
        rf1 = GBRegressor(**{**GBR_CV_PARAMS, "n_estimators": _n_est})
```

Apply the same pattern to all four GBR instantiations inside these two functions (both S1 and S2 trains).

- [ ] **Step 4.4: Replace GBRegressor instantiations in run_cv_s1_direct_s2_anchor(), run_cv_single_stage()**

Same `{**GBR_CV_PARAMS, "n_estimators": _n_est}` pattern wherever `_n_est` is in scope.

- [ ] **Step 4.5: Replace GBRegressor instantiations in train_final()**

Find:
```python
    gb1 = GBRegressor(n_estimators=250, max_depth=4, min_leaf=10, learning_rate=0.05, random_state=42)
```
Replace with:
```python
    gb1 = GBRegressor(**GBR_FINAL_PARAMS)
```

Same for gb2 and gb2d.

- [ ] **Step 4.6: Replace GBRegressor instantiations in train_final_gbr_s1_direct_s2_anchor() and train_final_gbr_single_stage()**

These already accept `_n_est` override. Change to:
```python
    gb_s1 = GBRegressor(**{**GBR_FINAL_PARAMS, "n_estimators": _n_est})
    gb_s2 = GBRegressor(**{**GBR_FINAL_PARAMS, "n_estimators": _n_est})
```

- [ ] **Step 4.7: Run full test suite**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests PASS (tests use `_n_est=2` override which still works).

- [ ] **Step 4.8: Commit**

```
git add Automation/08_train_forecast_model.py
git commit -m "feat: add GBR_CV_PARAMS/GBR_FINAL_PARAMS constants, tune n_est and lr (Finding 6)"
```

---

## Task 5: Retrain and verify

Run the full training pipeline to produce updated model files and confirm the new R² is higher than the pre-improvement baseline (R²=0.694 avg S2).

**Files:**
- No code changes — this is a run step.

- [ ] **Step 5.1: Run the full test suite one final time**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests PASS.

- [ ] **Step 5.2: Retrain baseline_gbr (the winner)**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/08_train_forecast_model.py --winner-only
```

Watch for:
- Four CV folds printed with S1 R² and S2 R²
- S2 mean R² higher than 0.694 (the previous winner's score)
- No errors or KeyErrors

- [ ] **Step 5.3: Verify model files were updated**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -c "
import json
with open('Models/model_metadata.json') as f:
    m = json.load(f)
print('trained_through:', m['trained_through'])
print('target_transforms:', m['target_transforms'])
print('s2_mean_r2:', m.get('cv_s2_mean_r2'))
print('features (S1):', len(m.get('s1_features', [])), 'features')
print('features (S2):', len(m.get('s2_features', [])), 'features')
"
```

Expected:
- `target_transforms.s2 == "signed_log1p"`
- `cv_s2_mean_r2 > 0.694`
- S1 features: 23, S2 features: 22

- [ ] **Step 5.4: Smoke-test inference**

Fill in `forecast_input_template.csv` with 7 rows of plausible values (or copy any recent 7-day window from the gold table), then run:

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/09_weekly_forecast.py
```

Confirm:
- Prints "Anchor state: level_m_anchor=... dvol_lag1=... dvol_lag2=... dvol_lag3=... outflow_lag1=..."
- Prints a 7-day forecast table with plausible level values (-214 to -208 m range)
- No NaN in pred_level_m column

- [ ] **Step 5.5: Commit retrained models and updated metadata**

```
git add Models/stage1_inflow_rf.pkl Models/stage2_volume_rf.pkl Models/stage2_direct_gb.pkl Models/model_metadata.json
git commit -m "chore: retrain baseline_gbr with all signal harvest improvements"
```

---

## Self-Review Checklist

**Spec coverage:**
- Finding 1 (transform) → Task 2 ✓
- Finding 2 (outflow_lag1_m3) → Tasks 1 + 3 ✓
- Finding 3 (dvol_lag2/lag3 anchors) → Tasks 1 + 3 ✓
- Finding 4 (RBF features) → Task 1 ✓
- Finding 5 (precip_intensity) → Task 1 ✓
- Finding 6 (hyperparameter tuning) → Task 4 ✓
- Inference consistency (09_weekly_forecast.py) → Tasks 2 + 3 ✓
- Test helpers updated for `outflow_baptism_m3` → Task 1, Step 1.9 ✓

**Gaps found and resolved:**
- `build_direct_s2_data()` reads `df["outflow_baptism_m3"]` (source column), not `outflow_lag1_m3` (feature name). Test helpers must include `outflow_baptism_m3`. ✓ (Step 1.9)
- `S2_DIRECT_NO_INFLOW_FEATURES` is auto-derived from `S2_DIRECT_FEATURES`, so the existing length test still holds after adding 3 new features. ✓ verified.
- Inverse transform must be applied in `09_weekly_forecast.py` (Step 2.6) — the deployed model outputs log-space predictions that need inversion before display. ✓

**No placeholders:** all code blocks show exact, complete snippets.

**Type consistency:** `inv_signed_log1p_transform` takes `np.ndarray` and returns `np.ndarray`. In the inference call `float(inv_signed_log1p_transform(gb2_direct.predict(s2_x))[0])`, `gb2_direct.predict(s2_x)` returns a 1-D ndarray, which is valid input. ✓
