# CORDEX Climate Scenario Product — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Streamlit page 9 that turns the 12-model CORDEX RCP4.5/RCP8.5 ensemble into a Kinneret water-balance climate projection to 2050/2100, using the Phase A physics pipeline already on disk.

**Architecture:** Physics-based water balance (Hargreaves ET₀ from calibrated slope/intercept + cloud-index rain propensity + soil-moisture bucket + outflow climatology) run per (model, scenario) pair over both CORDEX sites, calibrated against the 2006-2024 observed level record via a single scalar `catchment_scale`, projected forward and cached as parquet, then visualised in three dashboard tabs.

**Tech Stack:** pandas, numpy, pyarrow, scipy.optimize, plotly, streamlit; Phase A modules: `longrange_meteo`, `longrange_climatology`, `longrange_state` (all in `Automation/`).

---

## File map

| File | Action | Role |
|---|---|---|
| `Automation/longrange_cordex_ingest.py` | Create | Load both CORDEX CSVs, winsorize tmax, cache as parquet |
| `Automation/longrange_cordex_waterbalance.py` | Create | Physics chain per (model, scenario); output daily ΔV + level; cache parquet |
| `Automation/longrange_cordex_calibrate.py` | Create | Fit `catchment_scale` + `S_max` on 2006–2024 gold; write `docs/cordex_config.json` |
| `Automation/longrange_cordex_hindcast.py` | Create | Evaluate 2006–2024 projection vs observed; append RMSE/corr to config |
| `kinneret_app/pages/9_Climate_Scenarios.py` | Create | Streamlit page: 3 tabs (evap demand, water balance, hindcast check) |
| `tests/test_longrange_cordex_ingest.py` | Create | Winsorization, schema, site coverage |
| `tests/test_longrange_cordex_waterbalance.py` | Create | Mass balance, vol↔level round-trip, anchor propagation |
| `tests/test_longrange_cordex_calibrate.py` | Create | Calibration convergence and config I/O |
| `docs/cordex_config.json` | Written by scripts | `catchment_scale_Mm3_per_mm`, `S_max_mm`, `anchor_date`, `anchor_level_m`, `hindcast_rmse_m`, `hindcast_corr` |

---

## Task 1: CORDEX ingest module

**Files:**
- Create: `Automation/longrange_cordex_ingest.py`
- Create: `tests/test_longrange_cordex_ingest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_cordex_ingest.py
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_fake_csv(tmp_path, site, n=10):
    """Write a minimal CORDEX-shaped CSV to tmp_path."""
    import io
    rows = []
    for i in range(n):
        rows.append({
            "year": 2006, "month": 1, "day": i + 1,
            "tmin": 5.0 + i * 0.1,
            "tmax": 55.0 if i == 0 else 20.0 + i * 0.1,  # one outlier
            "model": "cnrm_cclm",
            "scenario": "rcp45",
        })
    df = pd.DataFrame(rows)
    p = tmp_path / f"{site}_tmin_tmax_12models_rcp45_rcp85_qdm.csv"
    df.to_csv(p, index=False)
    return p


def test_winsorize_clips_tmax_above_49(tmp_path, monkeypatch):
    """tmax values above 49°C must be capped at 49°C at ingestion."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    assert df["tmax"].max() <= 49.0


def test_schema_and_sites(tmp_path, monkeypatch):
    """Output must have required columns and both sites."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    for col in ["date", "model", "scenario", "site", "tmin", "tmax", "doy"]:
        assert col in df.columns, f"missing column: {col}"
    assert set(df["site"].unique()) == {"bet_zayda", "zemah"}


def test_doy_range(tmp_path, monkeypatch):
    """DOY must be in 1–366."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    assert df["doy"].between(1, 366).all()
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_longrange_cordex_ingest.py -v
```
Expected: `ModuleNotFoundError: No module named 'longrange_cordex_ingest'`

- [ ] **Step 3: Write the ingest module**

```python
# Automation/longrange_cordex_ingest.py
"""
CORDEX ensemble ingest — load both site CSVs, winsorize tmax, cache as parquet.

Winsorize at ingestion per project rule: the QDM hot-tail artifact (tmax up to
57°C, all 12 models, Aug-heavy) must be clipped before ANY downstream computation.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORDEX_FILES = {
    "bet_zayda": PROJECT_ROOT / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    "zemah":     PROJECT_ROOT / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
}
CACHE_PATH = PROJECT_ROOT / "Gold Data" / "cordex_ensemble.parquet"
TMAX_CAP = 49.0  # °C — QDM tail-inflation artifact above this threshold


def load_cordex(cache: bool = True) -> pd.DataFrame:
    """Load both CORDEX site files, winsorize tmax, return long DataFrame.

    Columns: date (datetime64[ns]), model (str), scenario (str), site (str),
             tmin (float64), tmax (float64), doy (int).
    """
    if cache and CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)
    frames = []
    for site, path in CORDEX_FILES.items():
        df = pd.read_csv(path)
        df["tmax"] = df["tmax"].clip(upper=TMAX_CAP)
        df["site"] = site
        df["date"] = pd.to_datetime(df[["year", "month", "day"]])
        df = df.drop(columns=["year", "month", "day"])
        frames.append(df[["date", "model", "scenario", "site", "tmin", "tmax"]])
    out = pd.concat(frames, ignore_index=True)
    out["doy"] = out["date"].dt.day_of_year
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE_PATH, index=False)
    return out


if __name__ == "__main__":
    df = load_cordex(cache=False)
    print(f"Loaded {len(df):,} rows | tmax max={df['tmax'].max():.1f}°C (capped at {TMAX_CAP})")
    print(df.groupby(["site", "scenario"])["model"].nunique().rename("n_models"))
```

- [ ] **Step 4: Run tests to confirm they pass**

```
python -m pytest tests/test_longrange_cordex_ingest.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```
git add Automation/longrange_cordex_ingest.py tests/test_longrange_cordex_ingest.py
git commit -m "feat: CORDEX ingest module (winsorize + parquet cache)"
```

---

## Task 2: Water balance module

**Files:**
- Create: `Automation/longrange_cordex_waterbalance.py`
- Create: `tests/test_longrange_cordex_waterbalance.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_cordex_waterbalance.py
import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_cordex_long(n_days=30):
    """Minimal long-frame CORDEX fixture: 1 model × 1 scenario × 2 sites × n days."""
    dates = pd.date_range("2006-01-01", periods=n_days)
    rows = []
    for site in ["bet_zayda", "zemah"]:
        for d in dates:
            rows.append({
                "date": d, "model": "cnrm_cclm", "scenario": "rcp45",
                "site": site, "tmin": 8.0, "tmax": 20.0,
                "doy": d.day_of_year,
            })
    return pd.DataFrame(rows)


def _make_clim(tmp_path):
    """Write a minimal climatology CSV (all DOYs, constant values)."""
    doys = list(range(1, 367))
    df = pd.DataFrame({
        "doy": doys,
        "temp_max_clim": [20.0] * 366,
        "temp_min_clim": [8.0] * 366,
        "dtr_clim": [12.0] * 366,
        "dtr_clearsky": [15.0] * 366,
        "et0_clim": [3.0] * 366,
        "p_wet_clim": [0.2] * 366,
        "amount_clim": [10.0] * 366,
        "outflow_clim": [400000.0] * 366,   # m³/day
    })
    p = tmp_path / "longrange_climatology.csv"
    df.to_csv(p, index=False)
    return p


def _make_configs(tmp_path):
    """Write minimal longrange_config.json and cordex_config.json."""
    cfg = {"hargreaves_calibration": {"slope": 1.0, "intercept": 0.0}}
    (tmp_path / "longrange_config.json").write_text(json.dumps(cfg))
    ccfg = {"catchment_scale_Mm3_per_mm": 1.0, "S_max_mm": 150.0,
            "bathy_vol2level_coeffs": [-3.83e-7, 0.00917, -241.44]}
    (tmp_path / "cordex_config.json").write_text(json.dumps(ccfg))
    return tmp_path / "longrange_config.json", tmp_path / "cordex_config.json"


def test_level_from_volume_round_trip():
    """level_from_volume and volume_from_level must be mutual inverses."""
    import longrange_cordex_waterbalance as wb
    coeffs = [-3.83e-7, 0.00917, -241.44]
    for vol in [3400.0, 3800.0, 4200.0]:
        level = wb.level_from_volume(vol, coeffs)
        vol_back = wb.volume_from_level(level, coeffs)
        assert abs(vol_back - vol) < 0.1, f"round-trip failed at vol={vol}"


def test_run_water_balance_output_schema(tmp_path, monkeypatch):
    """run_water_balance must return required columns for every (model, scenario) pair."""
    import longrange_cordex_waterbalance as wb
    monkeypatch.setattr(wb, "CFG_PATH", tmp_path / "longrange_config.json")
    monkeypatch.setattr(wb, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(wb, "CLIM_PATH", tmp_path / "longrange_climatology.csv")
    _make_configs(tmp_path)
    _make_clim(tmp_path)
    cordex = _make_cordex_long(n_days=30)
    result = wb.run_water_balance(cordex, anchor_level_m=-211.65, anchor_date="2006-01-01")
    for col in ["date", "model", "scenario", "dv_Mm3", "volume_Mm3", "level_m",
                "lake_ET_Mm3", "P_est_mm", "runoff_mm"]:
        assert col in result.columns, f"missing column: {col}"


def test_volume_integrates_from_anchor(tmp_path, monkeypatch):
    """volume_Mm3 on anchor_date must equal the anchor volume (within 0.5 Mm³)."""
    import longrange_cordex_waterbalance as wb
    monkeypatch.setattr(wb, "CFG_PATH", tmp_path / "longrange_config.json")
    monkeypatch.setattr(wb, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(wb, "CLIM_PATH", tmp_path / "longrange_climatology.csv")
    _make_configs(tmp_path)
    _make_clim(tmp_path)
    cordex = _make_cordex_long(n_days=30)
    result = wb.run_water_balance(cordex, anchor_level_m=-211.65, anchor_date="2006-01-01")
    anchor_row = result[result["date"] == pd.Timestamp("2006-01-01")]
    expected_vol = wb.volume_from_level(-211.65, [-3.83e-7, 0.00917, -241.44])
    assert abs(anchor_row["volume_Mm3"].iloc[0] - expected_vol) < 0.5
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/test_longrange_cordex_waterbalance.py -v
```
Expected: `ModuleNotFoundError: No module named 'longrange_cordex_waterbalance'`

- [ ] **Step 3: Write the water balance module**

```python
# Automation/longrange_cordex_waterbalance.py
"""
Physics-based water balance over the CORDEX ensemble.

Chain per (model, scenario):
  bet-zayda tmin/tmax -> Hargreaves ET0 (catchment) -> cloud_index -> rain propensity
  zemah     tmin/tmax -> Hargreaves ET0 (lake surface) -> open-water evaporation
  soil-moisture bucket -> runoff Q -> inflow Mm3
  ΔV = inflow - lake_ET - outflow_clim
  V_t = V_{t-1} + ΔV_t, anchored at first observed level

Outputs cached as Gold Data/cordex_waterbalance.parquet.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CFG_PATH       = PROJECT_ROOT / "docs" / "longrange_config.json"
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
CLIM_PATH      = PROJECT_ROOT / "Gold Data" / "longrange_climatology.csv"
LEVEL_PATH     = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
CACHE_PATH     = PROJECT_ROOT / "Gold Data" / "cordex_waterbalance.parquet"
LAKE_AREA_KM2  = 166.0   # km²; 1 mm × 166 km² × 0.001 = 0.166 Mm³


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
    # pick root in hydrological range 3000-5000 Mm³
    for v in (v1, v2):
        if 2000 < v < 6000:
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


def run_water_balance(
    cordex_long: pd.DataFrame,
    anchor_level_m: float,
    anchor_date: str,
) -> pd.DataFrame:
    """Run physics chain for every (model, scenario) pair in cordex_long.

    cordex_long: output of load_cordex() with both sites.
    Returns DataFrame with columns:
        date, model, scenario, dv_Mm3, volume_Mm3, level_m,
        lake_ET_Mm3, P_est_mm, runoff_mm, et0_lake_mm, et0_catch_mm
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_meteo import hargreaves_et0, cloud_index
    from longrange_state import soil_moisture_bucket

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

        doy = bz_grp["doy"].values

        # Hargreaves ET0 (calibrated): ET0_cal = slope * ET0_HS + intercept
        et0_catch = np.clip(
            slope * hargreaves_et0(bz_grp["tmax"].values, bz_grp["tmin"].values, doy) + intercept,
            0, None)
        et0_lake = np.clip(
            slope * hargreaves_et0(zm_grp["tmax"].values, zm_grp["tmin"].values, doy) + intercept,
            0, None)
        lake_ET_Mm3 = et0_lake * LAKE_AREA_KM2 * 0.001

        # Rain propensity: scale DOY climatology by cloud_index anomaly
        dtr_bz = (bz_grp["tmax"] - bz_grp["tmin"]).values
        dtr_cs = clim.loc[doy, "dtr_clearsky"].values
        ci = cloud_index(dtr_bz, dtr_cs)
        ci_clim = cloud_index(clim.loc[doy, "dtr_clim"].values, dtr_cs)
        ci_clim = np.where(ci_clim < 0.01, 0.01, ci_clim)
        rain_scale = np.clip(ci / ci_clim, 0.0, 3.0)

        P_est = rain_scale * clim.loc[doy, "p_wet_clim"].values * clim.loc[doy, "amount_clim"].values

        # Soil-moisture bucket
        _, Q = soil_moisture_bucket(P_est, et0_catch, S_max=S_max)
        inflow_Mm3 = Q * catchment_scale

        # Outflow climatology (m³ → Mm³)
        outflow_Mm3 = clim.loc[doy, "outflow_clim"].values / 1e6

        dv = inflow_Mm3 - lake_ET_Mm3 - outflow_Mm3

        # Integrate volume from anchor date
        n = len(bz_grp)
        vol = np.empty(n)
        vol[:] = np.nan
        anchor_idx = int((bz_grp["date"] >= anchor_ts).idxmax()) if (bz_grp["date"] >= anchor_ts).any() else None
        if anchor_idx is not None:
            v = anchor_vol
            for i in range(anchor_idx, n):
                v += dv[i]
                vol[i] = v

        level_arr = np.where(np.isnan(vol), np.nan, level_from_volume(vol, bathy_coeffs))

        results.append(pd.DataFrame({
            "date":        bz_grp["date"].values,
            "model":       model,
            "scenario":    scenario,
            "dv_Mm3":      dv,
            "volume_Mm3":  vol,
            "level_m":     level_arr,
            "lake_ET_Mm3": lake_ET_Mm3,
            "P_est_mm":    P_est,
            "runoff_mm":   Q,
            "et0_lake_mm": et0_lake,
            "et0_catch_mm": et0_catch,
        }))

    return pd.concat(results, ignore_index=True)


def cache_water_balance(force: bool = False) -> pd.DataFrame:
    """Run water balance for the full CORDEX ensemble and cache as parquet.

    Reads anchor level from the observed level file (most recent date in gold).
    """
    if not force and CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```
python -m pytest tests/test_longrange_cordex_waterbalance.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```
git add Automation/longrange_cordex_waterbalance.py tests/test_longrange_cordex_waterbalance.py
git commit -m "feat: CORDEX physics water balance (ET0 + bucket + outflow integration)"
```

---

## Task 3: Calibration — fit `catchment_scale`

**Files:**
- Create: `Automation/longrange_cordex_calibrate.py`
- Create: `tests/test_longrange_cordex_calibrate.py`

The calibration exploits the fact that volume is **linear** in `catchment_scale`:
- `V(cs) = V_base + cs × cumsum(Q)` where `V_base = cumsum(−lake_ET − outflow)`
- So the optimal `cs` can be found with a 1-D bounded scalar search via `scipy.optimize`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_longrange_cordex_calibrate.py
import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_wb_result(catchment_scale=2.0, n=365):
    """Synthetic water balance output as if calibrated at catchment_scale=2.0."""
    dates = pd.date_range("2012-01-01", periods=n)
    # constant daily components
    Q_mm = 0.5     # mm/day runoff
    et_Mm3 = 0.2   # lake ET Mm3/day
    out_Mm3 = 0.4  # outflow Mm3/day
    dv = Q_mm * catchment_scale - et_Mm3 - out_Mm3
    vol = 3800.0 + np.cumsum(np.full(n, dv))
    coeffs = [-3.83e-7, 0.00917, -241.44]
    level = np.polyval(coeffs, vol)
    return pd.DataFrame({
        "date": dates, "model": "m1", "scenario": "rcp45",
        "dv_Mm3": dv, "volume_Mm3": vol, "level_m": level,
        "lake_ET_Mm3": et_Mm3, "P_est_mm": 1.0,
        "runoff_mm": Q_mm, "et0_lake_mm": 1.5, "et0_catch_mm": 1.2,
    })


def _make_obs(wb_df):
    """Observed level = the projected level + tiny noise (should recover cs=2)."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "date": wb_df["date"],
        "kinneret_level": wb_df["level_m"] + rng.normal(0, 0.02, len(wb_df)),
    })


def test_calibrate_recovers_true_scale(tmp_path, monkeypatch):
    """calibrate_catchment_scale must recover catchment_scale within 20%."""
    import longrange_cordex_calibrate as cal

    true_cs = 2.0
    wb = _make_wb_result(catchment_scale=true_cs)
    obs = _make_obs(wb)

    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(cal, "CFG_PATH",
                        Path(__file__).resolve().parent.parent / "docs" / "longrange_config.json")

    result = cal.calibrate_catchment_scale(wb_result=wb, obs_level=obs,
                                           bathy_coeffs=[-3.83e-7, 0.00917, -241.44])
    assert abs(result["catchment_scale_Mm3_per_mm"] - true_cs) / true_cs < 0.20


def test_calibrate_writes_config(tmp_path, monkeypatch):
    """calibrate_catchment_scale must write cordex_config.json with required keys."""
    import longrange_cordex_calibrate as cal

    wb = _make_wb_result(catchment_scale=2.0)
    obs = _make_obs(wb)
    monkeypatch.setattr(cal, "CORDEX_CFG_PATH", tmp_path / "cordex_config.json")
    monkeypatch.setattr(cal, "CFG_PATH",
                        Path(__file__).resolve().parent.parent / "docs" / "longrange_config.json")

    cal.calibrate_catchment_scale(wb_result=wb, obs_level=obs,
                                  bathy_coeffs=[-3.83e-7, 0.00917, -241.44])
    cfg = json.loads((tmp_path / "cordex_config.json").read_text())
    for key in ["catchment_scale_Mm3_per_mm", "S_max_mm", "bathy_vol2level_coeffs",
                "anchor_date", "anchor_level_m", "calibration_rmse_m"]:
        assert key in cfg, f"missing key: {key}"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python -m pytest tests/test_longrange_cordex_calibrate.py -v
```
Expected: `ModuleNotFoundError: No module named 'longrange_cordex_calibrate'`

- [ ] **Step 3: Write the calibration script**

```python
# Automation/longrange_cordex_calibrate.py
"""
Fit catchment_scale (Mm³/mm) on the 2006-2024 observed level record and write
docs/cordex_config.json.

Volume is linear in catchment_scale:
    V(cs) = V_base(t) + cs * cumQ(t)
where cumQ = cumsum(runoff_mm) and V_base = V0 + cumsum(-lake_ET - outflow).
This lets scipy.optimize.minimize_scalar solve in <1s.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

PROJECT_ROOT    = Path(__file__).resolve().parent.parent
CFG_PATH        = PROJECT_ROOT / "docs" / "longrange_config.json"
CORDEX_CFG_PATH = PROJECT_ROOT / "docs" / "cordex_config.json"
LEVEL_PATH      = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"
ANCHOR_DATE     = "2006-01-01"
ANCHOR_LEVEL_M  = -211.65
S_MAX_DEFAULT   = 150.0


def calibrate_catchment_scale(
    wb_result: pd.DataFrame,
    obs_level: pd.DataFrame,
    bathy_coeffs: list,
) -> dict:
    """Fit catchment_scale by minimising annual-mean-level RMSE on the overlap.

    wb_result: output of run_water_balance(...) with cs=1.0 over 2006-2024.
    obs_level: DataFrame with columns date (datetime64), kinneret_level (float).
    bathy_coeffs: [a, b, c] for np.polyval(bathy_coeffs, volume_Mm3) -> level_m.

    Returns and writes the full cordex_config dict.
    """
    import sys; sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_waterbalance import volume_from_level

    a, b, c = bathy_coeffs
    anchor_vol = volume_from_level(ANCHOR_LEVEL_M, bathy_coeffs)

    # Use ensemble median (model/scenario don't matter; cs applies uniformly)
    med = (
        wb_result.groupby("date")[["runoff_mm", "lake_ET_Mm3", "dv_Mm3"]]
        .median()
        .reset_index()
        .sort_values("date")
    )
    Q_arr      = med["runoff_mm"].values          # mm/day
    et_arr     = med["lake_ET_Mm3"].values         # Mm³/day
    # reconstruct outflow from stored dv = Q*cs - et - outflow (cs=1 at time of call)
    # dv = Q*1 - et - outflow  ->  outflow = Q - et - dv
    out_arr    = Q_arr - et_arr - med["dv_Mm3"].values  # Mm³/day
    cumQ       = np.cumsum(Q_arr)                 # Mm³/mm when multiplied by cs
    V_base     = anchor_vol + np.cumsum(-et_arr - out_arr)

    # Align with observed
    obs = (
        obs_level.copy()
        .rename(columns={"kinneret_level": "obs_level"})
        .assign(date=lambda d: pd.to_datetime(d["date"]))
        .set_index("date")
    )
    med = med.set_index("date")
    overlap = med.index.intersection(obs.index)
    if len(overlap) < 30:
        raise ValueError(f"Only {len(overlap)} overlapping dates — need ≥30")

    idx = [list(med.index).index(d) for d in overlap]
    obs_vals  = obs.loc[overlap, "obs_level"].values
    V_base_ov = V_base[idx]
    cumQ_ov   = cumQ[idx]

    def rmse(cs):
        vol_pred = V_base_ov + cs * cumQ_ov
        lev_pred = np.polyval(bathy_coeffs, vol_pred)
        return float(np.sqrt(np.mean((lev_pred - obs_vals) ** 2)))

    res = minimize_scalar(rmse, bounds=(0.05, 20.0), method="bounded")
    cs_opt = float(res.x)
    cal_rmse = float(res.fun)

    cfg = {
        "catchment_scale_Mm3_per_mm": round(cs_opt, 6),
        "S_max_mm": S_MAX_DEFAULT,
        "bathy_vol2level_coeffs": bathy_coeffs,
        "anchor_date": ANCHOR_DATE,
        "anchor_level_m": ANCHOR_LEVEL_M,
        "calibration_rmse_m": round(cal_rmse, 4),
    }
    CORDEX_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORDEX_CFG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"catchment_scale={cs_opt:.4f} Mm³/mm  calibration RMSE={cal_rmse:.3f} m")
    return cfg


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_waterbalance import run_water_balance
    from longrange_cordex_ingest import load_cordex
    import json

    meta = json.loads((PROJECT_ROOT / "Models" / "model_metadata.json").read_text())
    bathy = meta["bathy_vol2level_coeffs"]

    cordex = load_cordex()
    # Run with cs=1 over 2006-2024 for calibration data
    mask_calib = cordex["date"] <= pd.Timestamp("2024-12-31")
    wb = run_water_balance(cordex[mask_calib].copy(),
                           anchor_level_m=ANCHOR_LEVEL_M, anchor_date=ANCHOR_DATE)
    obs = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    calibrate_catchment_scale(wb, obs, bathy)
```

- [ ] **Step 4: Run tests to confirm they pass**

```
python -m pytest tests/test_longrange_cordex_calibrate.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Run calibration on real data**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project\Automation"
python longrange_cordex_calibrate.py
```
Expected output:
```
catchment_scale=X.XXXX Mm³/mm  calibration RMSE=X.XXX m
```
Inspect `docs/cordex_config.json` — verify all 6 keys are present.

- [ ] **Step 6: Commit**

```
git add Automation/longrange_cordex_calibrate.py tests/test_longrange_cordex_calibrate.py docs/cordex_config.json
git commit -m "feat: calibrate catchment_scale on 2006-2024 gold level record"
```

---

## Task 4: Hindcast evaluation

**Files:**
- Create: `Automation/longrange_cordex_hindcast.py`

No separate test file — the hindcast is an evaluation script, and its correctness is verified by inspecting the written metrics (RMSE, corr) in the config.

- [ ] **Step 1: Write the hindcast script**

```python
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

    Writes hindcast_rmse_m and hindcast_corr back to cordex_config.json.
    Caches the full hindcast DataFrame as Gold Data/cordex_hindcast.parquet.
    Returns the metrics dict.
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "Automation"))
    from longrange_cordex_ingest import load_cordex
    from longrange_cordex_waterbalance import cache_water_balance

    # Re-run with calibrated scale (cache_water_balance reads cordex_config.json)
    wb = cache_water_balance(force=True)

    # Restrict to hindcast period 2006-2024
    hindcast = wb[wb["date"].dt.year <= 2024].copy()

    # Ensemble median level per date
    med = (
        hindcast.groupby("date")["level_m"]
        .median()
        .reset_index()
        .rename(columns={"level_m": "level_pred"})
    )

    obs = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    merged = med.merge(obs.rename(columns={"kinneret_level": "level_obs"}),
                       on="date", how="inner").dropna()

    rmse = float(np.sqrt(np.mean((merged["level_pred"] - merged["level_obs"]) ** 2)))
    corr = float(merged["level_pred"].corr(merged["level_obs"]))

    # Append to cordex_config.json
    cfg = json.loads(CORDEX_CFG_PATH.read_text())
    cfg["hindcast_rmse_m"] = round(rmse, 4)
    cfg["hindcast_corr"]   = round(corr, 4)
    cfg["hindcast_n_days"] = int(len(merged))
    CORDEX_CFG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"Hindcast 2006-2024: RMSE={rmse:.3f} m  corr={corr:.3f}  n={len(merged)}")

    hindcast.to_parquet(HINDCAST_CACHE, index=False)
    return cfg


if __name__ == "__main__":
    run_hindcast()
```

- [ ] **Step 2: Run hindcast on real data**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project\Automation"
python longrange_cordex_hindcast.py
```
Expected output (values will vary by calibration):
```
Hindcast 2006-2024: RMSE=X.XXX m  corr=0.XXX  n=XXXX
```

Inspect `docs/cordex_config.json` — verify `hindcast_rmse_m` and `hindcast_corr` are present.

Note: if `hindcast_rmse_m > 2.0` the dashboard will show a warning banner — this is by design.

- [ ] **Step 3: Commit**

```
git add Automation/longrange_cordex_hindcast.py docs/cordex_config.json Gold Data/cordex_hindcast.parquet Gold Data/cordex_waterbalance.parquet
git commit -m "feat: hindcast evaluation 2006-2024 (RMSE + corr -> cordex_config)"
```

---

## Task 5: Streamlit page — Climate Scenarios

**Files:**
- Create: `kinneret_app/pages/9_Climate_Scenarios.py`

Three tabs:
1. **Evaporative Demand** — annual lake ET₀ (Mm³/year) per scenario, HIGH confidence
2. **Water Balance** — annual mean level trajectory + 2030/2050/2100 box plots, MEDIUM confidence
3. **Hindcast Check** — observed vs ensemble median 2006–2024

- [ ] **Step 1: Write the page**

```python
# kinneret_app/pages/9_Climate_Scenarios.py
"""
9_Climate_Scenarios.py — CORDEX ensemble water-balance climate projection.

Shows what temperature warming does to Kinneret evaporative demand and inferred
water balance under RCP4.5 vs RCP8.5 (12 models, 2006-2100).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app_utils import PROJECT_ROOT
    from theme import inject_theme, style_plotly, PALETTE
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    PALETTE = {"aqua": "#2BD9C4", "ember": "#FF6B35", "gold": "#F2B441",
               "leaf": "#86E05A", "bone": "#F4EBDD", "ink": "#0C0B09"}
    def inject_theme(): return None
    def style_plotly(fig, **kw): return fig

WB_CACHE  = PROJECT_ROOT / "Gold Data" / "cordex_waterbalance.parquet"
HC_CACHE  = PROJECT_ROOT / "Gold Data" / "cordex_hindcast.parquet"
CFG_PATH  = PROJECT_ROOT / "docs" / "cordex_config.json"
LEVEL_PATH = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"

SCENARIO_COLORS = {"rcp45": PALETTE["aqua"], "rcp85": PALETTE["ember"]}
SCENARIO_LABELS = {"rcp45": "RCP 4.5 (moderate)", "rcp85": "RCP 8.5 (high emissions)"}
MODEL_OPACITY   = 0.15

# Kinneret operating thresholds (m ASL, negative = below sea level)
LOWER_RED_LINE  = -215.5   # operational lower limit
FULL_LEVEL      = -208.8   # operational full level


# ── Data loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_wb():
    if not WB_CACHE.exists():
        return None
    return pd.read_parquet(WB_CACHE)


@st.cache_data(ttl=3600)
def load_hindcast():
    if not HC_CACHE.exists():
        return None
    return pd.read_parquet(HC_CACHE)


@st.cache_data(ttl=3600)
def load_config():
    if not CFG_PATH.exists():
        return {}
    return json.loads(CFG_PATH.read_text())


@st.cache_data(ttl=3600)
def load_obs_level():
    lev = pd.read_csv(LEVEL_PATH, parse_dates=["date"])
    return lev.rename(columns={"kinneret_level": "level_obs"})


# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Climate Scenarios", page_icon="🌡", layout="wide")
inject_theme()

st.markdown("<h1>🌡 Climate Scenarios</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="kn-subtitle">What does warming do to the Kinneret?</p>',
    unsafe_allow_html=True,
)

# Assumption callout — always visible
st.info(
    "**Held assumptions:** Inflow volume and pumping are held at modern-period "
    "climatology. This projection shows the effect of temperature — not of policy "
    "or land-use change.",
    icon="ℹ️",
)

wb = load_wb()
cfg = load_config()

if wb is None:
    st.warning(
        "Climate scenario data not yet computed. "
        "Run `Automation/longrange_cordex_calibrate.py` then `longrange_cordex_hindcast.py`."
    )
    st.stop()

# Hindcast gate warning
if cfg.get("hindcast_rmse_m", 0) > 2.0:
    st.warning(
        f"⚠️ Hindcast RMSE = {cfg['hindcast_rmse_m']:.2f} m — the water balance "
        "cannot closely track the 2006–2024 observed record. "
        "Forward projections are exploratory only.",
        icon="⚠️",
    )

tab1, tab2, tab3 = st.tabs(["☀️ Evaporative Demand", "💧 Water Balance", "📋 Hindcast Check"])


# ── Tab 1: Evaporative Demand ─────────────────────────────────────────────────

with tab1:
    st.markdown(
        "**Confidence: HIGH** — Hargreaves ET₀ is deterministic physics from "
        "tmin/tmax alone. This is the most robust output of the model.",
    )

    # Annual lake ET0 sum per model+scenario
    wb["year"] = pd.to_datetime(wb["date"]).dt.year
    annual_et0 = (
        wb.groupby(["year", "model", "scenario"])["lake_ET_Mm3"]
        .sum()
        .reset_index()
        .rename(columns={"lake_ET_Mm3": "annual_ET0_Mm3"})
    )

    fig1 = go.Figure()
    for scenario, color in SCENARIO_COLORS.items():
        sub = annual_et0[annual_et0["scenario"] == scenario]
        # Envelope (10th–90th)
        envelope = sub.groupby("year")["annual_ET0_Mm3"].quantile([0.1, 0.9]).unstack()
        fig1.add_trace(go.Scatter(
            x=list(envelope.index) + list(envelope.index[::-1]),
            y=list(envelope[0.9]) + list(envelope[0.1][::-1]),
            fill="toself", fillcolor=color.replace(")", ",0.15)").replace("rgb", "rgba")
                if "rgb" in color else color + "26",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        # Individual model lines
        for model in sub["model"].unique():
            m = sub[sub["model"] == model]
            fig1.add_trace(go.Scatter(
                x=m["year"], y=m["annual_ET0_Mm3"],
                mode="lines", line=dict(color=color, width=0.8),
                opacity=MODEL_OPACITY, showlegend=False, hoverinfo="skip",
            ))
        # Median line
        med = sub.groupby("year")["annual_ET0_Mm3"].median().reset_index()
        fig1.add_trace(go.Scatter(
            x=med["year"], y=med["annual_ET0_Mm3"],
            mode="lines", line=dict(color=color, width=2.5),
            name=SCENARIO_LABELS[scenario],
        ))

    # Reference: 2006-2024 observed mean
    obs_mean = annual_et0[annual_et0["year"] <= 2024]["annual_ET0_Mm3"].mean()
    fig1.add_hline(y=obs_mean, line_dash="dash", line_color=PALETTE.get("bone", "#F4EBDD"),
                   annotation_text=f"2006-2024 mean ({obs_mean:.0f} Mm³/yr)",
                   annotation_position="bottom right")

    style_plotly(fig1)
    fig1.update_layout(
        title="Annual Open-Water Evaporation Demand",
        xaxis_title="Year",
        yaxis_title="Lake ET₀ (Mm³ / year)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Decade summary table
    decade_bins = [2010, 2030, 2050, 2080, 2100]
    rows = []
    for scenario in ["rcp45", "rcp85"]:
        for start, end in zip(decade_bins[:-1], decade_bins[1:]):
            vals = annual_et0[
                (annual_et0["scenario"] == scenario) &
                (annual_et0["year"].between(start, end))
            ]["annual_ET0_Mm3"]
            rows.append({
                "Scenario": SCENARIO_LABELS[scenario],
                "Period": f"{start}–{end}",
                "Median ET₀ (Mm³/yr)": f"{vals.median():.0f}",
                "10th–90th pct": f"{vals.quantile(0.1):.0f}–{vals.quantile(0.9):.0f}",
            })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ── Tab 2: Water Balance ──────────────────────────────────────────────────────

with tab2:
    st.markdown(
        "**Confidence: MEDIUM** — rain propensity is inferred from temperature "
        "(DTR signal, AUC 0.811). Bands show model uncertainty, not measurement precision.",
    )

    annual_level = (
        wb.groupby(["year", "model", "scenario"])["level_m"]
        .mean()
        .reset_index()
        .rename(columns={"level_m": "annual_mean_level"})
    )

    fig2 = go.Figure()
    for scenario, color in SCENARIO_COLORS.items():
        sub = annual_level[annual_level["scenario"] == scenario]
        envelope = sub.groupby("year")["annual_mean_level"].quantile([0.1, 0.9]).unstack()
        fig2.add_trace(go.Scatter(
            x=list(envelope.index) + list(envelope.index[::-1]),
            y=list(envelope[0.9]) + list(envelope[0.1][::-1]),
            fill="toself",
            fillcolor=color + "26" if not color.startswith("rgba") else color,
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        for model in sub["model"].unique():
            m = sub[sub["model"] == model]
            fig2.add_trace(go.Scatter(
                x=m["year"], y=m["annual_mean_level"],
                mode="lines", line=dict(color=color, width=0.8),
                opacity=MODEL_OPACITY, showlegend=False, hoverinfo="skip",
            ))
        med = sub.groupby("year")["annual_mean_level"].median().reset_index()
        fig2.add_trace(go.Scatter(
            x=med["year"], y=med["annual_mean_level"],
            mode="lines", line=dict(color=color, width=2.5),
            name=SCENARIO_LABELS[scenario],
        ))

    fig2.add_hline(y=LOWER_RED_LINE, line_dash="dot",
                   line_color=PALETTE.get("ember", "#FF6B35"),
                   annotation_text="Lower operating limit", annotation_position="top left")
    fig2.add_hline(y=FULL_LEVEL, line_dash="dot",
                   line_color=PALETTE.get("aqua", "#2BD9C4"),
                   annotation_text="Full level", annotation_position="bottom left")

    style_plotly(fig2)
    fig2.update_layout(
        title="Annual Mean Lake Level",
        xaxis_title="Year",
        yaxis_title="Level (m ASL)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Snapshot box plots: 2030, 2050, 2100
    st.markdown("##### Level distribution at key horizons")
    horizons = {2030: "2025–2035", 2050: "2045–2055", 2100: "2090–2100"}
    fig3 = go.Figure()
    for i, (yr, label) in enumerate(horizons.items()):
        lo, hi = yr - 5, yr + 5
        for scenario, color in SCENARIO_COLORS.items():
            sub = annual_level[
                (annual_level["year"].between(lo, hi)) &
                (annual_level["scenario"] == scenario)
            ]["annual_mean_level"]
            fig3.add_trace(go.Box(
                y=sub, name=f"{label}<br>{SCENARIO_LABELS[scenario]}",
                marker_color=color, boxmean=True, showlegend=False,
            ))
    style_plotly(fig3)
    fig3.update_layout(
        title="Level Distribution at Key Horizons (all 12 models)",
        yaxis_title="Annual Mean Level (m ASL)",
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(
        "Box spans 25th–75th percentile across 12 models; whiskers = 10th–90th. "
        "No single number is a forecast — the spread IS the message."
    )


# ── Tab 3: Hindcast Check ─────────────────────────────────────────────────────

with tab3:
    rmse = cfg.get("hindcast_rmse_m")
    corr = cfg.get("hindcast_corr")
    n    = cfg.get("hindcast_n_days")

    col1, col2, col3 = st.columns(3)
    col1.metric("Hindcast RMSE", f"{rmse:.2f} m" if rmse else "—",
                delta="⚠️ >2 m — exploratory" if rmse and rmse > 2 else "✓ within tolerance")
    col2.metric("Correlation (r)", f"{corr:.3f}" if corr else "—")
    col3.metric("Overlap days", str(n) if n else "—")

    hc = load_hindcast()
    obs = load_obs_level()
    if hc is not None and obs is not None:
        hc_year = hc[hc["date"].dt.year <= 2024].copy()
        med_hc = hc_year.groupby("date")["level_m"].agg(
            level_med="median",
            level_p10=lambda x: x.quantile(0.1),
            level_p90=lambda x: x.quantile(0.9),
        ).reset_index()

        fig4 = go.Figure()
        # Envelope
        fig4.add_trace(go.Scatter(
            x=list(med_hc["date"]) + list(med_hc["date"][::-1]),
            y=list(med_hc["level_p90"]) + list(med_hc["level_med"][::-1]),
            fill="toself", fillcolor=PALETTE["aqua"] + "20",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig4.add_trace(go.Scatter(
            x=med_hc["date"], y=med_hc["level_med"],
            mode="lines", line=dict(color=PALETTE["aqua"], width=1.5),
            name="Ensemble median (projected)",
        ))
        fig4.add_trace(go.Scatter(
            x=obs["date"], y=obs["level_obs"],
            mode="lines", line=dict(color=PALETTE.get("bone", "#F4EBDD"), width=2),
            name="Observed level",
        ))
        style_plotly(fig4)
        fig4.update_layout(
            title="Hindcast vs Observed (2006–2024)",
            xaxis_title="Date",
            yaxis_title="Level (m ASL)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig4, use_container_width=True)

    st.caption(
        "The hindcast uses the same physics chain and calibrated `catchment_scale` "
        "as the forward projection. If the chain cannot track the past, forward "
        "projections are shown as exploratory only."
    )
```

- [ ] **Step 2: Run full test suite to verify nothing is broken**

```
python -m pytest tests/ -v --tb=short -q
```
Expected: all previously passing tests still pass; no new failures.

- [ ] **Step 3: Launch the dashboard and verify the page loads**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project\kinneret_app"
streamlit run app.py
```
Open `http://localhost:8501` and navigate to **9 Climate Scenarios**. Verify:
- Page loads without error
- Assumption callout visible
- All three tabs render (if waterbalance.parquet exists) or the missing-data warning appears

- [ ] **Step 4: Commit**

```
git add kinneret_app/pages/9_Climate_Scenarios.py
git commit -m "feat: Climate Scenarios dashboard page (3 tabs, CORDEX ensemble)"
```

---

## Self-review against spec

| Spec requirement | Task |
|---|---|
| Winsorize tmax > 49°C at ingestion | Task 1 (`TMAX_CAP = 49.0`) |
| Hargreaves ET₀ calibrated (slope 1.06) | Task 2 (`slope * hargreaves_et0 + intercept`, reads from `longrange_config.json`) |
| Cloud-index rain propensity from DTR | Task 2 (`cloud_index(dtr_bz, dtr_cs)` → `rain_scale`) |
| Soil-moisture bucket | Task 2 (`soil_moisture_bucket`) |
| Outflow climatology (modern DOY) | Task 2 (`clim["outflow_clim"] / 1e6`) |
| Volume → level via bathymetric poly | Task 2 (`level_from_volume`, reads from `model_metadata.json`) |
| Fit `catchment_scale` on 2006-2024 | Task 3 (scalar optimization, writes `cordex_config.json`) |
| Hindcast gate (RMSE > 2 m = warning) | Task 4 + Task 5 (dashboard banner) |
| Tab 1: Evap demand, HIGH confidence | Task 5 (Tab 1, badge, ribbon chart) |
| Tab 2: Level trajectory + snapshots | Task 5 (Tab 2, ribbon + box plots) |
| No single "level in 2080" point | Task 5 (only box plots, captioned clearly) |
| Tab 3: Hindcast Check | Task 5 (Tab 3) |
| Assumption callout always visible | Task 5 (`st.info` above tabs) |
| Two sites: bet-zayda (catchment) / zemah (lake) | Task 1 + Task 2 |
| All 12 models shown individually | Task 5 (thin lines + ribbon) |
| RCP4.5 vs RCP8.5 distinct colors | Task 5 (`SCENARIO_COLORS`) |
