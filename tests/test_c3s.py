"""Acceptance tests for Automation/c3s.py: the C3S multi-model seasonal forecast, no look-ahead."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Automation"))
import c3s  # noqa: E402
import seas5  # noqa: E402


def table(system, years, rain=lambda init, lead: 2.0, temp=lambda init, lead: 20.0, months=range(1, 13)):
    rows = []
    for y in years:
        for m in months:
            init = pd.Timestamp(y, m, 1)
            for lead in range(1, 7):
                rows.append({"system": system, "init": init, "lead": lead,
                             "target": init + pd.DateOffset(months=lead - 1),
                             "rain_mm_day": rain(init, lead), "t2m_C": temp(init, lead)})
    return pd.DataFrame(rows)


def row(a, init, lead=1):
    return a[(a.init == pd.Timestamp(init)) & (a.lead == lead)].iloc[0]


def test_start_uses_only_multimodel_forecasts_already_published():
    # the C3S multi-model forecast is released on the 13th
    assert c3s.init_for(pd.Timestamp("2020-10-13")) == pd.Timestamp("2020-09-01")
    assert c3s.init_for(pd.Timestamp("2020-10-14")) == pd.Timestamp("2020-10-01")


def test_each_system_bias_cancels_before_averaging():
    # system "wet" always forecasts 5x the rain of "dry"; in 2010 both say 1.5x their norm.
    # The multi-model ratio is 1.5, not dominated by the wet model's bias.
    sig = lambda i, l: 1.5 if i.year == 2010 else 1.0
    t = pd.concat([table("dry", range(2000, 2011), rain=lambda i, l: 1.0 * sig(i, l)),
                   table("wet", range(2000, 2011), rain=lambda i, l: 5.0 * sig(i, l))])
    a = c3s.anomalies(t, test_year=2010)
    assert abs(row(a, "2010-11-01").rain_ratio - 1.5) < 1e-9


def test_a_system_missing_in_a_year_does_not_shift_the_mean():
    # "wet" stops after 2005 (like ukmo 610 after 2016). In 2010 "dry" alone says 1.0x:
    # averaging raw rain would read the wet model's absence as a dry season.
    t = pd.concat([table("dry", range(2000, 2011), rain=lambda i, l: 1.0),
                   table("wet", range(2000, 2006), rain=lambda i, l: 5.0)])
    a = c3s.anomalies(t, test_year=2010)
    r = row(a, "2010-11-01")
    assert abs(r.rain_ratio - 1.0) < 1e-9 and r.n_systems == 1


def test_baseline_uses_earlier_years_only():
    # 2011 forecasts 100 mm/day; the 2010 anomalies must not see it
    t = pd.concat([table(s, range(2000, 2012), rain=lambda i, l: {2010: 3.0, 2011: 100.0}.get(i.year, 1.5))
                   for s in ("a", "b")])
    a = c3s.anomalies(t, test_year=2010)
    assert abs(row(a, "2010-11-01").rain_ratio - 2.0) < 1e-9


def test_temperature_anomaly_is_the_mean_of_system_anomalies():
    t = pd.concat([table("a", range(2000, 2011), temp=lambda i, l: 22.0 if i.year == 2010 else 20.0),
                   table("b", range(2000, 2011), temp=lambda i, l: 14.0 if i.year == 2010 else 10.0)])
    a = c3s.anomalies(t, test_year=2010)
    assert abs(row(a, "2010-11-01").t2m_anom - 3.0) < 1e-9


def test_starts_missing_from_one_system_use_the_others():
    # ukmo-like system has Apr-Nov starts only: a January start comes from the rest
    t = pd.concat([table("all", range(2000, 2011), rain=lambda i, l: 2.0 if i.year == 2010 else 1.0),
                   table("ukmo", range(2000, 2011), months=range(4, 12))])
    a = c3s.anomalies(t, test_year=2010)
    jan = row(a, "2010-01-01")
    assert abs(jan.rain_ratio - 2.0) < 1e-9 and jan.n_systems == 1


def test_output_plugs_into_adjust_clim_with_the_later_release():
    days = pd.date_range("2000-01-01", "2000-12-31")
    clim = pd.DataFrame({"rainfall_mm": 1.0, "temp_mean_C": 10.0, "temp_max_C": 15.0, "temp_min_C": 5.0},
                        index=pd.Index(days.dayofyear, name="doy")).groupby(level=0).first()
    anom = pd.DataFrame({"init": [pd.Timestamp("2010-09-01")] * 6 + [pd.Timestamp("2010-10-01")] * 6,
                         "lead": list(range(1, 7)) * 2, "rain_ratio": [2.0] * 6 + [3.0] * 6, "t2m_anom": 0.0})
    dec = pd.Timestamp("2010-12-15").dayofyear
    # on 10 Oct SEAS5's October forecast is out, the multi-model's is not yet
    assert c3s.adjust_clim(clim, pd.Timestamp("2010-10-10"), anom).loc[dec, "rainfall_mm"] == 2.0
    assert seas5.adjust_clim(clim, pd.Timestamp("2010-10-10"), anom).loc[dec, "rainfall_mm"] == 3.0


def test_load_combines_both_start_dimensions(tmp_path):
    xr = pytest.importorskip("xarray")
    for name, dim in (("jma_4", "indexing_time"), ("dwd_22", "forecast_reference_time")):
        inits = pd.date_range("2005-01-01", periods=2, freq="MS")
        shape = (3, 2, 6, 2, 2)
        ds = xr.Dataset({"tprate": (("number", dim, "forecastMonth", "latitude", "longitude"),
                                    np.full(shape, 1e-8)),
                         "t2m": (("number", dim, "forecastMonth", "latitude", "longitude"), np.full(shape, 290.0))},
                        coords={"number": range(3), dim: inits, "forecastMonth": range(1, 7),
                                "latitude": [33.5, 32.5], "longitude": [35.5, 36.5]})
        ds.to_netcdf(tmp_path / f"{name}_2005.nc")
    t = c3s.load(tmp_path, with_seas5=False)
    assert set(t.system) == {"jma_4", "dwd_22"}
    assert len(t) == 2 * 2 * 6
    assert np.allclose(t.rain_mm_day, 1e-8 * 86400 * 1000) and np.allclose(t.t2m_C, 290.0 - 273.15)
    assert (t.target == [i + pd.DateOffset(months=l - 1) for i, l in zip(t.init, t.lead)]).all()
