# Long-Range Temp Forecast — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the calculation library and data foundation for the long-range temperature-only level forecast, ending in a make-or-break empirical check that the temp→rain premise holds in our data.

**Architecture:** Three pure-function library modules (meteo, climatology, antecedent state) reusing the FAO-56 astronomy already in `model_lib.py`, plus four pipeline scripts (deep ERA5 ingest → bias-correct → Hargreaves calibration → climatology build) and one diagnostic gate (premise check). No changes to the existing 7-day model. Phases B (bake-off) and C (winner design) get separate plans after this gate passes.

**Tech Stack:** Python, numpy, pandas, requests (Open-Meteo archive API), pytest. Mirrors existing `Automation/*.py` + `tests/test_*.py` conventions.

**Design spec:** `docs/superpowers/specs/2026-06-01-longrange-temp-forecast-design.md` (calculation groups referenced below as "Group N").

---

## File structure (Phase A)

| File | Responsibility |
|------|----------------|
| `Automation/longrange_meteo.py` | Group 1 astronomy (reuse model_lib), Group 2 Hargreaves ET₀, Group 3 DTR + cloud_index |
| `Automation/longrange_climatology.py` | Group 4 harmonic normals + hurdle rain climatology, Group 5 standardized anomalies |
| `Automation/longrange_state.py` | Group 6 API + soil-moisture bucket (the "Architecture J done right" integrator) |
| `Automation/longrange_fetch_era5.py` | Pull deep ERA5 daily history (→1960) from Open-Meteo archive |
| `Automation/longrange_bias_correct.py` | Group 8 monthly quantile-mapping ERA5→IMS gold on 2012–2024 overlap |
| `Automation/longrange_calibrate_hargreaves.py` | Calibrate Hargreaves vs Penman-Monteith `et0_mm`; write coefficient to config |
| `Automation/longrange_build_climatology.py` | Build per-DOY normals + modern outflow climatology table |
| `Automation/longrange_premise_check.py` | **Make-or-break gate:** does low-DTR + cold-Tmax-anomaly + wet-season predict rain/inflow in gold? |
| `tests/test_longrange_meteo.py` | Tests for meteo module |
| `tests/test_longrange_climatology.py` | Tests for climatology module |
| `tests/test_longrange_state.py` | Tests for state module (incl. the saturation-threshold J-fix) |
| `tests/test_longrange_fetch_era5.py` | Tests for ERA5 fetch (mocked HTTP) |
| `tests/test_longrange_bias_correct.py` | Tests for quantile mapping |
| `tests/test_longrange_calibrate_hargreaves.py` | Tests for the calibration fit |

**Data outputs (created by scripts, gitignored like other Silver/Gold):**
- `Silver Data/Meteorological/era5_kinneret_daily.csv` — raw deep ERA5 history
- `Silver Data/Meteorological/era5_kinneret_daily_corrected.csv` — bias-corrected
- `Gold Data/longrange_climatology.csv` — per-DOY normals + outflow climatology
- `docs/longrange_config.json` — calibrated Hargreaves coefficient
- `docs/longrange_premise_report.md` — the gate's verdict + numbers

**Conventions to follow (verified in repo):**
- CSVs read/written with `encoding="utf-8-sig"`; dates as `date` column.
- Constants: import `LATITUDE` (32.82), `ELEVATION` (-212.0) from `model_lib`.
- Tests import modules directly after `sys.path.insert(0, ROOT/"Automation")` (already done in `tests/conftest.py`); new modules have no digit prefix, so `from longrange_meteo import ...` works.
- Gold table: `Gold Data/kinneret_gold_features.csv`; key columns used here: `date`, `temp_max_C`, `temp_min_C`, `temp_mean_C`, `rainfall_mm`, `et0_mm`, `inflow_obstacle_m3`, `outflow_baptism_m3`.

---

## Task 1: Meteo module — astronomy, Hargreaves ET₀, DTR/cloud proxy

**Files:**
- Create: `Automation/longrange_meteo.py`
- Test: `tests/test_longrange_meteo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_meteo.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_ra_matches_model_lib_inline_formula():
    """longrange_meteo Ra must equal the trusted inline Ra in model_lib.compute_et0
    (same FAO-56 block) for several days of year."""
    from longrange_meteo import extraterrestrial_radiation
    from model_lib import LATITUDE
    lat = np.radians(LATITUDE)
    for J in [1.0, 80.0, 172.0, 264.0, 355.0]:
        dr   = 1 + 0.033 * np.cos(2 * np.pi / 365 * J)
        decl = 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)
        oms  = np.arccos(np.clip(-np.tan(lat) * np.tan(decl), -1, 1))
        ra_ref = (24 * 60 / np.pi) * 0.0820 * dr * (
            oms * np.sin(lat) * np.sin(decl)
            + np.cos(lat) * np.cos(decl) * np.sin(oms))
        assert abs(extraterrestrial_radiation(J) - ra_ref) < 1e-9


def test_hargreaves_summer_value_is_physical():
    """Summer-solstice ET0 for a hot dry day lands in a plausible 5-8 mm band."""
    from longrange_meteo import hargreaves_et0
    et0 = hargreaves_et0(temp_max_C=33.0, temp_min_C=20.0, doy=172.0)
    assert 5.0 < et0 < 8.0


def test_hargreaves_increases_with_diurnal_range():
    """Wider Tmax-Tmin (clearer sky) => more evaporation."""
    from longrange_meteo import hargreaves_et0
    narrow = hargreaves_et0(28.0, 24.0, 172.0)   # DTR = 4
    wide   = hargreaves_et0(32.0, 20.0, 172.0)   # DTR = 12
    assert wide > narrow


def test_cloud_index_high_when_dtr_below_clearsky():
    """Compressed range relative to clear-sky envelope => high cloud_index (rain flag)."""
    from longrange_meteo import cloud_index
    # clear-sky DTR for this day = 12; observed DTR = 3 (overcast)
    ci = cloud_index(dtr=3.0, dtr_clearsky=12.0)
    assert 0.4 < ci <= 1.0
    # observed DTR at/above clear-sky envelope => cloud_index ~ 0
    assert cloud_index(dtr=12.0, dtr_clearsky=12.0) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_meteo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_meteo'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_meteo.py
"""
longrange_meteo.py - Temperature-only meteorology for the long-range forecast.

Group 1 (astronomy), Group 2 (Hargreaves ET0), Group 3 (DTR/cloud proxy) of
docs/superpowers/specs/2026-06-01-longrange-temp-forecast-design.md.

Astronomy reproduces the exact FAO-56 Ra block in model_lib.compute_et0; a test
asserts the two stay identical so they never drift.
"""
from __future__ import annotations

import numpy as np

from model_lib import LATITUDE   # 32.82 deg N - single source of truth

_GSC = 0.0820   # solar constant, MJ m-2 min-1
_INV_LAMBDA = 0.408   # 1 / latent heat of vaporisation (2.45 MJ/kg): MJ m-2 -> mm


def solar_declination(doy):
    """Solar declination [rad] for day-of-year J (FAO-56 eq. 24)."""
    J = np.asarray(doy, dtype=float)
    return 0.409 * np.sin(2 * np.pi / 365 * J - 1.39)


def extraterrestrial_radiation(doy):
    """Daily extraterrestrial radiation Ra [MJ m-2 day-1] (FAO-56 eq. 21).

    Closed-form in date + latitude only - no forecast needed."""
    J = np.asarray(doy, dtype=float)
    lat = np.radians(LATITUDE)
    dr = 1 + 0.033 * np.cos(2 * np.pi / 365 * J)
    decl = solar_declination(J)
    oms = np.arccos(np.clip(-np.tan(lat) * np.tan(decl), -1, 1))
    return (24 * 60 / np.pi) * _GSC * dr * (
        oms * np.sin(lat) * np.sin(decl)
        + np.cos(lat) * np.cos(decl) * np.sin(oms))


def hargreaves_et0(temp_max_C, temp_min_C, doy, coeff=0.0023):
    """Hargreaves-Samani reference ET0 [mm/day] from Tmin, Tmax, Ra (Group 2).

    coeff defaults to the textbook 0.0023; the calibrated value lives in
    docs/longrange_config.json and is passed in by callers after Task 6."""
    Tx = np.asarray(temp_max_C, dtype=float)
    Tn = np.asarray(temp_min_C, dtype=float)
    Tmean = (Tx + Tn) / 2.0
    ra = extraterrestrial_radiation(doy)
    dtr = np.clip(Tx - Tn, 0, None)
    return coeff * (_INV_LAMBDA * ra) * (Tmean + 17.8) * np.sqrt(dtr)


def cloud_index(dtr, dtr_clearsky):
    """Group 3 cloud/rain proxy in [0, 1].

    1 - clip(sqrt(DTR)/sqrt(DTR_clearsky), 0, 1). Low observed range relative to
    the clear-sky envelope => high cloud_index => rain-likely."""
    dtr = np.clip(np.asarray(dtr, dtype=float), 0, None)
    dtr_cs = np.clip(np.asarray(dtr_clearsky, dtype=float), 1e-9, None)
    return 1.0 - np.clip(np.sqrt(dtr) / np.sqrt(dtr_cs), 0, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_meteo.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add Automation/longrange_meteo.py tests/test_longrange_meteo.py
git commit -m "feat: longrange meteo module (astronomy, Hargreaves ET0, cloud index)"
```

---

## Task 2: Climatology module — harmonic normals, anomalies, hurdle rain climatology

**Files:**
- Create: `Automation/longrange_climatology.py`
- Test: `tests/test_longrange_climatology.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_climatology.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_harmonic_fit_recovers_known_sinusoid():
    """Fitting a clean 1-harmonic signal recovers it to high accuracy."""
    from longrange_climatology import fit_harmonic, eval_harmonic
    doy = np.arange(1, 366, dtype=float)
    true = 20 + 8 * np.sin(2 * np.pi * doy / 365) + 3 * np.cos(2 * np.pi * doy / 365)
    coeffs = fit_harmonic(doy, true, K=3)
    recon = eval_harmonic(doy, coeffs)
    assert np.max(np.abs(recon - true)) < 1e-6


def test_anomaly_zscore_centers_near_zero():
    """Standardized anomalies of the training data have ~0 mean and ~unit std."""
    from longrange_climatology import fit_harmonic, anomaly_zscore
    rng = np.random.default_rng(0)
    doy = np.tile(np.arange(1, 366, dtype=float), 5)
    seasonal = 20 + 8 * np.sin(2 * np.pi * doy / 365)
    values = seasonal + rng.normal(0, 2.0, size=doy.size)
    mean_coeffs = fit_harmonic(doy, values, K=3)
    z = anomaly_zscore(doy, values, mean_coeffs, var_coeffs=None)
    assert abs(np.mean(z)) < 0.1
    assert 0.8 < np.std(z) < 1.2


def test_hurdle_rain_climatology_separates_wet_dry_seasons():
    """Wet-season DOYs get higher wet-day probability than dry-season DOYs."""
    from longrange_climatology import fit_rain_climatology, eval_harmonic
    rng = np.random.default_rng(1)
    doy = np.tile(np.arange(1, 366, dtype=float), 6)
    # Winter (Nov-Mar) wet, summer bone dry
    p_true = np.where((doy < 90) | (doy > 305), 0.5, 0.02)
    rain = np.where(rng.random(doy.size) < p_true, rng.uniform(1, 30, doy.size), 0.0)
    pwet_coeffs, amt_coeffs = fit_rain_climatology(doy, rain, wet_threshold_mm=1.0, K=3)
    assert eval_harmonic(15.0, pwet_coeffs) > eval_harmonic(200.0, pwet_coeffs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_climatology.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_climatology'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_climatology.py
"""
longrange_climatology.py - Per-day-of-year climatology (Group 4) and
standardized anomalies (Group 5).

Harmonic regression (K=3) on day-of-year avoids leap-year/window-edge artefacts
and yields smooth normals. Rainfall uses a two-part (hurdle) climatology:
probability of a wet day, and mean amount on wet days.
"""
from __future__ import annotations

import numpy as np


def _design_matrix(doy, K):
    J = np.asarray(doy, dtype=float)
    cols = [np.ones_like(J)]
    for k in range(1, K + 1):
        cols.append(np.cos(2 * np.pi * k * J / 365))
        cols.append(np.sin(2 * np.pi * k * J / 365))
    return np.column_stack(cols)


def fit_harmonic(doy, values, K=3):
    """Least-squares fit of K harmonics; returns coefficient vector (length 2K+1).
    NaNs in values are dropped before fitting."""
    J = np.asarray(doy, dtype=float)
    y = np.asarray(values, dtype=float)
    ok = ~np.isnan(y)
    X = _design_matrix(J[ok], K)
    coeffs, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    return coeffs


def eval_harmonic(doy, coeffs):
    """Evaluate a fitted harmonic at day(s)-of-year."""
    K = (len(coeffs) - 1) // 2
    X = _design_matrix(doy, K)
    return X @ coeffs


def anomaly_zscore(doy, values, mean_coeffs, var_coeffs=None):
    """(value - mean_clim(doy)) / sigma_clim(doy)  (Group 5).

    If var_coeffs is None, uses a single global residual std."""
    resid = np.asarray(values, dtype=float) - eval_harmonic(doy, mean_coeffs)
    if var_coeffs is None:
        sigma = np.nanstd(resid)
        sigma = sigma if sigma > 1e-9 else 1.0
    else:
        sigma = np.sqrt(np.clip(eval_harmonic(doy, var_coeffs), 1e-9, None))
    return resid / sigma


def fit_variance_harmonic(doy, values, mean_coeffs, K=3):
    """Harmonic fit of squared residuals -> seasonal variance (for sigma_clim)."""
    resid = np.asarray(values, dtype=float) - eval_harmonic(doy, mean_coeffs)
    return fit_harmonic(doy, resid ** 2, K=K)


def fit_rain_climatology(doy, rain_mm, wet_threshold_mm=1.0, K=3):
    """Two-part rain climatology. Returns (p_wet_coeffs, amount_coeffs):
      p_wet_coeffs   - harmonic fit of the wet-day indicator 1[rain > threshold]
      amount_coeffs  - harmonic fit of mean amount on wet days only
    """
    rain = np.asarray(rain_mm, dtype=float)
    wet = (rain > wet_threshold_mm).astype(float)
    p_wet_coeffs = fit_harmonic(doy, wet, K=K)
    wet_mask = rain > wet_threshold_mm
    amount_coeffs = fit_harmonic(np.asarray(doy)[wet_mask], rain[wet_mask], K=K)
    return p_wet_coeffs, amount_coeffs


def clearsky_dtr_by_doy(doy, dtr, K=3, quantile=0.90):
    """Clear-sky DTR envelope per DOY: harmonic fit of the seasonal `quantile` of
    DTR, approximated by fitting the mean then shifting by the residual quantile.
    Returns coeffs usable with eval_harmonic (Group 3 DTR_clearsky)."""
    mean_coeffs = fit_harmonic(doy, dtr, K=K)
    resid = np.asarray(dtr, dtype=float) - eval_harmonic(doy, mean_coeffs)
    shift = np.nanquantile(resid, quantile)
    out = mean_coeffs.copy()
    out[0] = out[0] + shift   # raise the intercept to the quantile envelope
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_climatology.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add Automation/longrange_climatology.py tests/test_longrange_climatology.py
git commit -m "feat: longrange climatology (harmonic normals, anomalies, hurdle rain)"
```

---

## Task 3: Antecedent-state module — API and soil-moisture bucket (the J-fix)

**Files:**
- Create: `Automation/longrange_state.py`
- Test: `tests/test_longrange_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_state.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_api_decays_without_rain():
    """With no rain, API decays geometrically by factor k each day."""
    from longrange_state import antecedent_precip_index
    P = np.array([100.0, 0.0, 0.0, 0.0])
    A = antecedent_precip_index(P, k=0.9, a0=0.0)
    assert abs(A[0] - 100.0) < 1e-9
    assert abs(A[1] - 90.0) < 1e-9
    assert abs(A[2] - 81.0) < 1e-9


def test_bucket_dry_soil_produces_no_runoff():
    """The J-fix, half 1: dry soil soaks rain (low runoff) -> fixes 2023-style
    drought over-prediction."""
    from longrange_state import soil_moisture_bucket
    P = np.array([20.0])
    ET = np.array([2.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=0.0)
    assert Q[0] == 0.0           # all absorbed, nothing overflows
    assert abs(S[0] - 18.0) < 1e-9


def test_bucket_saturated_soil_spills_to_runoff():
    """The J-fix, half 2: saturated soil spills rain straight to runoff -> fixes
    2021-style wet under-prediction. Same rain, opposite outcome vs dry soil."""
    from longrange_state import soil_moisture_bucket
    P = np.array([20.0])
    ET = np.array([2.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=200.0)
    assert abs(Q[0] - 18.0) < 1e-9     # 200 + 20 - 2 - 200 = 18 overflow
    assert abs(S[0] - 200.0) < 1e-9    # stays capped at S_max


def test_bucket_never_below_zero():
    """ET on an empty bucket can't drive storage negative."""
    from longrange_state import soil_moisture_bucket
    P = np.array([0.0, 0.0])
    ET = np.array([10.0, 10.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=5.0)
    assert (S >= 0).all()
    assert (Q == 0).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_state'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_state.py
"""
longrange_state.py - Antecedent catchment-state variables (Group 6).

The soil-moisture bucket is "Architecture J done right": flat 30/45-day rainfall
sums (Arch J) could not encode catchment saturation, so they failed in opposite
directions (2023 drought over-predicted runoff, 2021 wet under-predicted it). The
bucket's S_max cap + overflow term Q ARE that saturation threshold:
  - dry soil (low S)  -> rain refills storage, little Q -> low inflow  (fixes 2023)
  - wet soil (S~S_max) -> rain spills to Q -> high inflow              (fixes 2021)
"""
from __future__ import annotations

import numpy as np


def antecedent_precip_index(rainfall_mm, k=0.90, a0=0.0):
    """API_t = k * API_{t-1} + P_t   (Group 6). Returns array same length as input."""
    P = np.asarray(rainfall_mm, dtype=float)
    A = np.empty(P.shape[0], dtype=float)
    prev = a0
    for i in range(P.shape[0]):
        prev = k * prev + P[i]
        A[i] = prev
    return A


def soil_moisture_bucket(rainfall_mm, et_mm, S_max=200.0, S0=None):
    """Bucket model (Group 6). Returns (S, Q):
      S_t = clip(S_{t-1} + P_t - ET_t, 0, S_max)         storage [mm]
      Q_t = max(0, S_{t-1} + P_t - ET_t - S_max)         overflow/runoff [mm]
    S0 defaults to half capacity if not given (spin-up should override in practice).
    """
    P = np.asarray(rainfall_mm, dtype=float)
    ET = np.asarray(et_mm, dtype=float)
    n = P.shape[0]
    S = np.empty(n, dtype=float)
    Q = np.empty(n, dtype=float)
    s = 0.5 * S_max if S0 is None else float(S0)
    for i in range(n):
        avail = s + P[i] - ET[i]
        q = max(0.0, avail - S_max)
        s = min(max(avail, 0.0), S_max)
        S[i] = s
        Q[i] = q
    return S, Q
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_state.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add Automation/longrange_state.py tests/test_longrange_state.py
git commit -m "feat: longrange antecedent state (API + soil-moisture bucket, the J-fix)"
```

---

## Task 4: Deep ERA5 ingestion from Open-Meteo archive

**Files:**
- Create: `Automation/longrange_fetch_era5.py`
- Test: `tests/test_longrange_fetch_era5.py`

Mirrors `kinneret_app/met_update.py` Open-Meteo archive usage. The archive API is ERA5-backed and serves data from 1940; we request from 1960 to match the level record.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_fetch_era5.py
import sys
from datetime import date
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


def test_parse_archive_payload_to_frame(monkeypatch):
    """A daily payload maps onto tidy columns (date, temp_max_C, temp_min_C, ...)."""
    import longrange_fetch_era5 as f
    payload = {"daily": {
        "time": ["1960-01-01", "1960-01-02"],
        "temperature_2m_max": [14.0, 15.5],
        "temperature_2m_min": [6.0, 7.0],
        "precipitation_sum": [0.0, 12.3],
        "shortwave_radiation_sum": [9.1, 4.2],
        "relative_humidity_2m_mean": [70.0, 88.0],
        "wind_speed_10m_mean": [10.8, 7.2],   # km/h in Open-Meteo
    }}
    monkeypatch.setattr(f.requests, "get", lambda *a, **k: _FakeResp(payload))
    df = f.fetch_era5_daily(date(1960, 1, 1), date(1960, 1, 2))
    assert list(df["date"].astype(str)) == ["1960-01-01", "1960-01-02"]
    assert df.loc[1, "temp_max_C"] == 15.5
    assert df.loc[1, "rainfall_mm"] == 12.3
    # wind converted km/h -> m/s
    assert abs(df.loc[0, "wind_speed_ms"] - 10.8 / 3.6) < 1e-9


def test_empty_payload_returns_empty_frame(monkeypatch):
    import longrange_fetch_era5 as f
    monkeypatch.setattr(f.requests, "get", lambda *a, **k: _FakeResp({"daily": {}}))
    df = f.fetch_era5_daily(date(1960, 1, 1), date(1960, 1, 2))
    assert df.empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_fetch_era5.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_fetch_era5'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_fetch_era5.py
"""
longrange_fetch_era5.py - Deep ERA5 daily history for the Kinneret point via the
Open-Meteo archive API (ERA5-backed, 1940-present). Mirrors kinneret_app/met_update.py.

Writes Silver Data/Meteorological/era5_kinneret_daily.csv with tidy columns:
  date, temp_max_C, temp_min_C, rainfall_mm, radiation_MJm2, humidity_pct, wind_speed_ms
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import requests

_LAT = 32.7724    # Open-Meteo grid point (same as met_update.py)
_LON = 35.5458
_TZ = "Asia/Jerusalem"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_START = date(1960, 1, 1)

OUT_PATH = (Path(__file__).resolve().parent.parent
            / "Silver Data" / "Meteorological" / "era5_kinneret_daily.csv")

# Open-Meteo daily var -> (tidy column, unit factor)
_VAR_MAP = [
    ("temperature_2m_max",        "temp_max_C",     1.0),
    ("temperature_2m_min",        "temp_min_C",     1.0),
    ("precipitation_sum",         "rainfall_mm",    1.0),
    ("shortwave_radiation_sum",   "radiation_MJm2", 1.0),   # already MJ/m2
    ("relative_humidity_2m_mean", "humidity_pct",   1.0),
    ("wind_speed_10m_mean",       "wind_speed_ms",  1 / 3.6),  # km/h -> m/s
]


def fetch_era5_daily(from_date: date, to_date: date) -> pd.DataFrame:
    daily_vars = [v for v, _, _ in _VAR_MAP]
    r = requests.get(_ARCHIVE_URL, params={
        "latitude": _LAT, "longitude": _LON,
        "start_date": str(from_date), "end_date": str(to_date),
        "daily": ",".join(daily_vars), "timezone": _TZ,
    }, timeout=120)
    r.raise_for_status()
    data = r.json().get("daily", {})
    if not data or not data.get("time"):
        return pd.DataFrame()
    out = pd.DataFrame({"date": pd.to_datetime(data["time"]).date})
    for var, col, factor in _VAR_MAP:
        if var in data:
            out[col] = pd.to_numeric(pd.Series(data[var]), errors="coerce") * factor
    return out


def main():
    df = fetch_era5_daily(DEFAULT_START, date.today())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} rows ({df['date'].min()}..{df['date'].max()}) to {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_fetch_era5.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Fetch the real data and sanity-check**

Run: `python Automation/longrange_fetch_era5.py`
Expected: prints `Wrote ~24000 rows (1960-01-01..2026-...)`. If Open-Meteo rejects the 1960 start, note the earliest accepted date in the commit message and set `DEFAULT_START` accordingly.

- [ ] **Step 6: Commit**

```bash
git add Automation/longrange_fetch_era5.py tests/test_longrange_fetch_era5.py
git commit -m "feat: deep ERA5 ingestion via Open-Meteo archive (1960-present)"
```

---

## Task 5: ERA5 -> gold bias correction (monthly quantile mapping)

**Files:**
- Create: `Automation/longrange_bias_correct.py`
- Test: `tests/test_longrange_bias_correct.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_bias_correct.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_quantile_map_shifts_distribution_onto_reference():
    """Mapping a biased source onto a reference matches the reference mean closely."""
    from longrange_bias_correct import quantile_map
    rng = np.random.default_rng(0)
    ref = rng.normal(20.0, 2.0, 2000)     # station truth
    src = rng.normal(23.0, 2.0, 2000)     # ERA5, +3 warm bias
    corrected = quantile_map(src, ref)
    assert abs(np.mean(corrected) - np.mean(ref)) < 0.3
    assert abs(np.std(corrected) - np.std(ref)) < 0.3


def test_quantile_map_is_monotonic():
    """Quantile mapping preserves ordering of source values."""
    from longrange_bias_correct import quantile_map
    rng = np.random.default_rng(1)
    ref = rng.normal(0, 1, 500)
    src = np.array([1.0, 2.0, 3.0, 4.0])
    out = quantile_map(src, ref)
    assert np.all(np.diff(out) >= 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_bias_correct.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_bias_correct'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_bias_correct.py
"""
longrange_bias_correct.py - Group 8 monthly empirical quantile mapping of the deep
ERA5 record onto the IMS gold distribution, calibrated on the 2012-2024 overlap.
Without this the model would learn a fake discontinuity at the splice.

Temperature columns use quantile mapping (handles mean + variance bias). Run as a
script to produce era5_kinneret_daily_corrected.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ERA5_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily.csv"
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
OUT_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily_corrected.csv"

OVERLAP_START = "2012-01-01"
OVERLAP_END = "2024-12-31"
# ERA5 tidy column -> gold reference column
CORRECT_COLS = {
    "temp_max_C": "temp_max_C",
    "temp_min_C": "temp_min_C",
    "rainfall_mm": "rainfall_mm",
}


def quantile_map(src, ref):
    """Empirical quantile mapping: map each src value to the ref value at the same
    empirical rank. Returns array same shape as src."""
    src = np.asarray(src, dtype=float)
    ref = np.asarray(ref, dtype=float)
    ref = ref[~np.isnan(ref)]
    ref_sorted = np.sort(ref)
    n = ref_sorted.size
    ref_q = (np.arange(n) + 0.5) / n
    src_sorted = np.sort(src[~np.isnan(src)])
    m = src_sorted.size
    # empirical CDF rank of each src value within the src distribution
    ranks = (np.searchsorted(src_sorted, src, side="right") - 0.5) / max(m, 1)
    ranks = np.clip(ranks, 0, 1)
    return np.interp(ranks, ref_q, ref_sorted)


def correct_dataframe(era5: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    era5 = era5.copy()
    era5["date"] = pd.to_datetime(era5["date"])
    gold = gold.copy()
    gold["date"] = pd.to_datetime(gold["date"])
    overlap = gold[(gold["date"] >= OVERLAP_START) & (gold["date"] <= OVERLAP_END)]
    era5["month"] = era5["date"].dt.month
    overlap = overlap.assign(month=overlap["date"].dt.month)
    era5_ov = era5[(era5["date"] >= OVERLAP_START) & (era5["date"] <= OVERLAP_END)]

    for ecol, gcol in CORRECT_COLS.items():
        if ecol not in era5.columns or gcol not in gold.columns:
            continue
        for m in range(1, 13):
            ref = overlap.loc[overlap["month"] == m, gcol].values
            src_overlap = era5_ov.loc[era5_ov["month"] == m, ecol].values
            if ref.size < 30 or src_overlap.size < 30:
                continue   # not enough overlap to calibrate this month
            mask = era5["month"] == m
            era5.loc[mask, ecol] = quantile_map(era5.loc[mask, ecol].values, ref)
    return era5.drop(columns="month")


def main():
    era5 = pd.read_csv(ERA5_PATH, encoding="utf-8-sig")
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    out = correct_dataframe(era5, gold)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote bias-corrected ERA5 ({len(out)} rows) to {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_bias_correct.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run on real data and sanity-check the splice**

Run: `python Automation/longrange_bias_correct.py`
Expected: prints row count. Sanity check (manual): corrected ERA5 monthly means over 2012-2024 should sit within ~0.5°C of gold monthly means for temp columns.

- [ ] **Step 6: Commit**

```bash
git add Automation/longrange_bias_correct.py tests/test_longrange_bias_correct.py
git commit -m "feat: monthly quantile-mapping bias correction ERA5 -> gold"
```

---

## Task 6: Calibrate Hargreaves against Penman-Monteith ET₀

**Files:**
- Create: `Automation/longrange_calibrate_hargreaves.py`
- Test: `tests/test_longrange_calibrate_hargreaves.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_calibrate_hargreaves.py
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_fit_recovers_known_linear_relation():
    """If et0_pm = a*et0_hs + b exactly, the fit recovers a and b."""
    from longrange_calibrate_hargreaves import fit_linear_calibration
    rng = np.random.default_rng(0)
    et0_hs = rng.uniform(1, 9, 500)
    et0_pm = 1.15 * et0_hs - 0.3
    a, b = fit_linear_calibration(et0_hs, et0_pm)
    assert abs(a - 1.15) < 1e-6
    assert abs(b + 0.3) < 1e-6


def test_calibration_drops_nan_rows():
    """Rows where either ET0 is NaN are ignored."""
    from longrange_calibrate_hargreaves import fit_linear_calibration
    et0_hs = np.array([1.0, 2.0, np.nan, 4.0])
    et0_pm = np.array([1.1, np.nan, 3.0, 4.4])
    a, b = fit_linear_calibration(et0_hs, et0_pm)
    assert np.isfinite(a) and np.isfinite(b)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_calibrate_hargreaves.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_calibrate_hargreaves.py
"""
longrange_calibrate_hargreaves.py - Calibrate temp-only Hargreaves ET0 to the
model's trained Penman-Monteith et0_mm scale (Group 2 calibration note).

Fits et0_pm ~ a*et0_hs + b over the gold record (where both exist) and writes the
linear calibration to docs/longrange_config.json so downstream code reproduces the
ET0 scale the existing model was trained on.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from longrange_meteo import hargreaves_et0

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
CONFIG_PATH = ROOT / "docs" / "longrange_config.json"


def fit_linear_calibration(et0_hs, et0_pm):
    """Least-squares fit et0_pm = a*et0_hs + b. Returns (a, b). Drops NaN rows."""
    x = np.asarray(et0_hs, dtype=float)
    y = np.asarray(et0_pm, dtype=float)
    ok = ~np.isnan(x) & ~np.isnan(y)
    A = np.column_stack([x[ok], np.ones(ok.sum())])
    (a, b), *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    return float(a), float(b)


def main():
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    gold["date"] = pd.to_datetime(gold["date"])
    doy = gold["date"].dt.dayofyear.values
    et0_hs = hargreaves_et0(gold["temp_max_C"].values, gold["temp_min_C"].values, doy)
    a, b = fit_linear_calibration(et0_hs, gold["et0_mm"].values)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(
        {"hargreaves_calibration": {"slope": a, "intercept": b,
         "note": "et0_pm ~= slope*et0_hs + intercept, fit on gold"}}, indent=2))
    print(f"Hargreaves calibration: slope={a:.4f} intercept={b:.4f} -> {CONFIG_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_calibrate_hargreaves.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run on real data**

Run: `python Automation/longrange_calibrate_hargreaves.py`
Expected: prints slope/intercept (slope plausibly ~0.9-1.2) and writes `docs/longrange_config.json`.

- [ ] **Step 6: Commit**

```bash
git add Automation/longrange_calibrate_hargreaves.py tests/test_longrange_calibrate_hargreaves.py docs/longrange_config.json
git commit -m "feat: calibrate Hargreaves ET0 to Penman-Monteith scale"
```

---

## Task 7: Build per-DOY climatology + modern outflow climatology table

**Files:**
- Create: `Automation/longrange_build_climatology.py`
- Test: extend `tests/test_longrange_climatology.py` (one integration test)

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_longrange_climatology.py
def test_build_climatology_table_has_all_doys_and_columns(tmp_path):
    """The build produces one row per DOY (1..366) with all normal columns."""
    import importlib, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))
    bc = importlib.import_module("longrange_build_climatology")
    import numpy as np, pandas as pd
    rng = np.random.default_rng(0)
    dates = pd.date_range("2000-01-01", "2010-12-31")
    doy = dates.dayofyear.values
    df = pd.DataFrame({
        "date": dates,
        "temp_max_C": 25 + 8 * np.sin(2 * np.pi * doy / 365) + rng.normal(0, 1, len(doy)),
        "temp_min_C": 14 + 6 * np.sin(2 * np.pi * doy / 365) + rng.normal(0, 1, len(doy)),
        "rainfall_mm": np.where((doy < 90) | (doy > 305), rng.uniform(0, 20, len(doy)), 0.0),
        "et0_mm": 4 + 2 * np.sin(2 * np.pi * doy / 365) + rng.normal(0, 0.2, len(doy)),
        "outflow_baptism_m3": rng.uniform(0.2e6, 0.6e6, len(doy)),
    })
    out = bc.build_climatology(df, modern_df=df)
    assert len(out) == 366
    for col in ["doy", "temp_max_clim", "temp_min_clim", "dtr_clim",
                "dtr_clearsky", "et0_clim", "p_wet_clim", "amount_clim",
                "outflow_clim"]:
        assert col in out.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_longrange_climatology.py::test_build_climatology_table_has_all_doys_and_columns -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'longrange_build_climatology'`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_build_climatology.py
"""
longrange_build_climatology.py - Build the per-day-of-year normals table used by
the long-range model. Meteorological normals come from the deep (bias-corrected)
record; outflow climatology comes from the MODERN record only (2012+), because
pumping policy is non-stationary (Group 9).

Writes Gold Data/longrange_climatology.csv keyed by doy (1..366).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from longrange_climatology import (fit_harmonic, eval_harmonic, fit_rain_climatology,
                                    clearsky_dtr_by_doy)

ROOT = Path(__file__).resolve().parent.parent
DEEP_PATH = ROOT / "Silver Data" / "Meteorological" / "era5_kinneret_daily_corrected.csv"
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
OUT_PATH = ROOT / "Gold Data" / "longrange_climatology.csv"
MODERN_START = "2012-01-01"


def build_climatology(deep_df: pd.DataFrame, modern_df: pd.DataFrame) -> pd.DataFrame:
    deep = deep_df.copy()
    deep["date"] = pd.to_datetime(deep["date"])
    doy = deep["date"].dt.dayofyear.values
    dtr = (deep["temp_max_C"] - deep["temp_min_C"]).values

    tmax_c = fit_harmonic(doy, deep["temp_max_C"].values)
    tmin_c = fit_harmonic(doy, deep["temp_min_C"].values)
    dtr_c = fit_harmonic(doy, dtr)
    dtr_cs_c = clearsky_dtr_by_doy(doy, dtr)
    et0_c = fit_harmonic(doy, deep["et0_mm"].values) if "et0_mm" in deep else None
    pwet_c, amt_c = fit_rain_climatology(doy, deep["rainfall_mm"].values)

    modern = modern_df.copy()
    modern["date"] = pd.to_datetime(modern["date"])
    modern = modern[modern["date"] >= MODERN_START]
    mdoy = modern["date"].dt.dayofyear.values
    outflow_c = fit_harmonic(mdoy, modern["outflow_baptism_m3"].values)

    grid = np.arange(1, 367, dtype=float)
    out = pd.DataFrame({
        "doy": grid.astype(int),
        "temp_max_clim": eval_harmonic(grid, tmax_c),
        "temp_min_clim": eval_harmonic(grid, tmin_c),
        "dtr_clim": eval_harmonic(grid, dtr_c),
        "dtr_clearsky": eval_harmonic(grid, dtr_cs_c),
        "et0_clim": eval_harmonic(grid, et0_c) if et0_c is not None else np.nan,
        "p_wet_clim": np.clip(eval_harmonic(grid, pwet_c), 0, 1),
        "amount_clim": np.clip(eval_harmonic(grid, amt_c), 0, None),
        "outflow_clim": eval_harmonic(grid, outflow_c),
    })
    return out


def main():
    deep = pd.read_csv(DEEP_PATH, encoding="utf-8-sig")
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    out = build_climatology(deep, gold)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Wrote climatology ({len(out)} DOY rows) to {OUT_PATH}")


if __name__ == "__main__":
    main()
```

Note: the integration test calls `build_climatology(df, modern_df=df)` with a frame
lacking `et0_mm`-free path covered (the synthetic frame includes `et0_mm`), so the
`et0_c is not None` branch is exercised.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_longrange_climatology.py -v`
Expected: PASS (all, including the new integration test).

- [ ] **Step 5: Run on real data**

Run: `python Automation/longrange_build_climatology.py`
Expected: writes `Gold Data/longrange_climatology.csv` with 366 rows.

- [ ] **Step 6: Commit**

```bash
git add Automation/longrange_build_climatology.py tests/test_longrange_climatology.py
git commit -m "feat: build per-DOY climatology + modern outflow climatology table"
```

---

## Task 8: Premise-check gate — does temperature predict rain in our data?

**Files:**
- Create: `Automation/longrange_premise_check.py`
- Test: `tests/test_longrange_premise_check.py`

This is the make-or-break gate from the spec's Phase A. It quantifies, on the gold
record, whether the temp-derived rain signature (low DTR + negative Tmax anomaly,
in the wet season) actually predicts rainfall/inflow. If it doesn't, the whole
product premise is dead and Phase B should not start.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_premise_check.py
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_wet_day_auc_detects_real_signal():
    """When cloud_index genuinely drives wet days, AUC should be well above 0.5."""
    from longrange_premise_check import wet_day_auc
    rng = np.random.default_rng(0)
    cloud = rng.uniform(0, 1, 2000)
    wet = rng.random(2000) < cloud          # higher cloud -> more likely wet
    auc = wet_day_auc(cloud, wet)
    assert auc > 0.7


def test_wet_day_auc_half_for_noise():
    """Random predictor gives AUC ~ 0.5."""
    from longrange_premise_check import wet_day_auc
    rng = np.random.default_rng(1)
    cloud = rng.uniform(0, 1, 4000)
    wet = rng.random(4000) < 0.3            # independent of cloud
    auc = wet_day_auc(cloud, wet)
    assert 0.45 < auc < 0.55


def test_evaluate_premise_returns_pass_fail(tmp_path):
    """evaluate_premise computes wet-season AUC and a PASS/FAIL verdict."""
    from longrange_premise_check import evaluate_premise
    rng = np.random.default_rng(2)
    dates = pd.date_range("2013-01-01", "2020-12-31")
    doy = dates.dayofyear.values
    # winter wet, driven by compressed DTR; summer dry
    is_winter = (doy < 90) | (doy > 305)
    dtr = np.where(is_winter, rng.uniform(3, 14, len(doy)), rng.uniform(10, 16, len(doy)))
    wetp = np.where(is_winter, np.clip((14 - dtr) / 14, 0, 1) * 0.8, 0.02)
    rain = np.where(rng.random(len(doy)) < wetp, rng.uniform(1, 25, len(doy)), 0.0)
    gold = pd.DataFrame({
        "date": dates,
        "temp_max_C": 20 - 0.0 + dtr,   # ensure Tmax>Tmin
        "temp_min_C": 20.0,
        "rainfall_mm": rain,
        "inflow_obstacle_m3": rain * 1e5 + rng.uniform(0, 1e5, len(doy)),
    })
    result = evaluate_premise(gold, auc_threshold=0.6)
    assert "wet_season_auc" in result
    assert result["verdict"] in ("PASS", "FAIL")
    assert result["verdict"] == "PASS"      # signal is real in this fixture
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_longrange_premise_check.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# Automation/longrange_premise_check.py
"""
longrange_premise_check.py - PHASE A MAKE-OR-BREAK GATE.

Quantifies whether the temperature-derived rain signature (cloud_index from low
DTR vs the clear-sky envelope, plus negative Tmax anomaly), in the wet season,
actually predicts wet days / rainfall / inflow in the gold record. If the
wet-season AUC is below threshold, the product premise fails and Phase B must not
start. Writes docs/longrange_premise_report.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from longrange_meteo import cloud_index
from longrange_climatology import (fit_harmonic, eval_harmonic, clearsky_dtr_by_doy,
                                    anomaly_zscore)

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
REPORT_PATH = ROOT / "docs" / "longrange_premise_report.md"
WET_SEASON_MONTHS = {11, 12, 1, 2, 3}     # Nov-Mar
REQUIRED_COLS = ["date", "temp_max_C", "temp_min_C", "rainfall_mm"]


def wet_day_auc(score, wet):
    """ROC AUC of a continuous `score` predicting a binary `wet` label, via the
    Mann-Whitney U relationship. No sklearn dependency."""
    score = np.asarray(score, dtype=float)
    wet = np.asarray(wet, dtype=bool)
    ok = ~np.isnan(score)
    score, wet = score[ok], wet[ok]
    n_pos, n_neg = wet.sum(), (~wet).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(score, return_inverse=True, return_counts=True)
    sum_ranks = np.zeros(len(counts))
    np.add.at(sum_ranks, inv, ranks)
    ranks = (sum_ranks / counts)[inv]
    auc = (ranks[wet].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def evaluate_premise(gold: pd.DataFrame, auc_threshold=0.6):
    missing = [c for c in REQUIRED_COLS if c not in gold.columns]
    if missing:
        raise ValueError(f"gold table missing required columns: {missing}")
    g = gold.copy()
    g["date"] = pd.to_datetime(g["date"])
    doy = g["date"].dt.dayofyear.values
    dtr = (g["temp_max_C"] - g["temp_min_C"]).values

    dtr_cs = eval_harmonic(doy, clearsky_dtr_by_doy(doy, dtr))
    ci = cloud_index(dtr, dtr_cs)
    tmax_mean_c = fit_harmonic(doy, g["temp_max_C"].values)
    tmax_anom_z = anomaly_zscore(doy, g["temp_max_C"].values, tmax_mean_c)
    # combined rain-propensity score: cloudier + colder-than-normal => wetter
    score = ci - 0.5 * tmax_anom_z

    wet = g["rainfall_mm"].values > 1.0
    is_wet_season = g["date"].dt.month.isin(WET_SEASON_MONTHS).values

    overall_auc = wet_day_auc(score, wet)
    wet_season_auc = wet_day_auc(score[is_wet_season], wet[is_wet_season])
    # correlation of cloud_index with same-day rainfall (wet season)
    ws = is_wet_season
    corr = np.corrcoef(ci[ws], g["rainfall_mm"].values[ws])[0, 1]

    verdict = "PASS" if (wet_season_auc >= auc_threshold) else "FAIL"
    return {
        "overall_auc": overall_auc,
        "wet_season_auc": wet_season_auc,
        "wet_season_cloud_rain_corr": float(corr),
        "auc_threshold": auc_threshold,
        "verdict": verdict,
    }


def main():
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    res = evaluate_premise(gold)
    lines = [
        "# Long-Range Forecast - Premise Check (Phase A gate)", "",
        f"- Wet-season wet-day AUC: **{res['wet_season_auc']:.3f}** "
        f"(threshold {res['auc_threshold']:.2f})",
        f"- Overall wet-day AUC: {res['overall_auc']:.3f}",
        f"- Wet-season cloud_index vs rainfall corr: {res['wet_season_cloud_rain_corr']:.3f}",
        "", f"## Verdict: **{res['verdict']}**", "",
        "PASS => proceed to Phase B bake-off. FAIL => temperature does not carry"
        " enough rain signal in our data; revisit the premise before modeling.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_longrange_premise_check.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the gate on real gold data**

Run: `python Automation/longrange_premise_check.py`
Expected: prints the report and writes `docs/longrange_premise_report.md`. **Record the verdict** — a PASS unlocks Phase B; a FAIL means stop and report back before any modeling.

- [ ] **Step 6: Commit**

```bash
git add Automation/longrange_premise_check.py tests/test_longrange_premise_check.py docs/longrange_premise_report.md
git commit -m "feat: Phase A premise-check gate (temp->rain signal in gold)"
```

---

## Task 9: Full Phase A run + suite verification

**Files:** none new — verification only.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: all prior tests still pass plus the new longrange tests (no regressions to the 7-day model — none of its files were touched).

- [ ] **Step 2: Run the Phase A pipeline end to end**

```bash
python Automation/longrange_fetch_era5.py
python Automation/longrange_bias_correct.py
python Automation/longrange_calibrate_hargreaves.py
python Automation/longrange_build_climatology.py
python Automation/longrange_premise_check.py
```
Expected: each prints its summary; the four data artifacts and the premise report exist.

- [ ] **Step 3: Report the gate verdict**

Summarize the premise-check verdict and the climatology/calibration numbers. If PASS, Phase B planning can begin. If FAIL, stop and surface the numbers for a premise rethink (per spec, the temp→rain premise is make-or-break).

- [ ] **Step 4: Commit any data-artifact gitignore updates if needed**

```bash
git add .gitignore
git commit -m "chore: gitignore long-range data artifacts" || echo "nothing to commit"
```

---

## Self-review notes

- **Spec coverage:** Phase A items all mapped — deepen record (Tasks 4–5), validate premise (Task 8), calibrate Hargreaves (Task 6), build climatology + outflow climatology (Task 7); calculation Groups 1–6 + 8 implemented as the library (Tasks 1–3, 5). Groups 7 (rain hurdle), 9 outflow-anchor *use*, 10–12 (volume→level, bands, evaluation) belong to Phase B/C and are intentionally deferred.
- **No placeholders:** every code/test step contains complete runnable code.
- **Type/name consistency:** `extraterrestrial_radiation`, `hargreaves_et0`, `cloud_index`, `fit_harmonic`/`eval_harmonic`, `fit_rain_climatology`, `clearsky_dtr_by_doy`, `anomaly_zscore`, `antecedent_precip_index`, `soil_moisture_bucket`, `fetch_era5_daily`, `quantile_map`, `fit_linear_calibration`, `build_climatology`, `wet_day_auc`, `evaluate_premise` are defined once and referenced consistently.
- **Deferred to Phase B (own plan):** the J-guardrails (collinearity gate, fold-failure test, ablation) operate on trained models, so they live with Phase B; Task 3 only builds the bucket they will scrutinize.
