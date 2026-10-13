"""Truth tests for the coverage slide (intent/kinneret-talk-deck R39, plan D21).

The coverage chart draws each data source's record against time. Every date it draws is a
historical ledger entry, and every ledger entry is checked here against the data files
themselves, never against copies of the dates.

Contract fixed here:
- Every record is read as it stood at the freeze: readings after freeze_date don't count.
- Series (D21's order): data.<series>.start for each; data.<series>.end only for a record that
  stopped (its last reading more than STOPPED_DAYS before the freeze); gaps of more than
  GAP_DAYS inside the model's years (from data.gold.start) as data.<series>.gap<n>.{start,end},
  start = the last reading before the gap, end = the first reading after it; source changes as
  data.<series>.switch<n> with a "note" naming the new source.
- Switches: the weather moves from the IMS records to Open-Meteo the day after the IMS hourly
  coverage file ends; the radiation sensor dies the day after its own W/m2 readings end, and the
  record continues from the backfill.
- docs/talk/charts.py chart_data("coverage", ledger) returns {"series": [{id, start, end, gaps,
  switches}], "line": {date, label}, "end": freeze date}; the drawn values are exactly these.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
TALK = ROOT / "docs" / "talk"
LEDGER = TALK / "numbers_ledger.json"
sys.path.insert(0, str(TALK))

GAP_DAYS = 20
STOPPED_DAYS = 30
LEVEL = ("Silver Data/Kinneret Level/kinneret_level.csv", "date", "kinneret_level")
FLOW = "Silver Data/Jordan River Silver/jordan_river_daily_flow_clean.csv"
MET = "Silver Data/Meteorological/met_data_daily_clean.csv"
MET_COVERAGE = "Silver Data/Meteorological/met_coverage_daily.csv"
SERIES = ["level", "flow.obstacle_bridge", "flow.sede_nehemya", "flow.yarmuk", "flow.old_bridge",
          "flow.baptism_site", "weather", "radiation"]
FLOW_COLUMNS = {"flow.obstacle_bridge": "JORDAN - OBSTACLE BRIDGE",
                "flow.sede_nehemya": "JORDAN - SEDE NEHEMYA",
                "flow.yarmuk": "YARMUQ - NAHARAYIM",
                "flow.old_bridge": "JORDAN - NEAR OLD BRIDGE",
                "flow.baptism_site": "JORDAN - BAPTISM SITE"}


@pytest.fixture(scope="module")
def ledger():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _days(path, date_col, col):
    df = pd.read_csv(ROOT / path, usecols=[date_col, col], parse_dates=[date_col])
    return pd.DatetimeIndex(sorted(df.loc[df[col].notna(), date_col]))


@pytest.fixture(scope="module")
def readings():
    """Each series' days with a reading, straight from the data files."""
    out = {"level": _days(*LEVEL)}
    for sid, col in FLOW_COLUMNS.items():
        out[sid] = _days(FLOW, "Date", col)
    met = pd.read_csv(ROOT / MET, parse_dates=["date"]).set_index("date")
    out["weather"] = pd.DatetimeIndex(sorted(met.index[met.notna().any(axis=1)]))
    out["radiation"] = _days(MET, "date", "tzamach_global_radiation_MJm2")
    return out


def _iso(d):
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def expected(days, gold_start, freeze):
    days = days[days <= freeze]                    # the record as it stood at the freeze
    gaps = []
    for a, b in zip(days[:-1], days[1:]):
        if b >= gold_start and (b - a).days > GAP_DAYS:
            gaps.append((_iso(a), _iso(b)))
    stopped = (freeze - days.max()).days > STOPPED_DAYS
    return {"start": _iso(days.min()), "end": _iso(days.max()) if stopped else None, "gaps": gaps}


def from_ledger(ledger, sid):
    gaps, n = [], 1
    while f"data.{sid}.gap{n}.start" in ledger:
        gaps.append((ledger[f"data.{sid}.gap{n}.start"]["value"], ledger[f"data.{sid}.gap{n}.end"]["value"]))
        n += 1
    end = ledger.get(f"data.{sid}.end")
    return {"start": ledger[f"data.{sid}.start"]["value"], "end": end and end["value"], "gaps": gaps}


def switches(ledger, sid):
    out, n = [], 1
    while f"data.{sid}.switch{n}" in ledger:
        out.append(ledger[f"data.{sid}.switch{n}"])
        n += 1
    return out


def test_coverage_spans_match_the_data_files(ledger, readings):
    gold_start = pd.Timestamp(ledger["data.gold.start"]["value"])
    freeze = pd.Timestamp(ledger["freeze_date"]["value"])
    for sid in SERIES:
        assert from_ledger(ledger, sid) == expected(readings[sid], gold_start, freeze), sid


def test_coverage_switches_match_the_data_files(ledger, readings):
    cov = pd.read_csv(ROOT / MET_COVERAGE, parse_dates=["date"])
    ims_end = cov.loc[cov.drop(columns="date").fillna(0).sum(axis=1) > 0, "date"].max()
    sensor_end = _days(MET, "date", "tzamach_global_radiation_Wm2_mean").max()
    want = {"weather": _iso(ims_end + pd.Timedelta(days=1)),
            "radiation": _iso(sensor_end + pd.Timedelta(days=1))}
    for sid in SERIES:
        got = switches(ledger, sid)
        if sid in want:
            assert [s["value"] for s in got] == [want[sid]], sid
            assert "open-meteo" in got[0]["note"].lower(), sid
        else:
            assert got == [], sid


def test_coverage_entries_are_dated_historical_facts(ledger):
    keys = [k for k in ledger if k.startswith("data.") and k.split(".")[1] != "gold"]
    assert keys
    for k in keys:
        e = ledger[k]
        assert e["kind"] == "historical" and e["unit"] == "date", k
        assert e["date"] == e["value"], k
        assert e["value"][:4] in e["display"], k
        assert e["source"], k


def test_coverage_chart_draws_the_ledger(ledger):
    from charts import chart_data
    d = chart_data("coverage", ledger)
    assert [s["id"] for s in d["series"]] == SERIES
    for s in d["series"]:
        want = from_ledger(ledger, s["id"])
        assert (s["start"], s["end"], [tuple(g) for g in s["gaps"]]) == (want["start"], want["end"], want["gaps"])
        assert [w["date"] for w in s["switches"]] == [x["value"] for x in switches(ledger, s["id"])]
    assert d["line"] == {"date": ledger["data.gold.start"]["value"], "label": "all sources line up"}
    assert d["end"] == ledger["freeze_date"]["value"]
