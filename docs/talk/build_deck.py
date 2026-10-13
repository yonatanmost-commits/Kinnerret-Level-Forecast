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
        elif line.startswith("object:"):
            cur.object = line[len("object:"):].strip()
        elif line.startswith("text:"):
            cur.text = line[len("text:"):].strip()
    for s in slides:
        s.notes = s.notes.strip()
    return slides


def fill(text: str, ledger: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(ledger[m.group(1)]["display"]), text)
