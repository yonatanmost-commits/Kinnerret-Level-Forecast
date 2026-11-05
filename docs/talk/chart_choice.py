"""
chart_choice.py - slide 9, "The choice" (originator, 5 Nov 2026), in the errors slide's place: when to
use classic ML and when to try the neural network. "When the input was estimated, the neural network
was better." A table in the errors slide's style (originator: "use another table, like the error
table"), two blocks of the same two models at the same four horizons:

  click 1  With the real weather      the trees lower at every range
  click 2  With a seasonal forecast   a tie at a week and a month; the network lower at 6 months
                                       and a year

Teal = a CLEAR win WITH THE WEATHER YOU'D REALLY HAVE (originator, 5 Nov: "mark the 2.0 and the 55
and 85 ... no one has the real weather 6 months ahead so dont highlight the 8.0 and 41"; then, told
55 vs 64 is not clear: "keep only the 2.0 and 85 thats best for the talk"). The real weather counts
only for a week (a good 7-day forecast), the seasonal forecast from a month on. Clear = the 90%
year-block bootstrap of (network - trees) excludes zero (15 test years, 2000 draws, seed 0).
Since 5 Nov this slide takes the errors slide's place (that one is a Q&A backup).

Every cell is computed here from the backtest (docs/experiments/cfc_monthly: G = GBR, B14gru = GRU;
weather 'obs' = the real weather, 'seas5' = average weather nudged by Copernicus), mean absolute
level error in cm over the starts both models share (a fair head-to-head; pooling each model's own
starts moves the trees' real-weather 6 months and year by 1 cm: 42, 78). Rerunning the backtest
redraws the slide.
The cells it shares with the errors slide (the week with known weather; month, 6 months, year with
the forecast) must match it (tests/test_talk_crossover.py).

Run:  python docs/talk/chart_choice.py      # -> charts/choice_1..2.png (+ bare/), 1920 x 1080
"""
from __future__ import annotations

import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import numpy as np                                                   # noqa: E402
import pandas as pd                                                  # noqa: E402
from matplotlib.patches import FancyBboxPatch                        # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

BACKTEST = ROOT / "docs" / "experiments" / "cfc_monthly"
HORIZONS = [7, 30, 182, 365]
COLUMNS = ["Week", "Month", "6 months", "Year"]                    # as the errors slide, no star
BLOCKS = {"known": ("obs", "With the real weather"), "forecast": ("seas5", "With a seasonal forecast")}
MODELS = {"trees": ("G", "GBR", "Classic ML"), "network": ("B14gru", "GRU", "Neural network")}
CAPTION = "Error (cm) · teal = clearly lower, in practice"
CREDIT = "Copernicus Climate Change Service information, 2026"


def fmt(cm: float) -> str:
    """As the errors slide: one decimal under 10 cm, whole cm from 10."""
    return f"{cm:.1f}" if round(cm, 1) < 10 else f"{cm:.0f}"


def backtest_stamp() -> str:
    """The day the backtest files were last written (the 5 Nov cells hold for 2026-10-17)."""
    t = max(p.stat().st_mtime for p in BACKTEST.glob("*.json"))
    return date.fromtimestamp(t).isoformat()


@lru_cache(maxsize=1)
def table() -> dict:
    """{'known'|'forecast': {'trees'|'network': [ {cm, ci, clear} per horizon ]}}; ci = the 90%
    interval of (network - trees) in cm, the same on both rows."""
    sys.path.insert(0, str(ROOT / "Automation"))
    import cfc_tournament_report as r
    d = r.load(BACKTEST)
    out = {}
    for block, (weather, _) in BLOCKS.items():
        out[block] = {m: [] for m in MODELS}
        for H in HORIZONS:
            x = d[(d["H"] == H) & (d["weather"] == weather) & d["method"].isin([v[0] for v in MODELS.values()])]
            x = x.pivot_table(index=["year", "start"], columns="method", values="ae").dropna() * 100
            diff = x[MODELS["network"][0]] - x[MODELS["trees"][0]]
            by_year = {y: g.to_numpy() for y, g in diff.groupby(level="year")}
            years = np.array(sorted(by_year))
            rng = np.random.default_rng(0)
            boot = [np.concatenate([by_year[y] for y in rng.choice(years, len(years))]).mean()
                    for _ in range(2000)]
            lo, hi = (float(v) for v in np.percentile(boot, [5, 95]))
            for m, (method, *_) in MODELS.items():
                clear = lo > 0 if m == "trees" else hi < 0
                out[block][m].append({"cm": float(x[method].mean()), "ci": (lo, hi), "clear": clear})
        for c in range(len(HORIZONS)):
            real = (block == "known") == (HORIZONS[c] <= 7)        # a week: real; later: a forecast
            for m in MODELS:
                out[block][m][c]["marked"] = real and out[block][m][c]["clear"]
    return out


def draw(click: int) -> Path:
    tab = table()
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)                                          # pixel coordinates, y down
    ax.axis("off")

    name_x, type_x = 120, 335
    col_x = [890, 1145, 1400, 1655]                              # the errors slide's column centres
    head_y = 235
    block_y = {"known": 335, "forecast": 655}                    # each block's heading
    row_dy, row_h = 100, 120                                     # first row under its heading, row pitch
    cell_w, cell_h = 235, 104

    L = T.Labels()                                               # every word is native text in the show
    L.text(ax, "caption", (col_x[0] + col_x[-1]) / 2, 978, CAPTION, 28, False, T.INK_2,
           ha="center", va="center")                             # under the table, as the errors slide
    for k, (x, c) in enumerate(zip(col_x, COLUMNS), 1):
        L.text(ax, f"header.{k}", x, head_y, c, 32, True, T.INK_2, ha="center", va="center")
    ax.plot([name_x, col_x[-1] + cell_w / 2], [head_y + 45] * 2, color=T.FAINT, lw=2)

    for block in list(BLOCKS)[:click]:
        _, heading = BLOCKS[block]
        L.centered(ax, f"block.{block}", name_x, block_y[block], heading, 34, True, T.USED_TEXT, ha="left")
        for r, (m, (_, name, kind)) in enumerate(MODELS.items()):
            y = block_y[block] + row_dy + r * row_h
            L.centered(ax, f"{block}.{m}", name_x, y, name, 44, True, T.INK, ha="left")
            L.centered(ax, f"{block}.{m}.type", type_x, y, kind, 30, False, T.INK, ha="left")
            for x, cell in zip(col_x, tab[block][m]):
                if cell["marked"]:
                    ax.add_patch(FancyBboxPatch((x - cell_w / 2, y - cell_h / 2), cell_w, cell_h,
                                                boxstyle="round,pad=0,rounding_size=26",
                                                facecolor=T.USED_SOFT, edgecolor="none", zorder=1))
                T.text_centered(ax, x, y, fmt(cell["cm"]), 52, cell["marked"], T.INK, zorder=2)
    if click >= 2:
        L.text(ax, "credit", T.CREDIT_XY[0], T.CREDIT_XY[1], CREDIT, T.CREDIT_PT, False, T.INK_2,
               ha="left", va="baseline")

    path = HERE / "charts" / f"choice_{click}.png"
    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.name}")
    return path


if __name__ == "__main__":
    for k in (1, 2):
        draw(k)
    for w, (_, heading) in BLOCKS.items():                       # the cells and intervals, for the notes
        for m in MODELS:
            print(f"{heading:26} {m:8}", "  ".join(f"{fmt(c['cm']):>5}{'*' if c['clear'] else ' '}"
                                                   for c in table()[w][m]))
        print(" " * 36, "  ".join(f"[{c['ci'][0]:+.1f},{c['ci'][1]:+.1f}]" for c in table()[w]["trees"]))
