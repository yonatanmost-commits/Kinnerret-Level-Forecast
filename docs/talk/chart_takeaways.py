"""
chart_takeaways.py - slide 12, "The takeaways", after the horizon and before the Degania Dam
(originator, 2026-10-31; a third added 1 Nov). Three takeaways, one per click, each a teal number, one bold line and one
light line under it:

  1. the forecast, from a process engineer working outside his own field: the chance the lake is
     ABOVE the red line a year from the start. Read from the same file as the horizon slide's
     "1 in 3: still below" (data/slide11_fan.csv, last row's p_red), so the 5 Nov refresh moves
     both together.
     A process engineer's model, built outside my field.
  2. the better process is superior: Kasparov's centaur lesson (NYRB, 2010: "Weak human + machine
     + better process was superior to a strong computer alone and, more remarkably, superior to a
     strong human + machine + inferior process"); paraphrased, so "after", not quotation marks.
     The spoken script carries the originator's own second takeaway (originator, 31 Oct).
     Under the lines (originator, 31 Oct, fourth version): 1 "Nobody knows the coming winter, and
     I'm a process engineer"; 2 "Dare to work outside your field"; Kasparov's exact words as a
     note at the bottom with click 2.
     1 Nov (originator, from the full rehearsal): takeaway 2's line "Dare to expand your limits";
  3. not 10x faster but better work, and work I couldn't do before (the originator's own: "the
     quality of my work has gone up and I'm able to do stuff I wasn't able to do before").

The slide's title is the show's native title; the words here are native text too (theme.Labels),
so they can be designed by hand. Each frame is the whole slide, so a click only adds.

Run:  python docs/talk/chart_takeaways.py      # -> charts/takeaways_1..3.png (+ bare/), 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import pandas as pd                                                  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

FAN11 = HERE / "data" / "slide11_fan.csv"


def above_odds() -> str:
    """How often the lake ends the year above the red line (the fan's last horizon), as the
    same "k in n" the fan slide uses for its complement (chart_fan.odds)."""
    from chart_fan import odds
    p_red = float(pd.read_csv(FAN11).iloc[-1]["p_red"])
    return odds(1 - p_red)


def takeaways() -> list[tuple[str, str]]:
    return [(f"{above_odds()}: above the red line, a year from now",
             "Nobody knows the coming winter, and I'm a process engineer"),
            ("The better process is superior",
             "Dare to expand your limits"),
            ("Not 10x faster: better work",
             "and work I couldn't do before")]


# under takeaway 2, at the bottom: Kasparov's own words (NYRB, 2010), so the line above can paraphrase
NOTE = ("“Weak human + machine + better process was superior to a strong computer alone and, more remarkably,\n"
        "superior to a strong human + machine + inferior process.”   Garry Kasparov, NYRB, 2010")
NOTE_PT = 20


X_NUM, X_TEXT = T.MARGIN_X, T.MARGIN_X + 110
Y0, PITCH = 300, 225                       # the first takeaway's bold line, and the step to the next
BIG_PT, SUB_PT, NUM_PT = 50, 30, 72


def draw(click: int) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)
    ax.axis("off")
    L = T.Labels()                                               # every word is native text in the show
    for i, (big, sub) in enumerate(takeaways()[:click]):
        y = Y0 + i * PITCH
        L.centered(ax, f"num.{i + 1}", X_NUM, y + 30, str(i + 1), NUM_PT, True, T.USED_TEXT, ha="left")
        L.centered(ax, f"take.{i + 1}", X_TEXT, y, big, BIG_PT, True, T.INK, ha="left")
        L.centered(ax, f"sub.{i + 1}", X_TEXT, y + 85, sub, SUB_PT, False, T.INK_2, ha="left")
    if click >= 2:
        L.text(ax, "note", X_TEXT, T.H - 95, NOTE, NOTE_PT, False, T.INK_2, ha="left", va="baseline",
               linespacing=1.4)
    path = HERE / "charts" / f"takeaways_{click}.png"
    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    for n in range(1, len(takeaways()) + 1):
        draw(n)
