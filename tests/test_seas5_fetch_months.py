"""seas5_fetch asks CDS only for forecasts that exist (bug, 2026-10-26).

It asked for every start month of the year. For the current year that names months not issued
yet, and CDS fails the whole request ("MARS ... Request failed"), as a test fetch of 2026 did on
26 Oct. A month's forecast is out after the 5th (seas5.RELEASE_DAY), the same rule as init_for.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Automation"))
import seas5_fetch as f  # noqa: E402


def test_a_past_year_asks_for_all_twelve():
    assert f.months_for(2025, date(2026, 10, 26)) == list(range(1, 13))


def test_the_current_year_asks_only_for_issued_months():
    assert f.months_for(2026, date(2026, 10, 26)) == list(range(1, 11))


def test_the_month_counts_from_the_day_after_its_release():
    assert f.months_for(2026, date(2026, 11, 5)) == list(range(1, 11))
    assert f.months_for(2026, date(2026, 11, 6)) == list(range(1, 12))


def test_a_future_year_asks_for_nothing():
    assert f.months_for(2027, date(2026, 11, 6)) == []
