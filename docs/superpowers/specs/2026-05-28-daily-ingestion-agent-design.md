# Daily Ingestion Agent — Design Spec

**Date:** 2026-05-28  
**Scope:** Automated daily pipeline that fetches all four data sources, runs the full pipeline through gold feature engineering, trains only the Model Olympics champion, and writes a daily report. Runs via Windows Task Scheduler, CLI, and a dashboard button.

---

## 1. Goal

Replace manual data refresh steps with an automated daily agent that:
1. Fetches kinneret level, river flow, and met data from their live sources
2. Runs the full silver → gold pipeline
3. Retrains only the current Olympics champion model
4. Writes a structured report to stdout and file

The agent is also the first line of self-diagnosis: if a step fails it reports the error in detail so a human (aided by Claude browser extension) can investigate.

---

## 2. Data Fetchers

### New file: `kinneret_app/jordan_flow.py`

Fetches station 79 (JORDAN - OBSTACLE BRIDGE) from hydro.water.gov.il. Requires a session token from `<meta name="api-token">` on the main page, then POSTs to `get_hydro_observations_A7f3Q.php`. Returns ~48 hours of 10-minute readings as `{ "YYYY-MM-DD HH:mm:ss": { "79": [flow_m3s, water_height] } }`.

**Aggregation:** `mean(flow_m3s) × 86400 = daily_m3` — matching the existing silver column unit (existing rows show ~1.5M m³/day ≈ 17 m³/s).

**Limitations:**
- Only OBSTACLE BRIDGE is available live. BAPTISM SITE has been NaN since late 2025 and stays NaN.
- 48-hour window only. The 7-week gap (2026-04-08 → today) is accepted as NaN — no backfill possible.

**Silver target:** `Silver Data/Jordan River Silver/jordan_river_daily_flow.csv` (raw). The orchestrator then runs `05_clean_jordan_river_flow.py` to produce `_clean.csv`.

**Public API:**
```python
def fetch_new_flows(raw_csv_path: Path) -> pd.DataFrame
    # returns DataFrame[date (date), "JORDAN - OBSTACLE BRIDGE" (float)]

def append_to_flow_raw(df: pd.DataFrame, raw_csv_path: Path) -> int
    # appends to raw CSV, creates parent dirs, returns rows added
```

**Internal:**
```python
def _get_token(session: requests.Session) -> str
def _fetch_observations(session, token) -> dict        # raw API response
def _aggregate_daily(obs: dict, station_id: str = "79") -> pd.DataFrame
    # 10-min readings → daily mean × 86400
```

---

### New file: `kinneret_app/met_update.py`

Fetches station 115 (Lev Kinneret) from the IMS Envista archive API. Station 115 is the only IMS station with a live API — other stations (Beit Tzaida, Kfar Nachum, Tiberias, Tzamach) cannot be updated automatically and will remain NaN for new rows.

**Two-step fetch:**
1. `_discover_resource_id()` — calls `GET https://ims.gov.il/he/envista_station_info/` once, extracts the T-10 data resource_id for station 115, caches it to `Models/ims_resource_id.json`.
2. Single data.gov.il CKAN query: `fields=stn_num,time_obs,1,2,4,5,6,7,8,9,10,12,13` filtered by date range and `stn_num=115`.

**Channel → column mapping:**

| Channel | Column | Aggregation |
|---|---|---|
| 1 (Rain) | `lev_kinneret_rainfall_mm_sum` | sum |
| 2 (WSmax) | `lev_kinneret_wind_gust_speed_ms_max` | max |
| 4 (WS) | `lev_kinneret_wind_speed_ms_mean` | mean |
| 4 (WS) | `lev_kinneret_wind_speed_ms_max` | max |
| 5 (WD) | `lev_kinneret_wind_dir_deg_mean` | mean |
| 6 (STDwd) | `lev_kinneret_wind_dir_std_deg_mean` | mean |
| 7 (TD) | `lev_kinneret_temperature_C_mean` | mean |
| 8 (RH) | `lev_kinneret_relative_humidity_pct_mean` | mean |
| 9 (TDmax) | `lev_kinneret_temperature_C_max` | max |
| 9 (TDmax) | `lev_kinneret_temperature_max_C_max` | max |
| 10 (TDmin) | `lev_kinneret_temperature_C_min` | min |
| 10 (TDmin) | `lev_kinneret_temperature_min_C_min` | min |
| 12 (WS1mm) | `lev_kinneret_wind_speed_max1min_ms_max` | max |
| 13 (Ws10mm) | `lev_kinneret_wind_speed_max10min_ms_max` | max |

Columns not covered by station 115 stay NaN for new rows (already the pattern for the last ~10 rows in the existing silver CSV).

**Silver target:** Append to `Silver Data/Meteorological/met_data_daily.csv` (raw), then orchestrator runs `04_clean_daily_met_data.py` to produce `met_data_daily_clean.csv`.

**Public API:**
```python
def fetch_new_met(silver_csv_path: Path) -> pd.DataFrame
    # returns DataFrame[date (date), lev_kinneret_* columns only]

def append_to_met_silver(df: pd.DataFrame, silver_csv_path: Path) -> int
    # appends rows with all 80 columns (lev_kinneret_* populated, rest NaN)
    # creates parent dirs, returns rows added
```

**Internal:**
```python
def _discover_resource_id(cache_path: Path) -> str
    # reads cache if exists, else fetches envista_station_info and writes cache

def _fetch_channel_data(resource_id: str, from_date: date, to_date: date) -> pd.DataFrame
    # single CKAN query, all channels, returns raw 10-min data

def _aggregate_daily(raw_df: pd.DataFrame) -> pd.DataFrame
    # pivot + per-channel aggregation → one row per date
```

---

## 3. Orchestrator (`Automation/daily_agent.py`)

Five sequential steps. Each returns `{"status": "ok"|"skipped"|"failed", "rows_added": int|None, "detail": str|None}`.

```
Step 1: fetch_kinneret_level  →  kinneret_level.fetch_new_levels + append_to_silver
Step 2: fetch_river_flow      →  jordan_flow.fetch_new_flows + append_to_flow_raw
                                  + subprocess: python 05_clean_jordan_river_flow.py
Step 3: fetch_met             →  met_update.fetch_new_met + append_to_met_silver
                                  + subprocess: python 04_clean_daily_met_data.py
Step 4: build_gold            →  subprocess: python 07_build_gold_features.py
Step 5: train_winner          →  subprocess: python 08_train_forecast_model.py --winner-only
```

**Graceful degradation:**
- Steps 1-3 are independent. A failure in one does not skip the others.
- Step 4 always runs — the gold builder handles NaN rows.
- Step 5 only runs if step 4 succeeded (exit code 0).

**Subprocess calls** use `subprocess.run([sys.executable, script_path], capture_output=True, text=True, cwd=PROJECT_ROOT)`. Each subprocess stdout/stderr is captured and included in the report on failure.

---

## 4. Training Fix (`Automation/08_train_forecast_model.py`)

New function `train_winner_only()` reads `Models/olympics_results.json`, maps the `"winner"` key to the appropriate `train_final_*` function, and runs it.

Winner → function mapping:
- `"baseline_gbr"` → `train_final_gbr(df, oof_s1)` (**new function** — extracted from the inline training code currently in `run_cv`)
- `"xgboost"` → `train_final_xgb(df, oof_s1)` (already exists)
- `"lgbm"` → `train_final_lgb(df, oof_s1)` (already exists)

New CLI flag: `--winner-only`. When present, `main()` calls `train_winner_only()` instead of the full Olympics loop.

---

## 5. Report Format

Written to both stdout and `Reports/daily_agent_YYYY-MM-DD.txt` (directory created if absent):

```
=== Daily Agent Report — 2026-05-28 ===

DATA FETCH
  kinneret_level : ok        +1 row  (2026-05-28)
  river_flow     : ok        +2 rows (2026-05-27 to 2026-05-28)
  met            : ok        +9 rows (2026-05-20 to 2026-05-28)

PIPELINE
  04_clean_met   : ok
  05_clean_flow  : ok
  build_gold     : ok
  train_winner   : ok        baseline_gbr

HEALTH
  All checks passed.
```

Failed steps show the error message inline:
```
  river_flow     : FAILED    ConnectionError: ('Connection aborted.', RemoteDisconnected(...))
```

The report file path is also printed to stdout at the end.

---

## 6. Entry Points

| Entry point | File | Use |
|---|---|---|
| Task Scheduler (primary) | `Automation/run_daily_agent.ps1` | Nightly unattended run |
| CLI | `python Automation/daily_agent.py` | Manual trigger |
| Dashboard | `kinneret_app/pages/2_Pipeline.py` | "Run Daily Refresh" button |

**`run_daily_agent.ps1`:**
```powershell
$python = (Get-Command python).Source
& $python "$PSScriptRoot\daily_agent.py"
exit $LASTEXITCODE
```
Scheduled via Task Scheduler at 06:00 daily (data sources update overnight).

**Dashboard button** (`2_Pipeline.py`): calls `daily_agent.py` via subprocess (same as CLI), captures stdout, streams output into `st.text_area`. On exit code 0, shows the report text. On non-zero exit, `st.error()` with stderr.

---

## 7. Health Check

Runs before any fetch step. Checks:
1. `Models/olympics_results.json` exists and has a `winner` key — **required** (training cannot proceed without it)
2. `Gold Data/kinneret_gold_features.csv` exists — **warn** (pipeline can rebuild it)
3. Model pickle files exist (`Models/stage1_*.pkl`, `Models/stage2_*.pkl`) — **warn**
4. Silver CSVs exist — **warn** (fetch steps will create them if missing)

Required checks fail → write report with `HEALTH FAILED` section, exit code 1, no pipeline runs.
Warn checks fail → note in report, continue normally.

---

## 8. Self-Healing Workflow

When a fetch fails (e.g., website structure changed):
1. Daily agent reports failure with full error + HTTP response snippet
2. Report written to `Reports/daily_agent_YYYY-MM-DD.txt`
3. User reviews report, shares with Claude browser extension to diagnose website change
4. Fix applied to the relevant fetcher module (`jordan_flow.py`, `met_update.py`, or `kinneret_level.py`)
5. Re-run agent manually: `python Automation/daily_agent.py`

The agent never silently swallows errors — every failed step includes the full exception message and subprocess stderr.

---

## 9. Files Changed

| File | Change | Role |
|---|---|---|
| `kinneret_app/jordan_flow.py` | **New** | hydro.water.gov.il river flow fetcher |
| `kinneret_app/met_update.py` | **New** | IMS Envista station 115 met fetcher |
| `Automation/daily_agent.py` | **New** | Orchestrator + health check + report |
| `Automation/run_daily_agent.ps1` | **New** | Task Scheduler wrapper |
| `Automation/08_train_forecast_model.py` | **Modify** | Add `train_winner_only()` + `--winner-only` flag |
| `kinneret_app/pages/2_Pipeline.py` | **Modify** | Add "Run Daily Refresh" button |

No changes to `04_clean_daily_met_data.py`, `05_clean_jordan_river_flow.py`, `07_build_gold_features.py`, or any gold/model files.

---

## 10. Out of Scope

- Backfilling the 7-week river flow gap (API limitation)
- Fetching Beit Tzaida, Kfar Nachum, Tiberias, or Tzamach met stations
- Forecast generation within the agent (step 09 remains manual)
- Automatic Olympics re-run (winner is only updated manually)
- Retry logic on network failures (re-trigger manually)
