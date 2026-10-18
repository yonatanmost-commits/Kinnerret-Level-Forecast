"""
chart_models.py - slide 8, "Which model won?": a big, sparse table of three models by horizon.

Two rows, the GBR (classic ML) and the GRU (neural network), with a Type column (the liquid network left the talk, originator 2026-10-17); columns
are four real horizons (7, 30, 182 and 365 days), each with the weather you'd have at that range:
the week's real weather for the week, the Copernicus seasonal forecast ahead from a month on. Cells hold the typical lake-level error in cm. The lower error in each column gets a
teal highlight (both where they round equal); the other stays black, unhighlighted. A teal outline marks the model in use:
the two-stage GBR for the week, the GRU fan beyond. No small text (originator); the header
titles the slide with the horizon; the measure and unit sit under the table.

Numbers: the final run (cfc_monthly, branch fan-monthly @ 52fc2d2, station record 2011-2025,
15 test years), mean absolute level error pooled over forecast starts, recomputed from
docs/experiments/cfc_monthly/{B14gru_s3_ens,G_s3}.json and confirmed by model-coach.
Ties from per-test-year paired differences, 90% bootstrap.
Left out: a "year, if the winter were known" column. With perfect weather the trees lean ahead
(365 d 78 vs 85-86 cm; year-ahead mean 0.547 vs 0.651-0.673 m) but no pair is clear, so the
column would overstate it.

Run:  python docs/talk/chart_models.py       # -> charts/models_table.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import FancyBboxPatch                        # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

OUT = HERE / "charts" / "models_table.png"

COLUMNS = ["Week*", "Month", "6 months", "Year"]   # * the week assumes its weather is known
MODELS = [   # name, type, cm per column
    ("GBR", "Classic ML", ["2.0", "12", "64", "121"]),
    ("GRU", "Neural network", ["2.6", "12", "56", "85"]),
]
# per column, the rows that win or tie for the win: GRU-GBR +0.2 [-0.1, +0.5] at a week,
# +0.4 [-1.2, +1.9] at a month, -8.5 [-21.4, +4.0] at 6 months, -35.8 [-66.9, -8.6] at a year
# Each horizon uses the weather you'd actually have at that range (originator 2026-10-17): the
# week with the week's real weather (the app runs on a good 7-day forecast), from a month on the
# seasonal forecast ahead. Week: GRU-GBR +0.58 cm [+0.26, +0.89], clear. Month a tie (both
# highlighted); 6 months and year the GRU (6 months -8.5 [-21.4, +4.0] is NOT clear - the talk
# says "a little lower" there; the year -35.8 [-66.9, -8.6] is).
BEST = [{0}, {0, 1}, {1}, {1}]
# the model in use per column, outlined: the app's 7-day is the two-stage GBR, the fan the GRU
IN_USE = [0, 1, 1, 1]
TITLE = None                             # the show draws the slide title ("The errors", 18 Oct)
BELOW = "Prediction error (cm)"          # what the cells hold, under the table
STAR = "* weather known"                 # the week column's assumption, said aloud too


def draw(path: Path = OUT) -> Path:
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, T.W)
    ax.set_ylim(T.H, 0)                                          # pixel coordinates, y down
    ax.axis("off")

    name_x = 120
    type_x = 335
    col_x = [890, 1145, 1400, 1655]                              # column centres
    head_y, row_y0, row_h = 330, 520, 230
    cell_w, cell_h = 235, 160

    span_x = (col_x[0] + col_x[-1]) / 2
    if TITLE:
        T.title(fig, TITLE)
    ax.text(span_x, row_y0 + (len(MODELS) - 0.5) * row_h + 75, BELOW, ha="center", va="center",
            color=T.INK_2, fontproperties=T.font(True, 32))
    ax.text(name_x, row_y0 + (len(MODELS) - 0.5) * row_h + 75, STAR, ha="left", va="center",
            color=T.INK_2, fontproperties=T.font(False, 30))
    ax.text(type_x, head_y, "Model type", ha="left", va="center", color=T.INK_2, fontproperties=T.font(True, 32))
    for x, c in zip(col_x, COLUMNS):
        ax.text(x, head_y, c, ha="center", va="center", color=T.INK_2, fontproperties=T.font(True, 32))
    ax.plot([name_x, col_x[-1] + cell_w / 2], [head_y + 55] * 2, color=T.FAINT, lw=2)

    for r, (name, kind, cells) in enumerate(MODELS):
        y = row_y0 + r * row_h
        T.text_centered(ax, name_x, y, name, 50, True, T.INK, ha="left")
        T.text_centered(ax, type_x, y, kind, 32, False, T.INK, ha="left")
        for c, (x, v) in enumerate(zip(col_x, cells)):
            best = r in BEST[c]
            if best:
                ax.add_patch(FancyBboxPatch((x - cell_w / 2, y - cell_h / 2), cell_w, cell_h,
                                            boxstyle="round,pad=0,rounding_size=30",
                                            facecolor=T.USED_SOFT, edgecolor="none", zorder=1))
            if IN_USE[c] == r:
                ax.add_patch(FancyBboxPatch((x - cell_w / 2, y - cell_h / 2), cell_w, cell_h,
                                            boxstyle="round,pad=0,rounding_size=30", facecolor="none",
                                            edgecolor=T.USED, linewidth=5, zorder=3))
            T.text_centered(ax, x, y, v, 62, best, T.INK, zorder=2)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
