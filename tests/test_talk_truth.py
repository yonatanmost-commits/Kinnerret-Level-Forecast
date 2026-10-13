"""Truth tests for the Kinneret Conference talk deck (intent/kinneret-talk-deck A2-A6, A19).

These run only when the facts change (plan D8): Automation/talk_freeze_run.py runs them after
writing docs/talk/numbers_ledger.json and, when they pass, stamps the ledger's hash. They check
the ledger and the charts' data against the real sources (the level file, git history, the
stored long-range results), never against copies of the numbers.

Contract fixed here:
- Ledger: flat JSON, key -> {value, display, unit, source, date, kind}; kind is "freeze" (date =
  the freeze date, held in the "freeze_date" entry) or "historical" (date = original date).
- Placeholders in talk.md / qa_prep.md are written {key}.
- docs/talk/charts.py exposes chart_data(name, ledger) -> dict for "hook", "olympics",
  "timeline", "one_week" and "frontier"; the plotted values are exactly what it returns.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
TALK = ROOT / "docs" / "talk"
LEDGER = TALK / "numbers_ledger.json"
TEXT_FILES = [TALK / "talk.md", TALK / "qa_prep.md"]
OLYMPICS_FILE = "docs/olympics_results.json"
LONGRANGE_FILE = "docs/longrange_phaseb_results.json"

MODELS = ["baseline_gbr", "xgboost", "lgbm", "gru", "gbr_max_chain",
          "gbr_s1_direct_s2_anchor", "gbr_single_stage", "gbr_s1_chain_s2_roll1"]
FOLDS = ["2021", "2022", "2023", "2024"]
BANDS = ["0_7", "7_14", "14_30", "30_60", "60_90", "90_120", "120_plus"]
RED_LINE = -213.0
PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

sys.path.insert(0, str(TALK))
sys.path.insert(0, str(ROOT / "Automation"))


# ─── helpers ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ledger():
    assert LEDGER.exists(), f"missing ledger {LEDGER} (run Automation/talk_freeze_run.py)"
    return json.loads(LEDGER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def charts():
    import charts as charts_mod
    return charts_mod


def v(ledger, key):
    assert key in ledger, f"ledger has no entry {key!r}"
    return ledger[key]["value"]


def freeze_date(ledger):
    return v(ledger, "freeze_date")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def commit_date(sha):
    return git("log", "-1", "--format=%ad", "--date=short", sha).strip()


def olympics_snapshots():
    """Every commit that changed the Olympics results file -> champion R² in that commit."""
    out = {}
    for sha in git("log", "--format=%h", "--", OLYMPICS_FILE).split():
        try:
            blob = json.loads(git("show", f"{sha}:{OLYMPICS_FILE}"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        out[sha] = blob["models"]["baseline_gbr"]["cv_vol_r2_mean"]
    return out


def level_daily():
    import redline_backtest
    return redline_backtest.load_daily()


def texts():
    return {p.name: p.read_text(encoding="utf-8") for p in TEXT_FILES if p.exists()}


def need_talk():
    if not (TALK / "talk.md").exists():
        pytest.skip("docs/talk/talk.md not drafted yet (plan step 4)")


# ─── A2: every number traces to the ledger, with source and date ────────────

def test_a2_ledger_entries_are_complete_and_dated(ledger):
    fd = freeze_date(ledger)
    assert ISO_DATE.match(fd), f"freeze_date {fd!r} is not YYYY-MM-DD"
    for key, e in ledger.items():
        missing = {"value", "display", "unit", "source", "date", "kind"} - set(e)
        assert not missing, f"{key}: missing fields {missing}"
        assert e["source"], f"{key}: empty source"
        assert ISO_DATE.match(str(e["date"])), f"{key}: date {e['date']!r} not YYYY-MM-DD"
        assert e["kind"] in ("freeze", "historical"), f"{key}: kind {e['kind']!r}"
        if e["kind"] == "freeze":
            assert e["date"] == fd, f"{key}: freeze entry dated {e['date']}, freeze is {fd}"
        else:
            year = e["date"][:4]
            assert year in str(e["display"]), \
                f"{key}: historical display {e['display']!r} does not show its date ({e['date']})"


def test_a2_every_placeholder_in_the_text_resolves(ledger):
    need_talk()
    for name, text in texts().items():
        unknown = sorted({k for k in PLACEHOLDER.findall(text) if k not in ledger})
        assert not unknown, f"{name}: placeholders not in the ledger: {unknown}"


# ─── A3: all 8 Olympics models, R² mean + per fold + runtime, chart = ledger ─

def test_a3_all_eight_models_measured_on_the_freeze(ledger):
    for m in MODELS:
        folds = [v(ledger, f"olympics.{m}.r2_{f}") for f in FOLDS]
        mean = v(ledger, f"olympics.{m}.r2_mean")
        assert abs(mean - sum(folds) / len(folds)) <= 0.0015, \
            f"{m}: r2_mean {mean} is not the mean of its folds {folds}"
        rt = v(ledger, f"olympics.{m}.runtime_s")
        assert rt > 0, f"{m}: runtime {rt}"
        for k in [f"olympics.{m}.r2_mean", f"olympics.{m}.runtime_s"] + \
                 [f"olympics.{m}.r2_{f}" for f in FOLDS]:
            assert ledger[k]["kind"] == "freeze", f"{k} is not a freeze measurement"


def test_a3_olympics_chart_plots_exactly_the_ledger(ledger, charts):
    pts = charts.chart_data("olympics", ledger)["points"]
    assert sorted(p["model"] for p in pts) == sorted(MODELS)
    for p in pts:
        assert p["r2"] == v(ledger, f"olympics.{p['model']}.r2_mean"), p
        assert p["runtime_s"] == v(ledger, f"olympics.{p['model']}.runtime_s"), p


# ─── A4: persistence (zero change) and seasonal baselines, and the margin ───

def test_a4_baselines_scored_on_the_champions_folds(ledger):
    for b in ("zero_change", "seasonal"):
        for metric in ("r2", "mae"):
            k = f"baseline.{b}.{metric}"
            assert ledger[k]["kind"] == "freeze", k
            assert isinstance(v(ledger, k), (int, float)), k
        for f in FOLDS:
            assert v(ledger, f"baseline.{b}.n_{f}") == v(ledger, f"champion.n_{f}"), \
                f"{b} fold {f} scored on different rows from the champion"
    assert v(ledger, "champion.r2") == v(ledger, "olympics.baseline_gbr.r2_mean")
    margin = v(ledger, "margin.zero_change.r2")
    expect = v(ledger, "champion.r2") - v(ledger, "baseline.zero_change.r2")
    assert abs(margin - expect) <= 0.0015, f"margin {margin} != champion - zero change {expect}"


def test_a4_one_week_chart_and_script_state_the_margin(ledger, charts):
    data = charts.chart_data("one_week", ledger)
    assert data["champion_r2"] == v(ledger, "champion.r2")
    assert data["zero_change_r2"] == v(ledger, "baseline.zero_change.r2")
    need_talk()
    talk = (TALK / "talk.md").read_text(encoding="utf-8")
    assert "{margin.zero_change.r2}" in talk, "talk.md never states the champion-vs-zero-change margin"


# ─── A5: the R² timeline, every point at its date and value, every step labelled

def test_a5_timeline_points_match_git_and_the_freeze(ledger, charts):
    data = charts.chart_data("timeline", ledger)
    pts = data["points"]
    assert [p["date"] for p in pts] == sorted(p["date"] for p in pts), "timeline not in date order"

    snaps = olympics_snapshots()
    hist = [p for p in pts if p["kind"] == "historical"]
    shas = {p["sha"] for p in hist}
    assert shas == set(snaps), f"timeline snapshots {sorted(shas)} != git snapshots {sorted(snaps)}"
    for p in hist:
        assert p["r2"] == snaps[p["sha"]], f"{p['sha']}: plotted {p['r2']}, git has {snaps[p['sha']]}"
        assert p["date"] == commit_date(p["sha"]), f"{p['sha']}: plotted at {p['date']}"
        assert p["r2"] == v(ledger, p["key"]) and ledger[p["key"]]["kind"] == "historical"

    last = pts[-1]
    assert last["kind"] == "freeze"
    assert last["date"] == freeze_date(ledger)
    assert last["r2"] == v(ledger, "champion.r2")

    for p in pts[1:]:
        assert p.get("cause"), f"step to {p['date']} has no cause label"
        assert p.get("cause_type") in ("model", "data"), f"step to {p['date']}: {p.get('cause_type')}"


def test_a5_wade_storm_step_credits_rain_fix_and_six_fixes(ledger, charts):
    pts = charts.chart_data("timeline", ledger)["points"]
    idx = [i for i, p in enumerate(pts) if p["date"] == "2026-05-31" and p["r2"] == 0.758]
    assert idx, "no timeline point at 0.758 dated 2026-05-31"
    i = idx[0]
    assert i > 0 and pts[i - 1]["r2"] == 0.694, "the 0.758 step does not start from 0.694"
    cause = pts[i]["cause"].lower()
    assert "rain" in cause, f"Wade Storm step does not credit the rain fix: {cause!r}"
    assert "six" in cause or "signal harvest" in cause, \
        f"Wade Storm step does not credit the six fixes: {cause!r}"


# ─── A6: the hook — red line, freeze-date level, "lowest since" ─────────────

def _lowest_since(daily, when):
    """Latest earlier year whose level on the same calendar date was at or below today's."""
    today = daily[when]
    for y in range(when.year - 1, daily.index.min().year - 1, -1):
        t = pd.Timestamp(year=y, month=when.month, day=when.day)
        if t in daily.index and daily[t] <= today:
            return y
    return None


def test_a6_hook_shows_red_line_and_true_freeze_level(ledger, charts):
    fd = freeze_date(ledger)
    raw = pd.read_csv(ROOT / "Silver Data" / "Kinneret Level" / "kinneret_level.csv",
                      parse_dates=["date"]).set_index("date")["kinneret_level"]
    assert pd.Timestamp(fd) in raw.index, f"no measured level on the freeze date {fd}"
    level = float(raw[pd.Timestamp(fd)])

    assert v(ledger, "level.red_line_m") == RED_LINE
    assert v(ledger, "level.freeze_m") == level
    data = charts.chart_data("hook", ledger)
    assert data["red_line_m"] == RED_LINE
    assert data["freeze_level_m"] == level
    assert data["freeze_date"] == fd

    daily = level_daily()
    for d, lvl in data["series"]:
        assert abs(daily[pd.Timestamp(d)] - lvl) <= 0.001, f"hook series at {d}: {lvl}"
    assert data["series"][-1][0] == fd

    if fd == "2026-10-11":
        assert level == -213.655


def test_a6_lowest_since_claim_is_true_for_the_calendar_date(ledger):
    fd = pd.Timestamp(freeze_date(ledger))
    daily = level_daily()
    truth = _lowest_since(daily, fd)
    assert v(ledger, "level.lowest_since_year") == truth
    if freeze_date(ledger) == "2026-10-11":
        assert truth == 2018
    for name, text in texts().items():
        if fd.year - truth < 10:
            assert not re.search(r"(worst|lowest)\s+in\s+a\s+decade", text, re.I), \
                f"{name}: 'in a decade' claim, but it is only the lowest since {truth}"


# ─── A19: the frontier chart ────────────────────────────────────────────────

def _json_path(blob, path):
    for part in path.split("."):
        blob = blob[part]
    return blob


def test_a19_frontier_values_trace_to_stored_results(ledger, charts):
    pts = charts.chart_data("frontier", ledger)["points"]
    groups = {p["group"] for p in pts}
    assert {"7d", "14_30d", "summer"} <= groups, f"frontier groups {groups}"
    lr = json.loads((ROOT / LONGRANGE_FILE).read_text(encoding="utf-8"))
    lr_date = commit_date(git("log", "-1", "--format=%h", "--", LONGRANGE_FILE).strip())

    for p in pts:
        e = ledger[p["key"]]
        assert p["value"] == e["value"], f"frontier {p['key']}: plotted {p['value']} != ledger"
        if p["group"] == "7d":
            assert p["key"] == "champion.r2"
        elif p["group"] == "14_30d":
            assert e["kind"] == "historical" and e["date"] == lr_date, p["key"]
            src_file, _, src_path = e["source"].partition("#")
            assert src_file == LONGRANGE_FILE, e["source"]
            assert e["value"] == _json_path(lr, src_path), f"{p['key']} != {e['source']}"
            assert e.get("perfect_prognosis") is True, p["key"]
            assert "best case" in p["label"].lower(), f"{p['key']} label {p['label']!r}"
        else:
            assert e["kind"] == "freeze", p["key"]
            assert "not machine learning" in p["label"].lower() or "seasonal" in p["label"].lower(), \
                f"summer point {p['key']} not labelled as a seasonal (non-ML) method"


def test_a19_crossing_hindcast_run_on_the_freeze(ledger):
    for k in ["crossing.n", "crossing.never_crossed", "crossing.last_rain_mm"] + \
             [f"crossing.{s}.mae_{b}" for s in ("scaled", "unscaled") for b in BANDS]:
        assert ledger[k]["kind"] == "freeze", k
    assert v(ledger, "crossing.last_rain_mm") == 5
    # Independent count of downward crossings of the red line, 2006 to the freeze.
    daily = level_daily()
    daily = daily[(daily.index >= "2006-01-01") & (daily.index <= freeze_date(ledger))]
    below = daily < RED_LINE
    n = int((below & ~below.shift(1, fill_value=True)).sum())
    assert v(ledger, "crossing.n") == n, f"ledger says {v(ledger, 'crossing.n')} crossings, data has {n}"
