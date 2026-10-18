"""Slide 11 fan data: the live GRU fan (Models/longrange_fan.json) plus wet/normal/dry groups of past
winters with their SEAS5 weights, recomputed exactly as fan_today.main does."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(r"C:\Users\yonatanm\Pojects\ClaudeCode\Data Science Project")
OUT = Path(sys.argv[1])
os.environ.setdefault("CFC_HORIZONS", "monthly")
sys.path.insert(0, str(ROOT / "Automation"))
import cfc_fan_eval as fe, cfc_tournament as ct, cfc_tournament_report as r, seas5, fan_today as ft
ct.TABLE = "ims"; ct.L.set_features(None)
bench = ct.ims_table().set_index("date")["rainfall_mm"]
ct.L.set_features(ct.L.NO_INTENSITY)
era = ct.L.build_long_table().set_index("date")["rainfall_mm"]
S = seas5.load()
today = r.load(ROOT / "docs/experiments/cfc_today_monthly"); today = today[today["method"] == "B14gru"]
start = max(today.loc[today["weather"].str.startswith("ens|"), "start"])
mem = today[today["weather"].str.startswith("ens|") & (today["start"] == start)]
w = fe.weights_for(mem, S, fe.monthly(era), fe.monthly(bench))
mem = mem.assign(Y=mem["weather"].str.split("|").str[1].astype(int), w=w.loc[mem.index])
live = json.loads((ROOT / "Models/longrange_fan.json").read_text(encoding="utf-8"))
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
t.round(3).to_csv(OUT / "slide11_fan.csv", index=False)
meta = {"source": "Models/longrange_fan.json (live app, page 10), GRU, start " + live["start"], "level0": level0,
        "red_line": -213.0, "groups": {k: {kk: v for kk, v in g_.items() if kk != "path"} for k, g_ in groups.items()},
        "winter_weights": {f"{Y}-{str(Y+1)[2:]}": round(float(wy[Y]), 4) for Y in Ys},
        "winter_rain_mm": {f"{Y}-{str(Y+1)[2:]}": int(rain[Y]) for Y in Ys},
        "winter_end_level_365": {f"{Y}-{str(Y+1)[2:]}": (None if pd.isna(paths.loc[Y, 365]) else round(float(paths.loc[Y, 365]), 2)) for Y in Ys},
        "winters_per_horizon": {int(H): int(paths[H].notna().sum()) for H in paths.columns}}
(OUT / "slide11_fan_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
print(json.dumps(meta["groups"], indent=1))
print(t[t.H.isin([0, 91, 182, 365])][["H", "date", "median", "lo_50", "hi_50", "lo_80", "hi_80", "lo_90", "hi_90", "p_red", "wet_group", "normal_group", "dry_group"]].round(2).to_string(index=False))
