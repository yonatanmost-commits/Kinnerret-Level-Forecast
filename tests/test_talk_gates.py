"""Build gates for the Kinneret Conference talk deck (intent/kinneret-talk-deck A1, A7).

A1: the build stops when the ledger's hash doesn't match the truth stamp, and builds without
re-running the truth tests when it does (plan D8).
A7: the build stops on a number typed into the text instead of a {placeholder}, and names it
(plan D6).

Contract fixed here, in docs/talk/build_deck.py:
- BuildStopped: the exception every gate raises; its message names the cause.
- check_stamp(ledger_path, stamp_path): stamp JSON holds {"ledger_sha256": sha256 of the
  ledger file's bytes}.
- check_numbers(text_path, ledger): scans the file for digits outside {placeholders}. The file's
  `allow:` line lists exempt phrases separated by " | ". Lines starting with `allow:`,
  `object:`, `accepted:` or `## slide` are structure, not text, and are not scanned. An unknown
  {placeholder} also stops the build.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs" / "talk"))

LEDGER = {
    "freeze_date": {"value": "2026-10-11", "display": "11 October 2026", "unit": "",
                    "source": "fixture", "date": "2026-10-11", "kind": "freeze"},
    "champion.r2": {"value": 0.762, "display": "0.76", "unit": "",
                    "source": "fixture", "date": "2026-10-11", "kind": "freeze"},
}

CLEAN_TALK = """allow: 2023 | 15 minutes

## slide hook
object: chart:hook
text: Below the red line
notes:
On {freeze_date} the model scored {champion.r2}. In 2023 the rain went missing.
This takes 15 minutes.
accepted: 3f9a1c07

## slide olympics
object: picture:images/drop_01.png
text: Eight models
notes:
Eight models raced.
accepted:
"""


@pytest.fixture
def bd():
    import build_deck
    return build_deck


def write_ledger(tmp_path, ledger=LEDGER):
    p = tmp_path / "numbers_ledger.json"
    p.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return p


def write_stamp(tmp_path, ledger_path):
    p = tmp_path / "truth_stamp.json"
    p.write_text(json.dumps({"ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest()}),
                 encoding="utf-8")
    return p


def write_talk(tmp_path, text):
    p = tmp_path / "talk.md"
    p.write_text(text, encoding="utf-8")
    return p


# ─── A1 ─────────────────────────────────────────────────────────────────────

def test_a1_matching_stamp_builds_without_rerunning_truth_tests(bd, tmp_path, monkeypatch):
    ledger = write_ledger(tmp_path)
    stamp = write_stamp(tmp_path, ledger)

    def forbidden(*a, **k):
        raise AssertionError("truth tests re-ran although the facts did not change")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(pytest, "main", forbidden)

    bd.check_stamp(ledger, stamp)


def test_a1_changed_facts_stop_the_build(bd, tmp_path):
    ledger = write_ledger(tmp_path)
    stamp = write_stamp(tmp_path, ledger)
    changed = dict(LEDGER, **{"champion.r2": dict(LEDGER["champion.r2"], value=0.771)})
    write_ledger(tmp_path, changed)
    with pytest.raises(bd.BuildStopped, match="(?i)truth"):
        bd.check_stamp(ledger, stamp)


def test_a1_missing_stamp_stops_the_build(bd, tmp_path):
    ledger = write_ledger(tmp_path)
    with pytest.raises(bd.BuildStopped, match="(?i)truth"):
        bd.check_stamp(ledger, tmp_path / "truth_stamp.json")


# ─── A7 ─────────────────────────────────────────────────────────────────────

def test_a7_clean_text_passes(bd, tmp_path):
    bd.check_numbers(write_talk(tmp_path, CLEAN_TALK), LEDGER)


def test_a7_typed_number_stops_the_build_and_is_named(bd, tmp_path):
    talk = CLEAN_TALK.replace("Eight models raced.", "Eight models raced; the best scored 0.77.")
    with pytest.raises(bd.BuildStopped, match=r"0\.77"):
        bd.check_numbers(write_talk(tmp_path, talk), LEDGER)


def test_a7_typed_number_in_slide_text_is_caught(bd, tmp_path):
    talk = CLEAN_TALK.replace("text: Below the red line", "text: 66 cm below the red line")
    with pytest.raises(bd.BuildStopped, match="66"):
        bd.check_numbers(write_talk(tmp_path, talk), LEDGER)


def test_a7_number_not_on_the_allow_list_is_caught(bd, tmp_path):
    talk = CLEAN_TALK.replace("In 2023 the rain", "In 2021 the rain")
    with pytest.raises(bd.BuildStopped, match="2021"):
        bd.check_numbers(write_talk(tmp_path, talk), LEDGER)


def test_a7_unknown_placeholder_stops_the_build(bd, tmp_path):
    talk = CLEAN_TALK.replace("{champion.r2}", "{champion.r2_typo}")
    with pytest.raises(bd.BuildStopped, match=r"champion\.r2_typo"):
        bd.check_numbers(write_talk(tmp_path, talk), LEDGER)
