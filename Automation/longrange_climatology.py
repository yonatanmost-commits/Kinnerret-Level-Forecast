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
