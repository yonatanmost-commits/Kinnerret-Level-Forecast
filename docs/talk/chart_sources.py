"""
chart_sources.py - slide 5, "What data did we use?": one bar per source on a shared timeline.

Colour = the years the forecast uses; grey = the record exists but the model doesn't read it;
light teal = used to check, not to train: the seasonal forecast's 1993+ issues (they set its own
"normal") and Tzemach's rain from the 1998-99 winter (it scores Copernicus on slide 6).
Only the four sources the final model reads are drawn (a Row with used_from=None would draw as
a dashed "tested" outline). A dashed red line marks the cut, where the gold table starts (every
weather input measured at Tzemach). An amber outline on the weather bar is 2023, the year the
Lev Kinneret rain gauge was offline and the old cleaning wrote zeros; the gold table now takes
rain from Tzemach, unbroken through 2023. Each agency's logo sits at the end of its bar; the
Copernicus logo is the programme's own (climate.copernicus.eu/branding-guidelines), ECMWF's is
link-only under its terms, so it is not used.

No small text on the slide (originator, 2026-10-17): the amber and light-teal marks are
explained aloud, and the licence line "Copernicus Climate Change Service information, 2026"
lives on the closing credits slide.

Dates are read from the committed silver/gold files at draw time.

Run:  python docs/talk/chart_sources.py      # -> charts/sources_timeline.png, 1920 x 1080
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import pandas as pd                                                  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage         # noqa: E402
from matplotlib.patches import FancyBboxPatch                        # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402
from compose_sources import load as load_logo                        # noqa: E402

OUT = HERE / "charts" / "sources_timeline.png"
SILVER = ROOT / "Silver Data"
GOLD = ROOT / "Gold Data" / "kinneret_gold_features.csv"
TEST_FIRST, TEST_LAST = 2011, 2025          # the final run's walk-forward test years (model-coach)
LOGO_H = {"ims_logo.svg": 84, "copernicus_logo.png": 62}   # px before the 0.55 zoom; others 120


def first_date(path: Path, column: str, date_col: str = "date") -> date:
    s = pd.read_csv(path, usecols=[date_col, column], parse_dates=[date_col]).dropna()
    return s[date_col].min().date()


def last_date(path: Path, date_col: str = "date") -> date:
    return pd.read_csv(path, usecols=[date_col], parse_dates=[date_col])[date_col].max().date()


@dataclass
class Row:
    name: str                       # what it is, in plain words
    detail: str                     # who / which station, smaller
    start: date                     # first day on record
    end: date
    used_from: date | None          # None = tested only
    logo: str | None = None         # file in images/logos, or None
    logo_text: str | None = None    # text stand-in when there is no logo
    notches: list = field(default_factory=list)   # (start, end): a past fault, now fixed
    support: date | None = None     # from here to used_from: a supporting role (used to check, not train)


def rows() -> tuple[list[Row], date]:
    cut = first_date(GOLD, "level_m")                                   # gold's first row
    end = last_date(GOLD)
    met = SILVER / "Meteorological" / "met_data_daily_clean.csv"
    seas5_first = min(int(p.stem.split("_")[1]) for p in (ROOT / "Raw Data" / "SEAS5").glob("seas5_*.nc"))
    return [
        Row("Lake level", "daily", first_date(SILVER / "Kinneret Level" / "kinneret_level.csv",
            "kinneret_level"), end, cut, logo="kinneret_drainage_logo.png"),
        Row("River Jordan", "Obstacle Bridge", first_date(
            SILVER / "Jordan River Silver" / "jordan_river_daily_flow_clean.csv",
            "JORDAN - OBSTACLE BRIDGE", "Date"), end, cut, logo="hydro_logo.png"),
        Row("Weather stations", "Tzemach and four more", first_date(met, "tzamach_global_radiation_MJm2"),
            end, cut, logo="ims_logo.svg", notches=[(date(2023, 1, 1), date(2023, 12, 31))],
            support=date(1998, 10, 1)),   # Tzemach rain from the 1998-99 winter checks SEAS5 (chart_seas5)
        Row("Seasonal forecast", "SEAS5", date(seas5_first, 1, 1), end, cut,
            support=date(seas5_first, 1, 1),   # its own track record: 1993+ issues set SEAS5's "normal"
            logo="copernicus_logo.png"),
    ], cut


def yr(d: date) -> float:
    return d.year + (d.timetuple().tm_yday - 1) / 365.25


def draw(path: Path = OUT) -> Path:
    data, cut = rows()
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    # leave the top band for the slide's own question; the chart owns the rest
    ax = fig.add_axes([0.29, 0.13, 0.575, 0.62], facecolor=T.SURFACE)   # its top labels under the title rule
    x0, x1 = 1959, 2027.5
    ax.set_xlim(x0, x1)
    ys = [len(data) - i for i in range(len(data))]
    ax.set_ylim(min(ys) - 0.6, max(ys) + 0.6)
    bar_h = 0.46

    def bar(y, a, b, face, edge=None, ls="-"):
        ax.add_patch(FancyBboxPatch((a, y - bar_h / 2), b - a, bar_h,
                                    boxstyle="round,pad=0,rounding_size=0.12", mutation_aspect=1 / 6,
                                    facecolor=face, edgecolor=edge or face, linewidth=2, linestyle=ls))

    L = T.Labels()                                               # row names and the two notes are native text
    for i, (r, y) in enumerate(zip(data, ys), 1):
        s, e = yr(r.start), yr(r.end)
        if r.used_from is None:
            bar(y, s, e, T.SURFACE, edge=T.FAINT, ls=(0, (4, 3)))
        else:
            u = yr(r.used_from)
            v = max(s, yr(r.support)) if r.support else u        # where the supporting stretch starts
            if v > s:
                bar(y, s, v, T.UNUSED)
            if u > v:
                bar(y, v, u, T.USED_SOFT)
            bar(y, max(s, u), e, T.USED)
        # a past fault, in outline: the bar stays whole because the data is whole now
        for a, b in r.notches:
            ax.add_patch(plt.Rectangle((yr(a), y - bar_h / 2 - 0.08), yr(b) - yr(a), bar_h + 0.16,
                                       facecolor="none", edgecolor=T.AMBER, linewidth=2.6, zorder=4))
        # the first year on record, quietly, at the bar's left end
        ax.text(s - 0.6, y, str(r.start.year), ha="right", va="center", color=T.INK_2,
                fontproperties=T.font(False, 26))
        # row name and detail, left of the axis
        fig_y = ax.transData.transform((0, y))[1] / T.H
        col = T.INK if r.used_from else T.INK_2
        L.text(fig, f"row.{i}", 0.275, fig_y + 0.012, r.name, 30 if r.used_from else 23, True, col,
               ha="right", va="bottom")                         # 30: the longest clears the margin
        L.text(fig, f"row.{i}.sub", 0.275, fig_y + 0.004, r.detail, 27, False, T.INK_2, ha="right", va="top")
        # logo (or its text stand-in) just past the bar's end
        if r.logo:
            img = load_logo(r.logo, LOGO_H.get(r.logo, 120))
            ab = AnnotationBbox(OffsetImage(img, zoom=0.55), (x1 + 0.4, y), xycoords="data",
                                box_alignment=(0, 0.5), frameon=False, annotation_clip=False)
            ax.add_artist(ab)
        elif r.logo_text:
            ax.text(x1 + 0.6, y, r.logo_text, ha="left", va="center", color=T.INK_2,
                    fontproperties=T.font(r.used_from is not None, 22), linespacing=1.0)

    # the walk-forward test years: each one trained only on the years before it
    yb = max(ys) + 0.62
    ax.plot([TEST_FIRST, TEST_FIRST, TEST_LAST + 1, TEST_LAST + 1], [yb - 0.12, yb, yb, yb - 0.12],
            color=T.INK_2, lw=1.6, clip_on=False)
    L.text(ax, "test_years", (TEST_FIRST + TEST_LAST + 1) / 2, yb + 0.06, f"test years {TEST_FIRST}–{TEST_LAST}",
           26, False, T.INK_2, ha="center", va="bottom", clip_on=False)

    # the cut: from here on every input is measured
    xc = yr(cut)
    ax.axvline(xc, color=T.RED, lw=2.4, ls=(0, (5, 4)), zorder=3)
    L.text(ax, "models_start", xc - 0.5, max(ys) + 0.55, "models start · " + cut.strftime("%B %Y"), 28, True, T.RED,
           ha="right", va="bottom")

    ax.set_yticks([])
    ax.set_xticks(range(1970, 2030, 10))
    ax.tick_params(axis="x", length=0, pad=10, colors=T.INK_2)
    for lab in ax.get_xticklabels():
        lab.set_fontproperties(T.font(False, 26))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(T.FAINT)
    for x in range(1970, 2030, 10):
        ax.axvline(x, color=T.UNUSED, lw=1, zorder=0)

    L.save(fig, path)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    draw()
