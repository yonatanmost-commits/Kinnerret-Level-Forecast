# Kinneret Forecast Dashboard — Streamlit App Specification

> **Purpose:** A single `streamlit run app.py` launches a multi-page interactive dashboard
> covering the full project lifecycle: data sources → pipeline → statistics → model → forecast.
> All pages share the same Python environment and can directly call the existing model code.

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Repository Layout](#2-repository-layout)
3. [Shared Utilities — `app_utils.py`](#3-shared-utilities--app_utilspy)
4. [Page 0 — Home / Lake Dashboard](#4-page-0--home--lake-dashboard)
5. [Page 1 — Data Sources](#5-page-1--data-sources)
6. [Page 2 — Data Pipeline](#6-page-2--data-pipeline)
7. [Page 3 — Statistics & EDA](#7-page-3--statistics--eda)
8. [Page 4 — Model Info](#8-page-4--model-info)
9. [Page 5 — Forecast: Historical Validation](#9-page-5--forecast-historical-validation)
10. [Page 6 — Forecast: Live Next Week](#10-page-6--forecast-live-next-week)
11. [Styling & Theme](#11-styling--theme)
12. [Installation & Launch](#12-installation--launch)
13. [Data Flow Diagram](#13-data-flow-diagram)
14. [Open Questions / Future Extensions](#14-open-questions--future-extensions)

---

## 1. Technology Stack

| Concern | Package | Notes |
|---|---|---|
| App framework | `streamlit >= 1.35` | Multi-page via `pages/` folder |
| Charting | `plotly >= 5.20` | Interactive, hover, zoom; all charts |
| Data | `pandas`, `numpy` | Already in project env |
| Model | `model_lib.py` (project) | GBRegressor, feature constants |
| Styling | Streamlit theme config | `config.toml` sets brand colours |
| Export | `pandas` CSV / `plotly` PNG | Download buttons on key pages |

No new heavy dependencies. The full install is:

```bash
pip install streamlit plotly --break-system-packages
```

---

## 2. Repository Layout

```
kinneret_app/                          ← new folder inside the project root
├── app.py                             ← Home page (entry point)
├── app_utils.py                       ← Shared loaders, model runner, helpers
├── pages/
│   ├── 1_Data_Sources.py
│   ├── 2_Pipeline.py
│   ├── 3_Statistics.py
│   ├── 4_Model_Info.py
│   ├── 5_Forecast_Historical.py
│   └── 6_Forecast_Live.py
└── .streamlit/
    └── config.toml                    ← Theme: dark bg, teal accent
```

All pages resolve paths relative to the project root using:

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

---

## 3. Shared Utilities — `app_utils.py`

Central module imported by every page. Keeps data loading cached and avoids
re-reading CSVs or re-loading pkl files on every widget interaction.

### 3.1 `load_gold() -> pd.DataFrame`
```python
@st.cache_data
def load_gold() -> pd.DataFrame:
    """Load kinneret_gold_features.csv once; cache for the session."""
```
- Reads `Gold Data/kinneret_gold_features.csv`
- Parses `date` as datetime
- Returns 5,008 rows × 42 columns (2012-09-01 → 2026-05-18)

### 3.2 `load_models() -> tuple[GBRegressor, GBRegressor, dict]`
```python
@st.cache_resource
def load_models():
    """Load gb1, gb2_direct, and model_metadata.json."""
```
- Returns `(gb1, gb2_direct, meta)`
- `gb1`  → `Models/stage1_inflow_rf.pkl` (Stage 1: met → inflow)
- `gb2_direct` → `Models/stage2_direct_gb.pkl` (Stage 2 direct: met + anchor → ΔVol)
- `meta` → `Models/model_metadata.json` (CV results, bathy coefficients, feature lists)
- `@st.cache_resource` means pickle files are read **once** at startup

### 3.3 `run_forecast_from_df(forecast_df, history_df, gb1, gb2_direct, meta) -> list[dict]`
Thin wrapper around `09_weekly_forecast.run_forecast()` that returns the
results list plus stage-1 inflow detail for the step-by-step display.

Returns a list of 7 dicts with keys:
```
day, date, rain_mm, temp_mean_C,
pred_inflow_m3,           ← Stage 1 output (raw m³)
actual_inflow_m3,         ← NaN for future forecasts
pred_dvol_Mm3,            ← Stage 2 output
actual_dvol_Mm3,          ← NaN for future forecasts
cum_dvol_Mm3,
pred_level_m,
actual_level_m,           ← NaN for future forecasts
pred_volume_Mm3,
```

### 3.4 `vol_to_level(volume_Mm3, coeffs) -> float`
Thin re-export of the bathymetric polynomial from `model_lib`.

### 3.5 `LEVEL_MIN`, `LEVEL_MAX`, `LEVEL_LEGAL_MIN`, `LEVEL_LEGAL_MAX`
Constants for the gauge widget:
```python
LEVEL_MIN        = -214.87   # historical all-time low (2001)
LEVEL_MAX        = -208.89   # historical all-time high
LEVEL_LEGAL_MIN  = -213.00   # red lower management line
LEVEL_LEGAL_MAX  = -208.90   # upper spill line
```

---

## 4. Page 0 — Home / Lake Dashboard

**File:** `app.py`  
**Purpose:** Real-time state of the lake. First thing a user sees.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  🌊  KINNERET LEVEL FORECAST               [Last updated: 2026-05-18]│
├───────────────┬──────────────────────────┬───────────────────────────┤
│               │   -212.530 m MSL         │   3,727 Mm³               │
│  [  GAUGE  ]  │   ▲ +0.21 m this month   │   ▲ +12 Mm³ this week     │
│               │   ▼ -0.71 m vs last yr   │   Trend: RISING           │
├───────────────┴──────────────────────────┴───────────────────────────┤
│  [  30-day level sparkline  ──────────────────────────────────── ]   │
├──────────────────────────────────────────────────────────────────────┤
│  [  Year-over-year level overlay chart  (2020-2026 thin lines)  ]    │
├──────────────────────────────────────────────────────────────────────┤
│  📋 Data coverage    ⚙️ Pipeline    📊 Statistics    🧠 Model    🔮 Forecast │
└──────────────────────────────────────────────────────────────────────┘
```

### Components

**Water Level Gauge (SVG via `st.markdown`)**  
A vertical rectangle, filled from the bottom proportional to:
```
fill_pct = (current_level - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)
```
Coloured zones:
- Red zone: below `LEVEL_LEGAL_MIN` (-213.00 m)
- Green zone: `LEVEL_LEGAL_MIN` to `LEVEL_LEGAL_MAX`
- Blue zone: above `LEVEL_LEGAL_MAX`
Current fill line has a label with the level value. Tick marks at -214, -213, -212, -211, -210, -209 m.

**Metric Cards (3 columns)**
- Current level (m MSL), delta vs 30 days ago
- Current volume (Mm³), delta vs 30 days ago
- Days since last reading; model trained-through date

**30-day Sparkline**  
Plotly line chart, last 30 available level readings, no axis labels, minimal chrome. Shows the recent trend visually.

**Year-over-Year Overlay**  
Plotly line chart: x-axis = day-of-year (1–366), y-axis = level_m.  
One thin coloured line per year 2020–2025, one thick bright line for 2026.  
Allows immediate visual comparison to prior dry/wet years.

**"How far from limits?" callouts**
```
Distance to legal minimum:  +0.47 m  (≈ 57 Mm³ buffer)
Distance to spill level:    −3.63 m  (3,727 Mm³ below overflow)
```
If below legal minimum: show red warning banner.

**Quick-Nav Cards**  
Six clickable `st.page_link` cards, one per page, with icon and one-line description.

---

## 5. Page 1 — Data Sources

**File:** `pages/1_Data_Sources.py`  
**Purpose:** Explain where every number in the pipeline comes from.

### Layout

Top: horizontal `st.tabs` — one tab per source.

#### Tab A: Meteorological (IMS)
- **Station:** Kinneret / Zemach area
- **Variables table:** 9 columns (temp_max, temp_min, humidity_pct, wind_speed_ms, rainfall_mm, radiation_MJm2, et0_mm, vpd_kPa, daylength_hrs) — description, unit, derivation method
- **Coverage:** 2012-09-01 → present (from gold table date range)
- **Update cadence:** Manual batch ingestion via `01_ingest_met_data.py`
- **Raw file sample:** `st.dataframe` showing 5 rows from the most recent raw CSV in `Raw Data/Meteorological Data/`
- **Derived features explained:** Short prose on how VPD and ET0 (FAO-56 Penman-Monteith) are computed from raw met inputs

#### Tab B: Kinneret Level (IHS)
- **Source:** Israel Hydrological Service, daily level readings
- **Unit:** metres above mean sea level (m MSL); note: negative because lake is below sea level
- **Coverage:** 2012-09-01 → present; ~86 missing days (~1.7%)
- **Missing-data handling:** Forward-filled for feature computation; never imputed for training targets
- **Silver sample:** 5-row preview of `Silver Data/Kinneret Level/` parquet

#### Tab C: Jordan River / Obstacle Inflow
- **Source:** IHS gauge stations upstream of the lake
- **Key station:** Obstacle gauge (primary inflow used in model)
- **Unit:** m³/day
- **Coverage:** 2012-09-01 → present; gaps visible in null heatmap
- **Note on Baptist Site:** Outflow at the Baptist Site (southern outlet) available only through 2025-06-23; data gap explained with timeline visual

#### Tab D: Coverage Timeline
A Gantt-style Plotly chart:
- y-axis: source name (IMS Met, Kinneret Level, Jordan Inflow, Baptist Outflow)
- x-axis: date (2012 → 2026)
- Coloured bars = data present; white gaps = missing
- Highlights the Baptist Site cutoff at 2025-06-23

---

## 6. Page 2 — Data Pipeline

**File:** `pages/2_Pipeline.py`  
**Purpose:** Show the full ETL chain and let the user browse each layer.

### Layout

```
┌────────────────────────────────────────────────────────────┐
│   BRONZE (Raw)  →  SILVER (Clean)  →  GOLD (Features)     │
│   [diagram with arrows between stages]                      │
├────────────────────────────────────────────────────────────┤
│  [st.tabs: Scripts | Bronze | Silver | Gold]               │
└────────────────────────────────────────────────────────────┘
```

#### Pipeline Diagram
Rendered via `st.markdown` with an HTML/CSS flow diagram:

```
Raw CSVs           Parquets           Feature CSV
(per-station) ──► (cleaned,    ──►   (5,008 rows
                   daily)             42 columns)

01 Ingest Met     04 Clean Met        07 Build Gold
02 Pivot Wide  ─► 05 Clean Flows  ──► 08 Train Model
03 Aggregate      06 Ingest Level     09 Forecast
```

#### Tab: Scripts
`st.expander` per script (01–09), ordered sequentially.  
Each expander shows:
- **Script name** + one-line purpose
- **Inputs** (file paths / sources)
- **Outputs** (file paths / tables)
- **Key transforms** (3–5 bullet points, hand-written)
- `st.code` block showing the script's top docstring (read from file at render time)

Script summaries:

| Script | Purpose |
|--------|---------|
| `01_ingest_met_data.py` | Reads raw IMS CSV files from `Raw Data/Meteorological Data/`; standardises column names |
| `02_pivot_wide_met_data.py` | Pivots per-variable long format to one-row-per-date wide format |
| `03_aggregate_daily_met_data.py` | Optional sub-daily → daily aggregation |
| `04_clean_daily_met_data.py` | Outlier removal, gap-filling, QC flags |
| `05_clean_jordan_river_flow.py` | Cleans and consolidates multi-station flow Excel/CSV data |
| `06_ingest_kinneret_level.py` | Reads level files, converts to Mm³ via bathymetric polynomial |
| `07_build_gold_features.py` | Joins all silver tables; engineers 42 features |
| `07b_precalc_precip_intensity.py` | Adds precipitation intensity feature to gold |
| `08_train_forecast_model.py` | Walk-forward CV + final model training; saves 3 pkl files |
| `09_weekly_forecast.py` | Loads models + forecast CSV; produces 7-day prediction |

#### Tab: Bronze
- List of files in `Raw Data/Meteorological Data/` (count, date range from filename)
- List of files in `Raw Data/Jordan River Stations Raw Data/`
- List of files in `Raw Data/Kinneret_Level/`
- File count and total size per folder

#### Tab: Silver
- List of silver artefacts (parquet / CSV) with row counts
- `st.dataframe` showing column list and 5 preview rows for each silver table
- Null rate per column as a coloured bar (green=0%, red=100%)

#### Tab: Gold
- Full gold feature table: `st.dataframe` with:
  - Date range slider to filter rows
  - Column group multi-select (Seasonality / Met Raw / Met Derived / River Flows / Lake State)
  - 500-row page display with `st.dataframe` native scrolling
- Summary row: 5,008 rows × 42 columns, 2012-09-01 → 2026-05-18
- **Missing-data heatmap:** Plotly heatmap, x = column name (42 cols), y = year (2012–2026).  
  Cell colour = null % for that column in that year. Immediately shows the Baptist Site gap (2025+) and early-year data sparsity.

---

## 7. Page 3 — Statistics & EDA

**File:** `pages/3_Statistics.py`  
**Purpose:** Explore the gold feature table interactively.

### Sub-tabs (4)

#### 3A: Feature Profiler
A sortable summary table of all 42 columns:

| Column | Type | Non-null | Mean | Std | Min | P25 | Median | P75 | Max | Skew | Kurtosis |
|--------|------|----------|------|-----|-----|-----|--------|-----|-----|------|---------|

Clicking any row expands an inline panel showing:
- Histogram + KDE overlay (Plotly)
- Box plot
- Time series of that column (monthly aggregated)
- Null timeline (bar chart: nulls per year)

#### 3B: Correlation Heatmap
- Default: correlation matrix of the 18 Stage-1 + 18 Stage-2 features + 2 targets
- Toggle to show full 42×42 matrix
- Plotly heatmap with diverging colour scale (blue = −1, white = 0, red = +1)
- **Clickable cells:** clicking any cell opens a scatter plot panel below the heatmap showing that pair of features, coloured by season (winter=blue, summer=red), with linear trend line and Pearson r annotation
- Highlight row/column by selecting a feature from a dropdown

#### 3C: Distributions
Two-column layout:
- Left: column selector (grouped: Met / River / Lake State / Derived)
- Right: selected column visualised with:
  - Histogram + KDE (Plotly)
  - Q-Q plot vs normal distribution
  - Skew and kurtosis annotations
  - Toggle: raw values vs log-transformed (useful for inflow_obstacle_m3 with skew=2.22)

Optional overlay: split distribution by season (Oct–Mar vs Apr–Sep) to reveal bimodality in rainfall/inflow.

#### 3D: Seasonal Patterns
Three charts stacked vertically:

**Heatmap 1 — Monthly average level by year**  
x = month (Jan–Dec), y = year (2012–2026), colour = mean level_m.  
Instantly shows: dry summers (negative ΔVol), wet winters (positive ΔVol), 2018 drought, 2018-2020 recovery.

**Heatmap 2 — Monthly average inflow by year**  
Same layout, colour = mean inflow_obstacle_m3.  
Cross-reference against level heatmap to see the inflow → level lag.

**Chart 3 — Seasonal decomposition (level_m)**  
Plotly subplot (4 rows): original, trend (365-day rolling), seasonal (monthly median of residuals), residual.  
Confirms the annual oscillation amplitude (~2–3 m peak-to-trough).

---

## 8. Page 4 — Model Info

**File:** `pages/4_Model_Info.py`  
**Purpose:** Explain the model architecture, performance, and feature behaviour.

### Layout (4 sections)

#### 8.1 Architecture Overview

Prose explanation followed by a visual two-stage flow:

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1 — Inflow Predictor                                 │
│  Input:  18 features (rainfall lags, ET0, seasonality,      │
│          inflow lags)                                        │
│  Model:  GBRegressor (250 trees, depth=4, lr=0.05)          │
│  Output: predicted_inflow_m3                      [Mm³/day] │
│          CV R² = 0.914  |  CV MAE = 0.094 Mm³/day          │
├─────────────────────────────────────────────────────────────┤
│  STAGE 2 — Volume Change Predictor (Direct Multi-Step)      │
│  Input:  18 features (met + predicted inflow +              │
│          ANCHOR state: level at day 0, dvol at day 0,       │
│          horizon_h = 1…7)                                   │
│  Model:  GBRegressor (250 trees, depth=4, lr=0.05)          │
│  Output: volume_change_Mm3  (one prediction per horizon h)  │
│          CV R² = 0.689  |  CV MAE = 0.654 Mm³/day          │
├─────────────────────────────────────────────────────────────┤
│  KEY DESIGN CHOICE — Direct multi-step vs chained           │
│  The anchor state (level + dvol on day 0) is frozen for     │
│  the full 7-day window. The model sees horizon_h (1–7) as   │
│  an explicit feature so it learns that later horizons are   │
│  harder. This eliminates chaining error accumulation.       │
│  Training data: 32,991 rows (4,713 anchors × 7 horizons).  │
└─────────────────────────────────────────────────────────────┘
```

#### 8.2 Cross-Validation Results

Two side-by-side bar charts (S1 and S2), one bar per fold year:

**Stage 1 — Inflow CV**

| Fold | n_test | R² | MAE (Mm³/day) |
|------|--------|----|---------------|
| 2021 | 352 | 0.934 | 0.097 |
| 2022 | 340 | 0.948 | 0.090 |
| 2023 | 311 | 0.833 | 0.100 |
| 2024 | 346 | 0.943 | 0.089 |
| **Mean** | | **0.914** | **0.094** |

**Stage 2 — Volume Change CV**

| Fold | n_test | R² | MAE (Mm³/day) |
|------|--------|----|---------------|
| 2021 | 352 | 0.569 | 0.698 |
| 2022 | 340 | 0.864 | 0.577 |
| 2023 | 311 | 0.564 | 0.681 |
| 2024 | 346 | 0.760 | 0.661 |
| **Mean** | | **0.689** | **0.654** |

Note box: "2021 and 2023 are the hardest folds (drought-to-recovery transitions). The model trained on drier antecedent conditions generalises less well to anomalous wet years."

#### 8.3 Feature Importance

Computed from the GBRegressor trees (sum of squared improvements across all splits, normalised):

Two horizontal bar charts side by side:
- **Stage 1**: top 18 features ranked. Expected top 3: `inflow_lag1_m3`, `inflow_lag2_m3`, `rainfall_7d_mm`
- **Stage 2 direct**: top 18 features ranked. Expected top 3: `level_m_anchor`, `et0_mm`, `predicted_inflow_m3`

Implementation note — `GBRegressor` computes importance via:
```python
def feature_importances(gb, feature_names):
    """Sum split improvements across all trees."""
    importances = np.zeros(len(feature_names))
    for tree in gb.trees_:
        _accumulate_importance(tree, importances)
    importances /= importances.sum()
    return pd.Series(importances, index=feature_names).sort_values(ascending=False)
```

Toggle: normalised (0–1) vs percentage.

#### 8.4 Residual Analysis

Three Plotly subplots:
1. **Predicted vs Actual scatter** (Stage 2, all CV test rows): points coloured by season (blue=winter, red=summer). Diagonal line = perfect forecast. Annotation: R²=0.689, MAE=0.654 Mm³/day.
2. **Residual distribution** (histogram + KDE): residuals = actual − predicted. Should be centred at 0 with slight right skew in winter (underestimated flood peaks).
3. **Residuals over time** (line chart): reveals any temporal drift or seasonal bias. Look for systematic under/over-prediction in summer months.

---

## 9. Page 5 — Forecast: Historical Validation

**File:** `pages/5_Forecast_Historical.py`  
**Purpose:** Pick any week in the gold table history, run the model using actual weather, compare prediction to actual measurements.

### Layout

```
┌────────────────────────────────────────────────────────────────┐
│  SELECT WEEK                                                    │
│  Anchor date (Monday): [date picker, 2013-01-01 → 2026-05-11] │
│  [Run Forecast ▶]                                              │
├────────────────────────────────────────────────────────────────┤
│  ANCHOR STATE                                                   │
│  Level on {date}: -212.635 m  |  ΔVol lag1: +4.75 Mm³         │
├────────────────────────────────────────────────────────────────┤
│  STEP 1: INFLOW PREDICTIONS (Stage 1)                          │
│  [bar chart: predicted vs actual inflow, 7 days]               │
│  [table: day / date / pred_inflow / actual_inflow / error]     │
├────────────────────────────────────────────────────────────────┤
│  STEP 2: VOLUME CHANGE & LEVEL (Stage 2)                       │
│  [line chart: predicted level vs actual level, 7 days]         │
│  [table: full 7-day results with actuals and errors]           │
├────────────────────────────────────────────────────────────────┤
│  ACCURACY SUMMARY                                              │
│  Stage 1 MAE: x.xxx Mm³/day   Stage 2 MAE level: x.xxx m      │
│  Weekly Δ level: predicted vs actual                           │
└────────────────────────────────────────────────────────────────┘
```

### Interaction Flow

1. User selects anchor date (day 0) from `st.date_input`.
2. App loads 21 days of history before anchor date from gold table.
3. App loads 7 days of actual weather for the forecast window from gold table.
4. `st.button("Run Forecast")` triggers `run_forecast_from_df()`.
5. Results appear in two expandable sections (Stage 1 first, Stage 2 second) to show the pipeline step-by-step.

### Stage 1 Display

Grouped bar chart (Plotly):
- Blue bars = predicted inflow (Mm³/day)
- Orange bars = actual inflow (from `inflow_obstacle_m3` in gold)
- x-axis = date (7 days)
- Hover shows absolute values and % error

Below chart: compact table with error column coloured green (<10% error) → yellow (<25%) → red (>25%).

### Stage 2 Display

Line chart (Plotly):
- Blue line = predicted level (m MSL), with ±MAE shaded band
- Orange line = actual level (from `level_m` in gold, where available)
- Dashed horizontal lines at legal min (-213.00) and legal max (-208.90)
- x-axis = date (7 days + anchor day)

Accuracy summary panel:
```
Stage 1  |  Inflow MAE:   x.xxx Mm³/day
Stage 2  |  Level  MAE:   x.xxx m        (days with actual readings)
         |  ΔVol   MAE:   x.xxx Mm³
Weekly   |  Predicted Δ level: +0.076 m  |  Actual Δ level: +0.055 m
```

### Notes on Missing Actuals

Gold table has gaps in level (~86 missing days). Where `actual_level_m` is NaN, the comparison table shows "—" and the metric excludes that day from MAE computation with a note: "MAE based on N of 7 available reading(s)".

---

## 10. Page 6 — Forecast: Live Next Week

**File:** `pages/6_Forecast_Live.py`  
**Purpose:** Enter next week's weather forecast and produce a 7-day lake level prediction.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT STATE                                                   │
│  Last reading: 2026-05-18  |  Level: -212.530 m  |  Vol: 3,727  │
│  Forecasting: 2026-05-19 → 2026-05-25                           │
├─────────────────────────────────────────────────────────────────┤
│  WEATHER FORECAST INPUT                                          │
│  [editable st.data_editor table — 7 rows, columns below]        │
│  [Load template] [Clear] [Use last 7 days as test]              │
├─────────────────────────────────────────────────────────────────┤
│  [Run Forecast ▶]                                               │
├─────────────────────────────────────────────────────────────────┤
│  STEP 1: Predicted River Inflow                                  │
│  [bar chart — 7 days of predicted inflow]                        │
│  [table with inflow values and lag chain state]                  │
├─────────────────────────────────────────────────────────────────┤
│  STEP 2: Volume Change & Level Prediction                        │
│  [level chart with confidence band]                              │
│  [full results table]                                            │
├─────────────────────────────────────────────────────────────────┤
│  WHAT-IF SLIDERS                                                 │
│  Rainfall multiplier:  [0.0× ─────●───── 3.0×]                  │
│  Temperature offset:   [−5°C ──●──────── +5°C]                  │
│  [Re-run with modified weather]                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Download CSV]                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Weather Input Table

An `st.data_editor` with these columns and sensible defaults (pre-filled from the forecast_input_template.csv if it exists, else zeros):

| Column | Type | Unit | Required |
|--------|------|------|----------|
| date | date | YYYY-MM-DD | auto-filled (next 7 days) |
| temp_max_C | float | °C | ✓ |
| temp_min_C | float | °C | ✓ |
| rainfall_mm | float | mm | ✓ |
| humidity_pct | float | % | ✓ |
| wind_speed_ms | float | m/s | ✓ |
| radiation_MJm2 | float | MJ/m² | optional |

Buttons:
- **Load template**: reads `forecast_input_template.csv` from project root
- **Clear**: resets to zeros
- **Use last 7 days as test**: populates with actual gold data for the 7 days before the forecast window (useful for sanity-checking the live model against a known period)

### Stage 1 Display (Inflow Chain)

Bar chart (Plotly) showing predicted inflow for each of the 7 days.  
Below: small table showing how inflow lag1/lag2 chains through the week:

| Day | Horizon | Inflow lag1 → | Pred Inflow | → Becomes lag1 for D+1 |
|-----|---------|---------------|-------------|------------------------|
| 1 | h=1 | hist[-1] | x.xxx Mm³ | → D2 lag1 |
| ... | ... | ... | ... | ... |

This makes the Stage 1 chaining mechanism transparent to the user.

### Stage 2 Display (Direct Model)

Level chart (Plotly):
- Thick blue line = predicted level (m MSL)
- Light blue shaded band = ±0.654 Mm³/day (CV MAE, propagated to level via bathy polynomial)
- Dashed grey line = flat extrapolation from anchor (naïve baseline)
- Horizontal dashed lines: legal min (red, -213.00 m) and legal max (green, -208.90 m)

Annotation box at top right:
```
Anchor: -212.530 m (May 18)
End-of-week: -212.XXX m (May 25)
Change:      +X.XXX m
Trend:       ▲ RISING / ▼ FALLING / — STABLE
```

### What-If Sliders

Two `st.slider` widgets:
- **Rainfall multiplier** (0.0–3.0, step 0.1, default 1.0): scales all 7 days' `rainfall_mm`
- **Temperature offset** (−5 to +5 °C, step 0.5, default 0.0): adds offset to `temp_max_C` / `temp_min_C` / `temp_mean_C`

On slider change, `st.session_state` re-runs the forecast with modified inputs and overlays the alternative prediction as a dashed line on the level chart. Lets the user answer "what if it rains twice as much?" interactively.

### Download

`st.download_button("Download forecast CSV")` writes the 7-row results table including all predicted columns.

---

## 11. Styling & Theme

**File:** `kinneret_app/.streamlit/config.toml`

```toml
[theme]
base            = "dark"
primaryColor    = "#1E90FF"      # Dodger blue — water accent
backgroundColor = "#0F1117"      # Near-black background
secondaryBackgroundColor = "#1A1D27"   # Card / widget bg
textColor       = "#E0E0E0"      # Light grey text
font            = "sans serif"
```

### Consistent Chart Colours

All Plotly charts use a shared palette defined in `app_utils.py`:

```python
COLOURS = {
    "predicted": "#1E90FF",   # blue
    "actual":    "#FF7043",   # orange
    "winter":    "#4FC3F7",   # light blue
    "summer":    "#EF5350",   # red
    "rising":    "#66BB6A",   # green
    "falling":   "#EF5350",   # red
    "stable":    "#BDBDBD",   # grey
    "legal_min": "#EF5350",   # red line
    "legal_max": "#66BB6A",   # green line
    "band":      "rgba(30, 144, 255, 0.15)",  # confidence band fill
}
```

---

## 12. Installation & Launch

### Prerequisites

- Python 3.10+ (already in project environment)
- All existing project dependencies (`pandas`, `numpy`)

### Install Streamlit

```bash
pip install streamlit plotly --break-system-packages
```

### Launch

```bash
cd "C:\Users\yonatanm\OneDrive - ARW Group\Claude Workspace\Data Science Project"
streamlit run kinneret_app/app.py
```

Browser opens automatically at `http://localhost:8501`.

### Development Tips

- `st.cache_data` on `load_gold()` means the 5,008-row CSV loads once then is served from memory — page switches are instant.
- `st.cache_resource` on `load_models()` means pkl files are loaded once at startup.
- To force a full reload (e.g. after retraining): press **C** in the terminal running Streamlit, or use the "Clear cache" option in the browser top-right menu.

---

## 13. Data Flow Diagram

```
Gold CSV (5,008 × 42)
      │
      ├──► Home page:          last row → gauge + metrics
      │
      ├──► Data Sources:       coverage timeline (groupby source × year)
      │
      ├──► Pipeline:           schema + null heatmap + browser
      │
      ├──► Statistics:         full table → profiler, corr, dist, seasonal
      │
      ├──► Model Info:         CV results from model_metadata.json
      │                        feature importance from pkl trees
      │
      ├──► Forecast Historical:
      │        user picks date
      │        → gold[date-21:date]  → history_df
      │        → gold[date+1:date+7] → forecast_df (actual weather)
      │        → run_forecast_from_df()
      │        → compare vs gold[date+1:date+7].level_m
      │
      └──► Forecast Live:
               user fills weather form
               → gold[-21:]  → history_df
               → user input  → forecast_df
               → run_forecast_from_df()
               → display level chart + download
```

---

## 14. Open Questions / Future Extensions

| Item | Priority | Notes |
|------|----------|-------|
| Retrain button on Model Info page | Medium | `subprocess.run(["python", "Automation/08_train_forecast_model.py"])` with live log output via `st.empty()` |
| Confidence intervals from bootstrap | Low | Run forecast N=50 times with random feature perturbation; show P10/P90 bands |
| Multi-horizon accuracy chart | Medium | For any historical week, show MAE as a function of horizon h=1..7 to show how accuracy degrades |
| Mobile layout | Low | Streamlit's default responsive CSS handles most of it; gauge SVG may need narrow variant |
| Export as PDF | Low | `pdfkit` or headless Chrome screenshot; or use the existing `pdf` skill |
| Email/Teams alert | Low | If forecast shows level crossing legal min threshold, send alert |
| IMS live data ingestion | High (operational) | Replace manual CSV drop with API call to IMS; trigger pipeline automatically |
| Comparison mode | Medium | Side-by-side two historical weeks (e.g. dry year vs wet year) |
| Ensemble S1+S2 | Low | Train multiple Stage-1 variants (RF, GB, linear) and average; reduces inflow variance |

---

*Document generated: 2026-05-23. Matches project state: gold table 2012-09-01 → 2026-05-18 (5,008 rows, 42 features). Models trained through 2026-05-18.*
