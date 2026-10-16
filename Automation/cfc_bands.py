"""
cfc_bands.py  -  forecast ranges from scenarios and from the errors of earlier forecasts.

    bands(forecasts, levels, doy_window, min_years, errors=None, gamma=0.0)

forecasts: one row per forecast (start, H, pred, obs, year), or SEVERAL rows per
(start, H) when the forecast is a set of scenarios (e.g. one per past winter's weather).
An optional `weight` column weights the scenarios (e.g. by a seasonal forecast); the
band and the median then use weighted quantiles. Missing = equal weights.
For each (start, H) the band is the spread of

    scenario + model error

where the model errors (obs - pred) come from `errors` (default: the forecasts
themselves) and are only those that
  * had the same horizon H,
  * started within +-doy_window days of the start's day of year (errors depend on
    season: a start before the rains carries the whole winter), and
  * were already OBSERVED on the start day (their start + H <= start), so nothing from
    the forecast's future leaks in.
With one row per forecast this is an empirical, split-conformal band around the point
forecast. With scenarios and `errors` = the same model's forecasts given the actual
weather, the scenarios carry the weather uncertainty and the errors the model's own.
A band needs errors from at least min_years distinct years, else it is NaN.

gamma > 0 makes the band self-correcting (adaptive conformal inference, Gibbs & Candes
2021): per horizon, in time order, each outcome that becomes known nudges the level
used for the quantiles, wider after a miss and narrower after a hit, so the band
tracks the coverage it promises even when errors drift. Feedback arrives only when an
outcome is observed (start + H), never earlier.

Returns one row per (start, H): year, start, H, pred (median scenario), obs, members,
lo_<k>, hi_<k> for each level k (e.g. 80 -> lo_80, hi_80).
"""
import numpy as np
import pandas as pd


def _wquantile(draws: np.ndarray, cw: np.ndarray, q):
    """Weighted quantiles of sorted draws, cw = their cumulative weights scaled to 0..1
    at the draw midpoints (equal weights reproduce np.quantile's 'hazen' rule)."""
    return np.interp(q, cw, draws)


def _quantiles(draws: np.ndarray, cw: np.ndarray, a: float):
    """Central band leaving a total share a outside; a <= 0 widens past the extremes."""
    if a <= 0:
        span = draws[-1] - draws[0]
        return draws[0] - span * (-a), draws[-1] + span * (-a)
    a = min(a, 0.9999)
    return tuple(_wquantile(draws, cw, [a / 2, 1 - a / 2]))


def bands(forecasts: pd.DataFrame, levels=(0.5, 0.8, 0.9), doy_window: int = 45,
          min_years: int = 3, errors: pd.DataFrame = None, gamma: float = 0.0) -> pd.DataFrame:
    errors = forecasts if errors is None else errors
    f = forecasts.assign(_t=pd.to_datetime(forecasts["start"]))
    e = errors.assign(_t=pd.to_datetime(errors["start"]))
    e = e.assign(_end=e["_t"] + pd.to_timedelta(e["H"], unit="D"), _res=e["obs"] - e["pred"],
                 _doy=e["_t"].dt.dayofyear, _yr=e["_t"].dt.year)
    e = e[np.isfinite(e["_res"])]
    out = []
    for H, fh in f.groupby("H"):
        eh = e[e["H"] == H]
        end, res, edoy, eyr = (eh["_end"].to_numpy(), eh["_res"].to_numpy(),
                               eh["_doy"].to_numpy(), eh["_yr"].to_numpy())
        alpha = {p: 1 - p for p in levels}          # current outside share per level
        pending = []                                # (known on, level, inside)
        for t, g in sorted(fh.groupby("_t"), key=lambda kv: kv[0]):
            if gamma:
                still = []
                for known, p, inside in pending:
                    if known <= t:
                        alpha[p] += gamma * ((1 - p) - (not inside))
                    else:
                        still.append((known, p, inside))
                pending = still
            g = g.dropna(subset=["pred"])
            members = g["pred"].to_numpy(float)
            mw = g["weight"].to_numpy(float) if "weight" in g else np.ones(len(members))
            obs = g["obs"].iloc[0] if len(g) else np.nan
            if not len(members):
                continue
            o = np.argsort(members)
            mcw = (np.cumsum(mw[o]) - mw[o] / 2) / mw.sum()
            row = {"year": g["year"].iloc[0], "start": g["start"].iloc[0], "H": H, "obs": obs,
                   "pred": float(_wquantile(members[o], mcw, 0.5)), "members": len(members)}
            gap = np.abs(edoy - t.dayofyear)
            pool = (np.minimum(gap, 365 - gap) <= doy_window) & (end <= np.datetime64(t))
            if len(members) and len(np.unique(eyr[pool])) >= min_years:
                d = (members[:, None] + res[pool][None, :]).ravel()
                dw = np.repeat(mw, pool.sum())
                o = np.argsort(d)
                draws, dw = d[o], dw[o]
                cw = (np.cumsum(dw) - dw / 2) / dw.sum()
                for p in levels:
                    lo, hi = _quantiles(draws, cw, alpha[p])
                    k = int(round(p * 100))
                    row[f"lo_{k}"], row[f"hi_{k}"] = lo, hi
                    if gamma and np.isfinite(obs):
                        pending.append((t + pd.Timedelta(days=int(H)), p, lo <= obs <= hi))
            out.append(row)
    out = pd.DataFrame(out)
    for p in levels:                                # columns exist even when all NaN
        k = int(round(p * 100))
        for c in (f"lo_{k}", f"hi_{k}"):
            if c not in out:
                out[c] = np.nan
    return out


def coverage(out: pd.DataFrame, levels=(0.5, 0.8, 0.9)) -> pd.DataFrame:
    """Share of outcomes inside each band, per horizon (rows with a band only)."""
    rows = []
    for p in levels:
        k = int(round(p * 100))
        b = out.dropna(subset=[f"lo_{k}", "obs"])
        inside = (b["obs"] >= b[f"lo_{k}"]) & (b["obs"] <= b[f"hi_{k}"])
        width = b[f"hi_{k}"] - b[f"lo_{k}"]
        for H, g in inside.groupby(b["H"]):
            rows.append({"level": p, "H": H, "coverage": g.mean(), "width": width[g.index].median(), "n": len(g)})
    return pd.DataFrame(rows)
