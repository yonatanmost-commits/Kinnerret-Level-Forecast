# tests/test_ims_forecast.py
import math
import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from ims_forecast import _aggregate_to_daily, _find_tiberias

# ── Minimal XML fixture: two locations (Jerusalem + Tiberias), Tiberias has
#    four 6-hourly steps on 2026-05-29 only. ─────────────────────────────────
FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LocationForecasts>
  <Identification>
    <IssueDateTime>Thu May 28 10:00:00 IDT 2026</IssueDateTime>
  </Identification>
  <Location>
    <LocationMetaData>
      <LocationId>1</LocationId>
      <LocationNameEng>Jerusalem</LocationNameEng>
      <DisplayLat>31.778</DisplayLat><DisplayLon>35.200</DisplayLon>
      <DisplayHeight>780</DisplayHeight>
    </LocationMetaData>
    <LocationData>
      <Forecast>
        <ForecastTime>2026-05-29 09:00:00</ForecastTime>
        <MaxTemp>18</MaxTemp><MinTemp>14</MinTemp>
        <Rain>0.00</Rain><RelativeHumidity>65</RelativeHumidity>
        <WindSpeed>12</WindSpeed>
      </Forecast>
    </LocationData>
  </Location>
  <Location>
    <LocationMetaData>
      <LocationId>40</LocationId>
      <LocationNameEng>Tiberias</LocationNameEng>
      <DisplayLat>32.7920</DisplayLat><DisplayLon>35.5390</DisplayLon>
      <DisplayHeight>-200</DisplayHeight>
    </LocationMetaData>
    <LocationData>
      <Forecast>
        <ForecastTime>2026-05-29 03:00:00</ForecastTime>
        <MaxTemp>20</MaxTemp><MinTemp>16</MinTemp>
        <Rain>0.50</Rain><RelativeHumidity>60</RelativeHumidity>
        <WindSpeed>8</WindSpeed>
      </Forecast>
      <Forecast>
        <ForecastTime>2026-05-29 09:00:00</ForecastTime>
        <MaxTemp>24</MaxTemp><MinTemp>20</MinTemp>
        <Rain>1.00</Rain><RelativeHumidity>50</RelativeHumidity>
        <WindSpeed>12</WindSpeed>
      </Forecast>
      <Forecast>
        <ForecastTime>2026-05-29 15:00:00</ForecastTime>
        <MaxTemp>30</MaxTemp><MinTemp>26</MinTemp>
        <Rain>0.00</Rain><RelativeHumidity>40</RelativeHumidity>
        <WindSpeed>18</WindSpeed>
      </Forecast>
      <Forecast>
        <ForecastTime>2026-05-29 21:00:00</ForecastTime>
        <MaxTemp>24</MaxTemp><MinTemp>21</MinTemp>
        <Rain>0.00</Rain><RelativeHumidity>55</RelativeHumidity>
        <WindSpeed>10</WindSpeed>
      </Forecast>
    </LocationData>
  </Location>
</LocationForecasts>"""

# fc_dates: two days — one with data, one without
FC_DATES = [pd.Timestamp("2026-05-29"), pd.Timestamp("2026-05-30")]


@pytest.fixture
def root():
    return ET.fromstring(FIXTURE_XML)


@pytest.fixture
def tiberias(root):
    return _find_tiberias(root)


# ── _find_tiberias ─────────────────────────────────────────────────────────────

def test_find_tiberias_returns_location_element(root):
    loc = _find_tiberias(root)
    assert loc.findtext("LocationMetaData/LocationId") == "40"


def test_find_tiberias_raises_when_missing():
    no_tiberias = ET.fromstring(
        "<LocationForecasts>"
        "<Location><LocationMetaData><LocationId>1</LocationId>"
        "</LocationMetaData><LocationData/></Location>"
        "</LocationForecasts>"
    )
    with pytest.raises(ValueError, match="Tiberias"):
        _find_tiberias(no_tiberias)


# ── _aggregate_to_daily ────────────────────────────────────────────────────────
# Day 2026-05-29 aggregations from the fixture:
#   temp_max_C   = max(20, 24, 30, 24)          = 30
#   temp_min_C   = min(16, 20, 26, 21)          = 16
#   rainfall_mm  = 0.50+1.00+0.00+0.00         = 1.50
#   humidity_pct = mean(60, 50, 40, 55)         = 51.25
#   wind_speed_ms= mean(8,12,18,10)/3.6 = 12/3.6 = 3.3333...

def test_aggregate_temp_max(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert df.loc[0, "temp_max_C"] == 30


def test_aggregate_temp_min(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert df.loc[0, "temp_min_C"] == 16


def test_aggregate_rainfall(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert abs(df.loc[0, "rainfall_mm"] - 1.50) < 1e-9


def test_aggregate_humidity(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert abs(df.loc[0, "humidity_pct"] - 51.25) < 1e-9


def test_aggregate_wind_converted_to_ms(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert abs(df.loc[0, "wind_speed_ms"] - 12.0 / 3.6) < 1e-9


def test_aggregate_radiation_always_nan(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert math.isnan(df.loc[0, "radiation_MJm2"])


def test_aggregate_missing_date_fills_nan(tiberias):
    # 2026-05-30 has no steps in the fixture — all numeric cols should be NaN
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert math.isnan(df.loc[1, "temp_max_C"])
    assert math.isnan(df.loc[1, "rainfall_mm"])
    assert math.isnan(df.loc[1, "wind_speed_ms"])


def test_aggregate_dates_aligned_to_fc_dates(tiberias):
    df = _aggregate_to_daily(tiberias, FC_DATES)
    assert list(df["date"]) == FC_DATES


def test_aggregate_returns_correct_row_count(tiberias):
    fc7 = [pd.Timestamp("2026-05-29") + pd.Timedelta(days=i) for i in range(7)]
    df = _aggregate_to_daily(tiberias, fc7)
    assert len(df) == 7
