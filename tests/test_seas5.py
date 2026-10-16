"""Acceptance tests for Automation/seas5.py: seasonal-forecast anomalies with no look-ahead."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Automation"))
import seas5  # noqa: E402


def table(years, rain=lambda init, lead: 2.0, temp=lambda init, lead: 20.0):
    """Ensemble-mean table: one row per (init, lead)."""
    rows = []
    for y in years:
        for m in range(1, 13):
            init = pd.Timestamp(y, m, 1)
            for lead in range(1, 7):
                rows.append({"init": init, "lead": lead,
                             "target": init + pd.DateOffset(months=lead - 1),
                             "rain_mm_day": rain(init, lead), "t2m_C": temp(init, lead)})
    return pd.DataFrame(rows)


def test_start_uses_only_forecasts_already_published():
    # SEAS5 is released on the 5th: a start on the 5th still uses last month's forecast
    assert seas5.init_for(pd.Timestamp("2020-10-05")) == pd.Timestamp("2020-09-01")
    assert seas5.init_for(pd.Timestamp("2020-10-06")) == pd.Timestamp("2020-10-01")


def test_anomaly_baseline_uses_earlier_years_only():
    # 2000-2009 forecast 2 mm/day; 2010 forecasts 4; 2011 forecasts 100 (a future the
    # 2010 anomaly must not see). The 2010 ratio is 4/2 = 2.
    t = table(range(2000, 2012), rain=lambda i, l: {2010: 4.0, 2011: 100.0}.get(i.year, 2.0))
    a = seas5.anomalies(t, test_year=2010)
    row = a[(a.init == pd.Timestamp("2010-11-01")) & (a.lead == 1)].iloc[0]
    assert abs(row.rain_ratio - 2.0) < 1e-9


def test_temperature_anomaly_is_additive():
    t = table(range(2000, 2011), temp=lambda i, l: 22.5 if i.year == 2010 else 20.0)
    a = seas5.anomalies(t, test_year=2010)
    assert np.allclose(a[a.init.dt.year == 2010].t2m_anom, 2.5)


def test_adjusted_weather_scales_only_forecast_months_after_the_start():
    days = pd.date_range("2000-01-01", "2000-12-31")
    clim = pd.DataFrame({"rainfall_mm": 1.0, "temp_mean_C": 10.0, "temp_max_C": 15.0,
                         "temp_min_C": 5.0}, index=pd.Index(days.dayofyear, name="doy")).groupby(level=0).first()
    anom = pd.DataFrame({"init": pd.Timestamp("2010-10-01"), "lead": [1, 2, 3, 4, 5, 6],
                         "rain_ratio": 3.0, "t2m_anom": 1.0})
    adj = seas5.adjust_clim(clim, start=pd.Timestamp("2010-10-20"), anom=anom)
    jan = pd.Timestamp("2011-01-15").dayofyear
    jun = pd.Timestamp("2011-06-15").dayofyear          # past the 6-month reach (Oct-Mar)
    assert adj.loc[jan, "rainfall_mm"] == 3.0 and adj.loc[jan, "temp_max_C"] == 16.0
    assert adj.loc[jun, "rainfall_mm"] == 1.0 and adj.loc[jun, "temp_mean_C"] == 10.0


def test_calibration_slope_from_earlier_years_only():
    # each target month has one true signal r; every forecast of that month sees it (plus a
    # little noise) and the observed ratio is 1 + 2 (r - 1) in 2000-2009. From 2010 the
    # relation flips (a negative slope). The 2010 calibration must use 2000-2009 only: slope 2.
    rng = np.random.default_rng(0)
    months = pd.date_range("2000-01-01", "2012-06-01", freq="MS")
    r = pd.Series(1 + rng.normal(scale=0.1, size=len(months)), index=months)
    month_obs = pd.Series([1 + (2 if t.year < 2010 else -3) * (r[t] - 1) for t in months], index=months)
    rows = []
    for init in pd.date_range("2000-01-01", "2011-12-01", freq="MS"):
        for lead in range(1, 7):
            tgt = init + pd.DateOffset(months=lead - 1)
            rows.append({"init": init, "lead": lead, "target": tgt,
                         "rain_mm_day": 2.0 * (r[tgt] + rng.normal(scale=0.005)), "t2m_C": 20.0})
    t = pd.DataFrame(rows)
    slopes = seas5.calibration_slopes(seas5.anomalies(t, 2010), month_obs, test_year=2010)
    assert set(slopes) == set(range(1, 7))
    assert all(abs(s - 2.0) < 0.25 for s in slopes.values()), slopes


def test_calibrated_ratio_applies_the_slope():
    a = pd.DataFrame({"init": pd.Timestamp("2010-10-01"), "lead": [1, 2], "rain_ratio": [1.2, 0.9], "t2m_anom": 0.0})
    out = seas5.calibrate(a, {1: 2.0, 2: 0.5})
    assert np.allclose(out.rain_ratio, [1.4, 0.95])
