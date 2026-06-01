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
