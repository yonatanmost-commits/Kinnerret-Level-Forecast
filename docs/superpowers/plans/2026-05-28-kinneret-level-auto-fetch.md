# Kinneret Level Auto-Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate fetching of daily Kinneret water level readings from kineret.org.il and appending them to the silver CSV, triggerable from a CLI script or a "Refresh Level Data" button on Page 1 of the dashboard.

**Architecture:** A new pure-Python module `kinneret_app/kinneret_level.py` handles HTTP fetch, HTML parsing (Google Charts `data.addRow` pattern via regex), and silver CSV append. A thin CLI wrapper `Automation/06b_fetch_kinneret_level.py` imports it after inserting `kinneret_app/` into sys.path. Page 1 gains a button in the existing Kinneret Level tab that calls the same two public functions.

**Tech Stack:** `requests`, `re` (stdlib), `pandas`, `pathlib`, `streamlit`, `pytest`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tests/test_kinneret_level.py` | Unit tests for `_parse_levels`, `append_to_silver`, `fetch_new_levels` behavior |
| Create | `kinneret_app/kinneret_level.py` | HTTP fetch, HTML parse, silver CSV append — no Streamlit dependency |
| Create | `Automation/06b_fetch_kinneret_level.py` | CLI entry point — sys.path setup + human-readable output |
| Modify | `kinneret_app/pages/1_Data_Sources.py` | Add import + "Refresh Level Data" button in Kinneret Level tab |

`tests/conftest.py` already adds `kinneret_app/` to sys.path, so `kinneret_level` is importable from tests without changes.

---

## Task 1: Write failing tests for `kinneret_level.py`

**Files:**
- Create: `tests/test_kinneret_level.py`

- [ ] **Step 1: Create `tests/test_kinneret_level.py`**

```python
# tests/test_kinneret_level.py
import textwrap
from datetime import date

import pandas as pd
import pytest

from kinneret_level import _parse_levels, append_to_silver, fetch_new_levels

# Fixture HTML: 3 rows. Months are JS 0-indexed (4=May, 11=December).
FIXTURE_HTML = textwrap.dedent("""\
    var date = new Date(2026, 4, 20);
    data.addRow([date, -212.535, -208.8, -213]);
    var date = new Date(2026, 4, 21);
    data.addRow([date, -212.54, -208.8, -213]);
    var date = new Date(2025, 11, 31);
    data.addRow([date, -213.100, -208.8, -213]);
""")


# ── _parse_levels ──────────────────────────────────────────────────────────────

def test_parse_levels_count():
    assert len(_parse_levels(FIXTURE_HTML)) == 3


def test_parse_levels_month_conversion():
    pairs = _parse_levels(FIXTURE_HTML)
    assert pairs[0][0] == date(2026, 5, 20)   # JS month 4 -> calendar 5
    assert pairs[1][0] == date(2026, 5, 21)


def test_parse_levels_december():
    pairs = _parse_levels(FIXTURE_HTML)
    assert pairs[2][0] == date(2025, 12, 31)  # JS month 11 -> calendar 12


def test_parse_levels_float_values():
    pairs = _parse_levels(FIXTURE_HTML)
    assert pairs[0][1] == -212.535
    assert pairs[1][1] == -212.54


def test_parse_levels_empty_html():
    assert _parse_levels("no data here") == []


# ── append_to_silver ───────────────────────────────────────────────────────────

@pytest.fixture
def silver_csv(tmp_path):
    p = tmp_path / "kinneret_level.csv"
    p.write_text("date,kinneret_level\n2026-05-25,-212.560\n")
    return p


def test_append_count(silver_csv):
    df = pd.DataFrame({"date": [date(2026, 5, 26)], "kinneret_level": [-212.565]})
    assert append_to_silver(df, silver_csv) == 1


def test_append_row_written(silver_csv):
    df = pd.DataFrame({"date": [date(2026, 5, 26)], "kinneret_level": [-212.565]})
    append_to_silver(df, silver_csv)
    result = pd.read_csv(silver_csv)
    assert len(result) == 2
    assert result.iloc[1]["date"] == "2026-05-26"


def test_append_noop_on_empty(silver_csv):
    df = pd.DataFrame(columns=["date", "kinneret_level"])
    assert append_to_silver(df, silver_csv) == 0
    assert len(pd.read_csv(silver_csv)) == 1


# ── fetch_new_levels behavior (no network) ────────────────────────────────────

def test_already_uptodate_returns_empty_no_request(tmp_path, monkeypatch):
    import kinneret_level as kl
    today = date.today()
    p = tmp_path / "kinneret_level.csv"
    p.write_text(f"date,kinneret_level\n{today},-212.560\n")

    called = []
    monkeypatch.setattr(kl, "_fetch_html", lambda *a: called.append(1) or "")
    df = fetch_new_levels(p)
    assert df.empty
    assert called == []


def test_missing_csv_fetches_from_fallback_date(tmp_path, monkeypatch):
    import kinneret_level as kl
    captured = []

    def fake_fetch(from_date, to_date):
        captured.append(from_date)
        return ""

    monkeypatch.setattr(kl, "_fetch_html", fake_fetch)
    fetch_new_levels(tmp_path / "nope.csv")
    assert captured[0] == date(2024, 1, 1)
```

- [ ] **Step 2: Run tests — verify they fail with `ModuleNotFoundError`**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/test_kinneret_level.py -v
```

Expected: `ModuleNotFoundError: No module named 'kinneret_level'`

---

## Task 2: Implement `kinneret_app/kinneret_level.py`

**Files:**
- Create: `kinneret_app/kinneret_level.py`

- [ ] **Step 1: Create `kinneret_app/kinneret_level.py`**

```python
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

SILVER_DEFAULT_FROM = date(2024, 1, 1)
_URL = "https://kineret.org.il/miflasim/?fromdate={}&todate={}&Frequency=daily"
_PATTERN = re.compile(
    r'new Date\((\d{4}),\s*(\d+),\s*(\d+)\);\r?\ndata\.addRow\(\[date,\s*([-\d.]+)'
)


def _fetch_html(from_date: date, to_date: date) -> str:
    r = requests.get(
        _URL.format(from_date, to_date),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    return r.text


def _parse_levels(html: str) -> list:
    return [
        (date(int(yr), int(mo) + 1, int(dy)), float(lvl))
        for yr, mo, dy, lvl in _PATTERN.findall(html)
    ]


def fetch_new_levels(silver_csv_path: Path) -> pd.DataFrame:
    silver_csv_path = Path(silver_csv_path)
    if silver_csv_path.exists():
        last_date = (
            pd.read_csv(silver_csv_path, parse_dates=["date"])["date"].max().date()
        )
    else:
        last_date = SILVER_DEFAULT_FROM - timedelta(days=1)

    from_date = last_date + timedelta(days=1)
    if from_date > date.today():
        return pd.DataFrame(columns=["date", "kinneret_level"])

    html = _fetch_html(from_date, date.today())
    pairs = _parse_levels(html)
    if not pairs:
        return pd.DataFrame(columns=["date", "kinneret_level"])
    return pd.DataFrame(pairs, columns=["date", "kinneret_level"])


def append_to_silver(df: pd.DataFrame, silver_csv_path: Path) -> int:
    if df.empty:
        return 0
    silver_csv_path = Path(silver_csv_path)
    df.to_csv(silver_csv_path, mode="a", header=not silver_csv_path.exists(), index=False)
    return len(df)
```

- [ ] **Step 2: Run tests — verify all pass**

```
python -m pytest tests/test_kinneret_level.py -v
```

Expected: 12 tests PASSED, 0 failures.

- [ ] **Step 3: Commit**

```
git add kinneret_app/kinneret_level.py tests/test_kinneret_level.py
git commit -m "feat: add kinneret_level module with fetch, parse, append"
```

---

## Task 3: Create `Automation/06b_fetch_kinneret_level.py`

**Files:**
- Create: `Automation/06b_fetch_kinneret_level.py`

No new tests — this is a thin wrapper over the already-tested `kinneret_level` module.

- [ ] **Step 1: Create `Automation/06b_fetch_kinneret_level.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kinneret_app"))

import pandas as pd
from kinneret_level import append_to_silver, fetch_new_levels

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SILVER_CSV = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"


def main():
    if SILVER_CSV.exists():
        last = pd.read_csv(SILVER_CSV, parse_dates=["date"])["date"].max().date()
        print(f"Fetching Kinneret levels since {last} ...")
    else:
        last = None
        print("Fetching Kinneret levels (silver CSV not found, fetching from 2024-01-01) ...")

    df = fetch_new_levels(SILVER_CSV)

    if df.empty:
        print(f"  Already up to date (last: {last}). Nothing to fetch.")
        return

    n = append_to_silver(df, SILVER_CSV)
    d_min = df["date"].min()
    d_max = df["date"].max()
    print(f"  Added {n} new readings ({d_min} to {d_max})")
    print(f"  Silver CSV updated: Silver Data/Kinneret Level/kinneret_level.csv")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script to verify it works end-to-end**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python Automation/06b_fetch_kinneret_level.py
```

Expected (CSV already mostly up to date — will fetch any missing days):
```
Fetching Kinneret levels since 2026-05-25 ...
  Added 2 new readings (2026-05-26 to 2026-05-27)
  Silver CSV updated: Silver Data/Kinneret Level/kinneret_level.csv
```
Or if already up to date:
```
Fetching Kinneret levels since 2026-05-27 ...
  Already up to date (last: 2026-05-27). Nothing to fetch.
```

- [ ] **Step 3: Commit**

```
git add Automation/06b_fetch_kinneret_level.py
git commit -m "feat: add 06b_fetch_kinneret_level CLI script"
```

---

## Task 4: Add "Refresh Level Data" button to Page 1

**Files:**
- Modify: `kinneret_app/pages/1_Data_Sources.py`

`kinneret_app/` is already in sys.path via line 3 of this file (`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`), so `kinneret_level` is importable directly.

The button goes inside `with tab_level:` after the silver data sample block (currently ending at line 134).

- [ ] **Step 1: Add import** — insert after line 8

Current (line 8):
```python
from app_utils import load_gold, PROJECT_ROOT, COLOURS
```

Replace with:
```python
from app_utils import load_gold, PROJECT_ROOT, COLOURS
from kinneret_level import append_to_silver, fetch_new_levels
```

- [ ] **Step 2: Add the button block** at the very end of `with tab_level:`, after the `st.caption(...)` line that closes the silver data sample section (line 134).

After:
```python
        st.caption("(Showing from gold table — silver file not found at expected path)")
```

Add:
```python

    st.markdown('<div class="kn-divider"></div>', unsafe_allow_html=True)
    if st.button("Refresh Level Data", key="refresh_level"):
        with st.spinner("Fetching from kineret.org.il..."):
            try:
                df_new = fetch_new_levels(silver_level)
                n = append_to_silver(df_new, silver_level)
                if n > 0:
                    d_min = df_new["date"].min()
                    d_max = df_new["date"].max()
                    st.success(f"Added {n} new readings ({d_min} to {d_max})")
                    st.info("Re-run the pipeline (07 -> 08) to update the forecast model.")
                else:
                    st.success("Already up to date. No new readings.")
            except Exception as e:
                st.error(f"Fetch failed: {e}")
```

Note: `silver_level` is already defined on line 120 (`silver_level = PROJECT_ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv"`), so the button can reference it directly.

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```
cd "C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project"
python -m pytest tests/ -v
```

Expected: all tests PASSED (12 kinneret_level + 11 ims_forecast = 23 total).

- [ ] **Step 4: Commit**

```
git add kinneret_app/pages/1_Data_Sources.py
git commit -m "feat: add Refresh Level Data button to Data Sources page"
```
