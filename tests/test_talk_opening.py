"""Opening tests for the Kinneret Conference talk deck (intent/kinneret-talk-deck A20, plan D18).

The year-over-year slide gives two scenarios for the coming winter, each a real past winter from
the level record, never a forecast. These tests recompute them from the level file and check the
ledger and the slide's notes against that.

Contract fixed here (plan D18):
- Window: the last 20 complete winters before the freeze (2006-07 to 2025-26 at 2026-10-11).
- A winter's change = the level on 31 May of the next year minus the level on the freeze calendar
  date; it can be negative. Dry = the smallest change, wet = the largest. (Not peak minus start:
  a peak can't fall below the start, so a falling winter would read as "stays where it is".)
- Ledger: scenario.{dry,wet}.{season,change_m,spring_m}, kind "historical", dated 31 May of the
  winter's end year. season's value starts with the winter's first year;
  spring_m = the freeze level + change_m.
- talk.md: the notes of the slide drawing chart:hook name both seasons, and every placeholder on
  that slide is a scenario.* entry.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
TALK = ROOT / "docs" / "talk"
LEDGER = TALK / "numbers_ledger.json"
N_WINTERS = 20
PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")

sys.path.insert(0, str(ROOT / "Automation"))


@pytest.fixture(scope="module")
def ledger():
    assert LEDGER.exists(), f"missing ledger {LEDGER} (run Automation/talk_freeze_run.py)"
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def entry(ledger, key):
    assert key in ledger, f"ledger has no entry {key!r}"
    return ledger[key]


def winter_changes(fd: pd.Timestamp) -> dict[int, float]:
    """First year of each winter -> its change in metres to 31 May, recomputed from the record."""
    import redline_backtest
    daily = redline_backtest.load_daily()
    last = fd.year - 1 if fd >= pd.Timestamp(fd.year, 5, 31) else fd.year - 2
    changes = {}
    for y in range(last - N_WINTERS + 1, last + 1):
        start, end = pd.Timestamp(y, fd.month, fd.day), pd.Timestamp(y + 1, 5, 31)
        assert start in daily.index and end in daily.index, f"level record misses winter {y}"
        changes[y] = float(daily[end] - daily[start])
    return changes


def test_a20_scenarios_are_the_driest_and_wettest_past_winters(ledger):
    fd = pd.Timestamp(entry(ledger, "freeze_date")["value"])
    changes = winter_changes(fd)
    if fd == pd.Timestamp("2026-10-11"):
        assert min(changes) == 2006 and max(changes) == 2025
    truth = {"dry": min(changes, key=changes.get), "wet": max(changes, key=changes.get)}
    freeze_m = entry(ledger, "level.freeze_m")["value"]

    for name, year in truth.items():
        for field in ("season", "change_m", "spring_m"):
            e = entry(ledger, f"scenario.{name}.{field}")
            assert e["kind"] == "historical", f"scenario.{name}.{field} is not historical"
            assert e["date"] == f"{year + 1}-05-31", f"scenario.{name}.{field} dated {e['date']}"
            assert e["source"], f"scenario.{name}.{field}: empty source"
        season = str(entry(ledger, f"scenario.{name}.season")["value"])
        assert season.startswith(str(year)), f"{name} winter is {year}, ledger says {season!r}"
        change = entry(ledger, f"scenario.{name}.change_m")["value"]
        assert abs(change - changes[year]) <= 0.0015, \
            f"{name} change {change} != record {changes[year]:.3f}"
        spring = entry(ledger, f"scenario.{name}.spring_m")["value"]
        assert abs(spring - (freeze_m + change)) <= 0.0015, f"{name} spring {spring} != freeze + change"
    assert changes[truth["dry"]] < changes[truth["wet"]]


def test_a20_notes_speak_only_the_scenarios():
    talk = TALK / "talk.md"
    if not talk.exists():
        pytest.skip("docs/talk/talk.md not drafted yet")
    slides = re.split(r"(?m)^## slide ", talk.read_text(encoding="utf-8"))[1:]
    yoy = [s for s in slides if re.search(r"(?m)^object:\s*chart:hook\s*$", s)]
    assert yoy, "no slide draws chart:hook"
    body = yoy[0]
    keys = set(PLACEHOLDER.findall(body))
    assert {"scenario.dry.season", "scenario.wet.season"} <= keys, \
        f"the year-over-year slide does not name both winters: {sorted(keys)}"
    others = sorted(k for k in keys if not k.startswith("scenario."))
    assert not others, f"the year-over-year slide speaks numbers other than the scenarios: {others}"
