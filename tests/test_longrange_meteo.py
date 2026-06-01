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
