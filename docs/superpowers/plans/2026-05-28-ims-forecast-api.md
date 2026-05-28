# IMS Forecast API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Fetch from IMS" button to Page 6 that auto-fills the 7-day weather editor with live forecast data from the Israel Meteorological Service XML API using Tiberias (ID 40) as the station.

**Architecture:** A new `kinneret_app/ims_forecast.py` module handles HTTP fetch (cached 1 hour via `st.cache_data`), XML parsing, and 6-hourly → daily aggregation of Tiberias data. Page 6 gains a 4th button that calls `fetch_tiberias_7day(fc_dates)` and sets `st.session_state.fc_data`, then reruns. `app_utils.py` is untouched.

**Tech Stack:** Python stdlib `xml.etree.ElementTree`, `requests`, `pandas`, `streamlit.cache_data`, `pytest`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tests/__init__.py` | pytest package marker |
| Create | `tests/conftest.py` | add `kinneret_app/` to sys.path |
| Create | `tests/test_ims_forecast.py` | tests for `_find_tiberias` + `_aggregate_to_daily` |
| Create | `kinneret_app/ims_forecast.py` | fetch, parse, aggregate — no other files depend on it |
| Modify | `kinneret_app/pages/6_Forecast_Live.py` | import + 4th button |

---

## Task 1: Write failing tests for XML parsing and daily aggregation

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_ims_forecast.py`

- [ ] **Step 1: Create `tests/__init__.py`** (empty — makes tests/ a package for pytest)

```python
```

- [ ] **Step 2: Create `tests/conftest.py`** so pytest can find `ims_forecast` on the import path

```python
# tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kinneret_app"))
```

- [ ] **Step 3: Create `tests/test_ims_forecast.py`** with XML fixture and all assertions

```python
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
```

- [ ] **Step 4: Run tests — verify they fail with `ModuleNotFoundError`**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_ims_forecast.py -v
```

Expected: `ModuleNotFoundError: No module named 'ims_forecast'`

---

## Task 2: Implement `kinneret_app/ims_forecast.py`

**Files:**
- Create: `kinneret_app/ims_forecast.py`

- [ ] **Step 1: Create `kinneret_app/ims_forecast.py`**

```python
# kinneret_app/ims_forecast.py
import requests
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

IMS_URL = (
    "https://ims.gov.il/sites/default/files/ims_data/xml_files/"
    "isr_cities_1week_6hr_forecast.xml"
)
TIBERIAS_ID = 40


@st.cache_data(ttl=3600)
def _fetch_xml_root() -> ET.Element:
    resp = requests.get(IMS_URL, timeout=30)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def _find_tiberias(root: ET.Element) -> ET.Element:
    for loc in root.findall("Location"):
        if loc.findtext("LocationMetaData/LocationId") == str(TIBERIAS_ID):
            return loc
    raise ValueError(
        f"Tiberias (LocationId={TIBERIAS_ID}) not found in IMS forecast XML"
    )


def _aggregate_to_daily(location_elem: ET.Element, fc_dates: list) -> pd.DataFrame:
    rows = []
    for fc in location_elem.findall("LocationData/Forecast"):
        dt_date = pd.Timestamp(fc.findtext("ForecastTime")).date()
        rows.append({
            "date":             dt_date,
            "MaxTemp":          int(fc.findtext("MaxTemp")),
            "MinTemp":          int(fc.findtext("MinTemp")),
            "Rain":             float(fc.findtext("Rain")),
            "RelativeHumidity": int(fc.findtext("RelativeHumidity")),
            "WindSpeed":        int(fc.findtext("WindSpeed")),
        })

    agg = (
        pd.DataFrame(rows)
        .groupby("date")
        .agg(
            MaxTemp=("MaxTemp", "max"),
            MinTemp=("MinTemp", "min"),
            Rain=("Rain", "sum"),
            RelativeHumidity=("RelativeHumidity", "mean"),
            WindSpeed=("WindSpeed", "mean"),
        )
        .to_dict("index")
    ) if rows else {}

    out = []
    for d in fc_dates:
        key = pd.Timestamp(d).date()
        r = agg.get(key, {})
        out.append({
            "date":           pd.Timestamp(d),
            "temp_max_C":     r.get("MaxTemp",          float("nan")),
            "temp_min_C":     r.get("MinTemp",          float("nan")),
            "rainfall_mm":    r.get("Rain",             float("nan")),
            "humidity_pct":   r.get("RelativeHumidity", float("nan")),
            "wind_speed_ms":  r.get("WindSpeed",        float("nan")) / 3.6,
            "radiation_MJm2": float("nan"),
        })
    return pd.DataFrame(out)


def fetch_tiberias_7day(fc_dates: list) -> pd.DataFrame:
    root = _fetch_xml_root()
    location = _find_tiberias(root)
    return _aggregate_to_daily(location, fc_dates)
```

Note: `float("nan") / 3.6` propagates as NaN (IEEE 754), so missing-date wind values stay NaN with no extra guard needed.

- [ ] **Step 2: Run tests — verify all pass**

```
python -m pytest tests/test_ims_forecast.py -v
```

Expected: all tests PASSED, 0 failures.

- [ ] **Step 3: Commit**

```
git add kinneret_app/ims_forecast.py tests/__init__.py tests/conftest.py tests/test_ims_forecast.py
git commit -m "feat: add ims_forecast module with Tiberias daily aggregation"
```

---

## Task 3: Add "Fetch from IMS" button to Page 6

**Files:**
- Modify: `kinneret_app/pages/6_Forecast_Live.py`

- [ ] **Step 1: Add import of `fetch_tiberias_7day`** directly after the existing `from app_utils import ...` block (line 13 of the current file)

Current (lines 10–13):
```python
from app_utils import (
    load_gold, load_models, run_forecast_from_df, vol_to_level,
    COLOURS, LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX, PROJECT_ROOT,
)
```

Replace with:
```python
from app_utils import (
    load_gold, load_models, run_forecast_from_df, vol_to_level,
    COLOURS, LEVEL_LEGAL_MIN, LEVEL_LEGAL_MAX, PROJECT_ROOT,
)
from ims_forecast import fetch_tiberias_7day
```

- [ ] **Step 2: Expand the 3-button row to 4 columns and add the IMS button**

Current (lines 141–158):
```python
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("Load template", width='stretch'):
        st.session_state.fc_data = _default_fc_df()
        st.rerun()
with b2:
    if st.button("Clear (zeros)", width='stretch'):
        df_zero = pd.DataFrame({
            "date": fc_dates, "temp_max_C": [0.0]*7, "temp_min_C": [0.0]*7,
            "rainfall_mm": [0.0]*7, "humidity_pct": [50.0]*7,
            "wind_speed_ms": [2.0]*7, "radiation_MJm2": [0.0]*7,
        })
        st.session_state.fc_data = df_zero
        st.rerun()
with b3:
    if st.button("Use last 7 days as test", width='stretch'):
        st.session_state.fc_data = _last7_df()
        st.rerun()
```

Replace with:
```python
b1, b2, b3, b4 = st.columns(4)
with b1:
    if st.button("Load template", width='stretch'):
        st.session_state.fc_data = _default_fc_df()
        st.rerun()
with b2:
    if st.button("Clear (zeros)", width='stretch'):
        df_zero = pd.DataFrame({
            "date": fc_dates, "temp_max_C": [0.0]*7, "temp_min_C": [0.0]*7,
            "rainfall_mm": [0.0]*7, "humidity_pct": [50.0]*7,
            "wind_speed_ms": [2.0]*7, "radiation_MJm2": [0.0]*7,
        })
        st.session_state.fc_data = df_zero
        st.rerun()
with b3:
    if st.button("Use last 7 days as test", width='stretch'):
        st.session_state.fc_data = _last7_df()
        st.rerun()
with b4:
    if st.button("Fetch from IMS", width='stretch'):
        with st.spinner("Fetching IMS forecast…"):
            try:
                st.session_state.fc_data = fetch_tiberias_7day(fc_dates)
                st.rerun()
            except Exception as e:
                st.error(f"IMS fetch failed: {e}")
```

- [ ] **Step 3: Run pytest to confirm nothing broke**

```
python -m pytest tests/test_ims_forecast.py -v
```

Expected: all tests PASSED.

- [ ] **Step 4: Commit**

```
git add kinneret_app/pages/6_Forecast_Live.py
git commit -m "feat: add Fetch from IMS button to Live Forecast page"
```
