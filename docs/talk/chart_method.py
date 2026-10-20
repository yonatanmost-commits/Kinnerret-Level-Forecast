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


def box(ax, x0, x1, yc, h, words, kind="data", icon=None, L=None, name=None):
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
    y0 = ty - (len(lines) - 1) / 2 * step                         # the first line's centre
    if bold:                                                     # a bold first line, the rest light
        L.lines(ax, name, cx, y0, lines[:1], step, TEXT, True, T.INK, ha="center")
        if lines[1:]:
            L.lines(ax, f"{name}.sub", cx, y0 + step, lines[1:], step, TEXT, False, T.INK, ha="center")
    else:
        L.lines(ax, name, cx, y0, lines, step, TEXT, False, T.INK, ha="center")


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

    L = T.Labels()                                               # the lanes' words are native text in the show
    # WEEK AHEAD
    L.text(ax, "lane.1", C1[0], 215, "Week ahead  ·  retrained every morning", 34, True, T.INK, ha="left", va="center")
    y = 355
    box(ax, *C1, y, 150, "weather forecast\n7 days", L=L, name="box.1")
    box(ax, *C2, y, 190, "Jordan's flow", "model", trees_icon, L, "box.2")
    box(ax, *C3, y, 190, "lake's change", "model", trees_icon, L, "box.3")
    box(ax, *C4, y, 150, "level\n7 days", "out", L=L, name="box.4")
    flow(ax, C1[1], C2[0], y)
    flow(ax, C2[1], C3[0], y)
    flow(ax, C3[1], C4[0], y)

    # YEAR AHEAD
    L.text(ax, "lane.2", C1[0], 535, "Year ahead  ·  one run per past winter", 34, True, T.INK, ha="left", va="center")
    y, top_in, low_in = 740, 645, 835
    box(ax, *C1, top_in, 130, "last 14 days\nlake · river · weather", L=L, name="box.5")
    box(ax, *C1, low_in, 130, "weather ahead\nfrom each past winter", L=L, name="box.6")
    T.text_centered(ax, (C1[0] + C1[1]) / 2, (top_in + low_in) / 2, "+", 40, True, T.INK)
    box(ax, *C2, y, 200, "GRU", "model", chain_icon, L, "box.7")
    box(ax, *C3, y, 170, "one future\nper winter", L=L, name="box.8")
    box(ax, *C4, y, 200, "forecast\nwinters weighted\nby Copernicus", "out", L=L, name="box.9")
    for yin in (top_in, low_in):                                 # both inputs feed the GRU
        arrow(ax, (C1[1] + 8, yin), (C2[0] - 8, y + (yin - y) * 0.35), head=12)
    flow(ax, C2[1], C3[0], y)
    flow(ax, C3[1], C4[0], y)

    L.centered(ax, "footer", T.W / 2, 990, "trained on station data from July 2002", 30, False, T.INK_2)

    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
