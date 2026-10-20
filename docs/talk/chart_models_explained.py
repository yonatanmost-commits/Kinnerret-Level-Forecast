"""
chart_models_explained.py - slide 7, "What are the two models?": our own drawings of the two
standard pictures, side by side.

Left, classic ML (GBR, gradient boosting): small decision trees in a row joined by "+", each a
couple of yes/no splits, with "= forecast" under the row. Each tree is smaller than the last and a curved
arrow runs from one to the next: each tree fixes what the trees before it got wrong.
Right, deep learning (GRU, a recurrent network): one identical cell per day, day 1 -> today, with
a memory line running through the chain and a small gate on it in every cell; each cell takes
that day's input from below, and the last one gives the forecast.

Drawn here in the deck theme, not copied from any published diagram. Very few words, all large;
the title spot stays empty.

Run:  python docs/talk/chart_models_explained.py   # -> charts/models_explained.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch   # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

OUT = HERE / "charts" / "models_explained.png"
LINE = 4                                                             # stroke width, px-ish


def tree(ax, cx: float, top: float, s: float) -> tuple[float, float]:
    """A small decision tree: a root split, two children, one of them split again.
    Returns (bottom, half-width) so arrows and signs can sit around it."""
    r, dx, dy = 20 * s, 70 * s, 85 * s
    root = (cx, top)
    left, right = (cx - dx, top + dy), (cx + dx, top + dy)
    ll, lr = (left[0] - dx * 0.6, left[1] + dy), (left[0] + dx * 0.6, left[1] + dy)
    for a, b in ((root, left), (root, right), (left, ll), (left, lr)):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=T.INK_2, lw=LINE * s, zorder=1)
    for node in (root, left):                                    # yes/no questions
        ax.add_patch(Circle(node, r, facecolor=T.SURFACE, edgecolor=T.USED, lw=LINE, zorder=2))
    for leaf in (right, ll, lr):                                 # answers
        ax.add_patch(FancyBboxPatch((leaf[0] - r, leaf[1] - r), 2 * r, 2 * r,
                                    boxstyle=f"round,pad=0,rounding_size={6 * s}",
                                    facecolor=T.USED_SOFT, edgecolor=T.USED, lw=LINE * 0.75, zorder=2))
    return ll[1] + r, dx * 1.6 + r


def arrow(ax, a, b, color=T.INK_2, lw=LINE, rad=0.0, head=22):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=f"-|>,head_length={head / 20},head_width={head / 34}",
                                 connectionstyle=f"arc3,rad={rad}", color=color, lw=lw,
                                 mutation_scale=20, zorder=3, shrinkA=0, shrinkB=0))


def draw(path: Path = OUT) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)                                          # pixel coordinates, y down
    ax.set_aspect("equal")
    ax.axis("off")

    mid = T.W / 2
    ax.plot([mid, mid], [200, 960], color=T.FAINT, lw=2)
    for x, head, name in ((mid / 2, "Classic ML", "GBR"), (mid * 1.5, "Deep learning", "GRU")):
        ax.text(x, 250, head, ha="center", va="center", color=T.INK, fontproperties=T.font(True, 44))
        ax.text(x, 325, name, ha="center", va="center", color=T.INK_2, fontproperties=T.font(False, 34))

    # LEFT - boosting: trees, each smaller, joined by "+", then "= forecast"
    mid_y = 630                                                  # trees centred on this line
    scales, gap = [1.12, 0.93, 0.75], 76                         # gap holds a "+"; 1.5x the v1 trees
    row = sum(222 * s for s in scales) + gap * (len(scales) - 1)    # each tree is 132 s + 90 s wide
    x, xs, plus_x, tops = (T.W / 2 - row) / 2, [], [], []      # centred in the left half
    for s in scales:                                             # place trees by their width
        left, right = 132 * s, 90 * s                            # extent left / right of the root
        if xs:
            plus_x.append(x + gap / 2)
            x += gap
        cx = x + left
        top = mid_y - 85 * s                                     # the tree spans 2 x 85 s vertically
        tree(ax, cx, top, s)
        xs.append(cx)
        tops.append(top)
        x = cx + right
    for px in plus_x:                                            # "+" between trees
        T.text_centered(ax, px, mid_y, "+", 44, True, T.INK)
    for i in range(1, len(xs)):                                  # each tree fixes the last one's errors
        arrow(ax, (xs[i - 1] + 10, tops[i - 1] - 45), (xs[i] - 10, tops[i] - 40),
              color=T.AMBER, lw=3, rad=-0.45, head=12)
    T.text_centered(ax, T.W / 4, mid_y + 230, "= forecast", 34, True, T.INK)   # under the row

    # RIGHT - recurrent network: one cell per day, memory line through, input from below
    cy, w, h = 640, 130, 130
    cells = [(1180, "day 1"), (1380, "day 2"), (1690, "today")]
    memory_y = cy - 22
    ax.plot([1080, cells[-1][0] + w / 2], [memory_y] * 2, color=T.USED, lw=LINE * 2,
            solid_capstyle="round", zorder=1)
    T.text_centered(ax, 1535, memory_y + 40, "…", 48, True, T.INK_2)
    for x, label in cells:
        ax.add_patch(FancyBboxPatch((x - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0,rounding_size=22",
                                    facecolor=T.SURFACE, edgecolor=T.INK_2, lw=LINE, zorder=2))
        ax.plot([x - w / 2, x + w / 2], [memory_y] * 2, color=T.USED, lw=LINE * 2, zorder=3)
        ax.add_patch(Circle((x, memory_y), 13, facecolor=T.SURFACE, edgecolor=T.USED, lw=LINE, zorder=4))
        arrow(ax, (x, cy + 190), (x, cy + h / 2 + 4), head=12)   # that day's input from below
        ax.text(x, cy + 230, label, ha="center", va="center", color=T.INK,
                fontproperties=T.font(label == "today", 30))
    # the memory carries on between cells, and the last cell gives the forecast
    for a, b in ((cells[0][0] + w / 2, cells[1][0] - w / 2), (cells[1][0] + w / 2, 1495),
                 (1575, cells[2][0] - w / 2)):
        arrow(ax, (a, memory_y), (b, memory_y), color=T.USED, lw=LINE * 2, head=11)
    x_last = cells[-1][0]
    arrow(ax, (x_last, cy - h / 2 - 4), (x_last, 470), head=12)
    ax.text(x_last, 435, "forecast", ha="center", va="center", color=T.INK, fontproperties=T.font(True, 34))

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
