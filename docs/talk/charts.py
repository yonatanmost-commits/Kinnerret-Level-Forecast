"""
charts.py - The talk's five charts, drawn from the numbers ledger only (plan D9).

chart_data(name, ledger) returns exactly the values a chart plots; draw(name, ledger, path) plots
them. The truth tests (tests/test_talk_truth.py) check chart_data against the real sources, so
nothing reaches a chart except through it.

Look (plan D9/D10, dataviz skill, editorial - originator 2026-10-13): each chart states its point
as a headline, labels values directly, highlights one thing in teal and fades the rest; red is
kept for the red line. Chart text 20 pt and up, at slide size (13.33 x 7.5 in).

Run:  python docs/talk/charts.py          # draws every chart into docs/talk/charts/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER_PATH = HERE / "numbers_ledger.json"
OUT_DIR = HERE / "charts"

MODELS = ["baseline_gbr", "xgboost", "lgbm", "gru", "gbr_max_chain",
          "gbr_s1_direct_s2_anchor", "gbr_single_stage", "gbr_s1_chain_s2_roll1"]
MODEL_LABELS = {
    "baseline_gbr": "Two-stage boosting",
    "xgboost": "XGBoost",
    "lgbm": "LightGBM",
    "gru": "Neural network (GRU)",
    "gbr_max_chain": "Boosting, fully chained",
    "gbr_s1_direct_s2_anchor": "Boosting, direct",
    "gbr_single_stage": "Boosting, one stage",
    "gbr_s1_chain_s2_roll1": "Boosting, rolling",
}
BANDS = ["0_7", "7_14", "14_30", "30_60", "60_90", "90_120", "120_plus"]
BAND_LABELS = ["1-7", "8-14", "15-30", "31-60", "61-90", "91-120", ">120"]
BAND_SHORT = ["1 wk", "2 wk", "1 mo", "2 mo", "3 mo", "4 mo", "more"]   # the frontier's x-axis

# Short on-chart cause labels for the R² timeline, keyed by snapshot commit (the full cause
# stays in the ledger). The freeze point is keyed "freeze".
TIMELINE_SHORT = {
    "c3a72b3": "start",
    "ac2ede5": "Wade Storm:\nrain fix +\nsix fixes",
    "56d0555": "wetness\nmemory",
    "2da9bd7": "radiation\nrestored",
    "55d6a44": "newer data",
    "bae3e37": "quality filter\nskipped",
    "6b27d62": "quality filter\nrestored",
    "freeze": "data\nfreeze",
}

# Colours (dataviz six checks run 2026-10-13 on the warm surface: teal/ochre and teal/red pass,
# incl. colour-blind separation). Teal = the thing to look at; red = the red line only;
# ochre = the second category (a model change); everything else fades to MUTED.
SURFACE = "#fbfaf7"
INK = "#1d1d1b"
INK_2 = "#5f5d57"
MUTED = "#cfccc3"
GRID = "#ecebe6"
TEAL = "#009c8f"
OCHRE = "#c4831f"
RED = "#d6453d"


def load_ledger(path: Path = LEDGER_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _v(ledger, key):
    return ledger[key]["value"]


# ─── data ───────────────────────────────────────────────────────────────────

def chart_data(name: str, ledger: dict) -> dict:
    if name == "hook":
        return {
            "series": _v(ledger, "level.series"),
            "red_line_m": _v(ledger, "level.red_line_m"),
            "freeze_level_m": _v(ledger, "level.freeze_m"),
            "freeze_date": _v(ledger, "freeze_date"),
            "lowest_since_year": _v(ledger, "level.lowest_since_year"),
        }
    if name == "olympics":
        champ = _v(ledger, "champion.model")       # the best weekly mean (plan D19)
        return {"champion": champ,
                "points": [{"model": m, "label": MODEL_LABELS[m],
                            "r2": _v(ledger, f"olympics.{m}.r2_mean"),
                            "runtime_s": _v(ledger, f"olympics.{m}.runtime_s"),
                            "champion": m == champ} for m in MODELS]}
    if name == "timeline":
        hist = sorted(((e["date"], e["seq"]), k) for k, e in ledger.items()
                      if k.startswith("history.") and e["kind"] == "historical")
        hist = [(d, k) for (d, _), k in hist]
        pts = [{"key": k, "sha": ledger[k]["sha"], "date": d, "r2": ledger[k]["value"],
                "kind": "historical", "cause": ledger[k]["cause"],
                "cause_type": ledger[k]["cause_type"],
                "short": TIMELINE_SHORT.get(ledger[k]["sha"], ledger[k]["cause"])}
               for d, k in hist]
        # One yardstick throughout (plan D19): the history is the old champion scored one day at a
        # time, so it ends on that same score on the freeze, never on the weekly champion.
        c = ledger["history.freeze_day_ahead.r2"]
        pts.append({"key": "history.freeze_day_ahead.r2", "sha": None, "date": c["date"],
                    "r2": c["value"], "kind": "freeze", "cause": c["cause"],
                    "cause_type": c["cause_type"], "short": TIMELINE_SHORT["freeze"]})
        return {"points": pts, "note": c["note"]}
    if name == "one_week":
        return {"champion_r2": _v(ledger, "champion.r2"),
                "zero_change_r2": _v(ledger, "baseline.zero_change.r2")}
    if name == "frontier":
        pts = [{"group": "7d", "key": "champion.r2", "value": _v(ledger, "champion.r2"),
                "label": "1 week ahead: the champion, best case - if we knew the weather ahead"}]
        for season, word in (("wet", "winter"), ("dry", "summer")):
            k = f"frontier.{season}.temp_bucket_ss"
            pts.append({"group": "14_30d", "key": k, "value": _v(ledger, k), "season": season,
                        "label": f"{word}, best case - if we knew the weather ahead"})
        for method, label in (("scaled", "seasonal method, scaled to recent weeks - not machine learning"),
                              ("unscaled", "plain seasonal average")):
            for band, blabel in zip(BANDS, BAND_LABELS):
                k = f"crossing.paired.{method}.mae_{band}"   # only forecasts both brought to the line
                pts.append({"group": "summer", "key": k, "value": _v(ledger, k),
                            "method": method, "band": blabel, "label": label})
        return {"points": pts, "crossings": _v(ledger, "crossing.n"),
                "never_crossed": _v(ledger, "crossing.never_crossed"),
                "issued": _v(ledger, "crossing.issued"),
                "longrange_date": ledger["frontier.wet.temp_bucket_ss"]["date"]}
    raise KeyError(f"unknown chart {name!r}")


# ─── drawing ────────────────────────────────────────────────────────────────
# Editorial look (originator, 2026-10-13): every chart states its point as a headline, values are
# labelled directly instead of read off an axis, one element is highlighted and the rest fade.

HEADLINE_FONT = ["Georgia", "DejaVu Serif"]


def _style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "font.size": 20, "axes.titlesize": 22, "axes.labelsize": 20,
        "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "text.color": INK,
        "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": False, "grid.color": GRID, "grid.linewidth": 1,
        "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 10,
        "lines.linewidth": 2, "lines.solid_capstyle": "round",
    })
    return plt


def _fig(plt, headline: str, sub: str = "", w=13.33, h=7.0, top=0.80, **kw):
    """A figure with its takeaway as a headline, and a quieter line under it."""
    fig, ax = plt.subplots(figsize=(w, h), **kw)
    fig.text(0.035, 0.955, headline, fontfamily=HEADLINE_FONT, fontsize=32, fontweight="bold",
             color=INK, va="top")
    if sub:
        fig.text(0.035, 0.875, sub, fontsize=20, color=INK_2, va="top")
    fig.subplots_adjust(left=0.06, right=0.95, top=top, bottom=0.11)
    return fig, ax


def _dot(ax, x, y, color, size=13, z=5):
    ax.plot([x], [y], "o", color=color, markersize=size, markeredgecolor=SURFACE,
            markeredgewidth=2.5, zorder=z)


def _month(date: str) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(date)
    return f"{d.day} {d.strftime('%b')}"


def _runtime(seconds: float) -> str:
    return f"{seconds / 60:.0f} min" if seconds >= 90 else f"{seconds:.0f} s"


def _mix(a: str, b: str, t: float) -> str:
    """Hex colour a fraction t of the way from a to b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


MONTH_DOY = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]


def draw_hook(d, plt):
    """The app front page's year-over-year overlay (plan D18): earlier years faded, the freeze
    year highlighted and ending on the freeze date, the red line dashed. No level label: the
    speaker reads today's level from the app on the day."""
    import pandas as pd
    s = pd.DataFrame(d["series"], columns=["date", "level"])
    s["date"] = pd.to_datetime(s["date"])
    s["year"], s["doy"] = s["date"].dt.year, s["date"].dt.dayofyear
    fy = pd.Timestamp(d["freeze_date"]).year
    past = sorted(y for y in s["year"].unique() if y != fy)
    fig, ax = _fig(plt, f"{fy} is the lowest line on the chart",
                   f"Kinneret level through the year, in metres, {past[0]} to {fy}")

    ends = []
    for y in past:
        g = s[s["year"] == y]
        ax.plot(g["doy"], g["level"], color=MUTED, linewidth=2.2)
        ends.append([float(g["level"].iloc[-1]), str(y)])
    ax.axhline(d["red_line_m"], color=RED, linewidth=2.5, linestyle=(0, (6, 4)), zorder=3)
    ax.text(3, d["red_line_m"] + 0.07, "red line", color=RED, va="bottom", fontweight="bold")

    g = s[s["year"] == fy]
    ax.plot(g["doy"], g["level"], color=TEAL, linewidth=5, zorder=4)
    _dot(ax, g["doy"].iloc[-1], g["level"].iloc[-1], TEAL, size=15)
    ax.annotate(str(fy), (g["doy"].iloc[-1], g["level"].iloc[-1]), xytext=(16, -4),
                textcoords="offset points", color=TEAL, fontweight="bold", fontsize=24, va="top")

    lo, hi = s["level"].min(), s["level"].max()
    gap = (hi - lo) * 0.075                      # spread the year labels so none overlap
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    for yv, label in ends:
        ax.text(372, yv, label, color=INK_2, va="center")

    ax.set_xlim(1, 405)
    ax.set_ylim(lo - 0.3, max(hi, ends[-1][0]) + 0.2)
    ax.set_xticks(MONTH_DOY, ["Jan", "", "Mar", "", "May", "", "Jul", "", "Sep", "", "Nov", ""])
    ax.yaxis.grid(True)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}")
    return fig


def draw_olympics(d, plt):
    pts = sorted(d["points"], key=lambda p: p["r2"], reverse=True)
    fig, ax = _fig(plt, "Simple won. The neural network learned nothing.",
                   "Next-week forecasts, best case (the real weather) · 1 = perfect, 0 = average")
    fig.subplots_adjust(left=0.30, right=0.86)
    ys = range(len(pts))[::-1]
    for y, p in zip(ys, pts):
        col = TEAL if p["champion"] else MUTED
        ax.barh(y, p["r2"], color=col, height=0.62)
        txt_col = INK if (p["champion"] or p["model"] == "gru") else INK_2
        weight = "bold" if p["champion"] else "normal"
        ax.text(-0.02, y, p["label"], ha="right", va="center",
                color=txt_col, fontweight=weight)
        ax.text(max(p["r2"], 0) + 0.015, y, f"{p['r2']:.2f}", va="center", color=txt_col,
                fontweight=weight)
        ax.text(1.06, y, _runtime(p["runtime_s"]), va="center", ha="right", color=txt_col,
                fontweight=weight, transform=ax.get_yaxis_transform())
    ax.text(1.06, len(pts) - 0.35, "time", ha="right", va="bottom", color=INK_2,
            transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK_2, linewidth=1.2)
    ax.set_xlim(0, 0.9)
    ax.set_ylim(-0.6, len(pts) - 0.4)
    ax.set_xticks([]), ax.set_yticks([])
    ax.spines["bottom"].set_visible(False)
    return fig


def draw_timeline(d, plt):
    pts = d["points"]
    fig, ax = _fig(plt, "Most of the gain came from fixing data",
                   "The old champion's score, step by step, scored one day ahead")
    xs = list(range(len(pts)))
    ys = [p["r2"] for p in pts]
    ax.step(xs, ys, where="post", color=MUTED, linewidth=2.5, zorder=2)
    for x, p in zip(xs, pts):
        col = INK if p["kind"] == "freeze" else (TEAL if p["cause_type"] == "data" else OCHRE)
        _dot(ax, x, p["r2"], col, size=16 if x in (0, len(pts) - 1) else 13)
        prev = pts[x - 1]["r2"] if x else p["r2"] - 1
        if x and p["r2"] - prev > 0.03:            # a big jump: label it beside its riser
            ax.annotate(p["short"], (x, (p["r2"] + prev) / 2), xytext=(-16, 0),
                        textcoords="offset points", ha="right", va="center", color=INK,
                        linespacing=1.0)
            continue
        above = x and p["r2"] >= prev              # rises labelled above, drops (and start) below
        ax.annotate(p["short"], (x, p["r2"]), xytext=(0, 22 if above else -24),
                    textcoords="offset points", ha="center", va="bottom" if above else "top",
                    color=INK_2, linespacing=1.0)
    for x in (0, len(pts) - 1):                    # the two numbers that matter: start and now
        ax.annotate(f"{ys[x]:.2f}", (x, ys[x]), xytext=(-22 if x == 0 else 22, 0),
                    textcoords="offset points", ha="right" if x == 0 else "left", va="center",
                    fontsize=30, fontweight="bold", color=INK)
    seen, ticks = set(), []
    for p in pts:                                  # each date once
        m = _month(p["date"])
        ticks.append("" if m in seen else m)
        seen.add(m)
    ax.set_xticks(xs, ticks)
    ax.set_yticks([])
    ax.set_xlim(-0.9, len(pts) - 0.1)
    ax.set_ylim(min(ys) - 0.035, max(ys) + 0.035)
    for x0, col, name in ((0.66, TEAL, "data fix"), (0.79, OCHRE, "model change")):
        fig.text(x0, 0.872, "●", color=col, va="top", fontsize=22)
        fig.text(x0 + 0.022, 0.875, name, color=INK_2, va="top")
    return fig


def draw_one_week(d, plt):
    fig, ax = _fig(plt, "One week ahead, the model clearly beats “no change”",
                   "Next-week forecasts, best case (the real weather) · 1 = perfect, 0 = average",
                   h=6.2)
    fig.subplots_adjust(left=0.30, right=0.92, bottom=0.08)
    rows = [("the champion", d["champion_r2"], TEAL, INK),
            ("the lake stays the same", d["zero_change_r2"], MUTED, INK_2)]
    for y, (name, v, col, tcol) in zip((1, 0), rows):
        ax.barh(y, v, color=col, height=0.55)
        ax.text(-0.02, y, name, ha="right", va="center", color=tcol, fontsize=24)
        ax.text(max(v, 0) + 0.02, y, f"{v:.2f}", va="center", color=tcol, fontsize=40,
                fontweight="bold")
    ax.axvline(0, color=INK_2, linewidth=1.2)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xticks([]), ax.set_yticks([])
    ax.spines["bottom"].set_visible(False)
    return fig


def draw_frontier(d, plt):
    fig, axes = _fig(plt, "The further ahead, the less we can see",
                     "Each panel is measured its own way: read them side by side", h=7.0,
                     ncols=3, gridspec_kw={"width_ratios": [0.8, 1.2, 2.6], "wspace": 0.3})
    fig.subplots_adjust(left=0.035, right=0.84, top=0.70, bottom=0.14)
    by = {}
    for p in d["points"]:
        by.setdefault(p["group"], []).append(p)
    titles = ["1 week", "2 to 4 weeks", "Summer red-line date"]
    notes = ["best case", "best case", "seasonal method, not machine learning"]
    for ax, t, n in zip(axes, titles, notes):
        ax.set_title(t, loc="left", fontsize=24, fontweight="bold", color=INK, pad=38)
        ax.text(0, 1.02, n, transform=ax.transAxes, color=INK_2, fontsize=20, va="bottom")
        ax.set_yticks([])

    ax = axes[0]
    p = by["7d"][0]
    ax.bar([0], [p["value"]], color=TEAL, width=0.7)
    ax.text(0, p["value"] + 0.04, f"{p['value']:.2f}", ha="center", fontsize=30,
            fontweight="bold")
    ax.set_xticks([0], ["skill"])
    ax.set_xlim(-0.7, 0.7)
    ax.set_ylim(-0.8, 1)
    ax.axhline(0, color=INK_2, linewidth=1.2)
    ax.spines["bottom"].set_visible(False)

    ax = axes[1]
    pts = by["14_30d"]
    for i, q in enumerate(pts):
        v = q["value"]
        ax.bar(i, v, color=TEAL if v > 0 else MUTED, width=0.7)
        ax.text(i, v + (0.04 if v > 0 else -0.04), f"{v:+.2f}", ha="center", fontsize=30,
                fontweight="bold", va="bottom" if v > 0 else "top", color=INK if v > 0 else INK_2)
    ax.set_xticks(range(len(pts)), ["winter", "summer"])
    ax.set_ylim(-0.8, 1)
    ax.axhline(0, color=INK_2, linewidth=1.2)
    ax.spines["bottom"].set_visible(False)

    ax = axes[2]
    for method, col, name in (("unscaled", MUTED, "plain average"),
                              ("scaled", TEAL, "seasonal method")):
        pts = [q for q in by["summer"] if q["method"] == method]
        vals = [q["value"] for q in pts]
        ax.plot(range(len(pts)), vals, color=col, linewidth=3.5 if method == "scaled" else 2.5,
                zorder=3 if method == "scaled" else 2)
        for i, v in enumerate(vals):
            _dot(ax, i, v, col, size=10, z=4)
        ax.text(len(pts) - 0.7, vals[-1], name, color=INK if method == "scaled" else INK_2,
                va="center", linespacing=1.0)
    ax.set_xticks(range(len(BAND_SHORT)), BAND_SHORT, fontsize=20)
    ax.set_xlabel("warning given, up to", color=INK_2)
    ax.set_yticks([0, 10, 20, 30])
    ax.yaxis.grid(True)
    ax.set_ylabel("days off, on average", color=INK_2)
    ax.set_xlim(-0.4, len(BAND_SHORT) - 0.6)
    return fig


DRAWERS = {"hook": draw_hook, "olympics": draw_olympics, "timeline": draw_timeline,
           "one_week": draw_one_week, "frontier": draw_frontier}


def draw(name: str, ledger: dict, path: Path) -> Path:
    plt = _style()
    fig = DRAWERS[name](chart_data(name, ledger), plt)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main():
    ledger = load_ledger()
    for name in DRAWERS:
        print("drew", draw(name, ledger, OUT_DIR / f"{name}.png").relative_to(HERE))


if __name__ == "__main__":
    sys.exit(main())
