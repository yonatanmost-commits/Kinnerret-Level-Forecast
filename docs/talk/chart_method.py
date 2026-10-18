"""
chart_method.py - slide 9, "How did we set it up?": the method as two lanes, left to right.

Top lane, the week ahead: the 7-day weather forecast -> the two-stage GBR (step 1, the Jordan's
flow; step 2, the lake's change) -> the level for 7 days.
Bottom lane, the year ahead, as the app's forecast runs it (fan_today, 2026-10-18 v2): the last 14
days of the lake, river and weather, plus one past winter's real weather ahead -> the GRU -> one
future per past winter, every horizon at once -> the forecast, each winter weighted by Copernicus.
Copernicus never enters the GRU here; it only weights the winters (the "average year nudged by
Copernicus" input belongs to the scoreboard runs, not the product). The fan is rebuilt by hand.
The model boxes carry the slide 7 pictures in small (trees for the GBR, the cell chain for the
GRU). Columns line up across the two lanes. Few words, all large; the title spot stays empty.

Run:  python docs/talk/chart_method.py       # -> charts/method_lanes.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch                # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402
from chart_models_explained import arrow, tree                       # noqa: E402

OUT = HERE / "charts" / "method_lanes.png"

# column spans (x0, x1), shared by both lanes
C1, C2, C3, C4 = (55, 525), (585, 885), (950, 1320), (1385, 1880)
TEXT = 26


def box(ax, x0, x1, yc, h, words, kind="data", icon=None):
    """A rounded box. kind: data (inputs), model (soft teal), out (the lane's result, teal ring)."""
    face, edge, lw, bold = {"data": (T.SURFACE, T.FAINT, 3, False),
                            "model": (T.USED_SOFT, T.USED, 3, True),
                            "out": (T.SURFACE, T.USED, 5, True)}[kind]
    ax.add_patch(FancyBboxPatch((x0, yc - h / 2), x1 - x0, h, boxstyle="round,pad=0,rounding_size=24",
                                facecolor=face, edgecolor=edge, lw=lw, zorder=1))
    cx = (x0 + x1) / 2
    ty = yc
    if icon:                                                     # picture on top, words below
        icon(ax, cx, yc - h / 2 + 22)
        ty = yc + h / 2 - 45
    lines = words.split("\n")
    step = TEXT * 1.22 * T.DPI / 72
    for i, line in enumerate(lines):
        T.text_centered(ax, cx, ty + (i - (len(lines) - 1) / 2) * step, line, TEXT, bold and i == 0, T.INK)


def trees_icon(ax, cx, top):
    for dx, s in ((-48, 0.46), (62, 0.36)):                      # two trees, the second smaller
        tree(ax, cx + dx, top + (0.46 - s) * 85, s)


def chain_icon(ax, cx, top):
    w, gap = 44, 22
    cy = top + 40
    xs = [cx - w - gap, cx, cx + w + gap]
    ax.plot([xs[0] - w / 2 - 10, xs[-1] + w / 2 + 10], [cy - 6] * 2, color=T.USED, lw=5, zorder=3)
    for x in xs:
        ax.add_patch(FancyBboxPatch((x - w / 2, cy - w / 2), w, w, boxstyle="round,pad=0,rounding_size=9",
                                    facecolor=T.SURFACE, edgecolor=T.INK_2, lw=3, zorder=2))
        ax.add_patch(Circle((x, cy - 6), 6, facecolor=T.SURFACE, edgecolor=T.USED, lw=2.5, zorder=4))


def flow(ax, a, b, y):
    arrow(ax, (a + 8, y), (b - 8, y), head=12)


def draw(path: Path = OUT) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    # WEEK AHEAD
    ax.text(C1[0], 215, "Week ahead  ·  retrained every morning", ha="left", va="center", color=T.INK,
            fontproperties=T.font(True, 34))
    y = 355
    box(ax, *C1, y, 150, "weather forecast\n7 days")
    box(ax, *C2, y, 190, "Jordan's flow", "model", trees_icon)
    box(ax, *C3, y, 190, "lake's change", "model", trees_icon)
    box(ax, *C4, y, 150, "level\n7 days", "out")
    flow(ax, C1[1], C2[0], y)
    flow(ax, C2[1], C3[0], y)
    flow(ax, C3[1], C4[0], y)

    # YEAR AHEAD
    ax.text(C1[0], 535, "Year ahead  ·  one run per past winter", ha="left", va="center", color=T.INK,
            fontproperties=T.font(True, 34))
    y, top_in, low_in = 740, 645, 835
    box(ax, *C1, top_in, 130, "last 14 days\nlake · river · weather")
    box(ax, *C1, low_in, 130, "weather ahead\nfrom each past winter")
    T.text_centered(ax, (C1[0] + C1[1]) / 2, (top_in + low_in) / 2, "+", 40, True, T.INK)
    box(ax, *C2, y, 200, "GRU", "model", chain_icon)
    box(ax, *C3, y, 170, "one future\nper winter")
    box(ax, *C4, y, 200, "forecast\nwinters weighted\nby Copernicus", "out")
    for yin in (top_in, low_in):                                 # both inputs feed the GRU
        arrow(ax, (C1[1] + 8, yin), (C2[0] - 8, y + (yin - y) * 0.35), head=12)
    flow(ax, C2[1], C3[0], y)
    flow(ax, C3[1], C4[0], y)

    T.text_centered(ax, T.W / 2, 990, "trained on station data from July 2002", 30, False, T.INK_2)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
