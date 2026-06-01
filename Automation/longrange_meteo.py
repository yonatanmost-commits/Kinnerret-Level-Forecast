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
