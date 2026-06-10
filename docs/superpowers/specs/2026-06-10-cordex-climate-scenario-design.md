# CORDEX Climate Scenario Product — Design

**Date:** 2026-06-10  
**Status:** Approved  
**Branch:** `longrange-temp-forecast`

---

## Purpose

Turn the 12-model CORDEX RCP4.5/RCP8.5 ensemble (daily tmin/tmax, 2006–2100,
two sites) into a Kinneret water-balance climate projection. The product is a
new Streamlit dashboard page — page 9 — sitting alongside the existing 7-day
forecast and Expert Commentary pages.

This is **not** a forecast. It is a scenario: what warming does to evaporative
demand and catchment response, with pumping and inflow held at modern-period
climatology.

---

## Governing constraints

| Rule | Rationale |
|---|---|
| No single "level in 2080" point | Over-precision violates the confidence-split |
| Evap demand = HIGH confidence | Hargreaves chain is deterministic physics |
| Rain propensity = MEDIUM, bands only | AUC 0.811 gate licenses inference, not mm totals |
| Inflow amount + pumping = stated assumptions | Non-stationary, not in any climate file |
| Hindcast gate before forward plot | Credibility must be earned on the 2006–2024 overlap |
| Winsorize tmax > 49°C at ingestion | QDM tail-inflation artifact in source data |

---

## Data

| File | Rows | Content |
|---|---|---|
| `bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv` | 829 k | Inflow-valley temps |
| `zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv` | 829 k | Outlet/gauge temps |
| ERA5 corrected (`Silver Data/era5_corrected.csv`) | 24 k | Phase A bias-corrected reanalysis |
| Gold (`Silver Data/gold_2012_present.csv`) | ~4 k | Observed levels for hindcast check |
| DOY climatology (`Silver Data/longrange_climatology.csv`) | 366 rows | Normals, σ, wet-day freq |
| Outflow climatology (`Silver Data/outflow_climatology.csv`) | 366 rows | Modern-regime DOY median |
| Hargreaves config (`Silver Data/hargreaves_config.json`) | — | slope=1.06, intercept=0.81 |

**Site roles:** `bet-zayda` = inflow-valley (weather that feeds the catchment);
`zemah` = lake outlet (lake-surface weather, drives open-water evaporation).
Use `bet-zayda` for catchment-side computation (rain propensity, bucket, runoff);
use `zemah` for lake ET₀ (open-water evaporation from the lake surface itself).

---

## Computation chain

```
CORDEX tmin/tmax (winsorized tmax≤49°C at ingestion)
        ↓
[bet-zayda]                         [zemah]
Hargreaves ET₀ (slope 1.06)         Hargreaves ET₀ (open-water)
DTR → cloud_index                   → lake_ET_mm/day × lake_area_km²
→ hurdle rain propensity P̂_t
→ soil-moisture bucket S_t, Q_t
        ↓
ΔV/day = Q_t × catchment_scale_Mm³/mm
         − lake_ET_Mm³/day
         − outflow_clim(DOY)
        ↓
V_t = V_{t-1} + ΔV_t      (anchored at observed V on 2006-01-01)
level_t = poly(V_t)         (existing bathymetric polynomial)
```

All modules are Phase A artifacts already on disk — no new training required.

**Key constants (calibrate in Phase B step, or carry forward from Phase A):**
- `catchment_scale`: mm rainfall over catchment → Mm³ inflow. Fit by regressing
  `Q_t_bucket` against observed net inflow on the 2012–2024 gold overlap.
- `lake_area_km²` ≈ 166 km² (standard). Convert lake_ET_mm × 166 km² × 0.001 = Mm³.
- `S_max` ≈ 150 mm (Phase A default; tune to minimise hindcast RMSE).

---

## Ensemble handling

- All 12 models run independently. **Never average before plotting** — the spread
  is the message.
- Ribbon = 10th–90th percentile across models. Individual thin lines behind ribbon.
- RCP4.5 and RCP8.5 in distinct palette colors (cool vs warm).
- 12 models × 2 scenarios = 24 time series per chart; thin lines, low opacity.

---

## Dashboard page — "Climate Scenarios" (page 9)

### Layout

```
[Header] "What does warming do to the Kinneret?"
[Assumption callout] — prominent, not footnoted
[Tab 1: Evaporative Demand]   [Tab 2: Water Balance]   [Tab 3: Hindcast Check]
```

### Assumption callout (fixed, always visible)

> "Inflow volume and pumping are held at modern-period climatology.
> This projection shows the effect of temperature — not of policy or land use."

### Tab 1 — Evaporative Demand (HIGH confidence)

Chart: Annual sum of lake ET₀ (Mm³/year) vs year, 2006–2100.
- RCP4.5 ribbon + individual lines
- RCP8.5 ribbon + individual lines
- Horizontal reference: 2006–2024 observed mean (dashed)
- Y-axis label: "Open-water evaporation demand (Mm³/year)"
- Confidence badge: `HIGH — deterministic physics`

Sub-chart: Tmax seasonal anomaly by decade (to show when summer heat intensifies).

### Tab 2 — Water Balance & Level (MEDIUM confidence)

Chart A: Annual mean lake level (m above sea level) vs year, 2006–2100.
- Same ribbon/line treatment as Tab 1
- Horizontal bands: red line (lower operating level), blue line (full level)
- No single "level in 2080" number — only the envelope

Chart B: 2030 / 2050 / 2100 snapshot box plots.
- X-axis: horizon
- Y-axis: annual mean level
- Two box groups (RCP4.5, RCP8.5) per horizon
- Confidence badge: `MEDIUM — rain propensity estimated, not measured`

### Tab 3 — Hindcast Credibility (2006–2024)

Chart: Observed Kinneret level vs ensemble median projection, 2006–2024.
- Observed: solid black line
- Ensemble 10/90 ribbon
- RMSE and correlation displayed
- Gate rule: if RMSE > 2 m the forward projection shows a warning banner
  ("Hindcast skill insufficient — forward projections are exploratory only")

---

## Confidence-split display rules

| Tier | Visual treatment |
|---|---|
| HIGH | Solid ribbon, badge "HIGH — deterministic physics" |
| MEDIUM | Hatched ribbon or reduced opacity, badge "MEDIUM — propensity only" |
| ASSUMPTION | Italic text, never plotted as a line |

Rain propensity numbers (P̂_t) are **never shown as mm totals in the UI** —
only as a directional forcing inside the water-balance computation.

---

## Calibration step (one-time, before page ships)

Before plotting forward projections, fit `catchment_scale` on the 2012–2024
gold overlap by minimising hindcast RMSE of annual mean level. Record the fitted
value and the hindcast RMSE in a config JSON alongside the Hargreaves config.
This is not ML training — it is one scalar regression, reproducible in seconds.

---

## Implementation outline

1. **`longrange_cordex_ingest.py`** — load both CORDEX files, winsorize, build
   `(date, model, scenario, site, tmin, tmax)` long frame. Cache as parquet.
2. **`longrange_cordex_waterbalance.py`** — run the computation chain per
   `(model, scenario)`. Outputs daily ΔV + level. Cache as parquet.
3. **`longrange_cordex_calibrate.py`** — fit `catchment_scale` on gold overlap;
   write to `Silver Data/cordex_config.json`.
4. **`longrange_cordex_hindcast.py`** — run chain on 2006–2024, compare to
   observed. Writes RMSE/corr to config.
5. **`pages/09_climate_scenarios.py`** — Streamlit page. Reads cached parquet,
   renders three tabs.
6. **Tests** — unit tests for winsorization, water-balance step (mass balance
   check), calibration round-trip.

---

## Out of scope

- Snowmelt, teleconnection indices, sea-level pressure
- Any new ML model (the physics chain is the model)
- Changes to the 7-day forecast
- IMS extended forecast integration (live forecast product is a separate future step)
- Soil-moisture bucket back-port to 7-day model (separate thread)
