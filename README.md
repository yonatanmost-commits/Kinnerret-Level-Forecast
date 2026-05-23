# Kinneret Level Forecast

A machine-learning pipeline and interactive Streamlit dashboard for forecasting the water level of Lake Kinneret (Sea of Galilee), Israel.

---

## Overview

Lake Kinneret sits below sea level and is Israel's primary freshwater reservoir. This project ingests daily meteorological, hydrological, and lake-level data, trains a two-stage gradient-boosting model, and serves 7-day level forecasts through a 7-page Streamlit dashboard.

---

## Dashboard Pages

| Page | Description |
|---|---|
| 🌊 **Home** | Current level gauge, 30-day trend, year-over-year comparison |
| 📋 **Data Sources** | Coverage timeline, raw/silver data samples, variable definitions |
| ⚙️ **Data Pipeline** | ETL script descriptions and data-layer diagram |
| 📊 **Statistics & EDA** | Feature distributions, correlations, seasonality |
| 🧠 **Model Info** | Architecture, cross-validation results, feature importance, residuals |
| 🔍 **Historical Forecast** | Run the model on any past week and compare against actuals |
| 🔮 **Live Forecast** | Enter next week's weather → 7-day level & volume prediction |

---

## Model Architecture

**Stage 1 — Inflow Predictor**
- Input: rainfall lags, ET₀, VPD, seasonality, inflow autocorrelation
- Model: GradientBoosting · 250 trees · depth=4 · lr=0.05
- Output: predicted daily inflow (m³/day)
- CV R²: ~0.91

**Stage 2 — Volume Change (Direct multi-step)**
- Input: meteorological features + Stage 1 inflow + anchor state (level₀, ΔVol₀) + horizon h (1–7)
- Model: GradientBoosting · 250 trees · depth=4 · lr=0.05
- Output: cumulative volume change → converted to lake level via bathymetric polynomial
- CV R²: ~0.69

The direct multi-step design freezes the anchor state for the full 7-day window, eliminating cumulative chaining error.

---

## Data Sources

| Source | Data |
|---|---|
| Israel Meteorological Service (IMS) | Daily temperature, humidity, wind, rainfall, radiation |
| Israel Hydrological Service (IHS) | Kinneret level (m MSL), Jordan River inflow |
| Derived | ET₀ (FAO-56 Penman-Monteith), VPD, day length, rainfall lags |

Management lines: Lower −213.0 m MSL · Upper (spill) −208.9 m MSL

---

## Project Structure

```
├── Automation/          # ETL + training + forecast scripts (01–09)
│   ├── model_lib.py     # GBRegressor implementation
│   └── 09_weekly_forecast.py
├── kinneret_app/        # Streamlit dashboard
│   ├── app.py           # Home page
│   ├── app_utils.py     # Shared utilities, SVG gauge, data loaders
│   ├── pages/           # 6 sub-pages
│   └── .streamlit/      # Theme config (dark, accent #1E90FF)
├── docs/                # Design specs and implementation plans
└── Models/              # Trained model artefacts (not tracked in git)
```

---

## Running the Dashboard

```bash
pip install streamlit plotly pandas numpy
python -m streamlit run kinneret_app/app.py
```

Data directories (`Gold Data/`, `Silver Data/`, `Raw Data/`) and trained model binaries are excluded from the repository. Run the Automation scripts in order (01→08) to regenerate them.

---

## Key Management Lines

| Threshold | Level |
|---|---|
| Upper management (spill) | −208.90 m MSL |
| Lower management | −213.00 m MSL |
| Historical low (2001) | −214.87 m MSL |
