"""Slide 11 fan data: the live GRU fan (Models/longrange_fan.json) plus wet/normal/dry groups of past
winters with their SEAS5 weights, recomputed exactly as fan_today.main does; the monthly
most-likely dots with the model's own error bars; and where each path crosses the red line.

  dots(run, back, fan)        -> slide11_dots.csv      (one row per month ahead)
  crossings(fan_table, dots)  -> slide11_crossings.json

Run:  python docs/talk/data/slide11_fan_build.py [out_dir]     # default: this folder
      (after Automation/fan_today.py; chart_fan.py reads the four files)
      --run DIR --fan FILE: another from-today run and its fan (a dry run), instead of
      docs/experiments/cfc_today_monthly and Models/longrange_fan.json
"""
import argparse, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MONTHS = [30, 61, 91, 122, 152, 182, 213, 243, 274, 304, 335, 365]   # the monthly horizons, no 130/260
DOY_WINDOW = 45            # cfc_bands.bands' default: errors from starts within 45 days of the year
RED_LINE = -213.0
METHOD = "B14gru"


def dots(run: pd.DataFrame, back: pd.DataFrame, fan: dict) -> pd.DataFrame:
    """The fan's median and 80% band at each month ahead, the median plus the 10th..90th
    percentile of the model's own errors given the real weather (the errors cfc_bands blurs the
    scenarios with: same horizon, start within DOY_WINDOW days of the year, already observed on
    the start day), and the run with an average year's weather."""
    run = run[run["method"] == METHOD]
    back = back[(back["method"] == METHOD) & (back["year"] < run["year"].min())]
    err = pd.concat([back[back["weather"] == "obs"], run[run["weather"] == "obs"]])
    err = err.assign(e=err["obs"] - err["pred"], t=pd.to_datetime(err["start"])).dropna(subset=["e"])
    t0 = pd.Timestamp(fan["start"])
    clim = run[(run["start"] == fan["start"]) & (run["weather"] == "clim")].set_index("H")["pred"]
    h = {x["H"]: x for x in fan["horizons"]}
    rows = []
    for k, H in enumerate(MONTHS, 1):
        x = err[err["H"] == H]
        gap = (x["t"].dt.dayofyear - t0.dayofyear).abs()
        x = x[(np.minimum(gap, 365 - gap) <= DOY_WINDOW) & (x["t"] + pd.Timedelta(days=H) <= t0)]
        med = h[H]["median"]
        rows.append({"month": k, "H": H, "date": str((t0 + pd.Timedelta(days=H)).date()), "median": med,
                     "model_err_lo80": med + x["e"].quantile(0.1), "model_err_hi80": med + x["e"].quantile(0.9),
                     "model_err_mae": x["e"].abs().mean(), "model_err_years": x["year"].nunique(),
                     "model_err_n": len(x), "lo_80": h[H]["lo_80"], "hi_80": h[H]["hi_80"],
                     "avg_year": float(clim[H])})
    return pd.DataFrame(rows).round(3)


def crossings(fan_table: pd.DataFrame, dots: pd.DataFrame) -> dict:
    """Red-line crossings (straight line between the points, from today's level) and the highest
    point, of the most-likely path and the three groups (every horizon in the fan table, 130 and
    260 days too), and the crossings of the average year (its monthly dots)."""
    t = fan_table.sort_values("H")
    dates = pd.to_datetime(t["date"]).tolist()
    series = {k: (dates, t[k].tolist()) for k in ("median", "wet_group", "normal_group", "dry_group")}
    d = dots.sort_values("H")
    series["avg_year"] = ([dates[0]] + pd.to_datetime(d["date"]).tolist(), [t["median"].iloc[0]] + d["avg_year"].tolist())
    cross = {}
    for k, (ds, v) in series.items():
        cross[k] = []
        for (d0, v0), (d1, v1) in zip(zip(ds, v), zip(ds[1:], v[1:])):
            if (v0 < RED_LINE) != (v1 < RED_LINE):
                day = d0 + (d1 - d0) * ((RED_LINE - v0) / (v1 - v0))
                cross[k].append({"date": str(day.date()), "direction": "up" if v1 > v0 else "down"})
    peaks = {}
    for k in ("median", "wet_group", "normal_group", "dry_group"):
        ds, v = series[k]
        i = int(np.argmax(v[1:])) + 1
        peaks[k] = {"level": round(float(v[i]), 2), "date": str(ds[i].date())}
    return {"crossings": cross, "peaks": peaks}


def main(out: Path, run_dir: Path = ROOT / "docs/experiments/cfc_today_monthly",
         fan_file: Path = ROOT / "Models/longrange_fan.json") -> None:
    os.environ.setdefault("CFC_HORIZONS", "monthly")
    sys.path.insert(0, str(ROOT / "Automation"))
    import cfc_fan_eval as fe, cfc_tournament as ct, cfc_tournament_report as r, seas5
    ct.TABLE = "ims"; ct.L.set_features(None)
    bench = ct.ims_table().set_index("date")["rainfall_mm"]
    ct.L.set_features(ct.L.NO_INTENSITY)
    era = ct.L.build_long_table().set_index("date")["rainfall_mm"]
    S = seas5.load()
    run = r.load(run_dir)
    today = run[run["method"] == METHOD]
    start = max(today.loc[today["weather"].str.startswith("ens|"), "start"])
    mem = today[today["weather"].str.startswith("ens|") & (today["start"] == start)]
    w = fe.weights_for(mem, S, fe.monthly(era), fe.monthly(bench))
    mem = mem.assign(Y=mem["weather"].str.split("|").str[1].astype(int), w=w.loc[mem.index])
    live = json.loads(fan_file.read_text(encoding="utf-8"))
    assert live["start"] == str(pd.Timestamp(start).date()), (live["start"], start)
    # winters' Oct-Mar rain (gold), thirds over the past winters in the ensemble
    g = pd.read_csv(ROOT / "Gold Data/kinneret_gold_features.csv", parse_dates=[0], index_col=0)["rainfall_mm"]
    Ys = sorted(mem["Y"].unique())
    rain = pd.Series({Y: g[f"{Y}-10-01":f"{Y+1}-03-31"].sum() for Y in Ys})
    q = rain.rank(method="first")
    n = len(Ys); grp = pd.Series(np.where(q <= n / 3, "dry", np.where(q > 2 * n / 3, "wet", "normal")), index=rain.index)
    wy = mem.groupby("Y")["w"].first(); wy = wy / wy.sum()
    paths = mem.pivot_table(index="Y", columns="H", values="pred")
    level0 = live["level0"]
    groups = {}
    for k in ("wet", "normal", "dry"):
        ys = grp[grp == k].index
        sub = paths.loc[ys]
        def wmean(H):                                   # weights renormalised over the winters present at H
            ok = sub[H].notna(); ww = wy.loc[ys][ok]
            return float((sub[H][ok] * ww).sum() / ww.sum())
        ok365 = paths[365].notna()
        groups[k] = {"winters": [f"{Y}-{str(Y+1)[2:]}" for Y in ys],
                     "winters_at_365": [f"{Y}-{str(Y+1)[2:]}" for Y in ys if ok365[Y]],
                     "rain_mm_range": [int(rain[ys].min()), int(rain[ys].max())],
                     "chance_seas5": round(float(wy.loc[ys].sum()), 3), "chance_climate": round(len(ys) / n, 3),
                     "chance_seas5_at_365": round(float(wy[ok365].loc[[Y for Y in ys if ok365[Y]]].sum() / wy[ok365].sum()), 3),
                     "path": {int(H): round(wmean(H), 3) for H in paths.columns}}
    rows = [{"H": 0, "date": live["start"], "median": level0, **{f"{s}_{p}": level0 for p in (50, 80, 90) for s in ("lo", "hi")}, "p_red": float(level0 < -213)}]
    rows += [{k: h[k] for k in ("H", "date", "median", "lo_50", "hi_50", "lo_80", "hi_80", "lo_90", "hi_90", "p_red")} for h in live["horizons"]]
    t = pd.DataFrame(rows)
    for k in groups:
        t[f"{k}_group"] = [level0] + [groups[k]["path"][int(H)] for H in t["H"][1:]]
    for Y in Ys:
        t[f"winter_{Y}-{str(Y+1)[2:]}"] = [level0] + [None if pd.isna(paths.loc[Y, H]) else round(float(paths.loc[Y, H]), 3) for H in t["H"][1:]]
    t = t.round(3)
    t.to_csv(out / "slide11_fan.csv", index=False)
    meta = {"source": "Models/longrange_fan.json (live app, page 10), GRU, start " + live["start"], "level0": level0,
            "red_line": RED_LINE, "groups": {k: {kk: v for kk, v in g_.items() if kk != "path"} for k, g_ in groups.items()},
            "winter_weights": {f"{Y}-{str(Y+1)[2:]}": round(float(wy[Y]), 4) for Y in Ys},
            "winter_rain_mm": {f"{Y}-{str(Y+1)[2:]}": int(rain[Y]) for Y in Ys},
            "winter_end_level_365": {f"{Y}-{str(Y+1)[2:]}": (None if pd.isna(paths.loc[Y, 365]) else round(float(paths.loc[Y, 365]), 2)) for Y in Ys},
            "winters_per_horizon": {int(H): int(paths[H].notna().sum()) for H in paths.columns}}
    (out / "slide11_fan_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    d = dots(run, r.load(ROOT / "docs/experiments/cfc_monthly"), live)
    d.to_csv(out / "slide11_dots.csv", index=False)
    (out / "slide11_crossings.json").write_text(json.dumps(crossings(t, d), indent=1), encoding="utf-8")
    print(json.dumps(meta["groups"], indent=1))
    print(t[t.H.isin([0, 91, 182, 365])][["H", "date", "median", "lo_50", "hi_50", "lo_80", "hi_80", "lo_90", "hi_90", "p_red", "wet_group", "normal_group", "dry_group"]].round(2).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(HERE))
    ap.add_argument("--run", default=str(ROOT / "docs/experiments/cfc_today_monthly"))
    ap.add_argument("--fan", default=str(ROOT / "Models/longrange_fan.json"))
    a = ap.parse_args()
    main(Path(a.out), Path(a.run), Path(a.fan))
