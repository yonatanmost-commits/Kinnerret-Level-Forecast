# Kinneret Forecast Dashboard — Implementation Design
**Date:** 2026-05-23  
**Source spec:** `kinneret_dashboard_spec.md`  
**Approach:** Option A — sequential file build, all pages at once

---

## 1. What We Are Building

A 7-page Streamlit dashboard (`kinneret_app/`) for the Kinneret water-level forecast project. Launched with a single `streamlit run kinneret_app/app.py`. All model pkl files and the gold feature CSV already exist; no training is needed before the build.

---

## 2. File Creation Order

Files are written in this exact sequence so each file can reference what came before:

1. `kinneret_app/.streamlit/config.toml` — dark theme
2. `kinneret_app/app_utils.py` — shared loaders, constants, forecast wrapper
3. `kinneret_app/app.py` — Home / Lake Dashboard (entry point)
4. `kinneret_app/pages/1_Data_Sources.py`
5. `kinneret_app/pages/2_Pipeline.py`
6. `kinneret_app/pages/3_Statistics.py`
7. `kinneret_app/pages/4_Model_Info.py`
8. `kinneret_app/pages/5_Forecast_Historical.py`
9. `kinneret_app/pages/6_Forecast_Live.py`

---

## 3. Shared Utilities — `app_utils.py`

### Cached loaders
```python
@st.cache_data
def load_gold() -> pd.DataFrame
    # reads Gold Data/kinneret_gold_features.csv, parses date

@st.cache_resource
def load_models() -> tuple[GBRegressor, GBRegressor, dict]
    # loads stage1_inflow_rf.pkl, stage2_direct_gb.pkl, model_metadata.json
```

### Forecast wrapper
```python
def run_forecast_from_df(forecast_df, history_df, gb1, gb2_direct, meta) -> list[dict]
```
Thin wrapper around `09_weekly_forecast.run_forecast()`. Returns the 7-day results list. **Actuals (`actual_level_m`, `actual_inflow_m3`) are NOT returned here — Page 5 joins them from the gold table separately after calling this function.**

### Constants
```python
LEVEL_MIN        = -214.87   # historical all-time low
LEVEL_MAX        = -208.89   # historical all-time high
LEVEL_LEGAL_MIN  = -213.00   # lower management line (red)
LEVEL_LEGAL_MAX  = -208.90   # upper spill line (red)

COLOURS = {
    "predicted": "#1E90FF", "actual": "#FF7043",
    "winter": "#4FC3F7", "summer": "#EF5350",
    "rising": "#66BB6A", "falling": "#EF5350",
    "stable": "#BDBDBD", "legal_min": "#EF5350",
    "legal_max": "#66BB6A", "band": "rgba(30,144,255,0.15)",
}
```

---

## 4. Page 0 — Home / Lake Dashboard (`app.py`)

### Lake Level Gauge — updated design

Replaces the vertical-rectangle gauge from the original spec. Uses the lake's actual silhouette shape.

**Implementation:** inline SVG via `st.markdown(..., unsafe_allow_html=True)`

**Visual elements:**
- SVG lake silhouette path — approximated Kinneret outline (wider rounded top, narrowing southern tail). Not pixel-perfect; recognisably Kinneret-shaped.
- Water fill: dark teal → light teal gradient, clipped from the bottom up to the `y` coordinate computed from the current level proportion:
  ```
  fill_pct = (current_level - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
  ```
- Three horizontal reference lines crossing the silhouette:
  - Red dashed: `Upper Management Line  −208.90 m`
  - Red dashed: `Lower Management Line  −213.00 m`
  - Dark grey solid: `All-Time Low  −214.87 m`
- Labels appear to the left of each reference line, in English.

**Right-side info panel** (next to the lake, not overlapping):
- Large bold: `Lake Level: −212.53 m MSL` with ▲/▼ coloured trend arrow
- `↓ 0.5 cm since [30-days-ago date]`
- `3.73 m below maximum`
- `Since rainy season start: +88 cm` (Oct 1 baseline)

**Rest of Page 0** (unchanged from spec):
- 3 metric cards: current level, current volume, days since last reading
- 30-day sparkline (Plotly, no axis labels)
- Year-over-year overlay (2020–2026)
- Distance-to-limits callout; red warning banner if below legal min
- Quick-nav cards for all 6 sub-pages

---

## 5. Implementation Decisions

### 5.1 Correlation heatmap click events (Page 3)
Streamlit's native Plotly integration does not expose reliable cell-click callbacks. **Decision:** replace the "click any cell" interaction with a feature-pair dropdown below the heatmap. Selecting a pair shows the scatter + trend line in a panel beneath. Same information, fully supported, no extra dependencies.

### 5.2 Script docstring display (Page 2)
Page 2 reads each `Automation/*.py` file at render time and extracts the module-level docstring for display in `st.code`. Path resolved via `PROJECT_ROOT`. If a file is missing, the expander shows a "file not found" placeholder — no crash.

### 5.3 What-if sliders (Page 6)
Streamlit reruns on every slider change. The forecast is called twice inside the same render pass — once with original inputs, once with scaled/offset inputs — and both traces are drawn on the same Plotly figure (solid vs dashed). No `st.session_state` polling needed.

### 5.4 Historical validation actuals join (Page 5)
After `run_forecast_from_df()` returns the 7-day results, Page 5 joins actuals from the gold table by date:
```python
actuals = gold[gold["date"].isin(result_dates)][["date","level_m","inflow_obstacle_m3"]]
```
Where `actual_level_m` is NaN (gap days), the table shows `—` and those days are excluded from MAE computation with a note.

### 5.5 Feature importance (Page 4)
`GBRegressor` stores trees as `_Node` objects. Importance is computed by summing the variance-reduction at each internal split node across all trees, then normalising. This is implemented as a standalone function in Page 4 (not in `app_utils.py` since it is only used there).

---

## 6. Path Resolution

The original spec's one-liner (`parent.parent`) only works for `app.py`. Pages sit one level deeper and would need `parent.parent.parent`. **Decision:** define `PROJECT_ROOT` once in `app_utils.py` and import it everywhere:

```python
# app_utils.py  (lives at kinneret_app/app_utils.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # → project root

# every page
from app_utils import PROJECT_ROOT
```

This works because `app_utils.py` is always at `kinneret_app/`, so `parent.parent` correctly resolves to the project root regardless of which page imports it.

---

## 7. Install & Launch

```bash
pip install streamlit plotly
streamlit run kinneret_app/app.py
```

Browser opens at `http://localhost:8501`.

---

## 8. Out of Scope (not built in this session)

Per spec section 14 — retrain button, bootstrap confidence intervals, mobile layout, PDF export, email alerts, IMS live ingestion, comparison mode, ensemble Stage 1. None of these are implemented.
