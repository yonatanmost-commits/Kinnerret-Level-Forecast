"""
charts.py - The talk's five charts, drawn from the numbers ledger only (plan D9).

chart_data(name, ledger) returns exactly the values a chart plots; draw(name, ledger, path) plots
them. The truth tests (tests/test_talk_truth.py) check chart_data against the real sources, so
nothing reaches a chart except through it.

Look (plan D9/D10, dataviz skill, light theme): a near-white surface, muted grey series, one accent
red reserved for the red line and the champion, a validated blue for a second series. Chart
text 20 pt and up, at slide size (13.33 x 7.5 in).

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
    "baseline_gbr": "Champion: two-stage boosting",
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

# Colours (dataviz reference palette, light mode; blue/red pair validated)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#a8a7a1"
GRID = "#e7e6e2"
ACCENT = "#e34948"   # red line + champion only
BLUE = "#2a78d6"


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
        return {"points": [{"model": m, "label": MODEL_LABELS[m],
                            "r2": _v(ledger, f"olympics.{m}.r2_mean"),
                            "runtime_s": _v(ledger, f"olympics.{m}.runtime_s"),
                            "champion": m == "baseline_gbr"} for m in MODELS]}
    if name == "timeline":
        hist = sorted(((e["date"], e["seq"]), k) for k, e in ledger.items()
                      if k.startswith("history.") and e["kind"] == "historical")
        hist = [(d, k) for (d, _), k in hist]
        pts = [{"key": k, "sha": ledger[k]["sha"], "date": d, "r2": ledger[k]["value"],
                "kind": "historical", "cause": ledger[k]["cause"],
                "cause_type": ledger[k]["cause_type"],
                "short": TIMELINE_SHORT.get(ledger[k]["sha"], ledger[k]["cause"])}
               for d, k in hist]
        c = ledger["champion.r2"]
        pts.append({"key": "champion.r2", "sha": None, "date": c["date"], "r2": c["value"],
                    "kind": "freeze", "cause": c["cause"], "cause_type": c["cause_type"],
                    "short": TIMELINE_SHORT["freeze"]})
        return {"points": pts}
    if name == "one_week":
        return {"champion_r2": _v(ledger, "champion.r2"),
                "zero_change_r2": _v(ledger, "baseline.zero_change.r2")}
    if name == "frontier":
        pts = [{"group": "7d", "key": "champion.r2", "value": _v(ledger, "champion.r2"),
                "label": "1 week ahead: the champion"}]
        for season, word in (("wet", "winter"), ("dry", "summer")):
            k = f"frontier.{season}.temp_bucket_ss"
            pts.append({"group": "14_30d", "key": k, "value": _v(ledger, k), "season": season,
                        "label": f"{word}, best case - if we knew the weather ahead"})
        for method, label in (("scaled", "seasonal method, scaled to recent weeks - not machine learning"),
                              ("unscaled", "plain seasonal average")):
            for band, blabel in zip(BANDS, BAND_LABELS):
                k = f"crossing.{method}.mae_{band}"
                pts.append({"group": "summer", "key": k, "value": _v(ledger, k),
                            "method": method, "band": blabel, "label": label})
        return {"points": pts, "crossings": _v(ledger, "crossing.n"),
                "never_crossed": _v(ledger, "crossing.never_crossed"),
                "issued": _v(ledger, "crossing.issued"),
                "longrange_date": ledger["frontier.wet.temp_bucket_ss"]["date"]}
    raise KeyError(f"unknown chart {name!r}")


# ─── drawing ────────────────────────────────────────────────────────────────

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
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 1,
        "lines.linewidth": 2,
    })
    return plt


def _fig(plt, w=13.33, h=6.6):
    return plt.subplots(figsize=(w, h))


def _month(date: str) -> str:
    import datetime as dt
    d = dt.date.fromisoformat(date)
    return f"{d.day} {d.strftime('%b')}"


def draw_hook(d, plt):
    import pandas as pd
    fig, ax = _fig(plt)
    s = pd.DataFrame(d["series"], columns=["date", "level"])
    s["date"] = pd.to_datetime(s["date"])
    ax.plot(s["date"], s["level"], color=INK_2, linewidth=1.6)
    ax.axhline(d["red_line_m"], color=ACCENT, linewidth=2, linestyle=(0, (6, 4)))
    ax.text(s["date"].iloc[0], d["red_line_m"] - 0.12, "red line", color=ACCENT, va="top")
    fd = pd.Timestamp(d["freeze_date"])
    ax.plot([fd], [d["freeze_level_m"]], "o", color=ACCENT, markersize=12,
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
    ax.annotate(f"today\n{d['freeze_level_m']:.2f} m", (fd, d["freeze_level_m"]),
                xytext=(18, 0), textcoords="offset points", ha="left", va="center", color=INK)
    ax.set_xlim(s["date"].iloc[0], fd + pd.Timedelta(days=365 * 6))
    ax.set_ylabel("lake level (m)")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def draw_olympics(d, plt):
    fig, ax = _fig(plt)
    for p in d["points"]:
        col = ACCENT if p["champion"] else MUTED
        ax.plot([p["runtime_s"] / 60], [p["r2"]], "o", color=col, markersize=14,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    for p in d["points"]:
        if p["champion"] or p["model"] == "gru":
            ax.annotate(p["label"], (p["runtime_s"] / 60, p["r2"]), xytext=(14, 0),
                        textcoords="offset points", va="center",
                        color=INK if p["champion"] else INK_2)
    ax.set_xscale("log")
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    ax.xaxis.set_major_locator(FixedLocator([0.1, 1, 10, 60]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.set_xlabel("training time (minutes, log scale)")
    ax.set_ylabel("R² (1 = perfect)")
    ax.axhline(0, color=INK_2, linewidth=1)
    fig.tight_layout()
    return fig


def draw_timeline(d, plt):
    fig, ax = _fig(plt, h=6.8)
    pts = d["points"]
    xs = list(range(len(pts)))
    ys = [p["r2"] for p in pts]
    ax.step(xs, ys, where="post", color=MUTED, linewidth=2)
    for x, p in zip(xs, pts):
        col = ACCENT if p["kind"] == "freeze" else (BLUE if p["cause_type"] == "data" else INK_2)
        ax.plot([x], [p["r2"]], "o", color=col, markersize=12, markeredgecolor=SURFACE,
                markeredgewidth=2, zorder=3)
        prev = pts[x - 1]["r2"] if x else p["r2"] - 1
        above = p["r2"] >= prev            # rises labelled above, drops below
        ax.annotate(p["short"], (x, p["r2"]), xytext=(0, 26 if above else -30),
                    textcoords="offset points", ha="center", va="bottom" if above else "top",
                    fontsize=20, color=INK_2, linespacing=1.0)
    ax.set_xticks(xs, [_month(p["date"]) for p in pts])
    ax.set_ylabel("R² of the 1-week model")
    lo, hi = min(ys), max(ys)
    ax.set_ylim(lo - 0.06, hi + 0.06)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def draw_one_week(d, plt):
    fig, ax = _fig(plt, h=5.6)
    names = ["the lake stays the same", "the champion"]
    vals = [d["zero_change_r2"], d["champion_r2"]]
    ax.barh(names, vals, color=[MUTED, ACCENT], height=0.5)
    for i, v in enumerate(vals):
        ax.text(max(v, 0) + 0.02, i, f"{v:.2f}", va="center", color=INK)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.set_xlim(min(0, min(vals)) - 0.05, 1)
    ax.set_xlabel("R² on daily volume change (1 = perfect)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def draw_frontier(d, plt):
    import numpy as np
    fig, axes = plt.subplots(1, 3, figsize=(13.33, 6.6),
                             gridspec_kw={"width_ratios": [1, 1.3, 2.6]})
    by = {}
    for p in d["points"]:
        by.setdefault(p["group"], []).append(p)

    ax = axes[0]
    p = by["7d"][0]
    ax.bar([0], [p["value"]], color=ACCENT, width=0.6)
    ax.text(0, p["value"] + 0.03, f"{p['value']:.2f}", ha="center")
    ax.set_xticks([0], ["1 week"])
    ax.set_ylim(-0.8, 1)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.set_title("1 week: R²", color=INK_2)

    ax = axes[1]
    pts = by["14_30d"]
    vals = [q["value"] for q in pts]
    ax.bar(range(len(pts)), vals, color=[BLUE if v > 0 else MUTED for v in vals], width=0.6)
    for i, v in enumerate(vals):
        ax.text(i, v + (0.03 if v > 0 else -0.03), f"{v:+.2f}", ha="center",
                va="bottom" if v > 0 else "top")
    ax.set_xticks(range(len(pts)), ["winter", "summer"])
    ax.set_ylim(-0.8, 1)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.set_title("2-4 weeks: skill\nbest case", color=INK_2)

    ax = axes[2]
    for method, col in (("scaled", ACCENT), ("unscaled", MUTED)):
        pts = [q for q in by["summer"] if q["method"] == method]
        ax.plot(range(len(pts)), [q["value"] for q in pts], "o-", color=col, markersize=9,
                label="seasonal method" if method == "scaled" else "plain seasonal average")
    ax.set_xticks(range(len(BAND_LABELS)), BAND_LABELS, rotation=0, fontsize=20)
    ax.set_xlabel("days of warning")
    ax.set_title("summer red line: days off", color=INK_2)
    ax.legend(frameon=False, loc="upper left")
    for a in axes:
        a.grid(axis="x", visible=False)
    fig.tight_layout()
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
