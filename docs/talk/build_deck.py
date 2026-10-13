"""
build_deck.py - talk.md + numbers ledger + charts + pictures -> talk.pptx and talk.pdf.

Gates that run on every build (plan D6, D8; tests/test_talk_gates.py):
  check_stamp   the ledger must match the hash the truth tests last passed on (truth_stamp.json);
                a match means the facts are already proven, so the truth tests are not re-run
  check_numbers no digit may be typed into the text: numbers enter only as {ledger.key}
                placeholders, or as a phrase on the file's `allow:` line

talk.md format:
  allow: 2023 | 15 minutes            exempt phrases, " | "-separated (one line, near the top)

  ## slide <id>
  object: chart:<name> | picture:<path> | table:<name>
  qr: app                             optional: the app's QR code in the corner (plan D18)
  text: <on-slide words>
  notes:
  <speaker notes, any number of lines, with {placeholders}>
  accepted: <short content hash, or empty>
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
TALK_MD = HERE / "talk.md"
QA_MD = HERE / "qa_prep.md"
LEDGER_PATH = HERE / "numbers_ledger.json"
STAMP_PATH = HERE / "truth_stamp.json"

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")
NUMBER = re.compile(r"\d(?:[\d.,:/]*\d)?")
STRUCTURE = ("allow:", "object:", "accepted:", "## slide")


class BuildStopped(Exception):
    """A gate refused the build; the message says why."""


# ─── gates ──────────────────────────────────────────────────────────────────

def check_stamp(ledger_path: Path = LEDGER_PATH, stamp_path: Path = STAMP_PATH) -> None:
    ledger_path, stamp_path = Path(ledger_path), Path(stamp_path)
    if not stamp_path.exists():
        raise BuildStopped(f"no truth stamp ({stamp_path.name}): the truth tests have not passed "
                           f"on these facts - run Automation/talk_freeze_run.py")
    stamped = json.loads(stamp_path.read_text(encoding="utf-8")).get("ledger_sha256")
    current = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    if stamped != current:
        raise BuildStopped("the numbers ledger changed since the truth tests last passed - run "
                           "Automation/talk_freeze_run.py so the truth tests pass first")


def allow_list(text: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith("allow:"):
            return [p.strip() for p in line[len("allow:"):].split("|") if p.strip()]
    return []


def typed_numbers(text: str) -> list[tuple[int, str]]:
    """(line number, token) for every digit run outside placeholders and allowed phrases."""
    allowed = sorted(allow_list(text), key=len, reverse=True)
    found = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(STRUCTURE):
            continue
        scan = PLACEHOLDER.sub(" ", line)
        for phrase in allowed:
            scan = re.sub(rf"(?<![\w.]){re.escape(phrase)}(?![\w]|\.\d)", " ", scan)
        found += [(i, m.group()) for m in NUMBER.finditer(scan)]
    return found


def check_numbers(text_path: Path, ledger: dict) -> None:
    text_path = Path(text_path)
    text = text_path.read_text(encoding="utf-8")
    problems = [f"line {i}: typed number '{tok}'" for i, tok in typed_numbers(text)]
    unknown = sorted({k for k in PLACEHOLDER.findall(text) if k not in ledger})
    problems += [f"unknown placeholder {{{k}}}" for k in unknown]
    if problems:
        raise BuildStopped(f"{text_path.name}: numbers must come from the ledger -\n  "
                           + "\n  ".join(problems))


# ─── talk.md ────────────────────────────────────────────────────────────────

@dataclass
class Slide:
    id: str
    object: str = ""
    text: str = ""
    notes: str = ""
    accepted: str = ""
    extra: dict = field(default_factory=dict)

    def content_hash(self) -> str:
        body = "\n".join([self.id, self.object, self.text, self.notes])
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]


def parse_talk(text: str) -> list[Slide]:
    slides: list[Slide] = []
    cur, in_notes = None, False
    for line in text.splitlines():
        if line.startswith("## slide"):
            cur = Slide(id=line[len("## slide"):].strip())
            slides.append(cur)
            in_notes = False
            continue
        if cur is None:
            continue
        if line.startswith("accepted:"):
            cur.accepted = line[len("accepted:"):].strip()
            in_notes = False
        elif in_notes:
            cur.notes += line + "\n"
        elif line.startswith("notes:"):
            in_notes = True
        elif line.startswith("qr:"):
            cur.extra["qr"] = line[len("qr:"):].strip()
        elif line.startswith("object:"):
            cur.object = line[len("object:"):].strip()
        elif line.startswith("text:"):
            cur.text = line[len("text:"):].strip()
    for s in slides:
        s.notes = s.notes.strip()
    return slides


def fill(text: str, ledger: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(ledger[m.group(1)]["display"]), text)


# ─── numbers_check.md (spec A11, A14) ───────────────────────────────────────

# Every phrase on talk.md's allow: line needs a source here, so Adnan can check it (plan D18).
ALLOW_SOURCES = {
    "2023": "the year the lake's rain gauge went offline and the pipeline turned it into zero rain; "
            "fixed 2026-05-30 (R² history step ac2ede5)",
    "2005": "the PAL/CSS Freestyle chess tournament, won by two amateurs using three computers: "
            "G. Kasparov, 'The Chess Master and the Computer', New York Review of Books, 11 Feb 2010",
    "1960": "the start of the ERA5 weather reanalysis used to rebuild the past (Open-Meteo archive, "
            "1960-01-01 onward; commit ea3a1af; paper Table C)",
}

CROSSING_BANDS = [("0_7", "1-7"), ("7_14", "8-14"), ("14_30", "15-30"), ("30_60", "31-60"),
                  ("60_90", "61-90"), ("90_120", "91-120"), ("120_plus", "over 120")]


def write_numbers_check(ledger: dict, out: Path = HERE / "numbers_check.md") -> Path:
    """Every number the talk uses, where it appears, its value and its date - for the originator
    and Adnan to read. Generated; never edited by hand."""
    uses: dict[str, list[str]] = {}
    for path in (TALK_MD, QA_MD):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for s in parse_talk(text) if path == TALK_MD else []:
            for k in PLACEHOLDER.findall(s.text + "\n" + s.notes):
                uses.setdefault(k, []).append(f"slide {s.id}")
        if path == QA_MD:
            for k in PLACEHOLDER.findall(text):
                uses.setdefault(k, []).append("Q&A sheet")
    for s in parse_talk(TALK_MD.read_text(encoding="utf-8")):
        if s.object.startswith("chart:"):
            uses.setdefault(f"(chart) {s.object[6:]}", []).append(f"slide {s.id}")

    fd = ledger["freeze_date"]["value"]
    lines = ["# Numbers check: Kinneret Conference talk", "",
             f"Generated by build_deck.py from numbers_ledger.json. Data freeze: **{fd}**.",
             "Measured numbers come from one re-run on the freeze. Historical numbers keep the date "
             "they were first measured and show it wherever they appear.", "",
             "| Number | Shown as | Unit | Where | Kind | Date | Source |", "|---|---|---|---|---|---|---|"]
    for k in sorted(k for k in uses if not k.startswith("(chart)")):
        e = ledger[k]
        date = e["date"] + (f" ({e['measured_note']})" if e.get("measured_note") else "")
        where = ", ".join(dict.fromkeys(uses[k]))
        lines.append(f"| `{k}` | {e['display']} | {e['unit']} | "
                     f"{where} | {e['kind']} | {date} | {e['source']} |")
    charts = sorted(k for k in uses if k.startswith("(chart)"))
    lines += ["", "Charts draw only from the ledger (charts.py chart_data); "
              f"charts used: {', '.join(c[8:] for c in charts)}.", ""]

    allowed = allow_list(TALK_MD.read_text(encoding="utf-8"))
    if allowed:
        lines += ["## Typed phrases allowed in the script", "", "| Phrase | Source |", "|---|---|"]
        lines += [f"| {a} | {ALLOW_SOURCES.get(a, '**no source given**')} |" for a in allowed]
        lines.append("")

    if "crossing.issued" in ledger:
        lines += ["## Red-line crossing hindcast, per band of days of warning", "",
                  f"{ledger['crossing.n']['value']} crossings of -213.0 m since "
                  f"{ledger['crossing.first_year']['value']}; a forecast issued every day from the last "
                  f"rain of at least {ledger['crossing.last_rain_mm']['value']} mm. 'Paired' = only the "
                  "forecasts both methods brought to the line; every spoken comparison uses paired.", "",
                  "| Days of warning | Issued | Scaled never crossed | Plain never crossed | "
                  "Paired n | Paired MAE scaled (days) | Paired MAE plain (days) |",
                  "|---|---|---|---|---|---|---|"]
        for b, label in CROSSING_BANDS:
            g = lambda k: ledger[k]["value"]
            lines.append(f"| {label} | {g(f'crossing.issued_{b}')} | {g(f'crossing.scaled.never_{b}')} | "
                         f"{g(f'crossing.unscaled.never_{b}')} | {g(f'crossing.paired.n_{b}')} | "
                         f"{g(f'crossing.paired.scaled.mae_{b}')} | {g(f'crossing.paired.unscaled.mae_{b}')} |")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
