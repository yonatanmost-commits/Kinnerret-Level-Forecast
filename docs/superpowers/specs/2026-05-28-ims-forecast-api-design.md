# IMS Forecast API Integration — Design Spec

**Date:** 2026-05-28  
**Scope:** Connect the Israel Meteorological Service (IMS) live 8-day weather forecast XML to the Kinneret Forecast Dashboard's Live Forecast page.

---

## 1. Goal

Replace the manual weather-entry step on Page 6 (Live Forecast) with a one-click "Fetch from IMS" button that auto-fills the 7-day weather editor with live forecast data from the IMS public XML API.

---

## 2. Data Source

**URL:** `https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_cities_1week_6hr_forecast.xml`  
**Auth:** None — public HTTP GET  
**Update cadence:** Hourly  
**Format:** ~21 MB XML, UTF-8  
**Horizon:** 8 days (35 × 6-hour steps per location)  
**Steps:** 03:00 / 09:00 / 15:00 / 21:00 Israel time (UTC+2)

**Station used:** Tiberias (LocationId = 40), lat 32.792, lon 35.539, elevation -200 m MSL — closest city station to Lake Kinneret and at matching elevation.

---

## 3. Architecture

### New file: `kinneret_app/ims_forecast.py`

Self-contained module responsible for fetching and transforming IMS data. Kept separate from `app_utils.py` so it can be modified without requiring a Streamlit server restart (page files hot-reload; `app_utils.py` does not).

**Public API:**
```python
def fetch_tiberias_7day(fc_dates: list[pd.Timestamp]) -> pd.DataFrame:
    """
    Fetch the IMS XML, extract Tiberias forecast, aggregate to 7 daily rows
    aligned to fc_dates. Returns DataFrame with model-ready columns.
    Raises requests.RequestException or ValueError on fetch/parse failure.
    """
```

**Internal:**
```python
@st.cache_data(ttl=3600)
def _fetch_xml_root() -> ET.Element:
    """Download and parse the IMS XML. Cached for 1 hour."""
```

Caching the parsed root at `ttl=3600` s avoids re-downloading 21 MB on every rerun/button press within the same hour.

### Modified file: `kinneret_app/pages/6_Forecast_Live.py`

Adds a 4th button "Fetch from IMS" in the existing button row. On click:
1. Shows `st.spinner("Fetching IMS forecast…")`
2. Calls `fetch_tiberias_7day(fc_dates)`
3. Sets `st.session_state.fc_data = result`
4. Calls `st.rerun()`
5. On any exception: `st.error(f"IMS fetch failed: {e}")` — no crash, editor stays editable

---

## 4. Field Mapping

| Model column | IMS field | Aggregation | Notes |
|---|---|---|---|
| `date` | `ForecastTime` (date part) | aligned to `fc_dates` | |
| `temp_max_C` | `MaxTemp` | `max` across day's steps | integer °C |
| `temp_min_C` | `MinTemp` | `min` across day's steps | integer °C |
| `rainfall_mm` | `Rain` | `sum` across day's steps | 6-hour accumulations → daily total (mm) |
| `humidity_pct` | `RelativeHumidity` | `mean` across day's steps | integer % |
| `wind_speed_ms` | `WindSpeed` | `mean / 3.6` across day's steps | API is km/h; model expects m/s |
| `radiation_MJm2` | — | `NaN` | Not in IMS forecast; model tolerates missing radiation |

### Day grouping

Forecast steps are grouped by the calendar date of `ForecastTime`. For days where the API has fewer than 4 steps (e.g., the first or last day of the window), aggregation uses whatever steps are present (`min_count` / `min_periods` not enforced — partial days are acceptable).

If an `fc_date` has no matching API steps (API lag or date out of range), that row is filled with `NaN`.

---

## 5. Date Alignment

`fc_dates` is computed in Page 6 as the 7 consecutive days starting the day after the last gold data date. The function matches API forecast steps to these dates by calendar date, not by index. Steps from dates not in `fc_dates` are ignored.

---

## 6. Error Handling

| Scenario | Behaviour |
|---|---|
| HTTP error (timeout, 4xx/5xx) | `requests.raise_for_status()` → exception propagates → `st.error()` in page |
| Tiberias (ID 40) not found in XML | `ValueError("Tiberias not found in IMS forecast XML")` |
| No steps fall on `fc_dates` | Rows filled with NaN; user sees partially-filled editor |
| XML parse error | Exception propagates → `st.error()` |

---

## 7. Files Changed

| File | Change |
|---|---|
| `kinneret_app/ims_forecast.py` | **New** — fetch + parse + aggregate logic |
| `kinneret_app/pages/6_Forecast_Live.py` | **Modified** — add import + 4th button |

No changes to `app_utils.py`, `model_lib.py`, or any Automation scripts.

---

## 8. Out of Scope

- Saving fetched data to `forecast_input_template.csv` (CLI pipeline integration)
- Multi-station averaging
- Automated/scheduled fetching
- Radiation estimation from solar geometry (could be a future improvement)
