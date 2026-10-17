"""
c3s.py  -  the C3S multi-model seasonal forecast as "weather ahead", with no look-ahead.

The same interface as seas5.py, so the bench and the fan take either:

  load()          Raw Data/C3S/*.nc (one file per centre / system / year, c3s_fetch.py)
                  plus ECMWF SEAS5 from Raw Data/SEAS5 -> ensemble-mean table, one row
                  per (system, init, lead), averaged over the 4 cells around the lake
  init_for(day)   the latest multi-model forecast published by that day (the 13th)
  anomalies(t, Y) each system's rain ratio and temperature anomaly against ITS OWN mean
                  for that start month and lead over years before Y (seas5.anomalies),
                  then the mean over the systems that forecast that start. Averaging
                  anomalies, not raw rain, keeps one model's bias, or a model missing
                  that year (ukmo 610 stops in 2016, jma 4 in 2020), from moving the mean.
  adjust_clim(clim, start, anom)
                  seas5.adjust_clim with the 13th as release day

Systems are equally weighted; eccc 4 and eccc 5 count as two, as in the C3S product.
"""
from pathlib import Path

import pandas as pd

import seas5

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Raw Data" / "C3S"
RELEASE_DAY = 13                                   # C3S multi-model goes out on the 13th
START_DIMS = ("forecast_reference_time", "indexing_time")


def load(folder: Path = RAW, with_seas5: bool = True) -> pd.DataFrame:
    import xarray as xr
    rows = []
    for p in sorted(folder.glob("*_*_*.nc")):
        system = p.stem.rsplit("_", 1)[0]
        ds = xr.open_dataset(p)
        dim = next(d for d in START_DIMS if d in ds.dims)
        df = ds.mean(dim=["number", "latitude", "longitude"]).to_dataframe().reset_index()
        rows.append(pd.DataFrame({
            "system": system,
            "init": pd.to_datetime(df[dim]),
            "lead": df["forecastMonth"].astype(int),
            "rain_mm_day": df["tprate"] * 86400 * 1000,
            "t2m_C": df["t2m"] - 273.15}))
    t = pd.concat(rows, ignore_index=True).dropna()
    t["target"] = [i + pd.DateOffset(months=int(l) - 1) for i, l in zip(t["init"], t["lead"])]
    if with_seas5:
        t = pd.concat([t, seas5.load().assign(system="ecmwf_51")], ignore_index=True)
    return t


def init_for(day: pd.Timestamp) -> pd.Timestamp:
    return seas5.init_for(day, RELEASE_DAY)


def anomalies(t: pd.DataFrame, test_year: int) -> pd.DataFrame:
    per = pd.concat([seas5.anomalies(g, test_year) for _, g in t.groupby("system")], ignore_index=True)
    per = per.dropna(subset=["rain_ratio", "t2m_anom"])
    out = per.groupby(["init", "lead", "target"]).agg(rain_ratio=("rain_ratio", "mean"),
                                                     t2m_anom=("t2m_anom", "mean"),
                                                     n_systems=("system", "nunique")).reset_index()
    return out.assign(rain_ratio=out["rain_ratio"].clip(*seas5.RATIO_CLIP))


def adjust_clim(clim: pd.DataFrame, start: pd.Timestamp, anom: pd.DataFrame) -> pd.DataFrame:
    return seas5.adjust_clim(clim, start, anom, RELEASE_DAY)
