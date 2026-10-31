"""The talk's script, by slide, as Markdown, Word and plain text, from review/deck.html (through
build_show.slides). Same layout as the hand-made 26/28 Oct files: one section per slide (the
slide's question and word count under its title), [click] between clicks, the hidden Q&A slides
at the end as backups.

    python make_script.py
"""
import re
from pathlib import Path

import build_show as B

HERE = Path(__file__).parent
OUT = HERE / "Kinneret_Talk_Script"
WPM = 130                                   # the narration's pace
HEAD = "11 Nov 2026 · Beit Gavriel"


def words(paras: list[str]) -> int:
    return sum(len(re.findall(r"\S+", p)) for p in paras)


def sections():
    """(kind, number, title, question or "", paragraphs) per slide; kind "slide" or "backup"."""
    for s in B.slides(backups=True):
        paras = [p.strip() for p in s["script"] if p.strip()]
        q = "" if s.get("backup") and s["q"] == s["title"] else s["q"]
        yield ("backup" if s.get("backup") else "slide"), s["n"], s["title"], q, paras


def summary(secs) -> str:
    talk = [x for x in secs if x[0] == "slide"]
    n = sum(words(x[4]) for x in talk)
    return f"{HEAD} · {len(talk)} slides, {n} words (about {round(n / WPM)} min)"


def markdown(secs) -> str:
    out = ["# Kinneret talk: the script, by slide", "",
           f"*{summary(secs)} · **[click]** marks the next click*", ""]
    for kind, n, title, q, paras in secs:
        out += [f"## Slide {n} · {title}" if kind == "slide" else f"### Backup · {title}", ""]
        out += [f"*{q + ' · ' if q else ''}{words(paras)} words*", ""]
        out += "\n\n**[click]**\n\n".join(paras).split("\n") + [""]
    return "\n".join(out)


def text(secs) -> str:
    bar = "=" * 60
    out = ["KINNERET TALK: THE SCRIPT, BY SLIDE", f"{summary(secs)} · [click] marks the next click", ""]
    for kind, n, title, q, paras in secs:
        out += ["", bar, f"{'SLIDE ' + n if kind == 'slide' else 'BACKUP'} · {title}",
                f"{q + '  ·  ' if q else ''}{words(paras)} words", bar, ""]
        out += "\n\n[click]\n\n".join(paras).split("\n") + [""]
    return "\n".join(out)


def word(secs, path: Path) -> None:
    import docx
    from docx.shared import Pt, RGBColor
    d = docx.Document()
    d.add_heading("Kinneret talk: the script, by slide", 0)
    r = d.add_paragraph().add_run(f"{summary(secs)} · [click] marks the next click")
    r.font.size, r.font.color.rgb = Pt(10), RGBColor(0x66, 0x66, 0x66)
    for kind, n, title, q, paras in secs:
        d.add_heading(f"Slide {n} · {title}" if kind == "slide" else f"Backup · {title}", 1 if kind == "slide" else 2)
        p = d.add_paragraph()
        if q:
            r = p.add_run(q)
            r.italic, r.font.size, r.font.color.rgb = True, Pt(10), RGBColor(0x66, 0x66, 0x66)
        r = p.add_run(f"{'   ·   ' if q else ''}{words(paras)} words")
        r.font.size, r.font.color.rgb = Pt(9), RGBColor(0x99, 0x99, 0x99)
        for i, para in enumerate(paras):
            if i:
                r = d.add_paragraph().add_run("[click]")
                r.bold, r.font.size, r.font.color.rgb = True, Pt(9), RGBColor(0x1F, 0x7A, 0x7A)
            d.add_paragraph(para)
    d.save(path)


def main() -> None:
    secs = list(sections())
    OUT.with_suffix(".md").write_text(markdown(secs), encoding="utf-8")
    OUT.with_suffix(".txt").write_text(text(secs), encoding="utf-8-sig")
    word(secs, OUT.with_suffix(".docx"))
    print(summary(secs))


if __name__ == "__main__":
    main()
