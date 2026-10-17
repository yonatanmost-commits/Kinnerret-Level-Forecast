"""
cfc_fan_eval.py  -  the forecast fan, plain and SEAS5-weighted, and the red-line odds.

Reads a past-winters ensemble folder written by `cfc_tournament.py --ensemble` (one
scenario "ens|Y" per earlier winter Y, plus the "obs" rows that give the model's own
error), builds the fan with cfc_bands two ways and scores both:

  plain     every past winter equally likely
  seas5     each past winter weighted by how well its season's rain matches what the
            ECMWF SEAS5 forecast published by the start day said (seas5.member_weights)
  mm        the same with the C3S multi-model mean (--source c3s; c3s.py, out on the 13th)

Season rain ratio = the rain-weighted mean, over the months the SEAS5 forecast covers
from the start's month on, of each month's rain over its normal. SEAS5's skill (the fit
behind the weights) is measured on the ERA5 table's rain (1993+, more seasons); each
scenario's own season ratio on the bench table's rain (the weather it was run with).
Normals and fits use years before the test year only.

Scores per model and horizon:
  coverage of the 50/80% ranges, median 80% width, quantile score (mean pinball loss
  over 19 quantiles, about half the CRPS; lower = sharper and honest), median error;
  red-line odds: Brier score of P(level < -213 m) and P(level < -208.8 m) against what
  happened, Brier skill against the test-period base rate, and a reliability table.

    CFC_GOLD=<gold.csv> python Automation/cfc_fan_eval.py docs/experiments/cfc_ims_ext_ens
    ... --source c3s --out docs/experiments/cfc_fan_eval/fan_mm.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfc_bands as cb                      # noqa: E402
import cfc_tournament_report as r           # noqa: E402
import c3s                                  # noqa: E402
import seas5                                # noqa: E402

LEVELS = tuple(round(x, 2) for x in np.arange(0.1, 0.91, 0.1))
RED = {"red": -213.0, "upper": -208.8}
GAMMA = 0.005


def monthly(daily: pd.Series) -> pd.Series:
    return daily.resample("MS").sum(min_count=20)


def normals(m: pd.Series, test_year: int) -> pd.Series:
    e = m[m.index.year < test_year]
    return e.groupby(e.index.month).mean()


def season_ratio(m: pd.Series, normal: pd.Series, months) -> float:
    """Rain-weighted season ratio over the given month starts."""
    idx = pd.DatetimeIndex(months)
    tot = m.reindex(idx)
    if tot.isna().any():
        return np.nan
    return float(tot.sum() / normal.reindex(idx.month).sum())


def weights_for(members: pd.DataFrame, S: pd.DataFrame, era_m: pd.Series, bench_m: pd.Series,
                src=seas5) -> pd.Series:
    """Weight per member row (index-aligned), by the seasonal forecast at its start
    (src: seas5 or c3s, the module that publishes S)."""
    out = pd.Series(1.0, index=members.index)
    members = members.assign(_t=pd.to_datetime(members["start"]),
                             _y=members["weather"].str.split("|").str[1].astype(int))
    for T, mt in members.groupby("year"):
        anom = src.anomalies(S, T)
        n_era, n_bench = normals(era_m, T), normals(bench_m, T)
        fits = {}
        for t, g in mt.groupby("_t"):
            init = src.init_for(t)
            f = anom[(anom["init"] == init) & (anom["target"] >= pd.Timestamp(t.year, t.month, 1))]
            if f.empty:
                continue
            months = list(f["target"])
            w_n = n_era.reindex(pd.DatetimeIndex(months).month).to_numpy()
            fc = float((f["rain_ratio"].to_numpy() * w_n).sum() / w_n.sum())
            offs = tuple((tg.year - t.year, tg.month) for tg in months)
            key = (init.month, offs)
            if key not in fits:                     # same calendar window in earlier years
                rows = []
                for y in range(1993, T):
                    i_y = pd.Timestamp(y + (init.year - t.year), init.month, 1)
                    tg_y = [pd.Timestamp(y + dy, mo, 1) for dy, mo in offs]
                    fa = anom[(anom["init"] == i_y) & (anom["target"].isin(tg_y))]
                    if len(fa) != len(tg_y) or max(tg_y) >= pd.Timestamp(T, 1, 1):
                        continue
                    wy = n_era.reindex(pd.DatetimeIndex(fa["target"]).month).to_numpy()
                    rows.append({"year": y, "fc": float((fa["rain_ratio"].to_numpy() * wy).sum() / wy.sum()),
                                 "obs": season_ratio(era_m, n_era, tg_y)})
                fits[key] = pd.DataFrame(rows)
            seasons = fits[key]
            if len(seasons) < 5:
                continue
            ratios = pd.Series({Y: season_ratio(bench_m, n_bench, [pd.Timestamp(Y + dy, mo, 1) for dy, mo in offs])
                                for Y in g["_y"].unique()}).dropna()
            if ratios.empty:
                continue
            w = seas5.member_weights(fc, ratios, seasons, T)
            out.loc[g.index] = g["_y"].map(w).fillna(w.min()).to_numpy()
    return out


def quantile_score(o: pd.DataFrame) -> pd.Series:
    """Mean pinball loss over the band quantiles and the median, per row."""
    losses = []
    for p in LEVELS:
        k = int(round(p * 100))
        for q, col in (((1 - p) / 2, f"lo_{k}"), ((1 + p) / 2, f"hi_{k}")):
            e = o["obs"] - o[col]
            losses.append(np.maximum(q * e, (q - 1) * e))
    e = o["obs"] - o["pred"]
    losses.append(np.maximum(0.5 * e, -0.5 * e))
    return pd.concat(losses, axis=1).mean(axis=1)


def score(o: pd.DataFrame) -> pd.DataFrame:
    o = o.dropna(subset=["lo_80", "obs"])
    o = o.assign(qs=quantile_score(o), in80=(o.obs >= o.lo_80) & (o.obs <= o.hi_80),
                 in50=(o.obs >= o.lo_50) & (o.obs <= o.hi_50), w80=o.hi_80 - o.lo_80, ae=(o.pred - o.obs).abs())
    rows = []
    for H, g in o.groupby("H"):
        row = {"H": H, "n": len(g), "cov50": g.in50.mean(), "cov80": g.in80.mean(), "width80": g.w80.median(),
               "qscore": g.qs.mean(), "median_err": g.ae.mean()}
        for name, lvl in RED.items():
            ev = (g.obs < lvl).astype(float)
            bs = float(((g[f"p_{name}"] - ev) ** 2).mean())
            base = ev.mean()
            ref = float(((base - ev) ** 2).mean())
            row |= {f"{name}_events": int(ev.sum()), f"{name}_brier": bs,
                    f"{name}_bss": (1 - bs / ref) if ref > 0 else np.nan}
        rows.append(row)
    return pd.DataFrame(rows)


def paired_gain(plain: pd.DataFrame, weighted: pd.DataFrame, hs=(130, 260, 365), n=2000) -> dict:
    """Weighted minus plain, per score, pooled over the long horizons, with a 90% interval
    from resampling test years (negative = the SEAS5 weighting is better)."""
    def per_row(o):
        o = o.dropna(subset=["lo_80", "obs"])
        o = o[o["H"].isin(hs)]
        return o.assign(qs=quantile_score(o), ae=(o.pred - o.obs).abs(),
                        br=(o["p_red"] - (o.obs < RED["red"]).astype(float)) ** 2)[["year", "start", "H", "qs", "ae", "br"]]
    m = per_row(plain).merge(per_row(weighted), on=["year", "start", "H"], suffixes=("_p", "_w"))
    years = m["year"].unique()
    rng = np.random.default_rng(0)
    out = {}
    for k in ("qs", "ae", "br"):
        diff = (m[f"{k}_w"] - m[f"{k}_p"]).groupby(m["year"]).agg(["sum", "count"])
        est = diff["sum"].sum() / diff["count"].sum()
        boot = []
        for _ in range(n):
            pick = diff.loc[rng.choice(years, len(years))]
            boot.append(pick["sum"].sum() / pick["count"].sum())
        out[k] = (float(est), float(np.quantile(boot, 0.05)), float(np.quantile(boot, 0.95)))
    return out


def reliability(o: pd.DataFrame, name: str, hs=(130, 260, 365)) -> pd.DataFrame:
    g = o[o["H"].isin(hs)].dropna(subset=[f"p_{name}", "obs"])
    bins = pd.cut(g[f"p_{name}"], [-0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 1.01],
                  labels=["0-10%", "10-30%", "30-50%", "50-70%", "70-90%", "90-100%"])
    ev = (g["obs"] < RED[name]).astype(float)
    return pd.DataFrame({"forecasts": ev.groupby(bins, observed=False).size(),
                         "said": g[f"p_{name}"].groupby(bins, observed=False).mean(),
                         "happened": ev.groupby(bins, observed=False).mean()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--models", default="B14,B14gru")
    ap.add_argument("--out", default="")
    ap.add_argument("--source", choices=["seas5", "c3s"], default="seas5")
    a = ap.parse_args()
    import cfc_tournament as ct                              # reads CFC_GOLD for the bench table
    ct.TABLE = "ims"
    ct.L.set_features(None)
    bench = ct.ims_table().set_index("date")["rainfall_mm"]
    ct.L.set_features(ct.L.NO_INTENSITY)
    era = ct.L.build_long_table().set_index("date")["rainfall_mm"]
    src = c3s if a.source == "c3s" else seas5
    fc = "mm" if a.source == "c3s" else "seas5"             # the weighted fan's name
    S = src.load()
    d = r.load(Path(a.folder))
    result, tables = {}, []
    for m in a.models.split(","):
        dm = d[d["method"] == m]
        mem, ob = dm[dm["weather"].str.startswith("ens|")], dm[dm["weather"] == "obs"]
        w = weights_for(mem, S, monthly(era), monthly(bench), src)
        fans = {}
        for name, members in (("plain", mem), (fc, mem.assign(weight=w))):
            o = cb.bands(members, levels=LEVELS, errors=ob, gamma=GAMMA, thresholds=RED)
            fans[name] = o
            s = score(o).assign(model=m, fan=name)
            tables.append(s)
            result[f"{m}/{name}"] = {"scores": s.to_dict("records"),
                                     "reliability_red": reliability(o, "red").reset_index().to_dict("records")}
            if a.out:
                o.assign(model=m, fan=name).to_csv(Path(a.out).with_name(f"{Path(a.out).stem}_{m}_{name}.csv"), index=False)
                t = pd.to_datetime(o["start"])                 # one autumn start per year, for the report's fans
                pick = [o.loc[(t[t.dt.year == y] - pd.Timestamp(y, 10, 15)).abs().idxmin(), "start"]
                        for y in sorted(t.dt.year.unique())]
                lv0 = dm.drop_duplicates("start").set_index("start")["level0"]
                ex = o[o["start"].isin(pick)].assign(level0=lambda x: x["start"].map(lv0))
                result[f"{m}/{name}"]["examples"] = ex.replace({np.nan: None}).to_dict("records")
        print(f"{m}: weights spread  median {w.median():.2f}  10-90% {w.quantile(0.1):.2f}..{w.quantile(0.9):.2f}")
        g = paired_gain(fans["plain"], fans[fc])
        result[f"{m}/gain"] = g
        print(f"{m}: {fc}-weighted minus plain, 130-365 d [90% interval over test years]: " +
              "  ".join(f"{k} {v[0]:+.4f} [{v[1]:+.4f}, {v[2]:+.4f}]" for k, v in
                        (("quantile score", g["qs"]), ("median error", g["ae"]), ("red-line Brier", g["br"]))))
    t = pd.concat(tables)
    pd.set_option("display.width", 200)
    print(t[["model", "fan", "H", "n", "cov50", "cov80", "width80", "qscore", "median_err",
             "red_events", "red_brier", "red_bss", "upper_events", "upper_bss"]].round(3).to_string(index=False))
    for m in a.models.split(","):
        for name in ("plain", fc):
            print(f"\nreliability, P(level < -213 m) at 130-365 d, {m} {name}:")
            print(pd.DataFrame(result[f"{m}/{name}"]["reliability_red"]).round(2).to_string(index=False))
    if a.out:
        Path(a.out).write_text(json.dumps(result, default=float, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
