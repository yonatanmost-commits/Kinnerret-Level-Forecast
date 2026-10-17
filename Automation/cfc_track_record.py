"""
cfc_track_record.py  -  "why should we believe you": the shipped fan's backtest, one row per autumn.

Reads the SEAS5-weighted CfC fan backtest (cfc_fan_eval.py, fan_B14_seas5.csv) and writes:

  track_record.csv     one row per test autumn 2011-2025: the first October start with a fan, the
                       6-month (182 d) and 12-month (365 d) median, 50% and 80% ranges and
                       P(below -213 m), the level that happened, inside-80% flags, and that
                       winter's Oct-Mar rain as % of normal. 2011-13 have no fan (too few
                       earlier errors to pool; fan = False): median only. 182 d is interpolated linearly
                       between the 130 d and 260 d bench horizons, as the app's card does
                       (kinneret_app/fan_card.py _at); the actual level is the reading nearest that day (within 3 days).
  reliability_red.csv  P(level < -213 m) said vs happened per band, for each horizon and
                       pooled over 130/260/365 d (cfc_fan_eval's table), with the number of
                       forecasts and of distinct winters behind each band (weekly starts of
                       one winter are not independent).

Normal rain = mean Oct-Mar total of the complete winters in the gold record (2002-03 on).

    python Automation/cfc_track_record.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FAN = ROOT / "docs" / "experiments" / "cfc_fan_eval" / "fan_B14_seas5.csv"
GOLD = ROOT / "Gold Data" / "kinneret_gold_features.csv"
OUT = ROOT / "docs" / "experiments" / "cfc_fan_eval"
RED = -213.0
COLS = ["pred", "lo_50", "hi_50", "lo_80", "hi_80", "p_red"]
BANDS = [0, .1, .3, .5, .7, .9, 1.0001]
LABELS = ["0-10%", "10-30%", "30-50%", "50-70%", "70-90%", "90-100%"]


def at(rows: pd.DataFrame, days: int) -> pd.Series:
    """The fan at `days`, interpolated between bench horizons like the app's card."""
    rows = rows.sort_values("H")
    if len(rows) < 2 or rows[COLS[1:]].isna().all().all():          # no fan yet: median only
        return pd.Series({c: float(np.interp(days, rows["H"], rows[c])) if c == "pred" else np.nan for c in COLS})
    return pd.Series({c: float(np.interp(days, rows["H"], rows[c])) for c in COLS})


def winter_rain(gold: pd.DataFrame) -> pd.Series:
    r = gold["rainfall_mm"]
    w = r[r.index.month.isin([10, 11, 12, 1, 2, 3])]
    key = np.where(w.index.month >= 10, w.index.year, w.index.year - 1)
    days = w.groupby(key).count()
    tot = w.groupby(key).sum()[days >= 180]
    return tot / tot.mean() * 100


def track_record(fan: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    lv = gold["level_m"].dropna()
    level = lambda d: lv.iloc[abs(lv.index - d).argmin()] if abs(lv.index - d).min() <= pd.Timedelta(days=3) else np.nan
    rain = winter_rain(gold)
    out = []
    for y in sorted(fan["year"].unique()):
        oct_ = fan[(fan.year == y) & (fan.start.dt.month == 10) & fan.H.isin([130, 260])]
        full = oct_.dropna(subset=COLS).groupby("start").size()
        start = full[full == 2].index.min() if (full == 2).any() else oct_["start"].min()
        g = fan[(fan.start == start) & fan.H.isin([130, 260, 365])]
        row = {"autumn": int(y), "start": start.date(), "level_start": level(start),
               "fan": bool(g[COLS].notna().all(axis=1).any())}
        for days, tag in ((182, "6m"), (365, "12m")):
            f = at(g[g.H.isin([130, 260])], days) if days != 365 else g[g.H == 365][COLS].iloc[0]
            obs = level(start + pd.Timedelta(days=days))
            row.update({f"{tag}_date": (start + pd.Timedelta(days=days)).date(),
                        f"{tag}_median": f["pred"], f"{tag}_lo50": f["lo_50"], f"{tag}_hi50": f["hi_50"],
                        f"{tag}_lo80": f["lo_80"], f"{tag}_hi80": f["hi_80"], f"{tag}_p_red": f["p_red"],
                        f"{tag}_actual": obs,
                        f"{tag}_inside80": None if pd.isna(obs) or pd.isna(f["lo_80"]) else bool(f["lo_80"] <= obs <= f["hi_80"]),
                        f"{tag}_below_red": None if pd.isna(obs) else bool(obs < RED)})
        row["oct_mar_rain_pct_normal"] = rain.get(int(y))
        out.append(row)
    return pd.DataFrame(out).round(3)


def reliability(fan: pd.DataFrame) -> pd.DataFrame:
    o = fan[fan.H.isin([130, 260, 365])].dropna(subset=["p_red", "obs"]).copy()
    o["hit"] = o["obs"] < RED
    o["band"] = pd.cut(o["p_red"], BANDS, labels=LABELS, right=False)
    rows = []
    for name, g in [("130-365 pooled", o)] + [(f"{h} d", o[o.H == h]) for h in (130, 260, 365)]:
        for band, b in g.groupby("band", observed=True):
            rows.append({"horizon": name, "p_red": band, "forecasts": len(b), "winters": b["year"].nunique(),
                         "said": b["p_red"].mean(), "happened": b["hit"].mean()})
    return pd.DataFrame(rows).round(3)


def main():
    fan = pd.read_csv(FAN, parse_dates=["start"])
    gold = pd.read_csv(GOLD, parse_dates=[0], index_col=0)
    t, r = track_record(fan, gold), reliability(fan)
    t.to_csv(OUT / "track_record.csv", index=False)
    r.to_csv(OUT / "reliability_red.csv", index=False)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
