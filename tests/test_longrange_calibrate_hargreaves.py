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
