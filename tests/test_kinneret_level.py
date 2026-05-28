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
