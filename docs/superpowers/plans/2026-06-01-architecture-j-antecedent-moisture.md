# Architecture J: Antecedent Moisture Proxy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `rainfall_30d_mm` and `rainfall_45d_mm` (30-day and 45-day rolling rainfall sums) as features to S1 and S2 to give the model knowledge of watershed soil-moisture state, fixing the structural weakness in the 2021 and 2023 folds (R²≈0.665) identified by monthly residual analysis.

**Architecture:** The gold pipeline already computes 7d/14d/21d rolling sums; extending to 30d/45d is 2 lines there. `model_lib.py` is the single source of truth for feature lists — adding there propagates to training (`build_direct_s2_data` loops over `S2_MET_FEATURES` automatically) and inference (`run_forecast` already reads all `S2_DIRECT_FEATURES` from `build_feature_rows`). The inference script needs matching rolling-window computation added.

**Tech Stack:** Pure pandas rolling, existing `GBRegressor` in `model_lib.py`, walk-forward CV 2021–2024, full Olympics run to measure effect.

**Branch:** Create a new branch `arch-j-antecedent-moisture` off `master` before starting.

**Diagnostic baseline (from `diag_residuals_by_month.py`):**
- 2021 R²=0.657: worst months Jan (MAE=1.507), Feb (1.409), Dec (1.014)
- 2023 R²=0.596: worst months Feb (MAE=1.421), Dec (1.104), Nov (0.905)
- 2023 Feb signed residual = +0.919 (over-predicts floods that don't come in a drought year)
- 2021 Jan signed residual = −0.387 (under-predicts floods in wet year with saturated soil)
- Current overall mean R² = 0.758; target > 0.83

---

## File structure

| Action | Path | Change |
|--------|------|--------|
| Modify | `Automation/07_build_gold_features.py` | +2 rolling sums in `_add_met_features()` |
| Modify | `Automation/model_lib.py` | +2 features in `S1_FEATURES`, `S2_FEATURES`, `S2_MET_FEATURES`, `S1_DIRECT_FEATURES` |
| Modify | `Automation/09_weekly_forecast.py` | +2 rolling windows + 2 attach lines in `build_feature_rows()` |
| Create | `tests/test_antecedent_moisture.py` | 8 tests covering feature lists and inference rolling windows |
| Run | `python Automation/07_build_gold_features.py` | Regenerate gold CSV with new columns |
| Run | `python Automation/08_train_forecast_model.py` | Full Olympics run; verify improved CV scores |

`S2_DIRECT_FEATURES` does **not** need to be edited: it is defined as `S2_MET_FEATURES + [anchor features]`, so adding to `S2_MET_FEATURES` automatically propagates the new features there. `build_direct_s2_data` also needs no change — it already loops `for col in S2_MET_FEATURES: p[col] = df[col].shift(-h) if col in df.columns else np.nan`.

---

## Task 1 — Write failing tests

**Files:**
- Create: `tests/test_antecedent_moisture.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_antecedent_moisture.py
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


# ── Feature list membership ───────────────────────────────────────────────────

def test_rainfall_30d_in_s1_features():
    from model_lib import S1_FEATURES
    assert "rainfall_30d_mm" in S1_FEATURES, "rainfall_30d_mm missing from S1_FEATURES"


def test_rainfall_45d_in_s1_features():
    from model_lib import S1_FEATURES
    assert "rainfall_45d_mm" in S1_FEATURES, "rainfall_45d_mm missing from S1_FEATURES"


def test_rainfall_30d_in_s2_met_features():
    from model_lib import S2_MET_FEATURES
    assert "rainfall_30d_mm" in S2_MET_FEATURES


def test_rainfall_45d_in_s2_met_features():
    from model_lib import S2_MET_FEATURES
    assert "rainfall_45d_mm" in S2_MET_FEATURES


def test_rainfall_30d_in_s2_direct_features():
    """S2_MET_FEATURES is included in S2_DIRECT_FEATURES, so this must propagate."""
    from model_lib import S2_DIRECT_FEATURES
    assert "rainfall_30d_mm" in S2_DIRECT_FEATURES


def test_rainfall_30d_in_s2_features():
    from model_lib import S2_FEATURES
    assert "rainfall_30d_mm" in S2_FEATURES


# ── build_feature_rows produces rolling windows from history ──────────────────

def _make_history_and_forecast():
    """50 days history (enough for 45d rolling) + 7 day forecast."""
    rng = np.random.default_rng(42)
    hist_dates = pd.date_range("2024-01-01", periods=50)
    history = pd.DataFrame({
        "date":           hist_dates,
        "rainfall_mm":    rng.uniform(0, 5, 50),
        "et0_mm":         rng.uniform(2, 8, 50),
        "level_m":        rng.uniform(-214, -208, 50),
        "volume_Mm3":     rng.uniform(2000, 4200, 50),
        "volume_change_Mm3": rng.uniform(-1, 1, 50),
        "outflow_baptism_m3": rng.uniform(0.2e6, 0.6e6, 50),
        "inflow_obstacle_m3": rng.uniform(1e5, 1e6, 50),
        **{c: rng.uniform(0, 1, 50) for c in [
            "temp_max_C", "temp_min_C", "humidity_pct",
            "wind_speed_ms", "radiation_MJm2",
        ]},
    })
    fc_dates = pd.date_range("2024-02-20", periods=7)
    forecast = pd.DataFrame({
        "date":           fc_dates,
        "temp_max_C":     rng.uniform(15, 25, 7),
        "temp_min_C":     rng.uniform(5, 15, 7),
        "rainfall_mm":    rng.uniform(0, 3, 7),
        "humidity_pct":   rng.uniform(40, 80, 7),
        "wind_speed_ms":  rng.uniform(2, 8, 7),
        "radiation_MJm2": rng.uniform(10, 25, 7),
    })
    return history, forecast


def test_build_feature_rows_produces_rainfall_30d():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_09", Path(__file__).parent.parent / "Automation" / "09_weekly_forecast.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    history, forecast = _make_history_and_forecast()
    result = m.build_feature_rows(forecast, history)
    assert "rainfall_30d_mm" in result.columns, "build_feature_rows must produce rainfall_30d_mm"
    assert "rainfall_45d_mm" in result.columns, "build_feature_rows must produce rainfall_45d_mm"


def test_build_feature_rows_rainfall_30d_uses_history():
    """Day-1 rainfall_30d_mm must reflect the 30-day window that spans history, not just forecast."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_09b", Path(__file__).parent.parent / "Automation" / "09_weekly_forecast.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    history, forecast = _make_history_and_forecast()

    # Manually compute what the 30d rolling sum should be for forecast day 1:
    # history has 50 days, forecast day 1 is day 51.
    # The 30-day window ending on day 51 = sum of days 22..51.
    all_rain = pd.concat([
        history[["date", "rainfall_mm"]],
        forecast[["date", "rainfall_mm"]],
    ]).sort_values("date").reset_index(drop=True)
    expected_day1 = float(all_rain["rainfall_mm"].rolling(30, min_periods=10).sum().iloc[50])

    result = m.build_feature_rows(forecast, history)
    actual_day1 = float(result["rainfall_30d_mm"].iloc[0])
    np.testing.assert_almost_equal(actual_day1, expected_day1, decimal=6)
```

- [ ] **Step 2: Run tests to verify they all fail**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_antecedent_moisture.py -v
```

Expected: all 8 tests FAIL (AssertionError — features not in lists yet, columns not in output yet)

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_antecedent_moisture.py
git commit -m "test: add failing tests for Architecture J antecedent moisture features"
```

---

## Task 2 — Add rolling sums to gold pipeline

**Files:**
- Modify: `Automation/07_build_gold_features.py` around line 173

- [ ] **Step 1: Add 30d/45d rolling sums in `_add_met_features()`**

Find this block (lines 170-173):
```python
    # --- Infiltration proxy: rolling rainfall sums ---
    df["rainfall_7d_mm"]  = df["rainfall_mm"].rolling(7,  min_periods=1).sum()
    df["rainfall_14d_mm"] = df["rainfall_mm"].rolling(14, min_periods=1).sum()
    df["rainfall_21d_mm"] = df["rainfall_mm"].rolling(21, min_periods=1).sum()
```

Replace with:
```python
    # --- Infiltration proxy: rolling rainfall sums ---
    df["rainfall_7d_mm"]  = df["rainfall_mm"].rolling(7,  min_periods=1).sum()
    df["rainfall_14d_mm"] = df["rainfall_mm"].rolling(14, min_periods=1).sum()
    df["rainfall_21d_mm"] = df["rainfall_mm"].rolling(21, min_periods=1).sum()
    df["rainfall_30d_mm"] = df["rainfall_mm"].rolling(30, min_periods=10).sum()
    df["rainfall_45d_mm"] = df["rainfall_mm"].rolling(45, min_periods=15).sum()
```

- [ ] **Step 2: Regenerate the gold CSV**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/07_build_gold_features.py
```

Expected output ends with:
```
  Saved: Gold Data/kinneret_gold_features.csv
```
The gold CSV must now contain columns `rainfall_30d_mm` and `rainfall_45d_mm`.

- [ ] **Step 3: Verify gold CSV has the new columns**

```
python -c "
import pandas as pd
df = pd.read_csv('Gold Data/kinneret_gold_features.csv')
print('rainfall_30d_mm' in df.columns, 'rainfall_45d_mm' in df.columns)
print(df[['date','rainfall_mm','rainfall_30d_mm','rainfall_45d_mm']].tail(3))
"
```

Expected: `True True` on first line, and a 3-row table with non-NaN values.

- [ ] **Step 4: Commit**

```bash
git add Automation/07_build_gold_features.py
git commit -m "feat: add rainfall_30d_mm and rainfall_45d_mm rolling sums to gold pipeline"
```

---

## Task 3 — Add features to model_lib.py

**Files:**
- Modify: `Automation/model_lib.py`

- [ ] **Step 1: Add to `S1_FEATURES` (after `rainfall_21d_mm` line)**

Find this block (lines 44-46):
```python
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    # Moisture balance (rainfall - ET0): net catchment wetness proxy
```

Replace with:
```python
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    "rainfall_30d_mm",
    "rainfall_45d_mm",
    # Moisture balance (rainfall - ET0): net catchment wetness proxy
```

- [ ] **Step 2: Add to `S2_FEATURES` (after `rainfall_21d_mm` line)**

Find this block (lines 73-76):
```python
    "rainfall_mm",
    "rainfall_7d_mm",
    "rainfall_21d_mm",
    "temp_mean_C",
```

Replace with:
```python
    "rainfall_mm",
    "rainfall_7d_mm",
    "rainfall_21d_mm",
    "rainfall_30d_mm",
    "rainfall_45d_mm",
    "temp_mean_C",
```

- [ ] **Step 3: Add to `S2_MET_FEATURES` (after `rainfall_21d_mm` entry)**

Find this block (line 111):
```python
    "predicted_inflow_m3",
    "rainfall_mm", "rainfall_7d_mm", "rainfall_21d_mm",
    "temp_mean_C", "temp_max_C",
```

Replace with:
```python
    "predicted_inflow_m3",
    "rainfall_mm", "rainfall_7d_mm", "rainfall_21d_mm",
    "rainfall_30d_mm", "rainfall_45d_mm",
    "temp_mean_C", "temp_max_C",
```

- [ ] **Step 4: Add to `S1_DIRECT_FEATURES` (after `rainfall_21d_mm` line)**

Find this block (lines 145-148):
```python
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    "moisture_balance_7d_mm",
```

Replace with:
```python
    "rainfall_7d_mm",
    "rainfall_14d_mm",
    "rainfall_21d_mm",
    "rainfall_30d_mm",
    "rainfall_45d_mm",
    "moisture_balance_7d_mm",
```

- [ ] **Step 5: Run the 6 feature-list tests (should now pass)**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_antecedent_moisture.py::test_rainfall_30d_in_s1_features tests/test_antecedent_moisture.py::test_rainfall_45d_in_s1_features tests/test_antecedent_moisture.py::test_rainfall_30d_in_s2_met_features tests/test_antecedent_moisture.py::test_rainfall_45d_in_s2_met_features tests/test_antecedent_moisture.py::test_rainfall_30d_in_s2_direct_features tests/test_antecedent_moisture.py::test_rainfall_30d_in_s2_features -v
```

Expected: 6 PASSED

- [ ] **Step 6: Commit**

```bash
git add Automation/model_lib.py
git commit -m "feat: add rainfall_30d_mm and rainfall_45d_mm to S1/S2 feature lists (Architecture J)"
```

---

## Task 4 — Update inference rolling windows

**Files:**
- Modify: `Automation/09_weekly_forecast.py`

- [ ] **Step 1: Add rolling30/rolling45 to `build_feature_rows()`**

Find this block (lines 121-123):
```python
    rain_all["rolling7"]  = rain_all["rainfall_mm"].rolling(7,  min_periods=1).sum()
    rain_all["rolling14"] = rain_all["rainfall_mm"].rolling(14, min_periods=1).sum()
    rain_all["rolling21"] = rain_all["rainfall_mm"].rolling(21, min_periods=1).sum()
```

Replace with:
```python
    rain_all["rolling7"]  = rain_all["rainfall_mm"].rolling(7,  min_periods=1).sum()
    rain_all["rolling14"] = rain_all["rainfall_mm"].rolling(14, min_periods=1).sum()
    rain_all["rolling21"] = rain_all["rainfall_mm"].rolling(21, min_periods=1).sum()
    rain_all["rolling30"] = rain_all["rainfall_mm"].rolling(30, min_periods=10).sum()
    rain_all["rolling45"] = rain_all["rainfall_mm"].rolling(45, min_periods=15).sum()
```

- [ ] **Step 2: Attach the new columns to `fc`**

Find this block (lines 152-158):
```python
    fc["rainfall_7d_mm"]   = rain_feats["rolling7"].values
    fc["rainfall_14d_mm"]  = rain_feats["rolling14"].values
    fc["rainfall_21d_mm"]  = rain_feats["rolling21"].values
    fc["rainfall_lag1_mm"] = rain_feats["lag1"].values
    fc["rainfall_lag2_mm"] = rain_feats["lag2"].values
    fc["rainfall_lag3_mm"] = rain_feats["lag3"].values
```

Replace with:
```python
    fc["rainfall_7d_mm"]   = rain_feats["rolling7"].values
    fc["rainfall_14d_mm"]  = rain_feats["rolling14"].values
    fc["rainfall_21d_mm"]  = rain_feats["rolling21"].values
    fc["rainfall_30d_mm"]  = rain_feats["rolling30"].values
    fc["rainfall_45d_mm"]  = rain_feats["rolling45"].values
    fc["rainfall_lag1_mm"] = rain_feats["lag1"].values
    fc["rainfall_lag2_mm"] = rain_feats["lag2"].values
    fc["rainfall_lag3_mm"] = rain_feats["lag3"].values
```

- [ ] **Step 3: Run the 2 inference tests (should now pass)**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_antecedent_moisture.py::test_build_feature_rows_produces_rainfall_30d tests/test_antecedent_moisture.py::test_build_feature_rows_rainfall_30d_uses_history -v
```

Expected: 2 PASSED

- [ ] **Step 4: Run the full test suite (no regressions)**

```
python -m pytest tests/ -v
```

Expected: all existing tests pass. The 1 pre-existing failure in `test_error_prop_olympics.py::test_save_olympics_results_includes_new_architectures` is known (hardcoded path) — it is acceptable.

- [ ] **Step 5: Commit**

```bash
git add Automation/09_weekly_forecast.py
git commit -m "feat: add 30d/45d rainfall rolling windows to forecast inference (Architecture J)"
```

---

## Task 5 — Retrain and evaluate

**Files:**
- Run: `Automation/08_train_forecast_model.py` (no code change needed)

- [ ] **Step 1: Run the full Olympics training**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/08_train_forecast_model.py
```

This takes ~45–60 minutes on CPU (GRU folds dominate). Expected final lines:
```
  Saved: docs/olympics_results.json
  WINNER: baseline_gbr  (R²=X.XXX  MAE=X.XXX)
```

- [ ] **Step 2: Verify Architecture J improved the weak folds**

Check the printed CV output for `baseline_gbr`. The key numbers to watch:

| Fold | Before J | Target |
|------|----------|--------|
| 2021 | R²=0.665 | >0.76 |
| 2022 | R²=0.877 | maintain |
| 2023 | R²=0.664 | >0.76 |
| 2024 | R²=0.825 | maintain |
| mean | 0.758    | >0.80  |

If mean S2 R² improves by at least +0.02 over 0.758, the antecedent moisture signal is working.

- [ ] **Step 3: Re-run the diagnostic to see monthly improvement**

```
python Automation/diag_residuals_by_month.py
```

The Jan/Feb MAE for 2021 and the Feb MAE for 2023 should decrease compared to the earlier run.

- [ ] **Step 4: Commit results**

```bash
git add docs/olympics_results.json
git commit -m "feat: retrain with Architecture J — add R² delta to commit message"
```

Replace "add R² delta" with the actual improvement, e.g. `(R² 0.758→0.793)`.

---

## Self-review

**1. Spec coverage:**
- Add `rainfall_30d_mm` + `rainfall_45d_mm` to gold pipeline: Task 2 ✓
- Add to `S1_FEATURES`, `S2_FEATURES`, `S2_MET_FEATURES`, `S1_DIRECT_FEATURES`: Task 3 ✓
- Propagation to `S2_DIRECT_FEATURES` via `S2_MET_FEATURES` — no code change, automatic ✓
- `build_direct_s2_data` automatically picks up via `for col in S2_MET_FEATURES` — no code change ✓
- `build_feature_rows` in inference updated: Task 4 ✓
- Full retraining and CV evaluation: Task 5 ✓
- Tests for all of the above: Task 1 ✓

**2. Placeholder scan:** No TBDs. All code blocks are complete.

**3. Type consistency:**
- Column names `rainfall_30d_mm` / `rainfall_45d_mm` used consistently across all four files.
- `rolling30` / `rolling45` are intermediate names internal to `build_feature_rows` — not exposed.
- `min_periods=10` for 30d and `min_periods=15` for 45d match what `07_build_gold_features.py` uses — both files use the same values to ensure training/inference consistency.
