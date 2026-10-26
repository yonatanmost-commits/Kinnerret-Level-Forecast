"""
seas5_fetch.py  -  ECMWF SEAS5 seasonal forecasts over the Kinneret catchment.

Monthly means of total precipitation rate and 2 m temperature, every start month
1993..last year, lead months 1-6, all ensemble members (25 in hindcasts to 2016,
51 after), on the 1-degree cells around the lake (32.5-33.5 N, 35.5-36.5 E).
One NetCDF per start year in Raw Data/SEAS5/ (git-ignored). A year already on disk
is skipped, so a rerun only fetches what is missing. CDS caps queued requests per
account and dataset; a request rejected for that waits and retries. The current year asks
only for the start months already issued (after the 5th): naming a month not out yet fails
the whole request. To add a month just issued, move that year's file aside and rerun.

Needs a Copernicus CDS account: ~/.cdsapirc with url + personal access token, and
the licence of "seasonal-monthly-single-levels" accepted on the CDS site.

Run:  python Automation/seas5_fetch.py [first_year] [last_year]
"""
import sys
import time
from datetime import date
from pathlib import Path

import cdsapi
import requests

from seas5 import RELEASE_DAY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Raw Data" / "SEAS5"
AREA = [34, 35, 32, 37]                          # N, W, S, E -> cells 33.5/32.5 N x 35.5/36.5 E


def months_for(year: int, today: date) -> list:
    """The start months of `year` whose forecast is out by `today` (a month's is out after the 5th)."""
    if year < today.year:
        return list(range(1, 13))
    if year > today.year:
        return []
    return list(range(1, today.month + (today.day > RELEASE_DAY)))


def fetch(year: int, client: cdsapi.Client) -> Path:
    path = OUT / f"seas5_{year}.nc"
    if path.exists():
        return path
    tmp = path.with_suffix(".part")
    for attempt in range(30):
        try:
            return _retrieve(year, client, tmp, path)
        except requests.HTTPError as e:
            if "temporarily limited" not in str(e) and "queued requests" not in str(e):
                raise
            time.sleep(120)
    raise RuntimeError(f"{year}: CDS queue still full after 30 tries")


def _retrieve(year, client, tmp, path):
    client.retrieve("seasonal-monthly-single-levels", {
        "originating_centre": "ecmwf", "system": "51",
        "variable": ["total_precipitation", "2m_temperature"],
        "product_type": ["monthly_mean"],
        "year": [str(year)], "month": [f"{m:02d}" for m in months_for(year, date.today())],
        "leadtime_month": [str(k) for k in range(1, 7)],
        "data_format": "netcdf", "area": AREA,
    }, str(tmp))
    tmp.replace(path)
    return path


if __name__ == "__main__":
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 1993
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    OUT.mkdir(parents=True, exist_ok=True)
    c = cdsapi.Client(quiet=True, progress=False)
    for y in range(first, last + 1):
        print(y, fetch(y, c).stat().st_size, "bytes", flush=True)
