# tests/test_envista_export.py
"""The envista -> IMS export conversion (Automation/envista_to_ims_export.py)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("_envista", ROOT / "Automation" / "envista_to_ims_export.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)

WS, TD = ex.HEBREW["wind_speed_ms"], ex.HEBREW["temperature_C"]


def _month(start, ws, td):
    idx = pd.date_range(start, periods=len(td), freq="10min")
    return pd.DataFrame({WS: ws, TD: td}, index=idx)


def test_wind_that_repeats_temperature_is_blanked_for_the_month():
    td = np.linspace(10, 30, 144)
    df = ex.drop_copied_wind(_month("2001-03-01", td.copy(), td))
    assert df[WS].isna().all()
    assert df[TD].notna().all()                        # temperature itself is kept


def test_real_wind_survives_a_chance_match():
    td = np.linspace(10, 30, 144)
    ws = np.full(144, 2.0)
    ws[0] = td[0]                                      # one slot equal by chance
    df = ex.drop_copied_wind(_month("2003-03-01", ws, td))
    assert df[WS].notna().all()


def test_only_the_copied_month_is_blanked():
    td = np.linspace(10, 30, 144)
    a = _month("2002-06-30 00:00", td.copy(), td)      # June 30: copied
    b = _month("2002-07-01 00:00", np.full(144, 2.0), td)  # July 1: real
    df = ex.drop_copied_wind(pd.concat([a, b]))
    assert df.loc["2002-06", WS].isna().all()
    assert df.loc["2002-07", WS].notna().all()
