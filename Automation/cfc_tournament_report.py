"""
cfc_tournament_report.py  -  One page of charts for the CfC tournament and its memory check.

Reads every saved forecast (docs/experiments/cfc_tournament/*.json and memory/*.json),
so it works on a finished run or a partial one; methods or years not yet saved are
simply absent. Scores follow cfc_tournament.summary: methods are compared only on
the (start, horizon) forecasts every one of them made, clim weather.

Run:  python Automation/cfc_tournament_report.py [out.html]
"""
import html
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
T = Path(os.environ.get("CFC_OUT", ROOT / "docs" / "experiments" / "cfc_tournament"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "experiments" / "cfc_tournament_report.html"
H = [7, 13, 26, 130, 260, 365]
LONG = [130, 260, 365]
ROUND1 = ["A", "A1", "B14", "B60"]
REFS = ["persistence", "clim_change"]
NAMES = {"A": "A · relay, 2 steps", "A1": "A1 · relay, 1 step", "B14": "B · direct, 14 d",
         "B60": "B · direct, 60 d", "C60": "C · continuous time, 60 d", "C60f": "C · trained like B", "B14b": "B · + soil bucket",
         "relay7": "relay · 7 seeds", "relay3": "relay · 3 seeds",
         "persistence": "no change", "clim_change": "average change"}


# ── data ─────────────────────────────────────────────────────────────────────

def load(folder: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(folder.glob("*.json")):
        if not p.name.startswith("summary"):
            for recs in json.loads(p.read_text(encoding="utf-8")).values():
                rows += recs
    d = pd.DataFrame(rows)
    if len(d):
        d["ae"] = (d["pred"] - d["obs"]).abs()
        d["key"] = d["method"] + "/" + d["weather"]
    return d


def common(d: pd.DataFrame, keys: list) -> pd.DataFrame:
    """Rows of `keys` on the (start, H) pairs that every one of them has."""
    d = d[d["key"].isin(keys)]
    n = d.groupby(["start", "H"])["key"].nunique()
    idx = n[n == len(keys)].index
    if not len(idx):
        return d.iloc[:0]
    return d.set_index(["start", "H"]).loc[idx].reset_index()


def present(d, methods, weather="clim"):
    have = set(d["key"]) if len(d) else set()
    return [m for m in methods if f"{m}/{weather}" in have]


def mae(c, key, hs=H):
    s = c[(c["key"] == key) & c["H"].isin(hs)]["ae"]
    return float(s.mean()) if len(s) else np.nan


def by_h(c, key):
    return c[c["key"] == key].groupby("H")["ae"].mean().to_dict()


def boot(c, a, b, hs, n=2000):
    """Mean MAE difference a - b over (year, horizon) cells; 90% interval from
    resampling test years."""
    py = c[c["H"].isin(hs)].groupby(["key", "year", "H"])["ae"].mean().unstack("key")
    diff = (py[a] - py[b]).dropna()
    years = diff.index.get_level_values("year").unique().to_numpy()
    per = {y: diff.xs(y, level="year").to_numpy() for y in years}
    rng = np.random.default_rng(0)
    sims = [np.concatenate([per[y] for y in rng.choice(years, len(years))]).mean() for _ in range(n)]
    return float(diff.mean()), float(np.percentile(sims, 5)), float(np.percentile(sims, 95))


# ── svg ──────────────────────────────────────────────────────────────────────

def esc(s):
    return html.escape(str(s))


def logx(x0, x1, lo, hi):
    a, b = np.log(lo), np.log(hi)
    return lambda v: x0 + (np.log(v) - a) / (b - a) * (x1 - x0)


def lin(v0, v1, p0, p1):
    return lambda v: p0 + (v - v0) / (v1 - v0) * (p1 - p0)


def nice_max(v):
    for step in (0.05, 0.1, 0.2, 0.25, 0.5, 1, 2):
        if v / step <= 6:
            return step * np.ceil(v / step), step
    return np.ceil(v), 1


def spread(ys, gap=13):
    """Push label y positions apart so none overlap, keeping order."""
    order = np.argsort(ys)
    out = np.array(ys, float)
    for i in range(1, len(order)):
        if out[order[i]] - out[order[i - 1]] < gap:
            out[order[i]] = out[order[i - 1]] + gap
    return out


def svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'preserveAspectRatio="xMidYMid meet">{body}</svg>')


def horizon_chart(c, keys, label, w=720, h=360, names=None):
    """MAE (m) against horizon, log days; one line per key, references dashed."""
    ml, mr, mt, mb = 52, 215, 18, 40
    X = logx(ml, w - mr, 6, 400)
    top = max(max(by_h(c, k).values()) for k in keys)
    ymax, step = nice_max(top)
    Y = lin(0, ymax, h - mb, mt)
    g = []
    for v in np.arange(0, ymax + 1e-9, step):
        g.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
    for hh in H:
        g.append(f'<line class="grid faint" x1="{X(hh):.1f}" x2="{X(hh):.1f}" y1="{mt}" y2="{h - mb}"/>'
                 f'<text class="tick" x="{X(hh):.1f}" y="{h - mb + 18}" text-anchor="middle">{hh}</text>')
    g.append(f'<text class="axis" x="{(ml + w - mr) / 2}" y="{h - 4}" text-anchor="middle">days ahead</text>'
             f'<text class="axis" x="14" y="{(mt + h - mb) / 2}" transform="rotate(-90 14 {(mt + h - mb) / 2})" '
             f'text-anchor="middle">level error, m</text>')
    ends = []
    for k in keys:
        m = k.split("/")[0]
        pts = by_h(c, k)
        xs = [hh for hh in H if hh in pts]
        path = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(pts[x]):.1f}" for i, x in enumerate(xs))
        ref, obs = m in REFS or m.startswith("relay"), k.endswith("/obs")
        ens = k.endswith("/ens")
        g.append(f'<path class="ln {"ref" if ref and not obs else ""} {"obs" if obs else ""} {"ens" if ens else ""}" '
                 f'style="stroke:var(--m-{m})" d="{path}"/>')
        if not (ref or obs):
            g += [f'<circle cx="{X(x):.1f}" cy="{Y(pts[x]):.1f}" r="3.2" style="fill:var(--m-{m})"/>' for x in xs]
        name = (names or {}).get(k) or (m + " · weather known" if obs else NAMES.get(m, m))
        ends.append((Y(pts[xs[-1]]), m, pts[xs[-1]], name))
    ys = spread([e[0] for e in ends])
    for (y0, m, v, name), y in zip(ends, ys):
        g.append(f'<text class="lab" x="{w - mr + 10}" y="{y + 4:.1f}" style="fill:var(--m-{m})">'
                 f'{esc(name)} <tspan class="num">{v:.2f}</tspan></text>')
    return svg(w, h, "".join(g), label)


def long_bars(c, methods, label, w=720, h=250):
    """Grouped bars: MAE at 130/260/365 d per method; the best in each group marked."""
    ml, mr, mt, mb = 52, 10, 26, 40
    vals = {m: by_h(c, f"{m}/clim") for m in methods}
    refs = {r: by_h(c, f"{r}/-") for r in REFS if f"{r}/-" in set(c["key"])}
    top = max([vals[m].get(hh, 0) for m in methods for hh in LONG] +
              [refs[r].get(hh, 0) for r in refs for hh in LONG])
    ymax, step = nice_max(top)
    Y = lin(0, ymax, h - mb, mt)
    gw = (w - ml - mr) / len(LONG)
    bw = min(34, (gw - 40) / len(methods))
    g = []
    for v in np.arange(0, ymax + 1e-9, step):
        g.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
    for i, hh in enumerate(LONG):
        x0 = ml + i * gw + (gw - bw * len(methods)) / 2
        best = min(methods, key=lambda m: vals[m].get(hh, np.inf))
        for j, m in enumerate(methods):
            v = vals[m].get(hh)
            if v is None:
                continue
            x = x0 + j * bw
            g.append(f'<rect x="{x + 2:.1f}" y="{Y(v):.1f}" width="{bw - 4:.1f}" height="{Y(0) - Y(v):.1f}" '
                     f'rx="2" style="fill:var(--m-{m})" class="{"" if m == best else "dim"}"/>'
                     f'<text class="num small inbar" x="{x + bw / 2:.1f}" y="{Y(v) + 13:.1f}" text-anchor="middle">{v:.2f}</text>')
        for r, cls in zip(refs, ("ref1", "ref2")):
            v = refs[r].get(hh)
            if v is not None:
                g.append(f'<line class="refline {cls}" x1="{x0 - 6:.1f}" x2="{x0 + bw * len(methods) + 6:.1f}" '
                         f'y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
        g.append(f'<text class="tick strong" x="{ml + i * gw + gw / 2:.1f}" y="{h - mb + 20}" '
                 f'text-anchor="middle">{hh} days</text>')
    return svg(w, h, "".join(g), label)


def forest(rows, label, w=720):
    """rows: (left name, right name, (d, lo, hi) all horizons, (d, lo, hi) long).
    Negative = left better."""
    ml, mr, rh, mt = 150, 150, 46, 30
    h = mt + rh * len(rows) + 30
    ext = max(0.05, max(max(abs(r[2][1]), abs(r[2][2]), abs(r[3][1]), abs(r[3][2])) for r in rows)) * 1.15
    X = lin(-ext, ext, ml, w - mr)
    g = [f'<line class="zero" x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{mt - 10}" y2="{h - 26}"/>']
    _, step = nice_max(ext)
    for v in np.arange(-np.floor(ext / step) * step, ext, step):
        g.append(f'<text class="tick" x="{X(v):.1f}" y="{h - 8}" text-anchor="middle">'
                 f'{"0" if abs(v) < 1e-9 else f"{v:+.2f}"}</text>')
    g.append(f'<text class="axis" x="{X(-ext / 2):.1f}" y="{mt - 14}" text-anchor="middle">◀ left better</text>'
             f'<text class="axis" x="{X(ext / 2):.1f}" y="{mt - 14}" text-anchor="middle">right better ▶</text>')
    for i, (a, b, allh, lng) in enumerate(rows):
        y = mt + i * rh + rh / 2
        g.append(f'<text class="lab" x="{ml - 12}" y="{y + 4}" text-anchor="end" style="fill:var(--m-{a})">{esc(NAMES.get(a, a))}</text>'
                 f'<text class="lab" x="{w - mr + 12}" y="{y + 4}" style="fill:var(--m-{b})">{esc(NAMES.get(b, b))}</text>')
        for (d, lo, hi), dy, cls in ((allh, -7, "all"), (lng, 7, "long")):
            g.append(f'<line class="ci {cls}" x1="{X(lo):.1f}" x2="{X(hi):.1f}" y1="{y + dy}" y2="{y + dy}"/>'
                     f'<circle class="pt {cls}" cx="{X(d):.1f}" cy="{y + dy}" r="5"/>')
    return svg(w, h, "".join(g), label)


def year_heat(c, methods, hh, label, w=720):
    """Test year x method, cell = MAE at horizon hh; ring on each year's best."""
    ml, mt, rh = 54, 34, 22
    t = c[c["H"] == hh].groupby(["year", "key"])["ae"].mean().unstack()
    years = sorted(t.index)                      # the last test year has no 365-day outcome yet
    h = mt + rh * len(years) + 8
    cw = (w - ml - 10) / len(methods)
    vmax = float(np.nanmax(t[[f"{m}/clim" for m in methods]].to_numpy()))
    g = []
    for j, m in enumerate(methods):
        g.append(f'<text class="lab" x="{ml + j * cw + cw / 2:.1f}" y="{mt - 12}" text-anchor="middle" '
                 f'style="fill:var(--m-{m})">{esc(m)}</text>')
    for i, yv in enumerate(years):
        y = mt + i * rh
        g.append(f'<text class="tick" x="{ml - 8}" y="{y + rh / 2 + 4}" text-anchor="end">{yv}</text>')
        row = {m: t.loc[yv, f"{m}/clim"] for m in methods}
        best = min(row, key=row.get)
        for j, m in enumerate(methods):
            v = row[m]
            x = ml + j * cw
            g.append(f'<rect x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{rh - 2}" rx="2" '
                     f'class="heat" fill-opacity="{0.08 + 0.85 * v / vmax:.2f}"/>'
                     f'<text class="num small {"hot" if v / vmax > 0.55 else ""}" x="{x + cw / 2:.1f}" '
                     f'y="{y + rh / 2 + 4}" text-anchor="middle">{v:.2f}</text>')
            if m == best:
                g.append(f'<rect x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{rh - 2}" rx="2" class="best"/>')
    return svg(w, h, "".join(g), label)


def xy_chart(series, xs_ticks, xlabel, label, w=720, h=300, logscale=True):
    """series: (name, css colour var, {x: y}, dashed)."""
    ml, mr, mt, mb = 52, 120, 16, 40
    allx = [x for s in series for x in s[2]]
    lo, hi = min(allx + xs_ticks), max(allx + xs_ticks)
    X = logx(ml, w - mr, lo * 0.85, hi * 1.15) if logscale else lin(lo, hi, ml, w - mr)
    ymax, step = nice_max(max(v for s in series for v in s[2].values()))
    Y = lin(0, ymax, h - mb, mt)
    g = []
    for v in np.arange(0, ymax + 1e-9, step):
        g.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
    for x in xs_ticks:
        g.append(f'<text class="tick" x="{X(x):.1f}" y="{h - mb + 18}" text-anchor="middle">{x}</text>')
    g.append(f'<text class="axis" x="{(ml + w - mr) / 2}" y="{h - 4}" text-anchor="middle">{esc(xlabel)}</text>'
             f'<text class="axis" x="14" y="{(mt + h - mb) / 2}" transform="rotate(-90 14 {(mt + h - mb) / 2})" '
             f'text-anchor="middle">level error, m</text>')
    ends = []
    for name, col, pts, dashed in series:
        xs = sorted(pts)
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(pts[x]):.1f}" for i, x in enumerate(xs))
        g.append(f'<path class="ln {"ref" if dashed else ""}" style="stroke:var({col})" d="{d}"/>')
        g += [f'<circle cx="{X(x):.1f}" cy="{Y(pts[x]):.1f}" r="3.2" style="fill:var({col})"/>' for x in xs]
        ends.append((Y(pts[xs[-1]]), name, col))
    for (y0, name, col), y in zip(ends, spread([e[0] for e in ends])):
        g.append(f'<text class="lab" x="{w - mr + 10}" y="{y + 4:.1f}" style="fill:var({col})">{esc(name)}</text>')
    return svg(w, h, "".join(g), label)


def method_glyphs():
    """What each method does, drawn: from today (left) to a horizon (right)."""
    w, h = 170, 70
    def frame(body, name, sub, col):
        return (f'<figure class="glyph"><svg viewBox="0 0 {w} {h}" aria-hidden="true">'
                f'<line class="grid" x1="10" x2="{w - 10}" y1="{h - 14}" y2="{h - 14}"/>'
                f'<circle cx="14" cy="{h - 14}" r="4" class="today"/>{body}</svg>'
                f'<figcaption><b style="color:var({col})">{name}</b><span>{sub}</span></figcaption></figure>')
    hop = lambda x0, x1, y, col: (f'<path d="M{x0},{y} Q{(x0 + x1) / 2},{y - 18} {x1},{y}" '
                                  f'class="arc" style="stroke:var({col})"/>')
    yb = h - 14
    a = "".join(hop(14 + i * 22, 36 + i * 22, yb, "--m-A") +
                f'<rect x="{32 + i * 22}" y="{yb - 30}" width="8" height="8" rx="1" style="fill:var(--m-A)" opacity=".55"/>'
                for i in range(7))
    a1 = "".join(hop(14 + i * 22, 36 + i * 22, yb, "--m-A1") for i in range(7))
    b = "".join(f'<path d="M14,{yb} Q{(14 + x) / 2},{yb - 10 - (x - 14) * 0.25} {x},{yb}" class="arc" '
                f'style="stroke:var(--m-B60)"/>' for x in (40, 90, 160))
    grid = [1, 2, 3, 4, 5, 6, 8, 11, 15, 20, 26, 33, 41]
    cx = [14 + g * 11.2 for g in grid]
    cy = [yb - 6 - 30 * np.sin(i / 4.0) ** 2 for i in range(len(grid))]
    c = (f'<path d="M14,{yb} ' + " ".join(f"L{x:.1f},{y:.1f}" for x, y in zip(cx, cy)) +
         '" class="arc" style="stroke:var(--m-C60)"/>' +
         "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" style="fill:var(--m-C60)"/>' for x, y in zip(cx, cy)))
    return "".join([
        frame(a, "A", "day by day · inflow, then lake", "--m-A"),
        frame(a1, "A1", "day by day · lake only", "--m-A1"),
        frame(b, "B", "straight to each horizon", "--m-B60"),
        frame(c, "C", "one state, stepped in real time", "--m-C60"),
    ])


def bench_strip(years):
    """2001-2025 strip: one test year, everything before it trains; x len(years)."""
    w, h, ml = 720, 54, 10
    cw = (w - 2 * ml - 80) / 25
    ex = 2016
    g = []
    for i, y in enumerate(range(2001, 2026)):
        cls = "train" if y < ex else ("test" if y == ex else "unused")
        g.append(f'<rect x="{ml + i * cw + 1:.1f}" y="8" width="{cw - 2:.1f}" height="18" rx="2" class="{cls}"/>')
        if y in (2001, 2010, ex, 2025):
            g.append(f'<text class="tick" x="{ml + i * cw + cw / 2:.1f}" y="44" text-anchor="middle">{y}</text>')
    g.append(f'<text class="num big" x="{w - 70}" y="24">× {len(years)}</text>'
             f'<text class="tick" x="{w - 70}" y="42">test years</text>')
    return svg(w, h, "".join(g), "walk-forward: each test year trained on all years before it")


def ensemble_rows(e: pd.DataFrame) -> pd.DataFrame:
    """Per (method, start, H): median and 10/90% of the past-winters members, as rows
    with weather "ens" (pred = median) plus q10/q90 columns."""
    m = e[e["weather"].str.startswith("ens|")]
    g = m.groupby(["method", "year", "start", "H"])
    q = g["pred"].quantile([0.1, 0.5, 0.9]).unstack()
    q.columns = ["q10", "pred", "q90"]
    out = q.join(g["obs"].first()).join(g.size().rename("members")).reset_index()
    out["weather"] = "ens"
    out["key"] = out["method"] + "/ens"
    out["ae"] = (out["pred"] - out["obs"]).abs()
    return out


def relay_rows(seeds: int) -> pd.DataFrame:
    """The original IMS relay horizon test (liquid_nn_horizons.py, 2021-2024) as
    one row per horizon carrying its MAE, so it draws as a reference line."""
    p = ROOT / "docs" / "experiments" / f"liquid_nn_horizons_cfc_s{seeds}.json"
    if not p.exists():
        return pd.DataFrame()
    h = pd.DataFrame(json.loads(p.read_text(encoding="utf-8"))["horizons"])
    h = h[h["method"] == f"liquid_cfc_s{seeds}"]
    return pd.DataFrame({"method": f"relay{seeds}", "weather": h["weather"], "H": h["H"],
                         "ae": h["mae_m"], "key": f"relay{seeds}/" + h["weather"],
                         "start": "-", "year": 0})


def coverage_bars(cov: dict, label, w=720, h=230, target=0.8):
    """cov[method][H] = share of outcomes inside the 10-90% band; target line at 80%."""
    ml, mr, mt, mb = 52, 10, 20, 40
    methods = list(cov)
    Y = lin(0, 1, h - mb, mt)
    gw = (w - ml - mr) / len(H)
    bw = min(30, (gw - 16) / len(methods))
    g = []
    for v in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        g.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                 f'<text class="tick" x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.0%}</text>')
    g.append(f'<line class="refline ref1" x1="{ml}" x2="{w - mr}" y1="{Y(target):.1f}" y2="{Y(target):.1f}"/>')
    for i, hh in enumerate(H):
        x0 = ml + i * gw + (gw - bw * len(methods)) / 2
        for j, m in enumerate(methods):
            v = cov[m].get(hh)
            if v is None:
                continue
            x = x0 + j * bw
            g.append(f'<rect x="{x + 2:.1f}" y="{Y(v):.1f}" width="{bw - 4:.1f}" height="{Y(0) - Y(v):.1f}" '
                     f'rx="2" style="fill:var(--m-{m})"/>')
        g.append(f'<text class="tick strong" x="{ml + i * gw + gw / 2:.1f}" y="{h - mb + 20}" '
                 f'text-anchor="middle">{hh} d</text>')
    return svg(w, h, "".join(g), label)


def ims_section():
    """B14 on the IMS table with the past-winters ensemble, against the original relay."""
    folder = T.parent / "cfc_ims"
    e = load(folder) if folder.exists() else pd.DataFrame()
    if not len(e):
        return []
    e = e[e["year"] <= 2024]                         # the relay test's years
    ens = ensemble_rows(e)
    methods = [m for m in ("B14", "B14b") if m in set(e["method"])]
    rows = pd.concat([e[~e["weather"].str.startswith("ens|")], ens, relay_rows(7), relay_rows(3)])
    keys = ([f"{m}/{w}" for m in methods for w in ("clim", "ens")] + [f"{methods[0]}/obs"] +
            [k for k in ("relay7/clim", "relay7/obs", "relay3/obs") if k in set(rows["key"])])
    chart = horizon_chart(rows, keys, "IMS table: error by horizon",
                          names={f"{m}/ens": f"{m} · past winters" for m in methods} |
                                {f"{m}/clim": f"{m} · average weather" for m in methods} |
                                {f"{methods[0]}/obs": f"{methods[0]} · weather known",
                                 "relay7/clim": "relay 7 seeds · average", "relay7/obs": "relay 7 seeds · known",
                                 "relay3/obs": "relay 3 seeds · known"})
    cov = {m: ens[ens["method"] == m].assign(inside=lambda x: (x.obs >= x.q10) & (x.obs <= x.q90))
           .groupby("H")["inside"].mean().to_dict() for m in methods}
    n_mem = int(ens["members"].median())
    return [section("IMS table · past-winters ensemble", chart,
                    note=f"Test years 2021–2024. Past winters: one forecast per earlier year's weather "
                         f"(median of ~{n_mem}). Relay = the original day-by-day CfC on the same table."),
            section("IMS table · how often the outcome fell inside the 10–90% band",
                    coverage_bars(cov, "band coverage by horizon"),
                    note='<i class="key ref1"></i>80% = a calibrated band. ' +
                         " ".join(f'<i class="key sw" style="background:var(--m-{m})"></i>{esc(NAMES[m])}'
                                  for m in methods))]


# How the CfC computes, as ncps 1.0.1 runs it (ncps/torch/cfc_cell.py, mode "default"),
# with this bench's sizes. Static text: equations typeset by MathJax (SVG, no web fonts).
ALGEBRA = r"""
<section class="algebra"><h2>How a CfC step works</h2>
<div class="fig math">
<pre class="mermaid">
flowchart LR
  U["day t inputs u_t"] --> Z["stack z = [u_t ; h_t-1]"]
  H0["previous state h_t-1"] --> Z
  Z --> B["backbone b: 128 units, LeCun tanh"]
  B --> F1["f1 = tanh(W1 b)"]
  B --> F2["f2 = tanh(W2 b)"]
  B --> G["gate = sigmoid(a(b) * dt + beta(b))"]
  DT["elapsed time dt"] --> G
  F1 --> M["h_t = (1 - gate) * f1 + gate * f2"]
  F2 --> M
  G --> M
  M --> H1["new state h_t (32 units)"]
</pre>
<div class="eq">
\[
\begin{aligned}
z_t &= [\,u_t \,;\, h_{t-1}\,] && \text{15 inputs} + \text{32 state} = 47\\
b &= \varphi(W_b z_t + c_b), \quad \varphi(x) = 1.7159\,\tanh(0.666\,x) && \text{128 units}\\
f_1 &= \tanh(W_1 b + c_1), \qquad f_2 = \tanh(W_2 b + c_2) && \text{two candidate states}\\
\sigma_t &= \operatorname{sigmoid}\!\big(a(b)\,\Delta t + \beta(b)\big), \quad a = W_a b + c_a,\ \beta = W_\beta b + c_\beta && \text{time gate}\\
h_t &= (1-\sigma_t)\odot f_1 + \sigma_t \odot f_2 && \text{new state}
\end{aligned}
\]
</div>
<p class="cap">The closed-form solution of a liquid-time-constant ODE,
\( h(t) = \sigma(-f\,t)\odot g + \big(1-\sigma(-f\,t)\big)\odot \tilde h \): no solver. Each unit slides from
\(f_1\) toward \(f_2\) as time passes, at a rate \(a\) that depends on the input, so the time constant changes
with conditions. \(\Delta t = 1\) day in A and B; C's decoder steps with real lengths (1 day to day 14, then about 7).</p>
</div>
<div class="fig math">
<div class="eq">
\[
\begin{aligned}
h_{1..14} &= \text{CfC steps over the 14 days to the start day}, \quad h_0 = 0\\
s &= \text{weather of each horizon window (3 totals, 4 means)} && 6\times 7 = 42\\
\hat y &= W_4\,\operatorname{GELU}\!\big(W_3\,[\,h_{14} \,;\, s\,] + c_3\big) + c_4 && \text{6 horizons}\\
\Delta V_H &= \hat y_H\,\mathrm{sd}_H + \mathrm{mean}_H\\
\text{level}_H &= \text{level}_0 + P(V_0 + \Delta V_H) - P(V_0) && P = \text{bathymetry, volume}\to\text{level}
\end{aligned}
\]
</div>
<p class="cap">Model B, the winner. Window weather: rain, ET\(_0\), radiation totals; temperature, humidity, wind, VPD means. Inputs per day: 9 weather variables, season sine and cosine, log Jordan inflow,
level, volume change, a level-read flag (IMS table: + rain intensity; bucket: + storage, 30-day overflow).
Huber loss on standardised \(\Delta V\), AdamW, 3 seeds averaged. About 28k weights per seed
(cell 22.7k, head 5.2k).</p>
<p class="cap"><b>Why it remembers about a week:</b> \(h_t\) is a fresh blend of two functions of
\((u_t, h_{t-1})\). There is no additive carry path like an LSTM's \(c_t = f\,c_{t-1} + \dots\), so holding months
of history needs the backbone to copy the state step after step. Slow catchment memory has to come in as an input.</p>
</div>
</section>
"""


# ── page ─────────────────────────────────────────────────────────────────────

def section(title, *figs, note=""):
    return (f'<section><h2>{esc(title)}</h2>' + "".join(f'<div class="fig">{f}</div>' for f in figs) +
            (f'<p class="note">{note}</p>' if note else "") + '</section>')


def kpi(label, value, col=None):
    style = f' style="color:var({col})"' if col else ""
    return f'<div class="kpi"><span>{esc(label)}</span><b{style}>{value}</b></div>'


def build():
    d = load(T)
    mem = load(T / "memory") if (T / "memory").exists() else pd.DataFrame()
    parts, kpis = [], []

    # round 1
    r1 = present(d, ROUND1)
    c1 = common(d, [f"{m}/clim" for m in r1] + [f"{r}/-" for r in REFS])
    years = sorted(c1["year"].unique())
    score = {m: mae(c1, f"{m}/clim") for m in r1}
    score_long = {m: mae(c1, f"{m}/clim", LONG) for m in r1}
    w1 = min(score, key=score.get)
    wl = min(score_long, key=score_long.get)
    pers_long = mae(c1, "persistence/-", LONG)
    kpis += [kpi("round 1 winner", esc(NAMES[w1]), f"--m-{w1}"),
             kpi("best at 130–365 d", esc(NAMES[wl]), f"--m-{wl}"),
             kpi(f"{wl}, 130–365 d error", f"{score_long[wl]:.2f} m"),
             kpi("no-change, 130–365 d", f"{pers_long:.2f} m")]
    parts.append(section("Tested", f'<div class="glyphs">{method_glyphs()}</div>', bench_strip(years),
                         note="Horizons 7 · 13 · 26 · 130 · 260 · 365 days. A start every 7 days. "
                              "Weather ahead = average for that day of year. 3 seeds each."))
    parts.append(ALGEBRA)
    parts.append(section("Round 1 · error by horizon",
                         horizon_chart(common(d, [f"{m}/clim" for m in r1] + [f"{w1}/obs"] + [f"{r}/-" for r in REFS]),
                                       [f"{m}/clim" for m in r1] + [f"{w1}/obs"] + [f"{r}/-" for r in REFS],
                                       "round 1 level error by horizon")))
    parts.append(section("Round 1 · long range", long_bars(c1, r1, "long-range error per method"),
                         note='<i class="key ref1"></i>no change <i class="key ref2"></i>average change'))
    rows = []
    for a, b in (("A", "A1"), ("A1", "B14"), ("B14", "B60")):
        if a in r1 and b in r1:
            rows.append((a, b, boot(c1, f"{a}/clim", f"{b}/clim", H), boot(c1, f"{a}/clim", f"{b}/clim", LONG)))
    if rows:
        parts.append(section("What each change buys", forest(rows, "paired differences with 90% intervals"),
                             note='<i class="key dot all"></i>all horizons <i class="key dot long"></i>130–365 d · '
                                  'bars: 90% range over resampled test years'))
    parts.append(section("Year by year · 365 days ahead", year_heat(c1, r1, 365, "error per test year at 365 days")))

    # round 2: C against the rule winner, and against the long-range best if that differs
    win = w1
    if "C60" in present(d, ["C60"]):
        for i, m1 in enumerate(dict.fromkeys([w1, wl])):
            c2 = common(d, [f"{m1}/clim", "C60/clim"] + [f"{r}/-" for r in REFS])
            s2 = {m: mae(c2, f"{m}/clim", H if i == 0 else LONG) for m in (m1, "C60")}
            win = min(s2, key=s2.get)
            kpis.append(kpi("round 2 winner" if i == 0 else "long-range best overall",
                            esc(NAMES[win]), f"--m-{win}"))
            parts.append(section(f"Round 2 · {m1} vs C",
                                 horizon_chart(c2, [f"{m1}/clim", "C60/clim", "persistence/-"], "round 2 by horizon"),
                                 forest([(m1, "C60", boot(c2, f"{m1}/clim", "C60/clim", H),
                                          boot(c2, f"{m1}/clim", "C60/clim", LONG))], "round 2 paired difference")))

    # round 2 handicap check: C trained like B (every day, same stopping), on the years it ran
    if "C60f" in present(d, ["C60f"]):
        c3 = common(d, [f"{win}/clim", "C60/clim", "C60f/clim", "persistence/-"])
        ys = sorted(c3["year"].unique())
        parts.append(section("Round 2 · C with full training",
                             horizon_chart(c3, [f"{win}/clim", "C60/clim", "C60f/clim", "persistence/-"],
                                           "C with full training by horizon"),
                             forest([("C60f", win, boot(c3, "C60f/clim", f"{win}/clim", H),
                                      boot(c3, "C60f/clim", f"{win}/clim", LONG)),
                                     ("C60f", "C60", boot(c3, "C60f/clim", "C60/clim", H),
                                      boot(c3, "C60f/clim", "C60/clim", LONG))], "full-training C paired differences"),
                             note=f"Test years {', '.join(map(str, ys))}. C60: every other training day, 60 epochs. "
                                  "C60f: every day, 80 epochs, like B."))

    parts += ims_section()

    # memory
    if len(mem):
        # the tournament's own runs of the same method are sweep points too (same nets, same seeds)
        m0 = re.match(r"^(A1|A|B|C)", mem["method"].iat[0]).group(1)
        same = d[d["method"].str.fullmatch(rf"{m0}\d+") & d["weather"].isin(["clim", "obs"])]
        mem = pd.concat([mem, same]).drop_duplicates(["method", "weather", "start", "H"])
        method = mem["method"].str.extract(r"^(A1|A|B|C)_?(\d+)?$")
        mem = mem.assign(m=method[0], L=pd.to_numeric(method[1]).fillna(14).astype(int))
        mem = mem[mem["weather"].str.startswith("clim")]
        Ls = sorted(mem["L"].unique())
        full = mem[mem["weather"] == "clim"]
        keys = sorted(full["key"].unique())
        cm = common(full, keys)
        L_of = full.groupby("key")["L"].first()
        if len(Ls) > 1:
            pts_all = {int(L_of[k]): mae(cm, k) for k in keys}
            pts_long = {int(L_of[k]): mae(cm, k, LONG) for k in keys}
            m0 = mem["m"].iat[0]
            parts.append(section(f"Memory · how many past days {m0} should read",
                                 xy_chart([("130–365 d", "--m-B60", pts_long, False),
                                           ("all horizons", "--muted", pts_all, True)],
                                          [int(x) for x in Ls], "days of history the model reads", "history sweep"),
                                 note=f"{cm['year'].nunique()} test years ({cm['year'].min()}–{cm['year'].max()})"))
        occ = mem[mem["weather"].str.contains(r"\|")]
        if len(occ):
            series = []
            for i, L in enumerate(Ls):
                sub = mem[mem["L"] == L]
                if not sub["weather"].str.contains(r"\|").any():
                    continue
                sub = sub.assign(k=sub["weather"].str.split("|").str[1].fillna(str(L)).astype(int))
                sub = sub.assign(key=sub["k"].astype(str))
                cs = common(sub, sorted(sub["key"].unique()))
                series.append((f"trained on {L} d", f"--L{i % 6}",
                               {int(k): float(v) for k, v in cs[cs["H"].isin(LONG)].groupby("k")["ae"].mean().items()},
                               False))
            if series:
                parts.append(section("Memory · same model, older days blanked",
                                     xy_chart(series, sorted({k for s in series for k in s[2]}),
                                              "days of history left visible", "occlusion test"),
                                     note=f"130–365 d error · {occ['year'].nunique()} test years. "
                                          "Flat to the left of a point = days older than it are not used."))

    tests = (f"{len(years)} test years ({years[0]}–{years[-1]}) · {c1.groupby(['start']).ngroups} starts · "
             f"{len(c1):,} compared forecasts" if years else "")
    return PAGE.format(kpis="".join(kpis), body="".join(parts), tests=esc(tests),
                       stamp=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))


PAGE = """<title>CfC Horizon Tournament</title>
<meta name="claude:viewport-fit-sides" content="cover">
<script>window.MathJax = {{ svg: {{ fontCache: "global" }} }};</script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-svg.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* layout: one column of charts, each a self-explaining figure; kpis up top */
:root {{
  --bg:#f3f6f7; --panel:#ffffff; --fg:#122229; --muted:#5d717a; --grid:#d8e1e5;
  --m-A:#c26d1c; --m-A1:#d9a04b; --m-B14:#5fb0a8; --m-B60:#17716b; --m-C60:#6a56b8; --m-C60f:#a33d8f; --m-B14b:#2f5fa8;
  --m-relay7:#7a6a58; --m-relay3:#a8977f;
  --m-persistence:#8e9ca3; --m-clim_change:#b3bec3; --heat:#17716b;
  --L0:#a8d8d2; --L1:#5fb0a8; --L2:#17716b; --L3:#0d4c48; --L4:#6a56b8; --L5:#c26d1c;
  --sans:"Instrument Sans", "Segoe UI", system-ui, sans-serif;
  --mono:"JetBrains Mono", ui-monospace, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#0e181c; --panel:#142228; --fg:#e2ebee; --muted:#8ea2aa; --grid:#26363d;
  --m-A:#e2934a; --m-A1:#efc27f; --m-B14:#80cdc4; --m-B60:#38b2a6; --m-C60:#a594ea; --m-C60f:#e07fc6; --m-B14b:#7fa7e8;
  --m-relay7:#bfae96; --m-relay3:#8e7f6a;
  --m-persistence:#6e8088; --m-clim_change:#55666d; --heat:#38b2a6;
  --L0:#2d5f5a; --L1:#3f9289; --L2:#62c4b9; --L3:#a8e6de; --L4:#a594ea; --L5:#e2934a; color-scheme:dark }} }}
:root[data-theme="dark"] {{
  --bg:#0e181c; --panel:#142228; --fg:#e2ebee; --muted:#8ea2aa; --grid:#26363d;
  --m-A:#e2934a; --m-A1:#efc27f; --m-B14:#80cdc4; --m-B60:#38b2a6; --m-C60:#a594ea; --m-C60f:#e07fc6; --m-B14b:#7fa7e8;
  --m-relay7:#bfae96; --m-relay3:#8e7f6a;
  --m-persistence:#6e8088; --m-clim_change:#55666d; --heat:#38b2a6;
  --L0:#2d5f5a; --L1:#3f9289; --L2:#62c4b9; --L3:#a8e6de; --L4:#a594ea; --L5:#e2934a; color-scheme:dark }}
body {{ background:var(--bg); color:var(--fg); font-family:var(--sans); font-size:15px; line-height:1.5 }}
main {{ max-width:800px; margin:0 auto; padding-block:28px 48px;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px));
  display:grid; gap:22px }}
header {{ display:grid; gap:6px }}
h1 {{ font-size:1.7rem; margin:0; letter-spacing:-.01em; text-wrap:balance }}
.sub {{ color:var(--muted); font-family:var(--mono); font-size:.78rem }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px }}
.kpi {{ background:var(--panel); border:1px solid var(--grid); border-radius:8px; padding:10px 12px; display:grid; gap:2px; min-width:0 }}
.kpi span {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted) }}
.kpi b {{ font-size:1.02rem; font-variant-numeric:tabular-nums }}
section {{ display:grid; gap:8px }}
h2 {{ font-size:.78rem; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); margin:8px 0 0; font-weight:600 }}
.fig {{ background:var(--panel); border:1px solid var(--grid); border-radius:8px; padding:12px; overflow-x:auto }}
.fig svg {{ width:100%; min-width:520px; height:auto; display:block }}
.glyphs {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:12px }}
.glyphs svg {{ min-width:0 }}
.glyph {{ margin:0; display:grid; gap:4px }}
.glyph figcaption {{ display:grid; font-size:.8rem }} .glyph figcaption span {{ color:var(--muted) }}
.note {{ margin:0; color:var(--muted); font-size:.8rem }}
svg text {{ fill:var(--fg); font-family:var(--sans) }}
.tick {{ fill:var(--muted); font-size:11px; font-family:var(--mono) }} .tick.strong {{ fill:var(--fg); font-size:12px }}
.axis {{ fill:var(--muted); font-size:11px }}
.lab {{ font-size:12px; font-weight:600 }}
.num {{ font-family:var(--mono); font-variant-numeric:tabular-nums }} .small {{ font-size:10px }} .big {{ font-size:20px; font-weight:600 }}
.lab .num {{ fill:var(--muted); font-weight:400 }}
.grid {{ stroke:var(--grid); stroke-width:1 }} .faint {{ stroke-dasharray:2 4 }}
.ln {{ fill:none; stroke-width:2.4; stroke-linejoin:round }} .ln.obs {{ stroke-dasharray:0.1 5; stroke-linecap:round; stroke-width:3 }}
.ln.ens {{ stroke-width:3.2 }} .ln.ens + circle {{ r:4 }} .ln.ref {{ stroke-dasharray:5 4; stroke-width:1.8 }}
.dim {{ opacity:.55 }}
.refline {{ stroke-width:1.6; stroke-dasharray:5 3 }} .ref1 {{ stroke:var(--m-persistence) }} .ref2 {{ stroke:var(--m-clim_change) }}
.zero {{ stroke:var(--muted); stroke-width:1 }}
.ci {{ stroke-width:2.2 }} .ci.all, .pt.all {{ stroke:var(--muted) }} .ci.long {{ stroke:var(--fg) }}
.pt.all {{ fill:var(--panel); stroke-width:2 }} .pt.long {{ fill:var(--fg) }}
.heat {{ fill:var(--heat) }} .best {{ fill:none; stroke:var(--fg); stroke-width:2 }}
.hot, .inbar {{ fill:var(--panel) }}
.arc {{ fill:none; stroke-width:1.8 }} .today {{ fill:var(--fg) }}
.train {{ fill:var(--m-B14); opacity:.55 }} .test {{ fill:var(--m-A) }} .unused {{ fill:var(--grid) }}
i.key {{ display:inline-block; width:18px; height:0; border-top:2px dashed; vertical-align:middle; margin:0 4px 0 10px }}
i.key.ref1 {{ border-color:var(--m-persistence) }} i.key.ref2 {{ border-color:var(--m-clim_change) }}
i.key.dot {{ width:9px; height:9px; border:2px solid var(--muted); border-radius:50% }}
i.key.dot.long {{ background:var(--fg); border-color:var(--fg) }}
i.key.sw {{ width:10px; height:10px; border:0; border-radius:2px }}
footer {{ color:var(--muted); font-size:.72rem; font-family:var(--mono) }}
.math {{ display:grid; gap:10px }} .math .eq {{ overflow-x:auto; color:var(--fg) }}
.fig mjx-container svg {{ width:auto; min-width:0; display:inline }} .math pre.mermaid {{ margin:0; background:none }}
.cap {{ margin:0; color:var(--muted); font-size:.82rem; max-width:68ch }} .cap b {{ color:var(--fg) }}
@media (max-width: 560px) {{ h1 {{ font-size:1.35rem }} }}
</style>
<main>
<header><h1>CfC Horizon Tournament</h1><div class="sub">Lake Kinneret level · {tests}</div></header>
<div class="kpis">{kpis}</div>
{body}
<footer>built {stamp} · Automation/cfc_tournament_report.py · error = mean absolute level error (m), typical-day weather ahead</footer>
</main>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
