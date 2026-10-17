"""
seas5.py  -  ECMWF SEAS5 seasonal forecasts as "weather ahead", with no look-ahead.

  load()          Raw Data/SEAS5/*.nc -> ensemble-mean table, one row per (init, lead):
                  rain (mm/day) and 2 m temperature (C), averaged over the 4 cells
                  around the lake (32.5-33.5 N, 35.5-36.5 E)
  init_for(day)   the latest forecast published by that day (released on the 5th)
  anomalies(t, Y) rain ratio and temperature anomaly per (init, lead), against SEAS5's
                  own mean for that start month and lead over years before Y (its bias
                  cancels, and no later year enters)
  adjust_clim(clim, start, anom)
                  a day-of-year climatology with the forecast months after `start`
                  rescaled: rain x ratio, temperatures + anomaly. Months past the
                  6-month reach stay average.

Caveat: the climatology is indexed by day of year, so for a 365-day horizon the last
days that fall in the start's own month next year take the first forecast month's
anomaly. A few days at the very end of the longest horizon. The relay (A, G) rolls the
starts that share a forecast out together, adjusted from the group's first start: for
the later starts the extra adjusted days are already in their past (used only by that
same wrap at 365 days).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw Data" / "SEAS5"
RELEASE_DAY = 5                                    # SEAS5 goes out on the 5th
RATIO_CLIP = (0.25, 4.0)
TEMPS = ["temp_mean_C", "temp_max_C", "temp_min_C"]


def load(folder: Path = RAW) -> pd.DataFrame:
    import xarray as xr
    rows = []
    for p in sorted(folder.glob("seas5_*.nc")):
        ds = xr.open_dataset(p)
        m = ds.mean(dim=["number", "latitude", "longitude"])
        df = m.to_dataframe().reset_index()
        rows.append(pd.DataFrame({
            "init": pd.to_datetime(df["forecast_reference_time"]),
            "lead": df["forecastMonth"].astype(int),
            "rain_mm_day": df["tprate"] * 86400 * 1000,
            "t2m_C": df["t2m"] - 273.15}))
    t = pd.concat(rows, ignore_index=True).dropna()
    t["target"] = [i + pd.DateOffset(months=int(l) - 1) for i, l in zip(t["init"], t["lead"])]
    return t


def init_for(day: pd.Timestamp, release_day: int = RELEASE_DAY) -> pd.Timestamp:
    first = pd.Timestamp(day.year, day.month, 1)
    return first if day.day > release_day else first - pd.DateOffset(months=1)


def anomalies(t: pd.DataFrame, test_year: int) -> pd.DataFrame:
    t = t.assign(m=t["init"].dt.month)
    base = (t[t["init"].dt.year < test_year].groupby(["m", "lead"])[["rain_mm_day", "t2m_C"]].mean()
            .rename(columns={"rain_mm_day": "rain_base", "t2m_C": "t2m_base"}))
    a = t.join(base, on=["m", "lead"])
    a["rain_ratio"] = (a["rain_mm_day"] / a["rain_base"]).clip(*RATIO_CLIP)
    a["t2m_anom"] = a["t2m_C"] - a["t2m_base"]
    return a.drop(columns="m")


def observed_ratio(daily_rain: pd.Series, test_year: int) -> pd.Series:
    """Each month's rain total over the mean of that calendar month in years before
    test_year (index: month start). The partner of SEAS5's rain_ratio for calibration."""
    m = daily_rain.resample("MS").sum(min_count=20)
    base = m[m.index.year < test_year].groupby(m[m.index.year < test_year].index.month).mean()
    return (m / base.reindex(m.index.month).to_numpy()).dropna()


def calibration_slopes(anom: pd.DataFrame, month_obs: pd.Series, test_year: int) -> dict:
    """Per lead month, the least-squares slope of observed rain ratio on SEAS5's ratio,
    through (1, 1), over forecast months fully observed before test_year. SEAS5's
    swing is far smaller than real winters'; the slope says how much to stretch (or
    shrink) it, given how often it was right."""
    a = anom[anom["target"] < pd.Timestamp(test_year, 1, 1)].copy()
    a["obs"] = month_obs.reindex(pd.DatetimeIndex(a["target"])).to_numpy()
    a = a.dropna(subset=["obs", "rain_ratio"])
    out = {}
    for lead, g in a.groupby("lead"):
        x, y = g["rain_ratio"] - 1, g["obs"] - 1
        out[int(lead)] = float(np.clip((x * y).sum() / max((x * x).sum(), 1e-12), 0.0, 3.0))
    return out


def calibrate(anom: pd.DataFrame, slopes: dict) -> pd.DataFrame:
    """rain_ratio -> 1 + slope(lead) x (rain_ratio - 1); temperature unchanged."""
    s = anom["lead"].map(slopes).fillna(1.0)
    return anom.assign(rain_ratio=(1 + s * (anom["rain_ratio"] - 1)).clip(*RATIO_CLIP))


def season_calibrate(anom: pd.DataFrame, daily_rain: pd.Series, test_year: int) -> pd.DataFrame:
    """Calibrate on the SEASON, not the month: the lake answers a season's total rain.

    Per forecast (init), the season ratio is the rain-weighted mean of its monthly
    ratios (wet months count most; weights = normal monthly rain, earlier years). The
    slope of the observed season ratio on SEAS5's, through (1, 1), is fitted on seasons
    fully observed before test_year, and each forecast gets ONE calibrated ratio,
    1 + slope x (season ratio - 1), for all its months. Slope clipped to [0, 4]."""
    m = daily_rain.resample("MS").sum(min_count=20)
    early = m[m.index.year < test_year]
    normal = early.groupby(early.index.month).mean()
    a = anom.assign(w=normal.reindex(pd.DatetimeIndex(anom["target"]).month).to_numpy())
    a["obs"] = (m / normal.reindex(m.index.month).to_numpy()).reindex(pd.DatetimeIndex(a["target"])).to_numpy()
    wmean = lambda g, c: (g[c] * g["w"]).sum() / g["w"].sum()
    seasons = a.groupby("init").apply(lambda g: pd.Series({
        "fc": wmean(g, "rain_ratio"),
        "obs": wmean(g, "obs") if g["obs"].notna().all() else np.nan,
        "end": g["target"].max()}), include_groups=False)
    fit = seasons[(seasons["end"] < pd.Timestamp(test_year, 1, 1)) & seasons["obs"].notna()]
    x, y = fit["fc"] - 1, fit["obs"] - 1
    slope = float(np.clip((x * y).sum() / max((x * x).sum(), 1e-12), 0.0, 4.0))
    ratio = (1 + slope * (seasons["fc"] - 1)).clip(*RATIO_CLIP)
    return anom.assign(rain_ratio=anom["init"].map(ratio).to_numpy())


def member_weights(forecast: float, member_ratio: pd.Series, seasons: pd.DataFrame,
                   test_year: int) -> pd.Series:
    """Weights for past-winter scenarios given SEAS5's season forecast (importance weights).

    seasons: one row per past forecast season (year, fc = SEAS5's season rain ratio, obs =
    the season ratio that fell). On seasons before test_year, fit obs ~ 1 + b (fc - 1) with
    residual spread s, and take the climatological spread c of obs. A scenario whose season
    ratio is r gets N(r; 1 + b (forecast - 1), s) / N(r; 1, c): how much likelier its
    wetness is under the forecast than under plain climatology. A useless forecast (b ~ 0,
    s ~ c) leaves the weights near 1; a skilful one tilts them. Returned mean-1."""
    past = seasons[seasons["year"] < test_year].dropna(subset=["fc", "obs"])
    x, y = past["fc"] - 1, past["obs"] - 1
    b = float((x * y).sum() / max((x * x).sum(), 1e-12))
    c = float(np.sqrt((y ** 2).mean()))
    s = max(float(np.sqrt(((y - b * x) ** 2).mean())), 0.1 * c)
    # a slope fitted on a handful of seasons can be chance: shrink it by its own
    # certainty, b t^2 / (1 + t^2) with t = b / se, so noise barely tilts the weights
    t2 = b ** 2 * max((x * x).sum(), 1e-12) / s ** 2
    b *= t2 / (1 + t2) if len(past) > 2 else 0.0
    s = float(np.sqrt(max(c ** 2 - b ** 2 * float((x * x).mean()), (0.1 * c) ** 2)))
    mu = 1 + b * (forecast - 1)
    r = member_ratio.astype(float)
    logw = -0.5 * ((r - mu) / s) ** 2 + 0.5 * ((r - 1) / c) ** 2 + np.log(c / s)
    w = np.exp(logw - logw.max())
    return w / w.mean()


def adjust_clim(clim: pd.DataFrame, start: pd.Timestamp, anom: pd.DataFrame,
                release_day: int = RELEASE_DAY) -> pd.DataFrame:
    init = init_for(start, release_day)
    f = anom[anom["init"] == init]
    out = clim.copy()
    if f.empty:
        return out
    for _, r in f.iterrows():
        m0 = init + pd.DateOffset(months=int(r["lead"]) - 1)
        days = pd.date_range(m0, m0 + pd.offsets.MonthEnd(0))
        days = days[days > start]
        if days.empty:
            continue
        doy = np.unique(np.minimum(days.dayofyear, 366))
        doy = doy[np.isin(doy, out.index)]
        if "rainfall_mm" in out:
            out.loc[doy, "rainfall_mm"] = clim.loc[doy, "rainfall_mm"] * r["rain_ratio"]
        for c in TEMPS:
            if c in out:
                out.loc[doy, c] = clim.loc[doy, c] + r["t2m_anom"]
    return out
