# Kinneret Level Auto-Fetch — Design Spec

**Date:** 2026-05-28  
**Scope:** Automate fetching of daily Kinneret water level readings from kineret.org.il into the existing silver CSV, accessible from both the CLI pipeline and the Streamlit dashboard.

---

## 1. Goal

Replace the manual "download CSV from kineret.org.il" step with an automated incremental fetch that appends any missing readings to `Silver Data/Kinneret Level/kinneret_level.csv`. Triggerable both from the command line (fits between steps 06 and 07) and from a button on Page 1 of the dashboard.

---

## 2. Data Source

**URL:** `https://kineret.org.il/miflasim/?fromdate=YYYY-MM-DD&todate=YYYY-MM-DD&Frequency=daily`  
**Auth:** None — plain HTTP GET with a User-Agent header  
**Response:** Server-side rendered HTML (~136 KB), no JavaScript execution required  
**Data structure:** Level readings are embedded as Google Charts JavaScript inside the HTML:

```javascript
var date = new Date(2026, 4, 20);           // month is 0-indexed
data.addRow([date, -212.535, -208.8, -213]); // [date, level, upper_mgmt, lower_mgmt]
var date = new Date(2026, 4, 21);
data.addRow([date, -212.54, -208.8, -213]);
```

**Parsing regex:**
```python
r'new Date\((\d{4}),\s*(\d+),\s*(\d+)\);\r?\ndata\.addRow\(\[date,\s*([-\d.]+)'
# month + 1 to convert JS 0-indexed month to calendar month
```

**Coverage:** Daily from September 1966 to today.  
**Cloudflare:** Present but no rate-limit headers observed. Incremental fetches (a few days at a time) require no delay.

---

## 3. Architecture

### New file: `kinneret_app/kinneret_level.py`

Pure-Python module (no Streamlit dependency). Placed in `kinneret_app/` to follow the same pattern as `ims_forecast.py`. CLI scripts add `kinneret_app/` to sys.path to import it.

**Public API:**
```python
def fetch_new_levels(silver_csv_path: Path) -> pd.DataFrame:
    """
    Read last recorded date from silver CSV, fetch all readings from
    last_date+1 through today, return DataFrame(date, kinneret_level).
    Returns empty DataFrame if already up to date.
    """

def append_to_silver(df: pd.DataFrame, silver_csv_path: Path) -> int:
    """
    Append df rows to silver CSV. Returns count of rows added.
    No-op if df is empty.
    """
```

**Internal:**
```python
def _fetch_html(from_date: date, to_date: date) -> str:
    """HTTP GET with User-Agent header. Raises requests.RequestException on failure."""

def _parse_levels(html: str) -> list[tuple[date, float]]:
    """Extract (date, level) pairs from JS data.addRow lines in HTML."""
```

### New file: `Automation/06b_fetch_kinneret_level.py`

CLI entry point. Fits between `06_ingest_kinneret_level.py` and `07_build_gold_features.py` in the pipeline.

```
python Automation/06b_fetch_kinneret_level.py
```

Outputs:
```
Fetching Kinneret levels since 2026-05-25 ...
  Added 3 new readings (2026-05-26 → 2026-05-28)
  Silver CSV updated: Silver Data/Kinneret Level/kinneret_level.csv
```
Or if already up to date:
```
  Already up to date (last: 2026-05-28). Nothing to fetch.
```

### Modified file: `kinneret_app/pages/1_Data_Sources.py`

Add a "Refresh Level Data" button in the existing page. On click:
1. `st.spinner("Fetching from kineret.org.il…")`
2. `fetch_new_levels()` + `append_to_silver()`
3. `st.success("Added N new readings (YYYY-MM-DD → YYYY-MM-DD)")` on success
4. `st.info("Re-run the pipeline (07 → 08) to update the forecast model.")` after success
5. `st.error(f"Fetch failed: {e}")` on any exception — no crash

---

## 4. Data Flow

```
kineret.org.il  →  _fetch_html()  →  _parse_levels()  →  fetch_new_levels()
                                                               ↓
                              Silver Data/Kinneret Level/kinneret_level.csv
                                                               ↓
                              (manual) 07_build_gold_features.py
                                                               ↓
                              Gold Data/kinneret_gold_features.csv  →  Dashboard
```

The silver CSV append is the only automated step. Gold rebuild remains a manual pipeline step.

---

## 5. Silver CSV Format

The silver CSV (`Silver Data/Kinneret Level/kinneret_level.csv`) has two columns:
```
date,kinneret_level
2026-05-26,-212.540
2026-05-27,-212.545
```

`fetch_new_levels` reads the last `date` in this file to determine the fetch window. `append_to_silver` appends rows without re-sorting or deduplicating (silver CSV is already sorted; new rows are always after the last date).

---

## 6. Error Handling

| Scenario | Behaviour |
|---|---|
| HTTP error (timeout, 4xx/5xx) | `requests.raise_for_status()` → propagates → CLI prints error / dashboard `st.error()` |
| No `data.addRow` rows in HTML | `_parse_levels` returns `[]` → `fetch_new_levels` returns empty DataFrame → 0 rows appended |
| Silver CSV missing | `fetch_new_levels` falls back to `fromdate=2024-01-01` (one safe default) |
| Already up to date (`from_date > today`) | Returns empty DataFrame, no HTTP request made |

---

## 7. Files Changed

| File | Change |
|---|---|
| `kinneret_app/kinneret_level.py` | **New** — fetch, parse, append logic |
| `Automation/06b_fetch_kinneret_level.py` | **New** — CLI entry point |
| `kinneret_app/pages/1_Data_Sources.py` | **Modified** — add Refresh Level Data button |

No changes to `06_ingest_kinneret_level.py`, `app_utils.py`, or gold pipeline scripts.

---

## 8. Out of Scope

- Gold CSV rebuild from within the dashboard
- Scheduled/cron-based automatic fetching
- Backfilling historical data (the existing raw CSV covers 1966–present)
- Retry logic (incremental fetches are cheap; a failed fetch can simply be re-triggered)
