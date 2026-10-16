"""
cfc_bands.py  -  forecast ranges from the errors of earlier forecasts.

For each forecast (start day s, horizon H) the band is the forecast plus the
quantiles of past errors (obs - pred) that
  * had the same horizon H,
  * started within +-doy_window days of s's day of year (errors depend on season:
    a start before the rains carries the whole winter's uncertainty), and
  * were already OBSERVED by day s (their start + H <= s), so nothing from the
    future of the forecast leaks in.
A band needs errors from at least min_years distinct years; otherwise it is NaN.

The band is empirical (split-conformal in spirit): it inherits the model's real
error, bias included, instead of assuming a shape.

Use:  out = bands(records, levels=(0.5, 0.8, 0.9))  ->  adds lo_50, hi_50, lo_80, ...
"""
import numpy as np
import pandas as pd


def bands(df: pd.DataFrame, levels=(0.5, 0.8, 0.9), doy_window: int = 45,
          min_years: int = 3) -> pd.DataFrame:
    """df: one row per forecast with year, start (date or ISO str), H, pred, obs."""
    out = df.copy()
    start = pd.to_datetime(out["start"])
    end = start + pd.to_timedelta(out["H"], unit="D")
    doy = start.dt.dayofyear.to_numpy()
    resid = (out["obs"] - out["pred"]).to_numpy(float)
    year = start.dt.year.to_numpy()
    ok = np.isfinite(resid)
    qs = sorted({q for p in levels for q in ((1 - p) / 2, 1 - (1 - p) / 2)})
    Q = np.full((len(out), len(qs)), np.nan)
    for H, idx in out.groupby("H").indices.items():
        s_ns = start.to_numpy()[idx]
        e_ns = end.to_numpy()[idx]
        d = doy[idx]
        r, y, good = resid[idx], year[idx], ok[idx]
        for j in range(len(idx)):
            gap = np.abs(d - d[j])
            near = np.minimum(gap, 365 - gap) <= doy_window
            pool = good & near & (e_ns <= s_ns[j])
            if len(np.unique(y[pool])) < min_years:
                continue
            Q[idx[j]] = np.quantile(r[pool], qs)
    pred = out["pred"].to_numpy(float)
    for p in levels:
        k = int(round(p * 100))
        out[f"lo_{k}"] = pred + Q[:, qs.index((1 - p) / 2)]
        out[f"hi_{k}"] = pred + Q[:, qs.index(1 - (1 - p) / 2)]
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
