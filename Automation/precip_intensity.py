# -*- coding: utf-8 -*-
"""
precip_intensity.py  -  Daily peak 1-hour rain intensity at the lake

Owns the precip_intensity_mm_hr feature end to end:

  * daily_intensity(rain10)  - the definition: per 10-minute slot, Tzemach's
    gauge, or the mean of the other lake gauges where it is missing; then the
    largest 6-slot (60-minute) sum ending on each day. Tzemach first since
    2026-10-16, the station gold takes first (docs/experiments/ims_station_bias.md).
  * fetch_rain_10min(start, end) - the same 10-minute gauges from the IMS
    station-data service (no key needed). Tzemach, Lev Kinneret, Kfar Nahum and
    Tiberias publish 10-minute rain; Beit Tzaida publishes 1-minute rain, summed
    into 10-minute slots labelled by their end time, as the manual export did.
  * update_cache(path) - keeps every day up to the last day with a value, and
    recomputes the days after it (through yesterday) from the IMS feed.

Until 2026-04 the 10-minute data came from manual IMS exports through
met_data_wide.csv. The automatic feed reproduces those values exactly
(113/113 days, 2026-01-02 .. 2026-04-24).
"""

import json
import os
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

PRIORITY = "tzamach"
URL = ("https://ims.gov.il/he/envista_station_data_time_range/"
       "{sid}/{channel}/{a:%Y%m%d%H%M}/{b:%Y%m%d%H%M}/1/S/C/M/W")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
TEN_MIN = {8: "tzamach", 115: "lev_kinneret", 233: "kfar_nachum", 502: "tiberias"}
ONE_MIN = {301: "beit_tzaida"}
TRIES = 6


# ── the definition ───────────────────────────────────────────────────────────

def daily_intensity(rain10: pd.DataFrame) -> pd.Series:
    """Peak 60-minute rain (mm/hr) per day, from 10-minute gauge columns."""
    rain10 = rain10.sort_index()
    rain10 = rain10.reindex(pd.date_range(rain10.index.min(), rain10.index.max(), freq="10min"))
    fallback = rain10.mean(axis=1)
    rain = rain10[PRIORITY].fillna(fallback) if PRIORITY in rain10 else fallback
    peak = rain.rolling(6, min_periods=6).sum()
    return peak.groupby(peak.index.strftime("%Y-%m-%d")).max().rename("precip_intensity_mm_hr")


def one_minute_to_ten(rain1: pd.Series) -> pd.Series:
    """1-minute rain -> 10-minute sums, each slot labelled by the minute it ends on."""
    return rain1.resample("10min", label="right", closed="right").sum(min_count=1)


# ── the IMS feed ─────────────────────────────────────────────────────────────

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def fetch_channel(sid: int, channel: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """One gauge channel over [start, end). The service sometimes answers with no
    records at all; a gauge that is down still answers, with '-' values."""
    url = URL.format(sid=sid, channel=channel, a=start, b=end)
    for k in range(TRIES):
        time.sleep(2 + 5 * k)
        try:
            recs = json.loads(_get(url))["data"]["records"]
        except Exception:                       # network blip or a non-JSON page
            recs = []
        if recs:
            idx = pd.to_datetime([r["date"] for r in recs], format="%d/%m/%Y %H:%M")
            vals = pd.to_numeric(pd.Series([r[channel] for r in recs]), errors="coerce")
            return pd.Series(vals.to_numpy(), index=idx, dtype=float)
    raise RuntimeError(f"IMS returned no {channel} records for station {sid}, "
                       f"{start:%Y-%m-%d %H:%M}..{end:%Y-%m-%d %H:%M}, after {TRIES} tries")


def _chunks(start, end, days):
    edges = list(pd.date_range(start, end, freq=f"{days}D")) + [end]
    return [(a, b) for a, b in zip(edges[:-1], edges[1:]) if a < b]


def fetch_rain_10min(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    cols = {}
    for sid, name in TEN_MIN.items():
        cols[name] = pd.concat([fetch_channel(sid, "Rain", a, b) for a, b in _chunks(start, end, 31)])
    for sid, name in ONE_MIN.items():
        one = pd.concat([fetch_channel(sid, "Rain_1_min", a, b) for a, b in _chunks(start, end, 7)])
        cols[name] = one_minute_to_ten(one[~one.index.duplicated()])
    df = pd.DataFrame({k: v[~v.index.duplicated()] for k, v in cols.items()})
    return df[(df.index >= start) & (df.index < end)]


# ── the cache ────────────────────────────────────────────────────────────────

def _write_atomic(df: pd.DataFrame, path: Path) -> None:
    data = df.to_csv(index=False).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=Path(path).parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def update_cache(path: Path, fetch=fetch_rain_10min, today: pd.Timestamp = None) -> pd.DataFrame:
    """Recompute every day after the last day with a value, through yesterday."""
    today = (today or pd.Timestamp.now(tz="Asia/Jerusalem").tz_localize(None)).normalize()
    cache = pd.read_csv(path)
    good = cache.dropna(subset=["precip_intensity_mm_hr"])
    last_good = pd.Timestamp(good["date"].max())
    if last_good >= today - pd.Timedelta(days=1):
        return cache
    # a day of warm-up so the first new day's 60-minute windows can start before midnight
    rain10 = fetch(last_good - pd.Timedelta(days=1), today)
    fresh = daily_intensity(rain10)
    fresh = fresh[(fresh.index > f"{last_good:%Y-%m-%d}") & (fresh.index < f"{today:%Y-%m-%d}")]
    out = pd.concat([cache[cache["date"] <= f"{last_good:%Y-%m-%d}"],
                     fresh.rename_axis("date").reset_index()], ignore_index=True)
    _write_atomic(out, path)
    return out
