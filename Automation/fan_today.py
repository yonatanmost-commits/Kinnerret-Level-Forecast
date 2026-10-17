"""
fan_today.py  -  the long-range forecast fan and red-line odds for the app.

Takes a past-winters ensemble made from today (one scenario per earlier winter's weather,
the GRU on the station record; --method B14 for the CfC) and writes Models/longrange_fan.json, which page 10 of the
app draws (kinneret_app/fan_card.py):

  build(members, errors, weights, start, seasonal)  -> the file's content (a dict)
  write(fan, path)                                  -> plain JSON, written atomically

The numbers are cfc_bands.bands: each past winter's scenario, weighted by how well its
season rain matches the SEAS5 forecast published by the start (seas5.member_weights,
through cfc_fan_eval.weights_for), plus the model's own errors at the same horizon and
season from earlier years. Tested on 2011-2025 (docs/experiments/cfc_fan_eval).

Monthly refresh, after SEAS5 comes out on the 5th:

  cd Automation
  CFC_HORIZONS=monthly CFC_FUTURE=1 CFC_YEARS=<this year> CFC_OUT=../docs/experiments/cfc_today_monthly \\
      python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seeds 3
  python fan_today.py                      # latest start in cfc_today_monthly -> Models/longrange_fan.json

The backtest (--back, cfc_monthly) must have the same horizons: 7/13/26 d, every month to
12 months, and 130/260 d (CFC_HORIZONS=monthly, CFC_YEARS=2011..2025, made 2026-10-17).
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfc_bands as cb                      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Models" / "longrange_fan.json"
LINES = {"red": -213.0, "upper": -208.8}
LEVELS = (0.5, 0.8, 0.9)
MODELS = {"B14gru": "GRU network on the IMS station record, past winters weighted by SEAS5",
          "B14": "CfC liquid network on the IMS station record, past winters weighted by SEAS5"}
METHOD = "B14gru"           # the app's fan since 2026-10-17: the GRU ties the CfC and trains in a third of the time


def build(members: pd.DataFrame, errors: pd.DataFrame, weights: pd.Series, start: str,
          seasonal: dict, made_on: str = None, method: str = METHOD) -> dict:
    m = members[members["start"] == start]
    o = cb.bands(m.assign(weight=weights.loc[m.index]), levels=LEVELS, errors=errors,
                 thresholds=LINES).set_index("H").sort_index()
    t0 = pd.Timestamp(start)
    horizons = [{"H": int(H), "date": str((t0 + pd.Timedelta(days=int(H))).date()), "median": float(r.pred),
                 **{f"{s}_{int(p * 100)}": float(r[f"{s}_{int(p * 100)}"]) for p in LEVELS for s in ("lo", "hi")},
                 "p_red": float(r.p_red), "p_upper": float(r.p_upper)} for H, r in o.iterrows()]
    paths = m.assign(Y=m["weather"].str.split("|").str[1].astype(int)).pivot_table(index="Y", columns="H",
                                                                                      values="pred")
    end = paths[paths.columns.max()]
    scenarios = [{"kind": kind, "winter": f"{Y}-{str(Y + 1)[2:]}",
                  "path": [{"H": int(H), "level": float(v)} for H, v in paths.loc[Y].items()]}
                 for kind, Y in (("wettest", int(end.idxmax())), ("driest", int(end.idxmin())))]
    return {"made_on": made_on or str(date.today()), "start": start, "level0": float(m["level0"].iloc[0]),
            "model": MODELS[method], "seasonal": seasonal, "lines": dict(LINES), "horizons": horizons,
            "scenarios": scenarios}


def write(fan: dict, path: Path = OUT) -> None:
    data = json.dumps(fan, indent=1).encode("utf-8")
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def seasonal_lean(S, era_m, start: pd.Timestamp) -> dict:
    """SEAS5's season rain ratio for the start's forecast, and its rank among the same
    calendar month's forecasts since 1993 (normals from earlier years)."""
    import cfc_fan_eval as fe
    import seas5
    init = seas5.init_for(start)
    anom = seas5.anomalies(S, start.year)
    normal = fe.normals(era_m, start.year)

    def ratio(i):
        f = anom[anom["init"] == i]
        wn = normal.reindex(pd.DatetimeIndex(f["target"]).month).to_numpy()
        return float((f["rain_ratio"].to_numpy() * wn).sum() / wn.sum()) if len(f) else np.nan
    now = ratio(init)
    past = [r for r in (ratio(pd.Timestamp(y, init.month, 1)) for y in range(1993, init.year)) if np.isfinite(r)]
    return {"source": "ECMWF SEAS5", "init": init.strftime("%Y-%m"), "season_ratio": now,
            "rank": int(sum(p < now for p in past) + 1), "of": len(past) + 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=str(ROOT / "docs" / "experiments" / "cfc_today_monthly"))
    ap.add_argument("--back", default=str(ROOT / "docs" / "experiments" / "cfc_monthly"),
                    help="backtest ensemble folder: the model's earlier errors")
    ap.add_argument("--method", default=METHOD, choices=sorted(MODELS))
    ap.add_argument("--start", default=None, help="default: the latest start in --today")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    import cfc_fan_eval as fe
    import cfc_tournament as ct
    import cfc_tournament_report as r
    import seas5
    ct.TABLE = "ims"
    ct.L.set_features(None)
    bench = ct.ims_table().set_index("date")["rainfall_mm"]
    ct.L.set_features(ct.L.NO_INTENSITY)
    era = ct.L.build_long_table().set_index("date")["rainfall_mm"]
    S = seas5.load()
    today = r.load(Path(a.today))
    today = today[today["method"] == a.method]
    back = r.load(Path(a.back))
    back = back[(back["method"] == a.method) & (back["year"] < today["year"].min())]
    start = a.start or max(today.loc[today["weather"].str.startswith("ens|"), "start"])
    mem = today[today["weather"].str.startswith("ens|") & (today["start"] == start)]
    errors = pd.concat([back[back["weather"] == "obs"], today[today["weather"] == "obs"]])
    w = fe.weights_for(mem, S, fe.monthly(era), fe.monthly(bench))
    fan = build(mem, errors, w, start, seasonal_lean(S, fe.monthly(era), pd.Timestamp(start)),
                method=a.method)
    write(fan, Path(a.out))
    h = {x["H"]: x for x in fan["horizons"]}
    print(f"fan from {start} (level {fan['level0']:.2f}) -> {a.out}")
    for H, x in h.items():
        print(f"  {H:>3} d  median {x['median']:.2f}  80% {x['lo_80']:.2f}..{x['hi_80']:.2f}  "
              f"P(< -213) {x['p_red']:.0%}")


if __name__ == "__main__":
    main()
