"""
chart_seas5.py - Copernicus itself: its past seasonal rain forecasts against the rain that fell.

The limiting factor of any season-ahead lake forecast is the seasonal rain forecast. For each
winter (Oct-Mar) the chart shows Copernicus SEAS5's October forecast of the season's rain, as %
of its own normal (its ensemble mean), and the rain that actually fell, from the gold table the product reads (Tzemach-first), as % of
its own normal. The two winters the talk
opens with keep their rain dots in the lake animation's colours: 2018-19 (wet) and 2024-25 (dry),
findable when pointed at but not labelled. The last column is this winter (2026-27): its October
forecast, bolder, no actual yet. No ranges and no legend box (originator, v3): the hollow
forecast dots hug normal while the rain swings; the two dot types are named on the first winter.

Season ratio, as the product builds it (Automation/seas5.py, season_calibrate): the rain-weighted
mean of the monthly ratios, weights = the normal monthly rain. Each SEAS5 month is measured
against SEAS5's ensemble-mean normal for that lead; each observed month against its own normal.
Descriptive chart, so both normals use all years (the product uses only earlier years).
seasons() still returns SEAS5's RAW member 10th-90th percentiles (lo, hi), not drawn; the product does not use them (it weights past winters
by SEAS5 with a shrunk slope, which is why the fan's 80% holds 77-84%).
Skill (confirmed by model-coach 2026-10-17): October issue, 1998-99..2025-26 (n=27; 2000-01 has
no actual, March incomplete), normals from all years: Spearman 0.52, Pearson 0.57; the actual
falls inside the raw 80% range in 67% of winters. Pre-2002 Tzemach rain checked against ERA5
(daily r 0.76, monthly 0.91, totals 0.97, no phantom rain) - the same as after 2002.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import numpy as np                                                   # noqa: E402
import pandas as pd                                                  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import theme as T                                                    # noqa: E402

OUT = HERE / "charts" / "seas5_vs_rain.png"
SEAS5 = ROOT / "Raw Data" / "SEAS5"
GOLD = ROOT / "Gold Data" / "kinneret_gold_features.csv"
MET = ROOT / "Silver Data" / "Meteorological" / "met_data_daily_clean.csv"
FIRST = 1998                       # Tzemach's rain record starts 1998-02: first full winter 1998-99
ISSUE_MONTH = 10                   # the October issue (out on the 5th) for an autumn start
HIGHLIGHT = {2018: ("2018–19", T.GOOD), 2024: ("2024–25", T.BAD)}   # lake animation colours


def seasons() -> pd.DataFrame:
    """One row per winter: SEAS5 member mean and 10th/90th percentile, and the actual, as ratios."""
    import xarray as xr
    rows = []
    for p in sorted(SEAS5.glob("seas5_*.nc")):
        m = xr.open_dataset(p)["tprate"].mean(dim=["latitude", "longitude"])
        inits = [t for t in m.forecast_reference_time.values if pd.Timestamp(t).month == ISSUE_MONTH]
        if inits:
            rows.append(m.sel(forecast_reference_time=inits).to_dataframe().reset_index().dropna())
    f = pd.concat(rows)
    f["year"] = pd.to_datetime(f["forecast_reference_time"]).dt.year
    f["mm"] = f["tprate"] * 86400 * 1000
    normal_fc = f.groupby(["year", "forecastMonth"])["mm"].mean().groupby("forecastMonth").mean()
    f["ratio"] = f["mm"] / f["forecastMonth"].map(normal_fc)

    # the gold table (what the product reads) from July 2002; before it, the same Tzemach gauge
    # from the silver table (identical to gold on every day after 2002) - used to check, not train
    gold = pd.read_csv(GOLD, usecols=["date", "rainfall_mm"], parse_dates=["date"]).set_index("date")
    silver = pd.read_csv(MET, usecols=["date", "tzamach_rainfall_mm_sum"], parse_dates=["date"]).set_index("date")
    rain = gold["rainfall_mm"].combine_first(silver["tzamach_rainfall_mm_sum"])
    month = rain.resample("MS").sum(min_count=20)
    normal = month.groupby(month.index.month).mean()
    months = [10, 11, 12, 1, 2, 3]                                 # leads 1..6 of an October issue
    w = dict(zip(range(1, 7), normal.reindex(months).to_numpy()))
    f["w"] = f["forecastMonth"].map(w)

    member = f.groupby(["year", "number"]).apply(
        lambda g: (g["ratio"] * g["w"]).sum() / g["w"].sum(), include_groups=False)
    out = member.groupby("year").agg(fc="mean", lo=lambda s: s.quantile(0.1),
                                     hi=lambda s: s.quantile(0.9))
    wv = np.array([w[k] for k in range(1, 7)])
    actual = {}
    for y in out.index:
        idx = pd.date_range(f"{y}-10-01", periods=6, freq="MS")
        v = month.reindex(idx)
        if v.notna().all():
            actual[y] = float((v.to_numpy() / normal.reindex(idx.month).to_numpy() * wv).sum() / wv.sum())
    out["obs"] = pd.Series(actual)
    return out[(out.index >= FIRST) & (out.index <= month.index.max().year)]   # last = this winter, no actual yet


def draw(path: Path = OUT) -> Path:
    d = seasons() * 100
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0.09, 0.13, 0.86, 0.68], facecolor=T.SURFACE)   # top band: the title spot
    x = d.index.to_numpy()
    past, now = x[:-1], x[-1]                                  # the last column is this winter
    ax.plot([x[0] - 0.8, x[-1] + 0.6], [100, 100], color=T.FAINT, lw=2, ls=(0, (6, 5)), zorder=1)
    ax.text(x[-1] + 0.9, 100, "normal", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(False, 26))
    ax.plot(past, d.loc[past, "fc"], "o", ms=16, mfc=T.SURFACE, mec=T.INK_2, mew=3.5, zorder=3)
    for y, v in d["obs"].dropna().items():
        col = HIGHLIGHT.get(y, (None, T.USED))[1]
        ax.plot([y], [v], "o", ms={2018: 26, 2024: 22}.get(y, 16), color=col, zorder=4)
    ax.plot([now], [d.loc[now, "fc"]], "o", ms=22, mfc=T.SURFACE, mec=T.INK, mew=5.5, zorder=3)
    ax.plot([now, now], [d.loc[now, "fc"] + 4, d.loc[now, "fc"] + 19], color=T.INK, lw=2, zorder=3)
    ax.text(now, d.loc[now, "fc"] + 21, "this\nwinter", ha="center", va="bottom", color=T.INK,
            fontproperties=T.font(True, 30), linespacing=1.0)

    # the two dot types, named once, on the first winter (open space below and to its right)
    y0 = x[0]
    ax.text(y0 + 0.55, d.loc[y0, "obs"], "rain that fell", ha="left", va="center", color=T.USED,
            fontproperties=T.font(True, 30))
    ax.plot([y0 + 0.2, y0 + 0.5], [d.loc[y0, "fc"] - 3, 76], color=T.INK_2, lw=2)
    ax.text(y0 + 0.55, 73, "Copernicus\nforecast", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(True, 30), linespacing=1.0)

    # the test result, in the open sky over the middle years (Spearman 0.52, n=27, rounded)
    ax.text(2012, 170, "match with real rain: 0.5", ha="center", va="center", color=T.INK,
            fontproperties=T.font(True, 36))
    ax.text(2012, 158, "1 = perfect  ·  0 = guessing", ha="center", va="center", color=T.INK_2,
            fontproperties=T.font(False, 30))

    ax.set_xlim(x[0] - 0.8, x[-1] + 3.2)
    ax.set_ylim(45, 175)
    ax.set_yticks([50, 100, 150])
    ax.set_yticklabels(["50%", "100%", "150%"])
    ticks = [y for y in x if y % 4 == 2]                       # 1998-99, 2002-03 ... 2026-27
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{y}–{str(y + 1)[2:]}" for y in ticks])
    ax.tick_params(length=0, pad=10, colors=T.INK_2)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontproperties(T.font(False, 26))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(T.FAINT)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.relative_to(ROOT)} ({T.W} x {T.H})")
    return path


OURS = HERE / "data" / "seas5_ours.csv"        # model-coach, 2026-10-18 (fan11 weighting)
OUT_OURS = HERE / "charts" / "seas5_vs_rain_ours.png"


def draw_ours(path: Path = OUT_OURS) -> Path:
    """The same story with our calibrated season forecast added, 2007-08 .. 2026-27, every number
    from model-coach's seas5_ours.csv (each season fitted on earlier seasons only, as the fan's
    weighting is). Per winter: the plain-climate 80% range as a grey band, Copernicus as an open
    ring, ours as a teal dot with its 80% bar, the rain that fell as a dark dot on our bar.
    The first winters (to 2011-12, fitted on 5-9 seasons) are drawn lighter. Misses are points of
    a normal winter. Station rain, 19 winters: average miss ours 0.19, Copernicus 0.19, assume normal 0.22; inside
    our 80% 74% (14 of 19), inside the plain-climate 80% 79% (verified 2026-10-18)."""
    d = pd.read_csv(OURS)
    d["year"] = d["season"].str[:4].astype(int)
    d = d.set_index("year")[["copernicus", "ours", "ours_lo80", "ours_hi80", "normal_lo80",
                             "normal_hi80", "actual_station"]] * 100
    x = d.index.to_numpy()
    now = x[-1]
    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0.09, 0.20, 0.80, 0.58], facecolor=T.SURFACE)   # top: title spot + key

    xs = np.r_[x[0] - 0.5, np.repeat(x[1:] - 0.5, 2), x[-1] + 0.5]       # the band, step by winter
    ax.fill_between(xs, np.repeat(d["normal_lo80"], 2), np.repeat(d["normal_hi80"], 2),
                    color=T.UNUSED, lw=0, zorder=0)
    ax.plot([x[0] - 0.5, x[-1] + 0.5], [100, 100], color=T.FAINT, lw=2, ls=(0, (6, 5)), zorder=1)
    dx = 0.24                                                           # Copernicus sits left
    ax.plot(x - dx, d["copernicus"], "o", ms=13, mfc=T.SURFACE, mec=T.INK_2, mew=3, zorder=3)
    early = x <= 2011                                    # fitted on 5-9 seasons only: drawn lighter
    for sel, a in ((early, 0.4), (~early, 1.0)):
        ax.vlines(x[sel], d["ours_lo80"][sel], d["ours_hi80"][sel], color=T.USED, lw=4, alpha=a,
                  zorder=2)
        ax.plot(x[sel], d["ours"][sel], "o", ms=15, color=T.USED, alpha=a, zorder=3)
    for y, v in d["actual_station"].dropna().items():
        col = HIGHLIGHT.get(y, (None, T.INK))[1]
        ax.plot([y], [v], "D", ms={2018: 17, 2024: 15}.get(y, 11), color=col, zorder=4)
    ax.plot([now], [d.loc[now, "ours"]], "o", ms=22, mfc=T.USED, mec=T.INK, mew=4, zorder=4)
    ax.text(now, d.loc[now, "ours_hi80"] + 5, "this\nwinter", ha="center", va="bottom", color=T.INK,
            fontproperties=T.font(True, 30), linespacing=1.0)

    # the key, one line under the title spot (no box), and the honest result
    key_y = 0.83
    for kx, mark, kw, words, col in (
            (0.09, "D", dict(ms=13, color=T.INK), "rain that fell", T.INK),
            (0.31, "o", dict(ms=15, color=T.USED), "our forecast  ·  8 in 10 range", T.USED),
            (0.665, "o", dict(ms=13, mfc=T.SURFACE, mec=T.INK_2, mew=3), "Copernicus", T.INK_2)):
        fig.lines.append(plt.Line2D([kx + 0.008], [key_y], marker=mark, transform=fig.transFigure, **kw))
        fig.text(kx + 0.022, key_y, words, ha="left", va="center", color=col,
                 fontproperties=T.font(True, 28))
    lo, hi = d["normal_lo80"].iloc[-1], d["normal_hi80"].iloc[-1]   # a bracket on the band's edge
    bx = x[-1] + 0.62
    ax.plot([bx - 0.1, bx, bx, bx - 0.1], [hi, hi, lo, lo], color=T.INK_2, lw=2, zorder=1)
    ax.text(bx + 0.18, 122, "normal\nrange", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(False, 26), linespacing=1.0)
    ax.text(bx + 0.18, 100, "normal", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(False, 26))
    fig.text(0.09, 0.06, "average miss:  ours 19 pts  ·  Copernicus 19 pts  ·  assume normal 22 pts",
             ha="left", va="center", color=T.INK, fontproperties=T.font(True, 28))

    ax.set_xlim(x[0] - 0.8, x[-1] + 2.0)
    ax.set_ylim(35, 175)
    ax.set_yticks([50, 100, 150])
    ax.set_yticklabels(["50%", "100%", "150%"])
    ticks = [y for y in x if y % 4 == 2]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{y}–{str(y + 1)[2:]}" for y in ticks])
    ax.tick_params(length=0, pad=10, colors=T.INK_2)
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontproperties(T.font(False, 26))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(T.FAINT)

    fig.savefig(path, dpi=T.DPI, facecolor=T.SURFACE)
    plt.close(fig)
    print(f"saved {path.name}")
    return path


OUT_TRACK = HERE / "charts" / "seas5_track.png"
TRACK_FROM = 2012                  # first winter fitted on enough seasons (10+) to show unfaded
TRACK_STEPS = 4                    # the four clicks of slide 8


def draw_track(step: int = TRACK_STEPS, path: Path | None = None) -> Path:
    """Slide 8 v3 (originator, 2026-10-18): our way of reading Copernicus, built in four clicks on
    one axis. 1: Copernicus's lean per winter (hollow grey ring: its forecast against what it
    usually says, % of normal). 2: the rain that fell (dark dot) - it swings far wider than the
    rings. 3: our forecast, the lean stretched (bold teal dash: 1 + slope x lean, the slope fitted
    on the seasons before and shrunk by its own noise) - the centre the fan weighs past winters
    by. 4: our 8-in-10 range around it (the rounded grey bar); a rain dot outside turns into a
    hollow red ring, "9 of 14 inside". The dashed 100% line is the average winter, the
    no-forecast guess. This winter is the worked example, drawn larger; its rain is a "?".
    From seas5_ours.csv (model-coach), 2012-13 .. 2026-27; 9 of 14 inside (2013-14 out by 0.1
    point). Step 4 is the full chart (seas5_track.png); each step also as seas5_track_<n>.png.
    Honest scope: the scoreboard's "Copernicus ahead" runs feed the model the RAW lean; the dash
    is what weights the fan's past winters, not a model input."""
    from chart_fan import save, style
    path = path or (OUT_TRACK if step == TRACK_STEPS else OUT_TRACK.with_name(f"seas5_track_{step}.png"))
    d = pd.read_csv(OURS)
    d["year"] = d["season"].str[:4].astype(int)
    d = d[d["year"] >= TRACK_FROM].set_index("year")
    d[["copernicus", "ours", "ours_lo80", "ours_hi80", "actual_station"]] *= 100
    past = d[d["actual_station"].notna()]
    now = d.index.max()
    inside = (past["actual_station"] >= past["ours_lo80"]) & (past["actual_station"] <= past["ours_hi80"])
    rain, dash, bars = step >= 2, step >= 3, step >= 4

    fig = plt.figure(figsize=(T.W / T.DPI, T.H / T.DPI), dpi=T.DPI, facecolor=T.SURFACE)
    ax = fig.add_axes([0.10, 0.12, 0.80, 0.60], facecolor=T.SURFACE)   # under the two-row key
    ax.plot([d.index.min() - 0.7, now + 0.5], [100, 100], color=T.FAINT, lw=2, ls=(0, (6, 5)), zorder=0)
    ax.text(now + 0.62, 100, "average\nwinter", ha="left", va="center", color=T.INK_2,
            fontproperties=T.font(False, 26), linespacing=1.0)

    def column(y, r, now_col=False):
        if bars:
            ax.vlines(y, r["ours_lo80"], r["ours_hi80"], color=T.FAINT if now_col else T.UNUSED,
                      lw=40 if now_col else 30, capstyle="round", zorder=1)
        if dash:
            w = 0.30 if now_col else 0.22
            ax.plot([y - w, y + w], [r["ours"]] * 2, color=T.USED, lw=8 if now_col else 6,
                    solid_capstyle="round", zorder=3)
        ax.plot([y], [r["copernicus"]], "o", ms=18 if now_col else 14, mfc="none", mec=T.INK_2,
                mew=3.5 if now_col else 3, zorder=4)

    def top(r):                                  # labels sit where the full chart puts them: nothing jumps between clicks
        return max(r["ours_hi80"], r["actual_station"]) if pd.notna(r["actual_station"]) else r["ours_hi80"]

    for y, r in past.iterrows():
        column(y, r)
        if not rain:
            continue
        hit = bool(inside[y]) or not bars                        # misses are only named with the range
        ax.plot([y], [r["actual_station"]], "o", ms=20, zorder=5,
                mfc=T.INK if hit else T.SURFACE, mec=T.INK if hit else T.RED, mew=0 if hit else 5)
        if y in HIGHLIGHT:
            label, c = HIGHLIGHT[y]
            if r["actual_station"] < r["ours_lo80"]:                         # a dry winter: name it underneath
                ax.text(y, r["actual_station"] - 6, label, ha="center", va="top", color=c,
                        fontproperties=T.font(True, 30))
            else:
                ax.text(y, top(r) + 4, label, ha="center", va="bottom", color=c,
                        fontproperties=T.font(True, 30))
    r = d.loc[now]                                               # this winter, the worked example
    column(now, r, now_col=True)
    if bars:
        ax.text(now, r["ours_lo80"] + 12, "?", ha="center", va="center", color=T.SURFACE,
                fontproperties=T.font(True, 44))
        ax.text(now + 0.5, 26, f"{int(inside.sum())} of {len(past)} inside", ha="right", va="center",
                color=T.INK, fontproperties=T.font(True, 34))
    ax.text(now, top(r) + 5, "this\nwinter", ha="center", va="bottom", color=T.INK,
            fontproperties=T.font(True, 30), linespacing=1.0)

    ax.set_xlim(d.index.min() - 0.7, now + 1.9)
    ax.set_ylim(18, 172)
    ax.set_xticks(list(d.index))
    ax.set_xticklabels([f"{y % 100:02d}" for y in d.index])      # autumn the winter starts
    ax.set_yticks([50, 100, 150])
    ax.set_yticklabels(["50%", "100%", "150%"])
    style(ax)

    # legend under the title rule, two rows of two, one entry per click in click order; px, y down
    lg = fig.add_axes([0, 0, 1, 1], facecolor="none")
    lg.set_xlim(0, T.W)
    lg.set_ylim(T.H, 0)
    lg.axis("off")
    spots = [(T.MARGIN_X + 18, 205), (1120, 205), (T.MARGIN_X + 18, 255), (1120, 255)]
    marks = (lambda x, y: lg.plot([x], [y], "o", ms=16, mfc="none", mec=T.INK_2, mew=3.5),
             lambda x, y: lg.plot([x], [y], "o", ms=17, color=T.INK),
             lambda x, y: lg.plot([x - 16, x + 16], [y] * 2, color=T.USED, lw=7, solid_capstyle="round"),
             lambda x, y: lg.plot([x, x], [y - 18, y + 18], color=T.UNUSED, lw=24, solid_capstyle="round"))
    words = ("Copernicus: wetter or drier than it usually says", "the rain that fell",
             "our forecast: its lean, stretched", "our 8-in-10 range")
    for k, ((x, y), mark, w, col, bold) in enumerate(zip(spots, marks, words, (T.INK_2, T.INK, T.USED_TEXT, T.INK_2),
                                                         (False, True, True, False))):
        if k < step:
            mark(x, y)
            T.text_centered(lg, x + 34, y, w, 26, bold, col, ha="left")
    return save(fig, path)


if __name__ == "__main__":
    draw()
    draw_ours()
    for n in range(1, TRACK_STEPS + 1):
        draw_track(n)
