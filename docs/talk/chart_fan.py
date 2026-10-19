"""
chart_fan.py - two slides about the long-range forecast, both from the shipped GRU fan.

  track   "Why should we believe it?": every autumn the fan could be tested, 2014-2025. A bar is
          the 80% range forecast in October for a year later; the dot is where the lake was.
          Inside = a hit (teal); outside = a miss (hollow red). 2018-19 and 2024-25 named.
          Source: docs/experiments/cfc_fan_eval/track_record.csv (12-month columns; the first
          three test years, 2011-13, had no range yet and are left out).
  fan     "So which winter is coming?" (slide 11): the fan from 15 Oct 2026 out to 12 months -
          nested 50/80/90% bands and the most-likely line (exactly the app's page 10), wet / normal
          / dry groups of past winters with their SEAS5 chances, thin grey replays of every past
          winter, the red line, today's dot. Source: docs/talk/data/slide11_fan.csv + _meta.json
          (model-coach, from Models/longrange_fan.json). The track chart is now Q&A backup.

Run:  python docs/talk/chart_fan.py          # -> charts/fan_track.png and charts/fan_today.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import pandas as pd                                                  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

TRACK = ROOT / "docs" / "experiments" / "cfc_fan_eval" / "track_record.csv"
FAN = ROOT / "Models" / "longrange_fan.json"
ENS = ROOT / "docs" / "experiments" / "cfc_today_monthly" / "B14gru_s3_ens.json"
FAN11 = HERE / "data" / "slide11_fan.csv"              # model-coach, from Models/longrange_fan.json
FAN11_META = HERE / "data" / "slide11_fan_meta.json"   # (built by data/slide11_fan_build.py)
FAN11_DOTS = HERE / "data" / "slide11_dots.csv"         # monthly most-likely dots + model error bars
FAN11_CROSS = HERE / "data" / "slide11_crossings.json"  # red-line crossing dates (interpolated)
RED_LINE = -213.0
QR = HERE / "images" / "qr.png"                         # the live app (make_images.py)
CREDIT = "Copernicus Climate Change Service information, 2026"   # its licence wants it in the deck
NAMED = {2018: ("2018–19", T.GOOD), 2024: ("2024–25", T.BAD)}       # the lake animation's colours


def style(ax):
    ax.tick_params(length=0, pad=10, colors=T.INK_2)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontproperties(T.font(False, 26))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(T.FAINT)


def draw_track(path: Path = HERE / "charts" / "fan_track.png") -> Path:
    t = pd.read_csv(TRACK)
    t = t[t["fan"]].set_index("autumn")
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0.10, 0.13, 0.84, 0.64], facecolor=T.SURFACE)
    for y, r in t.iterrows():
        ax.vlines(y, r["12m_lo80"], r["12m_hi80"], color=T.UNUSED, lw=30, capstyle="round", zorder=1)
        hit = bool(r["12m_inside80"])
        col = NAMED.get(y, (None, T.USED))[1] if hit else T.RED
        ax.plot([y], [r["12m_actual"]], "o", ms=22, zorder=3,
                mfc=col if hit else T.SURFACE, mec=col, mew=0 if hit else 5)
        if y in NAMED:
            label, c = NAMED[y]
            ax.text(y, max(r["12m_hi80"], r["12m_actual"]) + 0.35, label, ha="center", va="bottom",
                    color=c, fontproperties=T.font(True, 30))
    n, hits = len(t), int(t["12m_inside80"].sum())
    ax.text(t.index.max() + 0.6, -215.6, f"{hits} of {n} inside", ha="right", va="center",
            color=T.INK, fontproperties=T.font(True, 34))
    ax.set_xlim(t.index.min() - 0.7, t.index.max() + 0.7)
    ax.set_ylim(-216.2, -207.5)
    ax.set_xticks(list(t.index))
    ax.set_xticklabels([f"{y % 100:02d}" for y in t.index])      # autumn of the forecast
    ax.set_yticks([-215, -213, -211, -209])
    ax.set_yticklabels(["−215 m", "−213 m", "−211 m", "−209 m"])
    style(ax)
    # legend in words, large: the bar and the two dot kinds, top right (title spot stays empty)
    lg = fig.add_axes([0.55, 0.82, 0.42, 0.15])
    lg.set_xlim(0, 1)
    lg.set_ylim(0, 1)
    lg.axis("off")
    lg.plot([0.03, 0.03], [0.55, 0.95], color=T.UNUSED, lw=26, solid_capstyle="round")
    lg.text(0.08, 0.75, "October's forecast, a year ahead", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(False, 28))
    lg.plot([0.03], [0.18], "o", ms=18, color=T.USED)
    lg.text(0.08, 0.18, "where the lake was", ha="left", va="center", color=T.INK,
            fontproperties=T.font(True, 28))
    return save(fig, path)


def _smooth(dates, values, n=400):
    """Monotone cubic (PCHIP) through the points: no overshoot, passes exactly through the data."""
    import matplotlib.dates as mdates
    import numpy as np
    from scipy.interpolate import PchipInterpolator
    x = mdates.date2num(pd.to_datetime(pd.Series(dates)))
    v = pd.Series(values).to_numpy(dtype=float)
    ok = ~np.isnan(v)
    xs = np.linspace(x[ok][0], x[ok][-1], n)
    return mdates.num2date(xs), PchipInterpolator(x[ok], v[ok])(xs)


def lake_outline():
    """The app's lake outline (kinneret_app/app_utils.build_lake_svg), as points in level units:
    x in the SVG's units, y mapped like the app's gauge (the outline's bottom = the all-time low,
    its top = the all-time high). Returns (x, level, x-units per metre)."""
    import re
    import numpy as np
    sys.path.insert(0, str(ROOT / "kinneret_app"))
    from app_utils import LEVEL_MAX, LEVEL_MIN, build_lake_svg
    d = re.search(r'<path d="([^"]+)"', build_lake_svg(-213.0)).group(1)
    tok = re.findall(r"[mcz]|-?[0-9]*[.]?[0-9]+(?:e-?[0-9]+)?", d)
    pos, pts, cmd, nums = np.zeros(2), [], None, []
    for k in tok + ["z"]:
        if k in "mcz":
            cmd, nums = k, []
            continue
        nums.append(float(k))
        if cmd == "m" and len(nums) == 2:
            pos = pos + nums
            pts.append(pos.copy())
            nums = []
        elif cmd == "c" and len(nums) == 6:
            p0, p1, p2, p3 = pos, pos + nums[0:2], pos + nums[2:4], pos + nums[4:6]
            for s in np.linspace(0, 1, 9)[1:]:
                pts.append((1 - s) ** 3 * p0 + 3 * (1 - s) ** 2 * s * p1 + 3 * (1 - s) * s ** 2 * p2 + s ** 3 * p3)
            pos, nums = p3, []
    pts = np.array(pts)
    top, bottom = pts[:, 1].min(), pts[:, 1].max()
    level = LEVEL_MIN + (bottom - pts[:, 1]) / (bottom - top) * (LEVEL_MAX - LEVEL_MIN)
    return pts[:, 0], level, (bottom - top) / (LEVEL_MAX - LEVEL_MIN)


def lake_range(fig, box, lo, hi, mid, red):
    """The lake next autumn: the app's outline with the 80% range across it (teal above the red
    line, red below, as on the fan) and the most likely level as a dark line."""
    import numpy as np
    from matplotlib.patches import Polygon, Rectangle
    x, lvl, units = lake_outline()
    ax = fig.add_axes(box, facecolor="none", zorder=3)
    ax.set_xlim(x.min() - 2, x.max() + 2)
    ax.set_ylim(lvl.min() - 0.05, lvl.max() + 0.05)
    ax.set_aspect(units, anchor="C")
    ax.axis("off")
    lake = Polygon(np.c_[x, lvl], closed=True, fc=T.UNUSED, ec="none", zorder=1)
    ax.add_patch(lake)
    w = x.max() - x.min() + 4
    for y0, y1, colour, a in ((max(lo, red), hi, T.USED, 0.55), (lo, min(hi, red), T.RED, 0.40)):
        if y1 > y0:
            r = Rectangle((x.min() - 2, y0), w, y1 - y0, fc=colour, alpha=a, ec="none", zorder=2)
            ax.add_patch(r)
            r.set_clip_path(lake)
    for y, colour, ls, lw in ((red, T.RED, (0, (5, 4)), 2.5), (mid, T.INK, "-", 4)):
        line, = ax.plot([x.min() - 2, x.max() + 2], [y, y], color=colour, ls=ls, lw=lw, zorder=3)
        line.set_clip_path(lake)
    ax.plot(x, lvl, color=T.USED, lw=3, zorder=4)
    return ax


def draw_fan(frame: int = 4, path: Path | None = None) -> Path:
    """Slide 11, a four-click build-up on fixed axes (v4: script peer + model-coach, 2026-10-17).
    Smoothed with PCHIP (no overshoot; dots on the real points); ONE band, the 80% range (the best
    tested). 1 today + red line + a line per past winter; 2 + the 80% band, "8 in 10" (replays
    fade); 3 + a dot a month for the most likely level ("+1 m" at 12 months), the green ~23 Feb
    crossing, wet / dry with their chances, the red ~14 Jun (dry falls back under); 4 the band's
    part under the red line turns red, "1 in 3: still below the red line, Oct 2027", and "misses:
    mostly up here" on the top edge (12 months: 16% above the top, 7% below the bottom).
    Cut vs v3: 50/90% bands, error bars, the average winter, the on-chart 2018 callout."""
    import numpy as np
    path = path or HERE / "charts" / f"fan_today_{frame}.png"
    t = pd.read_csv(FAN11, parse_dates=["date"])
    dots = pd.read_csv(FAN11_DOTS, parse_dates=["date"])
    meta = json.loads(FAN11_META.read_text())
    cross = json.loads(FAN11_CROSS.read_text())["crossings"]
    d, red, last, m12 = t["date"], meta["red_line"], t.iloc[-1], dots.iloc[-1]
    endx = d.iloc[-1] + pd.Timedelta(days=10)
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0.10, 0.13, 0.70, 0.70], facecolor=T.SURFACE)
    S = {c: _smooth(d, t[c]) for c in t.columns if c not in ("H", "date")}
    xs, lo, hi = S["lo_80"][0], S["lo_80"][1], S["hi_80"][1]
    at = lambda day: int(np.argmin(np.abs(np.array([x.timestamp() for x in xs]) - pd.Timestamp(day).timestamp())))

    def right(y, words, colour, bold=True, size=28):
        ax.text(endx, y, words, ha="left", va="center", color=colour, fontproperties=T.font(bold, size))

    def mark(day, colour):
        ax.plot([pd.Timestamp(day)], [red], "o", ms=18, color=colour, mec=T.SURFACE, mew=2.5, zorder=7)

    def date_label(day, dx_days):
        x = pd.Timestamp(day)
        ax.text(x + pd.Timedelta(days=dx_days), red - 0.30, "~" + x.strftime("%d %b").lstrip("0"),
                ha="center", va="top", color=T.INK, fontproperties=T.font(True, 26), zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", fc=T.SURFACE, ec="none", alpha=0.85))

    if frame <= 2:                                               # past winters, only while they explain
        for c in [c for c in S if c.startswith("winter_")]:
            ax.plot(*S[c], color=T.FAINT, lw=1.6, alpha=0.95 if frame == 1 else 0.55, zorder=2)
    ax.axhline(red, color=T.RED, lw=2.5, ls=(0, (6, 5)), zorder=2)
    ax.text(d.iloc[0] + pd.Timedelta(days=4), red + 0.12, "red line", ha="left", va="bottom",
            color=T.RED, fontproperties=T.font(True, 28))
    ax.plot([d.iloc[0]], [meta["level0"]], "o", ms=20, color=T.INK, zorder=6)
    ax.text(d.iloc[0] + pd.Timedelta(days=10), meta["level0"] - 0.3, "today", ha="left", va="top",
            color=T.INK, fontproperties=T.font(True, 30))
    if frame >= 2:                                               # the 80% range; from 4 its part under the line is red
        if frame >= 4:
            ax.fill_between(xs, np.maximum(lo, red), hi, where=hi > red, color=T.USED, alpha=0.30, lw=0, zorder=1)
            ax.fill_between(xs, lo, np.minimum(hi, red), where=lo < red, color=T.RED, alpha=0.22, lw=0, zorder=1)
        else:
            ax.fill_between(xs, lo, hi, color=T.USED, alpha=0.30, lw=0, zorder=1)
        k = at("2027-08-15")
        ax.text(xs[k], hi[k] - 0.12, "8 in 10", ha="center", va="top", color=T.INK,
                fontproperties=T.font(True, 32), zorder=6)
    if frame >= 3:
        ax.plot(dots["date"], dots["median"], "o", ms=16, color=T.INK, zorder=5)
        rise = m12["median"] - meta["level0"]                    # +1.1 m by Oct 2027
        right(m12["median"], f"+{rise:.0f} m", T.INK, size=36)
        mark(cross["median"][0]["date"], T.GOOD)
        date_label(cross["median"][0]["date"], 22)
        for col, word, colour, dy in (("wet_group", "wet", T.GOOD, 0.0), ("dry_group", "dry", T.BAD, 0.08)):
            ax.plot(*S[col], color=colour, lw=4.5, zorder=3)
            right(last[col] + dy, f"{word}  {round(meta['groups'][word]['chance_seas5'] * 100)}%", colour)
        down = [c for c in cross["dry_group"] if c["direction"] == "down"][0]["date"]
        mark(down, T.RED)
        date_label(down, 0)
    if frame >= 4:
        ax.text(pd.Timestamp("2027-05-01"), -214.6,
                f"{round(last['p_red'] * 3)} in 3: still below the red line, Oct 2027",
                ha="center", va="center", color=T.RED, fontproperties=T.font(True, 32), zorder=8)
        k = at("2027-06-20")
        y0 = hi[k] + 0.10
        ax.annotate("", xy=(xs[k], y0 + 0.6), xytext=(xs[k], y0), annotation_clip=False,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.8,head_width=0.45", color=T.AMBER, lw=3.5))
        ax.text(xs[k] + pd.Timedelta(days=12), y0 + 0.35, "misses: mostly up here", ha="left",
                va="center", color=T.AMBER, fontproperties=T.font(True, 28), zorder=8)
        # the lake itself next autumn, in the empty sky top left (originator, 18 Oct)
        # on its own card, so nobody reads it against the chart's axis (its scale is the app's gauge)
        from matplotlib.patches import FancyBboxPatch
        card = [0.135, 0.46, 0.165, 0.39]
        fig.patches.append(FancyBboxPatch((card[0], card[1]), card[2], card[3], transform=fig.transFigure,
                                          boxstyle="round,pad=0.006,rounding_size=0.015", fc="white",
                                          ec=T.FAINT, lw=1.5, zorder=0))
        fig.text(card[0] + card[2] / 2, card[1] + card[3] - 0.04, "next autumn", ha="center", va="center",
                 color=T.INK, fontproperties=T.font(True, 30))
        lake_range(fig, [card[0] + 0.02, card[1] + 0.02, card[2] - 0.04, card[3] - 0.10],
                   last["lo_80"], last["hi_80"], m12["median"], red)

    ax.set_xlim(d.iloc[0] - pd.Timedelta(days=12), d.iloc[-1] + pd.Timedelta(days=6))
    ax.set_ylim(-215.2, -208.5)
    ticks = [d.iloc[0] + pd.DateOffset(months=m) for m in (0, 3, 6, 9, 12)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([x.strftime("%b %Y") if x.month == 10 else x.strftime("%b") for x in ticks])
    ax.set_yticks([-215, -214, -213, -212, -211, -210, -209])
    ax.set_yticklabels([f"−{abs(v)} m" for v in (-215, -214, -213, -212, -211, -210, -209)])
    style(ax)
    fig.text(0.95, 0.90, "example run  ·  from the lake on 15 Oct 2026  ·  October seasonal forecast", ha="right",
             va="center", color=T.INK_2, fontproperties=T.font(False, 28))
    if frame >= 4:                                               # the last frame of the talk (the takeaway slide is gone)
        from PIL import Image
        qr = fig.add_axes([0.865, 0.615, 0.085, 0.085 * T.W / T.H])   # top right, clear of the band and labels
        qr.imshow(Image.open(QR))
        qr.axis("off")
        fig.text(0.9075, 0.605, "Between Flood\n& Drought", ha="center", va="top", color=T.INK,
                 fontproperties=T.font(True, 19), linespacing=1.1)
        fig.text(0.10, 0.03, CREDIT, ha="left", va="center", color=T.INK_2, fontproperties=T.font(False, 20))
    return save(fig, path)


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


if __name__ == "__main__":
    import shutil
    draw_track()                                                 # Q&A backup
    for n in range(1, 5):
        draw_fan(n)
    shutil.copyfile(HERE / "charts" / "fan_today_4.png", HERE / "charts" / "fan_today.png")   # = frame 4
