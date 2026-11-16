"""
c3s_fetch.py  -  C3S multi-model seasonal forecasts over the Kinneret catchment.

Companion to seas5_fetch.py (ECMWF): the other C3S centres' current systems, same
request shape. Monthly means of total precipitation and 2 m temperature, every start
month the CDS lists for that system and year, lead months 1-6, all members, on the
1-degree cells around the lake. One NetCDF per centre/system/year in Raw Data/C3S/
(git-ignored). A file already on disk is skipped, so a rerun only fetches what is missing.

The months asked for each year come from the dataset's CDS constraints, so a request
never names a start month the system does not have.

Needs ~/.cdsapirc and the licence of "seasonal-monthly-single-levels" accepted.

Run:  python Automation/c3s_fetch.py [workers]
"""
import json
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cdsapi
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Raw Data" / "C3S"
AREA = [34, 35, 32, 37]                          # N, W, S, E, as in seas5_fetch.py
DATASET = "seasonal-monthly-single-levels"
CONSTRAINTS = ("https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
               f"{DATASET}/constraints.json")
# The system each centre issues its 2026 forecasts with (CDS constraints, 2026-10-16).
# ukmo last: its 1993 hindcast came back "MARS returned no data" for systems 610 and 604.
SYSTEMS = [("meteo_france", "9"), ("dwd", "22"), ("cmcc", "4"), ("ncep", "2"),
           ("jma", "4"), ("eccc", "4"), ("eccc", "5"), ("ukmo", "610")]
YEARS = range(1993, 2026)


def available_months():
    """{(centre, system, year): [months]} for monthly-mean precipitation."""
    with urllib.request.urlopen(CONSTRAINTS, timeout=120) as r:
        entries = json.loads(r.read())
    months = defaultdict(set)
    for e in entries:
        if "monthly_mean" not in e.get("product_type", []):
            continue
        if "total_precipitation" not in e.get("variable", []):
            continue
        for o in e.get("originating_centre", []):
            for s in e.get("system", []):
                for y in e.get("year", []):
                    months[(o, s, int(y))] |= set(e.get("month", []))
    return {k: sorted(v) for k, v in months.items()}


def fetch(centre, system, year, months):
    path = OUT / f"{centre}_{system}_{year}.nc"
    if path.exists():
        return path, "skip"
    tmp = path.with_suffix(".part")
    for _ in range(30):
        try:
            return _retrieve(centre, system, year, months, tmp, path), "new"
        except requests.HTTPError as e:
            if "temporarily limited" not in str(e) and "queued requests" not in str(e):
                raise
            time.sleep(120)                      # over the per-user queue cap: wait our turn
    raise RuntimeError(f"{centre}_{system}_{year}: CDS queue still full after 30 tries")


def _retrieve(centre, system, year, months, tmp, path):
    cdsapi.Client(quiet=True, progress=False).retrieve(DATASET, {
        "originating_centre": centre, "system": system,
        "variable": ["total_precipitation", "2m_temperature"],
        "product_type": ["monthly_mean"],
        "year": [str(year)], "month": months,
        "leadtime_month": [str(k) for k in range(1, 7)],
        "data_format": "netcdf", "area": AREA,
    }, str(tmp))
    tmp.replace(path)
    return path


def job(args):
    centre, system, year, months = args
    try:
        path, how = fetch(centre, system, year, months)
        return f"{centre}_{system}_{year} {how} {path.stat().st_size} bytes"
    except Exception as e:                       # one failed year must not stop the rest
        return f"{centre}_{system}_{year} FAILED {type(e).__name__}: {str(e)[:200]}"


if __name__ == "__main__":
    # CDS rejects requests past a per-user queue cap for the dataset (shared with seas5_fetch.py)
    # usage: c3s_fetch.py [workers] [first_year last_year]
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    years = range(int(sys.argv[2]), int(sys.argv[3]) + 1) if len(sys.argv) > 3 else YEARS
    OUT.mkdir(parents=True, exist_ok=True)
    avail = available_months()
    jobs = [(c, s, y, avail[(c, s, y)]) for c, s in SYSTEMS for y in years if (c, s, y) in avail]
    print(f"{len(jobs)} centre/system/years to fetch", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        for line in ex.map(job, jobs):
            print(line, flush=True)
