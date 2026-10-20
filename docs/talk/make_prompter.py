"""
make_prompter.py - a teleprompter for practising the talk, built from the same script as the show.

Reads the talk from review/deck.html (through build_show.segments, so clicks, "[pause]" and the
merged slide-2 click match the show exactly), the narration clips' lengths (show/audio, the
calm-pace target per click) and a thumbnail of what is on screen at each click. Writes one
self-contained page, prompter.html: auto-scroll at a words-per-minute pace, a reading line,
click marks, a running clock against the narrated pace, and a cue-card mode with the slide
pointers only. Rebuild it after any script change.

Run:  python docs/talk/make_prompter.py        # -> docs/talk/prompter.html
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_show as B                                               # noqa: E402

OUT = HERE / "prompter.html"
TEMPLATE = HERE / "prompter_template.html"
STILLS = {"charts/lake_years.gif": "charts/lake_years.png", "charts/slide1_map.gif": "charts/slide1_map.png"}


def thumb(rel: str | None) -> str:
    if not rel:
        return ""
    path = HERE / STILLS.get(rel, rel)
    im = Image.open(path).convert("RGB")
    im.thumbnail((320, 180))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def talk() -> list[dict]:
    pointers = {s["n"]: s.get("pointers") or [] for s in B.slides()}
    out = []
    for g in B.segments():
        clip = B.AUDIO / f"{g['id']}.mp3"
        secs = B.duration(clip) + g["pause"] if clip.exists() else len(g["text"].split()) / 2.2
        if not out or out[-1]["n"] != g["n"]:
            out.append({"n": g["n"], "title": g["title"] or "", "q": g["q"], "clicks": [],
                        "pointers": [re.sub(r"^\[\d+\]\s*", "", p) for p in pointers.get(g["n"], [])]})
        out[-1]["clicks"].append({"text": g["text"], "secs": round(secs, 1), "thumb": thumb(g["image"])})
    return out


def main() -> None:
    data = json.dumps(talk(), ensure_ascii=False)
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__TALK__*/[]", data)
    OUT.write_text(page, encoding="utf-8")
    words = sum(len(c["text"].split()) for s in json.loads(data) for c in s["clicks"])
    print(f"saved {OUT.name}: {words} words, {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
