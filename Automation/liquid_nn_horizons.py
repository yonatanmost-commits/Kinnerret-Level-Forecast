"""
liquid_nn_horizons.py  -  Long-horizon and red-line tests: liquid society vs GBR.

Both models are the two-stage forecaster of 08_train_forecast_model.run_cv
(S1 met -> inflow, S2 -> daily volume change), with level_m = YESTERDAY's level
(see liquid_nn_compare.lag_level). Here they are rolled forward day by day with
ALL state chained: S1 inflow lags, S2 predicted inflow, dvol lags and level all
come from the model's own earlier predictions after day 0.

Future weather, two ways:
  obs   the weather that actually happened (upper bound: hydrology skill if the
        weather were known)
  clim  day-of-year climatology of the training years, rolling sums rebuilt from
        observed-then-climatological daily values (what a forecast could do)

Part A - horizons.  Walk-forward folds 2021-2024 (train < test year). Anchors
  every 7th day of the test year; level error at 7/13/26/130/260/365 days,
  against persistence and the training years' mean level change for that window.

Part B - red line.  Every crossing of -213.0 m in the gold table. Leave-one-year-
  out training (as talk_freeze_run.measure_crossings). A forecast issued every
  day from the last ERA5 rain >= 5 mm to the day before the crossing; scored by
  |predicted - actual days to the crossing|, per band of days of warning, next to
  the page's anomaly-scaled recession method on the same days.

Run:  python Automation/liquid_nn_horizons.py --cell cfc --seeds 7
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import liquid_nn_compare as lnc            # also loads 08 as lnc.t08
import redline_backtest as rb
from model_lib import (
    GBRegressor, S1_FEATURES, S1_TARGET, S2_FEATURES, S2_TARGET,
    signed_log1p_transform, inv_signed_log1p_transform,
)

t08 = lnc.t08
OUT_DIR = t08.BASE_DIR / "docs" / "experiments"
ERA5_FILE = t08.BASE_DIR / "Silver Data" / "Meteorological" / "era5_kinneret_daily.csv"

HORIZONS = [7, 13, 26, 130, 260, 365]
ANCHOR_EVERY = 7
RED_LINE = -213.0
LAST_RAIN_MM = 5
CAP_DAYS = 400
BACK = 60                                   # history rows before day 0 (>= 45d rain sums)
BANDS = [("0_7", 0, 7), ("7_14", 7, 14), ("14_30", 14, 30), ("30_60", 30, 60),
         ("60_90", 60, 90), ("90_120", 90, 120), ("120_plus", 120, 10**6)]

# daily weather the forecast does not know past day 0
DAILY_MET = ["temp_mean_C", "temp_max_C", "temp_min_C", "humidity_pct", "wind_speed_ms",
             "rainfall_mm", "radiation_MJm2", "vpd_kPa", "et0_mm", "precip_intensity_mm_hr"]
# columns the chain owns after day 0
S1_STATE = ["inflow_lag1_m3", "inflow_lag2_m3"]
S2_STATE = ["predicted_inflow_m3", "level_m", "volume_change_lag1_Mm3", "volume_change_lag2_Mm3"]


def rebuild_rolling(f: pd.DataFrame) -> pd.DataFrame:
    """Rolling/lag weather features from daily values (formulas of 07_build_gold_features)."""
    r, e = f["rainfall_mm"], f["et0_mm"]
    for n in (7, 14, 21, 30, 45):
        f[f"rainfall_{n}d_mm"] = r.rolling(n, min_periods=1).sum()
    f["et0_7d_mm"] = e.rolling(7, min_periods=1).sum()
    f["et0_14d_mm"] = e.rolling(14, min_periods=1).sum()
    f["moisture_balance_7d_mm"] = f["rainfall_7d_mm"] - f["et0_7d_mm"]
    f["moisture_balance_14d_mm"] = f["rainfall_14d_mm"] - f["et0_14d_mm"]
    for k in (1, 2, 3):
        f[f"rainfall_lag{k}_mm"] = r.shift(k)
    return f


def doy_climatology(df: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
    """Mean of every numeric column by day of year over the training rows."""
    tr = df[train_mask]
    num = tr.select_dtypes("number")
    return num.groupby(tr["date"].dt.dayofyear).mean().reindex(range(1, 367)).interpolate()


def extend(df: pd.DataFrame, days: int, clim: pd.DataFrame) -> pd.DataFrame:
    """Append `days` future rows filled from climatology (weather past the data end)."""
    dates = pd.date_range(df["date"].max() + pd.Timedelta(days=1), periods=days)
    ext = clim.loc[dates.dayofyear].reset_index(drop=True)
    ext.insert(0, "date", dates)
    for c in (S1_TARGET, S2_TARGET, "level_m", "volume_Mm3"):
        ext[c] = np.nan
    return pd.concat([df, ext[df.columns.intersection(ext.columns)]], ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Two-stage forecasters with a common rollout interface
# ─────────────────────────────────────────────────────────────────────────────

class _Stage:
    """One stage: fit on rows of a frame, predict on raw (anchors, rows, feats) windows."""

    def __init__(self, feats, kind, cell, seeds, seq_len):
        self.feats, self.kind, self.cell = feats, kind, cell
        self.seeds, self.L = seeds, seq_len

    def fit(self, df, idx, y):
        X = df[self.feats].to_numpy(float)
        if self.kind == "gbr":
            self.m = t08.GBRegressor(**t08.GBR_CV_PARAMS).fit(X[idx], y)
            return self
        # a tree cannot predict outside its training targets; hold the net to the same range
        self.y_lo, self.y_hi = float(np.min(y)), float(np.max(y))
        self.mu = np.nanmean(X[idx], axis=0)
        self.sd = np.nanstd(X[idx], axis=0) + 1e-8
        Z = np.nan_to_num((X - self.mu) / self.sd, nan=0.0).astype(np.float32)
        self.members = [lnc.LiquidRegressor(seq_len=self.L, seed=s,
                                            cell=lnc._member_cell(self.cell, s)).fit(Z, idx, y)
                        for s in range(self.seeds)]
        return self

    def predict_last(self, raw: np.ndarray) -> np.ndarray:
        """raw: (A, L, F) unstandardised window ending at the day to predict."""
        if self.kind == "gbr":
            return self.m.predict(raw[:, -1, :])
        Z = np.nan_to_num((raw - self.mu) / self.sd, nan=0.0).astype(np.float32)
        W = torch.tensor(Z)
        out = []
        for m in self.members:
            m.net.eval()
            with torch.no_grad():
                out.append(m.net(W).numpy() * m.y_sd + m.y_mu)
        return np.clip(np.mean(out, axis=0), self.y_lo, self.y_hi)


class TwoStage:
    def __init__(self, kind, cell="cfc", seeds=7, seq_len=14):
        self.kind = kind
        L = 1 if kind == "gbr" else seq_len
        self.L = L
        self.s1 = _Stage(S1_FEATURES, kind, cell, seeds, L)
        self.s2 = _Stage(S2_FEATURES, kind, cell, seeds, L)

    def fit(self, df: pd.DataFrame, train_mask: np.ndarray):
        ok1 = df[S1_FEATURES + [S1_TARGET]].notna().all(axis=1).to_numpy() & train_mask
        i1 = np.where(ok1)[0]
        y1 = df[S1_TARGET].to_numpy(float)[i1]
        self.s1.fit(df, i1, np.log1p(np.clip(y1, 0, None)) if self.kind != "gbr" else y1)
        d2 = df.copy()
        d2["predicted_inflow_m3"] = d2[S1_TARGET]           # actual = training proxy
        ok2 = d2[S2_FEATURES + [S2_TARGET]].notna().all(axis=1).to_numpy() & train_mask
        i2 = np.where(ok2)[0]
        self.s2.fit(d2, i2, signed_log1p_transform(d2[S2_TARGET].to_numpy(float)[i2]))
        return self

    def s1_out(self, p):
        return np.clip(np.expm1(p) if self.kind != "gbr" else p, 0, None)


def rollout(model: TwoStage, df: pd.DataFrame, anchors: np.ndarray, H: int,
            weather: str, clim: pd.DataFrame, bathy: list) -> np.ndarray:
    """Chain every state variable from each anchor (positional row) for H days.
    Returns predicted level (A, H): column h-1 = level at anchor + h days."""
    A, P = len(anchors), BACK + H + 1
    cols = list(dict.fromkeys(S1_FEATURES + S2_FEATURES + DAILY_MET +
                              [S1_TARGET, S2_TARGET, "volume_Mm3", "date"]))
    s1_raw = np.empty((A, P, len(S1_FEATURES)))
    s2_raw = np.empty((A, P, len(S2_FEATURES)))
    inflow = np.empty((A, P)); dvol = np.empty((A, P)); vol = np.empty((A, P))
    lvl_now = np.empty(A)
    for k, a in enumerate(anchors):
        f = df.iloc[a - BACK:a + H + 1][cols].reset_index(drop=True).copy()
        if weather == "clim":
            doy = f["date"].dt.dayofyear.to_numpy()
            fut = np.arange(P) > BACK
            for c in DAILY_MET:
                f.loc[fut, c] = clim.loc[doy[fut], c].to_numpy()
            f = rebuild_rolling(f)
        f["predicted_inflow_m3"] = f[S1_TARGET]
        s1_raw[k] = f[S1_FEATURES].to_numpy(float)
        s2_raw[k] = f[S2_FEATURES].to_numpy(float)
        inflow[k] = f[S1_TARGET].to_numpy(float)
        dvol[k] = f[S2_TARGET].to_numpy(float)
        vol[k] = f["volume_Mm3"].to_numpy(float)
        lvl_now[k] = df["level_m"].iat[a + 1]     # level_m is lagged: row a+1 holds level(a)
    i1 = {c: S1_FEATURES.index(c) for c in S1_STATE}
    i2 = {c: S2_FEATURES.index(c) for c in S2_STATE if c in S2_FEATURES}
    vol0 = vol[:, BACK].copy()
    cur = vol0.copy()
    out = np.empty((A, H))
    L = model.L
    for h in range(1, H + 1):
        r = BACK + h
        s1_raw[:, r, i1["inflow_lag1_m3"]] = inflow[:, r - 1]
        s1_raw[:, r, i1["inflow_lag2_m3"]] = inflow[:, r - 2]
        inflow[:, r] = model.s1_out(model.s1.predict_last(s1_raw[:, r - L + 1:r + 1]))
        if "predicted_inflow_m3" in i2:                     # absent in a one-step variant
            s2_raw[:, r, i2["predicted_inflow_m3"]] = inflow[:, r]
        s2_raw[:, r, i2["volume_change_lag1_Mm3"]] = dvol[:, r - 1]
        s2_raw[:, r, i2["volume_change_lag2_Mm3"]] = dvol[:, r - 2]
        s2_raw[:, r, i2["level_m"]] = lvl_now + (np.polyval(bathy, cur) - np.polyval(bathy, vol0)) \
            if h > 1 else lvl_now
        dvol[:, r] = inv_signed_log1p_transform(model.s2.predict_last(s2_raw[:, r - L + 1:r + 1]))
        cur = cur + dvol[:, r]
        out[:, h - 1] = lvl_now + np.polyval(bathy, cur) - np.polyval(bathy, vol0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Part A - horizons
# ─────────────────────────────────────────────────────────────────────────────

def part_horizons(df, models, bathy, weathers):
    print("\n=== Part A: horizons (walk-forward folds, anchors every 7 days) ===", flush=True)
    yrs = df["date"].dt.year.to_numpy()
    true_lvl = df.set_index("date")["level_m"].shift(-1)       # undo the lag: level(date)
    err = {}                                                    # (method, weather, H) -> list
    Hmax = max(HORIZONS)
    for fold, train_yrs, test_yr in t08.CV_FOLDS:
        t0 = time.time()
        trm = np.isin(yrs, train_yrs)
        clim = doy_climatology(df, trm)
        dfx = extend(df, Hmax + 1, clim)
        cand = np.where((yrs == test_yr))[0][::ANCHOR_EVERY]
        cand = cand[~np.isnan(df["volume_Mm3"].to_numpy()[cand])]   # needs a level reading
        # mean level change over each window, training years only
        lvl_tr = true_lvl[(true_lvl.index.year.isin(train_yrs))]
        fitted = {name: mk().fit(df, trm) for name, mk in models.items()}
        for w in weathers:
            for name, m in fitted.items():
                pred = rollout(m, dfx, cand, Hmax, w, clim, bathy)
                for H in HORIZONS:
                    for k, a in enumerate(cand):
                        d0 = df["date"].iat[a]
                        obs = true_lvl.get(d0 + pd.Timedelta(days=H), np.nan)
                        if np.isnan(obs):
                            continue
                        err.setdefault((name, w, H), []).append(pred[k, H - 1] - obs)
                        if name == next(iter(fitted)) and w == weathers[0]:
                            l0 = true_lvl[d0]
                            err.setdefault(("persistence", "-", H), []).append(l0 - obs)
                            chg = (lvl_tr.shift(-H) - lvl_tr)
                            chg = chg[chg.index.dayofyear == d0.dayofyear].mean()
                            err.setdefault(("clim_change", "-", H), []).append(l0 + chg - obs)
        print(f"  fold {fold}: {len(cand)} anchors  ({time.time() - t0:.0f}s)", flush=True)

    rows = []
    for (name, w, H), e in err.items():
        e = np.asarray(e)
        rows.append({"method": name, "weather": w, "H": H, "n": len(e),
                     "mae_m": round(float(np.mean(np.abs(e))), 3),
                     "rmse_m": round(float(np.sqrt(np.mean(e ** 2))), 3),
                     "bias_m": round(float(np.mean(e)), 3)})
    t = pd.DataFrame(rows)
    piv = t.assign(col=t["method"] + "/" + t["weather"]).pivot(index="H", columns="col", values="mae_m")
    print("\n  Level MAE (m) by horizon:\n" + piv.to_string())
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Part B - red-line crossings
# ─────────────────────────────────────────────────────────────────────────────

def _first_below(path: np.ndarray):
    hit = np.where(path < RED_LINE)[0]
    return int(hit[0]) + 1 if len(hit) else None


def recession_days(daily, t, cross_year):
    """The page's anomaly-scaled recession, as talk_freeze_run.measure_crossings."""
    rate = recession_by_doy_cache(daily, cross_year)
    win = t - pd.Timedelta(days=rb.OBS_WINDOW)
    obs_rate = (float(daily[t]) - float(daily[win])) / rb.OBS_WINDOW
    clim_win = np.mean([rate[d.dayofyear] for d in pd.date_range(win, t)])
    scale = float(np.clip(obs_rate / clim_win, *rb.SCALE_CLAMP)) if clim_win < -1e-4 else 1.0
    lvl, d = float(daily[t]), t
    for k in range(1, CAP_DAYS + 1):
        d += pd.Timedelta(days=1)
        lvl += rate[d.dayofyear] * scale
        if lvl < RED_LINE:
            return k
    return None


_rate_cache = {}
def recession_by_doy_cache(daily, year):
    if year not in _rate_cache:
        _rate_cache[year] = rb.recession_by_doy(daily, exclude_year=year)
    return _rate_cache[year]


def part_redline(df, models, bathy, weathers, seq_len):
    print("\n=== Part B: red-line crossings (leave-one-year-out) ===", flush=True)
    lvl = df.set_index("date")["level_m"].shift(-1).dropna()   # level(date)
    below = lvl < RED_LINE
    crossings = list(lvl.index[below & ~below.shift(1, fill_value=True)])
    rain = pd.read_csv(ERA5_FILE, parse_dates=["date"], encoding="utf-8-sig") \
        .set_index("date")["rainfall_mm"]
    daily = rb.load_daily()
    pos = pd.Series(np.arange(len(df)), index=df["date"])
    yrs = df["date"].dt.year.to_numpy()
    recs = []
    for cross in crossings:
        t0 = time.time()
        last_rain = rain[(rain.index < cross) & (rain >= LAST_RAIN_MM)].index.max()
        days = pd.date_range(last_rain, cross - pd.Timedelta(days=1))
        # a forecast needs a level reading on its issue day
        days = days[df["volume_Mm3"].to_numpy()[pos[days].to_numpy()] == df["volume_Mm3"].to_numpy()[pos[days].to_numpy()]]
        anchors = pos[days].to_numpy()
        Y = cross.year
        # leave Y out, and the first seq_len days after it (their windows reach into Y)
        trm = (yrs != Y) & ~((yrs == Y + 1) & (df["date"].dt.dayofyear.to_numpy() <= seq_len))
        clim = doy_climatology(df, trm)
        dfx = extend(df, CAP_DAYS + 1, clim)
        fitted = {name: mk().fit(df, trm) for name, mk in models.items()}
        for k, d0 in enumerate(days):
            recs.append({"cross": str(cross.date()), "issued": str(d0.date()),
                         "lead": (cross - d0).days, "method": "recession", "weather": "-",
                         "pred": recession_days(daily, d0, Y)})
        for w in weathers:
            for name, m in fitted.items():
                path = rollout(m, dfx, anchors, CAP_DAYS, w, clim, bathy)
                for k, d0 in enumerate(days):
                    recs.append({"cross": str(cross.date()), "issued": str(d0.date()),
                                 "lead": (cross - d0).days, "method": name, "weather": w,
                                 "pred": _first_below(path[k])})
        print(f"  crossing {cross.date()}: last rain {last_rain.date()}, {len(days)} forecasts "
              f"({time.time() - t0:.0f}s)", flush=True)

    f = pd.DataFrame(recs)
    f["err"] = (f["pred"] - f["lead"]).abs()
    f["key"] = f["method"] + "/" + f["weather"]
    keys = list(dict.fromkeys(f["key"]))
    wide = f.pivot_table(index=["cross", "issued"], columns="key", values="pred", aggfunc="first")
    lead = f.drop_duplicates(["cross", "issued"]).set_index(["cross", "issued"])["lead"]
    lead = lead.reindex(wide.index)
    table = []
    for band, lo, hi in BANDS:
        sel = (lead > lo) & (lead <= hi)
        b = wide[sel]
        paired = b.dropna()
        row = {"band": band, "issued": int(sel.sum()), "paired_n": len(paired)}
        for k in keys:
            row[f"{k} never"] = int(b[k].isna().sum())
            row[f"{k} paired_mae"] = round(float((paired[k] - lead[paired.index]).abs().mean()), 1) \
                if len(paired) else None
        table.append(row)
    tt = pd.DataFrame(table).set_index("band")
    print("\n  Days-of-warning bands: forecasts that never crossed (cap 400 d), and MAE in days\n"
          "  over the forecasts EVERY method brought to the line (paired):")
    print(tt.to_string())
    return {"crossings": [str(c.date()) for c in crossings], "bands": table,
            "per_crossing": f.groupby(["cross", "key"])["err"].mean().round(1).unstack().to_dict()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", default="cfc", choices=["cfc", "ltc", "mix"])
    ap.add_argument("--seeds", type=int, default=7)
    ap.add_argument("--seq-len", type=int, default=14)
    ap.add_argument("--parts", default="horizons,redline")
    ap.add_argument("--weather", default="obs,clim")
    a = ap.parse_args()

    df = lnc.lag_level(t08.load_data())
    bathy = t08.fit_vol2level_poly()
    weathers = a.weather.split(",")
    lnn = f"liquid_{a.cell}_s{a.seeds}"
    models = {lnn: lambda: TwoStage("lnn", a.cell, a.seeds, a.seq_len),
              "gbr": lambda: TwoStage("gbr")}
    res = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
           "config": vars(a), "level_input": "level_m lagged 1 day; all state chained"}
    if "horizons" in a.parts:
        res["horizons"] = part_horizons(df, models, bathy, weathers)
    if "redline" in a.parts:
        res["redline"] = part_redline(df, models, bathy, weathers, a.seq_len)
    out = OUT_DIR / f"liquid_nn_horizons_{a.cell}_s{a.seeds}.json"
    out.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\n  wrote {out.relative_to(t08.BASE_DIR)}")


if __name__ == "__main__":
    main()
