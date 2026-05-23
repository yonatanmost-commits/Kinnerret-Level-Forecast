# Kinneret Forecast Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 7-page Streamlit dashboard (`kinneret_app/`) for Kinneret water-level forecasting, featuring a lake-silhouette SVG gauge, interactive charts, and a live two-stage forecast engine.

**Architecture:** All pages share `app_utils.py` (cached data loaders + forecast wrapper). The lake SVG gauge on the Home page establishes the visual language. Pages 5 and 6 drive the forecast engine; pages 1–4 are exploratory/informational. Visual pages are built using the `frontend-design` skill for high design quality.

**Tech Stack:** Streamlit ≥ 1.35, Plotly ≥ 5.20, pandas, numpy, custom `GBRegressor` / `RFRegressor` from `Automation/model_lib.py`. No scikit-learn required.

---

## File Map

| File | Responsibility |
|------|---------------|
| `kinneret_app/.streamlit/config.toml` | Dark theme, brand colours |
| `kinneret_app/app_utils.py` | `load_gold`, `load_models`, `run_forecast_from_df`, constants, `PROJECT_ROOT` |
| `kinneret_app/app.py` | Home — lake SVG gauge, metrics, sparkline, YoY chart, nav cards |
| `kinneret_app/pages/1_Data_Sources.py` | Tabbed source descriptions, coverage Gantt |
| `kinneret_app/pages/2_Pipeline.py` | ETL diagram, script expanders, Bronze/Silver/Gold browsers |
| `kinneret_app/pages/3_Statistics.py` | Feature profiler, correlation heatmap, distributions, seasonal patterns |
| `kinneret_app/pages/4_Model_Info.py` | Architecture, CV results, feature importance, residual analysis |
| `kinneret_app/pages/5_Forecast_Historical.py` | Pick past week, run forecast, compare vs actuals with MAE |
| `kinneret_app/pages/6_Forecast_Live.py` | Enter weather, run forecast, what-if sliders, download CSV |

---

## Task 0: Verify Prerequisites

**Files:** none

- [ ] **Step 1: Check Python and pip**

```powershell
python --version
pip show streamlit plotly
```

Expected: Python 3.10+. If streamlit/plotly are missing, run:
```powershell
pip install streamlit plotly
```

- [ ] **Step 2: Confirm model files exist**

```powershell
ls "Models/"
```

Expected output includes: `stage1_inflow_rf.pkl`, `stage2_direct_gb.pkl`, `model_metadata.json`

- [ ] **Step 3: Confirm gold data exists**

```powershell
python -c "import pandas as pd; df = pd.read_csv('Gold Data/kinneret_gold_features.csv'); print(df.shape, df.columns.tolist()[:5])"
```

Expected: `(5008, 42)` and first few column names including `date`, `level_m`, `volume_Mm3`.

---

## Task 1: Project Scaffold + Dark Theme

**Files:**
- Create: `kinneret_app/.streamlit/config.toml`
- Create: `kinneret_app/pages/` (empty directory placeholder)

- [ ] **Step 1: Create directory structure**

```powershell
mkdir -p kinneret_app/.streamlit
mkdir -p kinneret_app/pages
```

- [ ] **Step 2: Write config.toml**

Create `kinneret_app/.streamlit/config.toml`:

```toml
[theme]
base                    = "dark"
primaryColor            = "#1E90FF"
backgroundColor         = "#0F1117"
secondaryBackgroundColor = "#1A1D27"
textColor               = "#E0E0E0"
font                    = "sans serif"
```

- [ ] **Step 3: Verify theme file is valid TOML**

```powershell
python -c "import tomllib; tomllib.load(open('kinneret_app/.streamlit/config.toml','rb')); print('OK')"
```

Expected: `OK`

---

## Task 2: Shared Utilities — `app_utils.py`

**Files:**
- Create: `kinneret_app/app_utils.py`

- [ ] **Step 1: Write app_utils.py**

Create `kinneret_app/app_utils.py` with the full content below:

```python
"""
app_utils.py — Shared utilities for the Kinneret dashboard.

Imported by every page. Provides:
  - PROJECT_ROOT  : absolute path to the project root
  - load_gold()   : cached gold feature DataFrame
  - load_models() : cached (gb1, gb2_direct, meta) tuple
  - run_forecast_from_df() : thin forecast wrapper
  - vol_to_level() : bathymetric polynomial
  - Constants: LEVEL_MIN/MAX, LEVEL_LEGAL_MIN/MAX, COLOURS
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTOMATION   = PROJECT_ROOT / "Automation"
GOLD_FILE    = PROJECT_ROOT / "Gold Data" / "kinneret_gold_features.csv"
MODELS_DIR   = PROJECT_ROOT / "Models"

# Ensure Automation/ is importable (for model_lib)
if str(AUTOMATION) not in sys.path:
    sys.path.insert(0, str(AUTOMATION))

from model_lib import GBRegressor  # noqa: E402

# ── Level constants ───────────────────────────────────────────────────────────
LEVEL_MIN        = -214.87   # historical all-time low (2001)
LEVEL_MAX        = -208.89   # historical all-time high
LEVEL_LEGAL_MIN  = -213.00   # lower management line
LEVEL_LEGAL_MAX  = -208.90   # upper spill line

# ── Chart colour palette ──────────────────────────────────────────────────────
COLOURS = {
    "predicted": "#1E90FF",
    "actual":    "#FF7043",
    "winter":    "#4FC3F7",
    "summer":    "#EF5350",
    "rising":    "#66BB6A",
    "falling":   "#EF5350",
    "stable":    "#BDBDBD",
    "legal_min": "#EF5350",
    "legal_max": "#66BB6A",
    "band":      "rgba(30, 144, 255, 0.15)",
}


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data
def load_gold() -> pd.DataFrame:
    """Load kinneret_gold_features.csv once per session."""
    df = pd.read_csv(GOLD_FILE, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_resource
def load_models():
    """Load trained models and metadata once at startup."""
    gb1        = GBRegressor.load(MODELS_DIR / "stage1_inflow_rf.pkl")
    gb2_direct = GBRegressor.load(MODELS_DIR / "stage2_direct_gb.pkl")
    with open(MODELS_DIR / "model_metadata.json", encoding="utf-8") as f:
        meta = json.load(f)
    return gb1, gb2_direct, meta


# ── Forecast wrapper ──────────────────────────────────────────────────────────

def _load_forecast_module():
    """Import 09_weekly_forecast.py via importlib (numeric filename workaround)."""
    path = AUTOMATION / "09_weekly_forecast.py"
    spec = importlib.util.spec_from_file_location("wf09", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_forecast_from_df(forecast_df: pd.DataFrame,
                         history_df:  pd.DataFrame,
                         gb1, gb2_direct, meta) -> tuple:
    """
    Run the two-stage forecast.

    Returns (results, start_level, start_volume, end_level, end_volume).
    results is a list of 7 dicts with keys:
        day, date, rain_mm, temp_mean_C,
        pred_inflow_Mm3, pred_dvol_Mm3, cum_dvol_Mm3,
        pred_level_m, pred_volume_Mm3

    Actuals (actual_level_m, actual_inflow_m3) are NOT included here.
    Page 5 joins them from the gold table after calling this function.
    """
    wf = _load_forecast_module()
    return wf.run_forecast(forecast_df, history_df, gb1, gb2_direct, meta)


# ── Bathymetric helper ────────────────────────────────────────────────────────

def vol_to_level(volume_Mm3: float, coeffs: list) -> float:
    """Convert volume (Mm³) to level (m MSL) via bathymetric polynomial."""
    return float(np.polyval(coeffs, volume_Mm3))


# ── SVG gauge helper ──────────────────────────────────────────────────────────

def build_lake_svg(current_level: float) -> str:
    """
    Return an inline SVG string of the Kinneret lake silhouette filled
    with a teal gradient up to current_level.

    The silhouette is approximated — wider teardrop at the north,
    narrowing southern tail — recognisably Kinneret-shaped.

    Coordinate system: viewBox="0 0 220 310"
    SVG y=0 is the top (highest water); y=290 is the bottom (all-time low).
    """
    SVG_H = 290.0   # pixel height of the lake shape bottom
    SVG_W = 220.0

    fill_pct = (current_level - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
    fill_pct = max(0.0, min(1.0, fill_pct))
    water_y  = SVG_H * (1.0 - fill_pct)   # y where the water surface sits

    def level_y(lvl: float) -> float:
        p = (lvl - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
        return SVG_H * (1.0 - p)

    legal_max_y = level_y(LEVEL_LEGAL_MAX)
    legal_min_y = level_y(LEVEL_LEGAL_MIN)
    hist_min_y  = level_y(LEVEL_MIN)      # = SVG_H = 290

    # Approximate Kinneret silhouette path (cx=110, widest ~y=100)
    lake_path = (
        "M 110,18 "
        "C 140,12 175,35 190,70 "
        "C 205,105 200,145 188,175 "
        "C 175,205 158,225 142,250 "
        "C 128,270 118,285 110,292 "
        "C 102,285 92,270 78,250 "
        "C 62,225 45,205 32,175 "
        "C 20,145 15,105 30,70 "
        "C 45,35 80,12 110,18 Z"
    )

    svg = f"""
<svg viewBox="0 0 {int(SVG_W)} 310" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:220px;display:block;margin:auto;">
  <defs>
    <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#4FC3F7"/>
      <stop offset="100%" stop-color="#006064"/>
    </linearGradient>
    <clipPath id="wc">
      <rect x="0" y="{water_y:.1f}" width="{int(SVG_W)}" height="310"/>
    </clipPath>
  </defs>

  <!-- Lake outline (empty portion) -->
  <path d="{lake_path}" fill="#1A1D27" stroke="#1E90FF" stroke-width="1.5"/>

  <!-- Water fill clipped to current level -->
  <path d="{lake_path}" fill="url(#wg)" clip-path="url(#wc)"/>

  <!-- Water surface line -->
  <line x1="0" y1="{water_y:.1f}" x2="{int(SVG_W)}" y2="{water_y:.1f}"
        stroke="#4FC3F7" stroke-width="1" stroke-dasharray="4 2"/>

  <!-- Upper management line -->
  <line x1="5"  y1="{legal_max_y:.1f}" x2="155" y2="{legal_max_y:.1f}"
        stroke="#EF5350" stroke-width="1.2" stroke-dasharray="6 3"/>
  <text x="158" y="{legal_max_y + 4:.1f}" fill="#EF5350" font-size="9"
        font-family="sans-serif">Upper mgmt −208.9 m</text>

  <!-- Lower management line -->
  <line x1="5"  y1="{legal_min_y:.1f}" x2="155" y2="{legal_min_y:.1f}"
        stroke="#EF5350" stroke-width="1.2" stroke-dasharray="6 3"/>
  <text x="158" y="{legal_min_y + 4:.1f}" fill="#EF5350" font-size="9"
        font-family="sans-serif">Lower mgmt −213.0 m</text>

  <!-- All-time low line -->
  <line x1="5"  y1="{hist_min_y:.1f}" x2="155" y2="{hist_min_y:.1f}"
        stroke="#9E9E9E" stroke-width="1"/>
  <text x="158" y="{hist_min_y + 4:.1f}" fill="#9E9E9E" font-size="9"
        font-family="sans-serif">All-time low −214.87 m</text>

  <!-- Current level label on the water line -->
  <text x="110" y="{max(water_y - 6, 14):.1f}" fill="#E0E0E0" font-size="10"
        font-family="sans-serif" text-anchor="middle" font-weight="bold">
    {current_level:+.2f} m
  </text>
</svg>"""
    return svg
```

- [ ] **Step 2: Smoke-test the utilities**

```powershell
cd kinneret_app
python -c "
import app_utils as u
df = u.load_gold()
print('Gold shape:', df.shape)
print('Last date:', df['date'].iloc[-1])
svg = u.build_lake_svg(-212.53)
print('SVG chars:', len(svg))
print('OK')
"
cd ..
```

Expected:
```
Gold shape: (5008, 42)
Last date: 2026-05-18 00:00:00
SVG chars: <some number>
OK
```

- [ ] **Step 3: Smoke-test model loading**

```powershell
cd kinneret_app
python -c "
import app_utils as u
gb1, gb2, meta = u.load_models()
print('gb1 trees:', len(gb1.trees_))
print('gb2 trees:', len(gb2.trees_))
print('meta keys:', list(meta.keys())[:4])
print('OK')
"
cd ..
```

Expected: tree counts and meta key names printed without error.

---

## Task 3: Home Page — Lake Gauge + Dashboard (`app.py`)

**Files:**
- Create: `kinneret_app/app.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/app.py` — the Home page of a dark-themed Streamlit dashboard for Kinneret lake water-level forecasting.
>
> Import from `app_utils`: `load_gold`, `load_models`, `build_lake_svg`, `LEVEL_MIN`, `LEVEL_MAX`, `LEVEL_LEGAL_MIN`, `LEVEL_LEGAL_MAX`, `COLOURS`, `PROJECT_ROOT`.
>
> **Layout (left to right, top to bottom):**
>
> 1. Page title: `st.set_page_config(page_title="Kinneret Forecast", page_icon="🌊", layout="wide")`
> 2. Header: "🌊 Kinneret Level Forecast" + last-updated date (from gold table's max date).
> 3. Two-column row — col1 (narrow): `st.markdown(build_lake_svg(current_level), unsafe_allow_html=True)`; col2 (wide): three `st.metric` cards stacked:
>    - "Lake Level" = current `level_m` (delta vs 30 days ago, formatted as `+X.XX m`)
>    - "Volume" = current `volume_Mm3` formatted as `{v:,.0f} Mm³` (delta vs 30 days ago)
>    - "Days Since Reading" = days since max date
> 4. Distance callouts below metrics:
>    - `Distance to Lower Mgmt Line: +X.XX m (≈ Y Mm³ buffer)` — green if positive, red if negative
>    - `Distance to Spill Level: −X.XX m` — always grey
>    - If `current_level < LEVEL_LEGAL_MIN`: show `st.error("⚠️ Lake is below the lower management line!")`
> 5. 30-day sparkline: Plotly line chart of last 30 `level_m` readings. No axis labels, no title, thin blue line, height=120px. Use `COLOURS["predicted"]` for the line.
> 6. Year-over-year overlay: Plotly line chart. x-axis = day of year (1–366), y-axis = `level_m`. One thin line per year 2020–2025, one thick bright line for 2026. Height=280px. Horizontal dashed lines at `LEVEL_LEGAL_MIN` (red) and `LEVEL_LEGAL_MAX` (green).
> 7. Quick-nav section: "Explore the Dashboard" heading + 6 `st.page_link` cards in a 3-column grid:
>    - Data Sources (`pages/1_Data_Sources.py`, icon 📋)
>    - Pipeline (`pages/2_Pipeline.py`, icon ⚙️)
>    - Statistics (`pages/3_Statistics.py`, icon 📊)
>    - Model Info (`pages/4_Model_Info.py`, icon 🧠)
>    - Historical Forecast (`pages/5_Forecast_Historical.py`, icon 🔍)
>    - Live Forecast (`pages/6_Forecast_Live.py`, icon 🔮)
>
> Use the dark theme colours: background `#0F1117`, card bg `#1A1D27`, accent blue `#1E90FF`, text `#E0E0E0`. Make the year-over-year chart compact and readable. The sparkline should feel like a heartbeat, not a full chart.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save generated code to `kinneret_app/app.py`**

- [ ] **Step 3: Launch and verify**

```powershell
streamlit run kinneret_app/app.py
```

Check:
- Lake SVG renders with teal fill
- Three metric cards show real numbers
- Sparkline and YoY chart appear
- Nav cards link to pages (pages will show "not found" until built — that's OK)

---

## Task 4: Page 5 — Forecast: Historical Validation

**Files:**
- Create: `kinneret_app/pages/5_Forecast_Historical.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/5_Forecast_Historical.py` — a Streamlit page that picks any past week from the gold table, runs the two-stage forecast model using actual weather data from that week, and compares predictions to actual lake level readings.
>
> Import from `app_utils`: `load_gold`, `load_models`, `run_forecast_from_df`, `PROJECT_ROOT`, `COLOURS`, `LEVEL_LEGAL_MIN`, `LEVEL_LEGAL_MAX`.
> Also add to sys.path: `str(PROJECT_ROOT / "Automation")` so `09_weekly_forecast.py` can import `model_lib`.
>
> **Interaction flow:**
>
> 1. `st.date_input("Anchor date (Monday = Day 0)", min_value=date(2013,1,8), max_value=<gold_max_date - 7 days>)` — anchor date is day 0 (the day before the 7-day forecast window).
> 2. Show anchor state: level and volume at anchor date (from gold table).
> 3. `st.button("Run Forecast ▶")` — on click:
>    a. `history_df` = gold rows in the 21 days ending on anchor date.
>    b. `forecast_df` = gold rows for the 7 days after anchor date, renamed to match forecast columns: `temp_max_C`, `temp_min_C`, `rainfall_mm`, `humidity_pct`, `wind_speed_ms`, `radiation_MJm2`.
>    c. Call `run_forecast_from_df(forecast_df, history_df, gb1, gb2_direct, meta)`.
>    d. Join actuals: merge results with gold on date to get `actual_level_m` and `actual_inflow_obstacle_m3`.
>
> **Display after run:**
>
> Stage 1 section (expandable, default open):
> - Grouped bar chart: predicted inflow (blue) vs actual inflow (orange), 7 bars each, x=date.
> - Table: day / date / pred_inflow_Mm3 / actual_inflow_m3 (converted to Mm³) / error_pct. Error column coloured: green <10%, yellow <25%, red ≥25%.
>
> Stage 2 section (expandable, default open):
> - Line chart: predicted level (blue solid, ±0.654 Mm³ band) vs actual level (orange dashed). Horizontal dashed lines at legal min (red) and legal max (green). x = date range (anchor day + 7 days).
> - Full results table: day, date, pred_level_m, actual_level_m, error_m. NaN actuals show "—".
>
> Accuracy summary panel (3 columns):
> - Stage 1 Inflow MAE: mean absolute error in Mm³/day (days with actual data only)
> - Stage 2 Level MAE: mean absolute error in m (days with actual data only)
> - Weekly Δ level: predicted change vs actual change
> Note below: "MAE based on N of 7 available readings" where N = count of non-NaN actuals.
>
> Use `COLOURS` palette. Dark theme. All Plotly charts use `template="plotly_dark"`.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save generated code to `kinneret_app/pages/5_Forecast_Historical.py`**

- [ ] **Step 3: Verify**

```powershell
streamlit run kinneret_app/app.py
```

Navigate to Page 5. Pick a date (e.g. 2024-01-15), click Run Forecast. Verify charts render and MAE is shown.

---

## Task 5: Page 6 — Forecast: Live Next Week

**Files:**
- Create: `kinneret_app/pages/6_Forecast_Live.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/6_Forecast_Live.py` — the live forecast page. User enters next-week's weather forecast, the model predicts 7-day lake level trajectory.
>
> Import from `app_utils`: `load_gold`, `load_models`, `run_forecast_from_df`, `PROJECT_ROOT`, `COLOURS`, `LEVEL_LEGAL_MIN`, `LEVEL_LEGAL_MAX`, `vol_to_level`.
>
> **Current state banner:**
> Show last reading date, level, volume from gold table's last row.
> Show forecasting window: last_date+1 → last_date+7.
>
> **Weather input table:**
> `st.data_editor` with 7 rows (dates auto-filled: last_date+1 through last_date+7) and columns:
> `date` (display only), `temp_max_C` (float), `temp_min_C` (float), `rainfall_mm` (float), `humidity_pct` (float), `wind_speed_ms` (float), `radiation_MJm2` (float, optional).
>
> Three buttons in a row:
> - "Load template": read `PROJECT_ROOT / "forecast_input_template.csv"`, populate editor via `st.session_state`.
> - "Clear": reset all numeric columns to 0.0.
> - "Use last 7 days as test": fill with actual gold data for the 7 days before the forecast window.
>
> **Run button:** `st.button("Run Forecast ▶")`
>
> On run:
> - `history_df` = last 21 rows of gold table.
> - `forecast_df` = the data_editor values as a DataFrame.
> - Call `run_forecast_from_df(...)`.
>
> **Stage 1 display (inflow chain):**
> Bar chart: predicted inflow for each of the 7 days (blue bars). Height 200px.
> Small table showing the lag chain: Day | Horizon | Input lag1 | Pred Inflow | → Next lag1.
>
> **Stage 2 display (level prediction):**
> Line chart:
> - Thick blue line = predicted level (m MSL)
> - Light blue shaded band = ±0.654 Mm³/day propagated to level (use `vol_to_level` with bathy coeffs from meta)
> - Grey dashed = flat anchor baseline (constant at start_level for 7 days)
> - Red dashed horizontal: Lower Mgmt Line (−213.00 m)
> - Green dashed horizontal: Upper Mgmt Line (−208.90 m)
>
> Annotation box (top right of chart): Anchor level | End-of-week level | Change | Trend (▲/▼/—).
>
> **What-if sliders (below chart):**
> - Rainfall multiplier: `st.slider("Rainfall multiplier", 0.0, 3.0, 1.0, 0.1)`
> - Temperature offset: `st.slider("Temperature offset (°C)", -5.0, 5.0, 0.0, 0.5)`
> On slider change: re-run forecast with modified weather. Overlay as dashed blue line on the level chart. Legend: "Base forecast" vs "What-if forecast".
>
> **Download button:** `st.download_button("Download forecast CSV", data=results_df.to_csv(index=False), file_name="kinneret_forecast.csv", mime="text/csv")`
>
> Use `COLOURS` palette. Dark theme. `template="plotly_dark"` for all charts.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save generated code to `kinneret_app/pages/6_Forecast_Live.py`**

- [ ] **Step 3: Verify**

```powershell
streamlit run kinneret_app/app.py
```

Navigate to Page 6. Click "Use last 7 days as test", then Run Forecast. Check inflow bar chart, level line chart, and download button.

---

## Task 6: Page 3 — Statistics & EDA

**Files:**
- Create: `kinneret_app/pages/3_Statistics.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/3_Statistics.py` — an interactive statistics and EDA page for the gold feature table.
>
> Import from `app_utils`: `load_gold`, `COLOURS`.
>
> **Four sub-tabs using `st.tabs(["Feature Profiler", "Correlation", "Distributions", "Seasonal Patterns"])`:**
>
> **Tab 1 — Feature Profiler:**
> Compute a summary table for all numeric columns: count non-null, mean, std, min, p25, median, p75, max, skew, kurtosis.
> Display as `st.dataframe` with column type indicator. When user selects a row (use `st.selectbox` of column names above the table), show below:
> - Plotly histogram + KDE (use `ff.create_distplot` or manual KDE) 
> - Box plot
> - Monthly-aggregated time series
>
> **Tab 2 — Correlation:**
> Compute Pearson correlation matrix of all 42 numeric columns.
> Plotly heatmap, diverging scale (blue=−1, white=0, red=+1), `zmin=-1, zmax=1`.
> Below heatmap: two `st.selectbox` widgets ("Feature A", "Feature B"). On selection, show scatter plot coloured by season (Oct–Mar = `COLOURS["winter"]`, Apr–Sep = `COLOURS["summer"]`), linear trendline via numpy polyfit, Pearson r annotation.
>
> **Tab 3 — Distributions:**
> Two columns: left = column selector grouped by category (Met Raw / Met Derived / River Flows / Lake State / Seasonality). Right = selected column shown with:
> - Histogram + KDE (Plotly)
> - Toggle `st.checkbox("Log transform")` — applies `np.log1p` to positive values
> - Split by season: `st.checkbox("Split by season")` — overlay two histograms (winter blue, summer red)
>
> **Tab 4 — Seasonal Patterns:**
> Three charts stacked:
> 1. Heatmap — monthly mean `level_m` by year. x=month (Jan–Dec), y=year (2012–2026). Plotly heatmap, `colorscale="RdBu"`, `zmid` at the series mean.
> 2. Heatmap — monthly mean `inflow_obstacle_m3` by year. Same layout, `colorscale="Blues"`.
> 3. Seasonal decomposition of `level_m`: compute 365-day rolling mean (trend), subtract for residual. Show 3-subplot Plotly figure: original, trend, residual. Height 400px.
>
> Use dark theme. `template="plotly_dark"`. All charts responsive.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save generated code to `kinneret_app/pages/3_Statistics.py`**

- [ ] **Step 3: Verify**

Navigate to Statistics page. Confirm all 4 tabs render without error. Select a feature in Tab 1 and check the plots appear.

---

## Task 7: Page 4 — Model Info

**Files:**
- Create: `kinneret_app/pages/4_Model_Info.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/4_Model_Info.py` — model architecture, cross-validation results, feature importance, and residual analysis.
>
> Import from `app_utils`: `load_gold`, `load_models`, `PROJECT_ROOT`, `COLOURS`.
> Also import from `model_lib` (via sys.path): `S1_FEATURES`, `S2_DIRECT_FEATURES`, `GBRegressor`.
>
> **Section 1 — Architecture Overview:**
> Two `st.expander` blocks side by side (use columns):
> - Stage 1: title, 18 input features listed, model params (250 trees, depth=4, lr=0.05), output description, CV R² and MAE from `meta["cv_s1_mean_r2"]` and `meta["cv_s1_mean_mae"]`.
> - Stage 2 Direct: same structure, 18 features listed, anchor-state explanation, CV R² from `meta["cv_s2_mean_r2"]` and MAE from `meta["cv_s2_mean_mae"]`.
> Below: a styled `st.info` callout explaining the direct multi-step design choice (frozen anchor state, horizon_h feature eliminates chaining error).
>
> **Section 2 — Cross-Validation Results:**
> Two side-by-side Plotly bar charts (one per stage). x=fold year, y=R² (bars) + MAE (line on secondary axis). Data from `meta` — keys to check: `cv_s1_folds`, `cv_s2_folds` (list of dicts with `year`, `r2`, `mae`, `n_test`). If folds not in meta, use the hardcoded values from the spec:
>
> Stage 1 folds: [(2021, 0.934, 0.097), (2022, 0.948, 0.090), (2023, 0.833, 0.100), (2024, 0.943, 0.089)]
> Stage 2 folds: [(2021, 0.569, 0.698), (2022, 0.864, 0.577), (2023, 0.564, 0.681), (2024, 0.760, 0.661)]
>
> Mean line annotation on each chart.
>
> **Section 3 — Feature Importance:**
> Compute importance from `gb1` and `gb2_direct` trees using this function:
> ```python
> def feature_importances(gb, feature_names):
>     from model_lib import _predict_tree
>     importances = np.zeros(len(feature_names))
>     for tree in gb.trees_:
>         _accumulate_node(tree, importances)
>     importances /= importances.sum() if importances.sum() > 0 else 1
>     return pd.Series(importances, index=feature_names).sort_values(ascending=False)
>
> def _accumulate_node(node, arr):
>     if node.feat == -1: return
>     arr[node.feat] += 1   # count splits per feature as proxy for importance
>     _accumulate_node(node.left, arr)
>     _accumulate_node(node.right, arr)
> ```
> Two horizontal bar charts side by side. `COLOURS["predicted"]` bars. Toggle: normalised (0–1) vs percentage.
>
> **Section 4 — Residual Analysis:**
> Load gold table, restrict to dates covered by CV (2021–2024). Run Stage 2 predictions using actual features (use `gb2_direct.predict(X)` with `S2_DIRECT_FEATURES` columns from gold). Compute residuals = actual `volume_change_Mm3` − predicted.
>
> Three Plotly subplots (stacked):
> 1. Predicted vs Actual scatter coloured by season, diagonal line, R² annotation.
> 2. Residual histogram + KDE.
> 3. Residuals over time (line chart).
>
> Use dark theme. `template="plotly_dark"`.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save generated code to `kinneret_app/pages/4_Model_Info.py`**

- [ ] **Step 3: Verify**

Navigate to Model Info. Confirm all 4 sections render. Check feature importance bars are non-zero.

---

## Task 8: Page 1 — Data Sources

**Files:**
- Create: `kinneret_app/pages/1_Data_Sources.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/1_Data_Sources.py` — a tabbed data-sources reference page.
>
> Import from `app_utils`: `load_gold`, `PROJECT_ROOT`, `COLOURS`.
>
> **Four tabs: `st.tabs(["Meteorological (IMS)", "Kinneret Level (IHS)", "Jordan River / Inflow", "Coverage Timeline"])`**
>
> **Tab A — Meteorological:**
> - Station info: Kinneret/Zemach area.
> - Variables table (`st.dataframe`): columns = Variable, Description, Unit, Derivation. 9 rows for: temp_max_C, temp_min_C, humidity_pct, wind_speed_ms, rainfall_mm, radiation_MJm2, et0_mm, vpd_kPa, daylength_hrs.
> - Coverage: show `gold["date"].min()` to `gold["date"].max()`.
> - Raw file sample: list CSV files in `PROJECT_ROOT / "Raw Data/Meteorological Data/"`. Show 5-row preview of the most recent one.
> - Short prose: how VPD (saturation vapour pressure deficit) and ET₀ (FAO-56 Penman-Monteith) are derived from raw met inputs.
>
> **Tab B — Kinneret Level:**
> - Source: Israel Hydrological Service, daily readings, m MSL (negative = below sea level).
> - Coverage from gold table. Compute missing day count from date range vs actual rows.
> - 5-row preview from `Silver Data/Kinneret Level/kinneret_level.csv` if it exists, else from gold `level_m` column.
> - Note: missing days forward-filled for features, never imputed for training targets.
>
> **Tab C — Jordan River / Inflow:**
> - Source: IHS gauge stations.
> - Key stat: Obstacle station, unit m³/day.
> - 5-row preview from `Silver Data/Jordan River Silver/jordan_river_daily_flow_clean.csv`.
> - Baptist Site outflow note: data gap after 2025-06-23 (display as `st.warning`).
>
> **Tab D — Coverage Timeline:**
> Plotly Gantt-style chart:
> - y-axis: ["IMS Meteorological", "Kinneret Level", "Jordan Inflow", "Baptist Site Outflow"]
> - x-axis: date (2012 → 2026)
> - Each source is a coloured horizontal bar from its min to max date in the gold table (or silver files).
> - Baptist Site bar ends at 2025-06-23.
> - Gaps shown as white space.
> Height=250px. Dark theme.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save to `kinneret_app/pages/1_Data_Sources.py`**

- [ ] **Step 3: Verify**

Navigate to Data Sources. Check all 4 tabs render. Verify Coverage Timeline appears.

---

## Task 9: Page 2 — Data Pipeline

**Files:**
- Create: `kinneret_app/pages/2_Pipeline.py`

**Use the `frontend-design` skill with this context:**

> Build `kinneret_app/pages/2_Pipeline.py` — the ETL pipeline explorer.
>
> Import from `app_utils`: `load_gold`, `PROJECT_ROOT`, `COLOURS`.
>
> **Pipeline flow diagram (top of page):**
> Use `st.markdown` with styled HTML to show the 3-stage ETL flow:
> ```
> Raw CSVs → (Bronze) → Parquets (Silver) → Feature CSV (Gold)
>  Scripts 01–03       Scripts 04–06         Scripts 07–09
> ```
> Style with coloured boxes (Bronze=#6D4C41, Silver=#546E7A, Gold=#F9A825) on dark background.
>
> **Four tabs: `st.tabs(["Scripts", "Bronze", "Silver", "Gold"])`**
>
> **Tab: Scripts**
> One `st.expander` per script, ordered 01–09. Each expander shows:
> - Script name + one-line purpose
> - Inputs / Outputs (bullet points)
> - Key transforms (3–5 bullets, hand-written per script below)
> - `st.code(docstring, language="python")` where docstring is read from the file via:
>   ```python
>   import ast
>   tree = ast.parse(open(script_path).read())
>   docstring = ast.get_docstring(tree) or "No docstring."
>   ```
>   If file not found: show "Script not found at {path}".
>
> Script metadata (hard-code in the page, do not read from file):
> | Script | Purpose | Key Transforms |
> |--------|---------|----------------|
> | 01_ingest_met_data.py | Read raw IMS CSVs, standardise column names | Reads all CSVs in Raw Data/Meteorological Data/, renames station columns, outputs long-format DataFrame |
> | 02_pivot_wide_met_data.py | Pivot per-variable long format to one-row-per-date wide | Groups by date, pivots variable column, fills gaps |
> | 03_aggregate_daily_met_data.py | Sub-daily → daily aggregation | Min/max/mean per day depending on variable |
> | 04_clean_daily_met_data.py | Outlier removal, QC flags | IQR-based outlier detection, forward-fill short gaps |
> | 05_clean_jordan_river_flow.py | Clean multi-station flow data | Consolidates Excel/CSV stations, removes duplicates, unit conversion |
> | 06_ingest_kinneret_level.py | Read level files, convert to Mm³ | Reads Miflas CSV, applies bathymetric polynomial, saves silver parquet |
> | 07_build_gold_features.py | Join all silver tables, engineer 42 features | Date alignment, rolling windows, moisture balance, seasonality features |
> | 07b_precalc_precip_intensity.py | Add precipitation intensity feature | Computes intensity bins, joins to gold |
> | 08_train_forecast_model.py | Walk-forward CV + final model training | 4-fold CV, trains Stage 1 and Stage 2 models, saves pkl + metadata |
> | 09_weekly_forecast.py | Two-stage 7-day forecast | Loads models, builds feature rows, runs Stage 1 then Stage 2 direct |
>
> **Tab: Bronze**
> List files in `Raw Data/Meteorological Data/` (filename, size in KB).
> List files in `Raw Data/Jordan River Stations Raw Data/` (filename, size in KB).
> List files in `Raw Data/Kinneret_Level/` (filename, size in KB).
> Show total file count and total size per folder.
>
> **Tab: Silver**
> For each silver CSV/parquet in `Silver Data/`, show: filename, row count, column count, 5-row preview in `st.dataframe`. Null rate per column as a compact bar (use `st.progress` or a Plotly bar).
>
> **Tab: Gold**
> Column group multi-select: `st.multiselect("Column groups", ["Seasonality","Met Raw","Met Derived","River Flows","Lake State"], default=["Lake State","Met Raw"])`.
> Filter gold table to selected groups + always include `date`.
> Date range slider: `st.slider("Date range", min_date, max_date, (min_date, max_date))`.
> Show filtered table via `st.dataframe(height=400)`.
> Summary: "Showing X rows × Y columns | Full table: 5,008 rows × 42 columns".
> Missing-data heatmap: Plotly heatmap, x=column name, y=year, colour=null % per year. Immediate visual of the Baptist Site gap (2025+).
>
> Use dark theme throughout.

- [ ] **Step 1: Invoke `frontend-design` skill with the context above**

- [ ] **Step 2: Save to `kinneret_app/pages/2_Pipeline.py`**

- [ ] **Step 3: Verify**

Navigate to Pipeline. Expand a script, check docstring displays. Check Gold tab loads the data editor.

---

## Task 10: Final Integration Check

**Files:** none (verification only)

- [ ] **Step 1: Full app launch**

```powershell
streamlit run kinneret_app/app.py
```

- [ ] **Step 2: Walk through all pages**

| Page | Check |
|------|-------|
| Home | Lake SVG renders, metrics show real numbers, YoY chart has multiple years |
| Data Sources | All 4 tabs render, coverage Gantt appears |
| Pipeline | Script expanders work, Gold tab filters correctly |
| Statistics | All 4 tabs render, feature selector works |
| Model Info | Feature importance bars non-zero, residual charts appear |
| Forecast Historical | Pick a date, run forecast, MAE appears |
| Forecast Live | Load template or fill manually, run forecast, what-if sliders respond |

- [ ] **Step 3: Check for console errors**

In the terminal running streamlit, confirm no Python tracebacks during normal navigation.

- [ ] **Step 4: Verify path resolution**

All pages should successfully import `app_utils` and load the gold CSV without FileNotFoundError.

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Home gauge — lake SVG silhouette (Task 3)
- ✅ 30-day sparkline and YoY overlay (Task 3)
- ✅ Data Sources with 4 tabs and Gantt (Task 8)
- ✅ Pipeline ETL diagram + script docs + Bronze/Silver/Gold browsers (Task 9)
- ✅ Statistics: profiler, correlation, distributions, seasonal (Task 6)
- ✅ Model Info: architecture, CV, feature importance, residuals (Task 7)
- ✅ Forecast Historical with actuals join + MAE (Task 4)
- ✅ Forecast Live with what-if sliders + download (Task 5)
- ✅ Dark theme config.toml (Task 1)
- ✅ `run_forecast_from_df` importlib workaround for numeric filename (Task 2)
- ✅ `PROJECT_ROOT` defined once in app_utils, imported by all pages (Task 2)

**Known simplification from spec:**
- Correlation heatmap uses dropdown pair selector instead of click-to-scatter (Streamlit limitation noted in design doc).
