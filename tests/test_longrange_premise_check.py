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


def test_evaluate_premise_corr_finite_with_nan_rows():
    """Missing-temp rows (NaN DTR) must not poison the cloud-rain correlation:
    the real gold record has a handful of NaN temp days, and a single NaN would
    make np.corrcoef return nan for the whole series."""
    from longrange_premise_check import evaluate_premise
    rng = np.random.default_rng(3)
    dates = pd.date_range("2013-01-01", "2018-12-31")
    doy = dates.dayofyear.values
    is_winter = (doy < 90) | (doy > 305)
    dtr = np.where(is_winter, rng.uniform(3, 14, len(doy)), rng.uniform(10, 16, len(doy)))
    wetp = np.where(is_winter, np.clip((14 - dtr) / 14, 0, 1) * 0.8, 0.02)
    rain = np.where(rng.random(len(doy)) < wetp, rng.uniform(1, 25, len(doy)), 0.0)
    temp_max = 20.0 + dtr
    temp_min = np.full(len(doy), 20.0)
    # inject a few missing-temp days inside the wet season (as in real gold)
    temp_max[5] = np.nan
    temp_max[40] = np.nan
    gold = pd.DataFrame({
        "date": dates, "temp_max_C": temp_max, "temp_min_C": temp_min,
        "rainfall_mm": rain,
    })
    result = evaluate_premise(gold, auc_threshold=0.6)
    assert np.isfinite(result["wet_season_cloud_rain_corr"]), \
        "NaN temp rows must be masked out of the cloud-rain correlation"
