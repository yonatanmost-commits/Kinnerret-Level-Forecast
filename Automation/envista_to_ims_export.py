"""
envista_to_ims_export.py  -  IMS envista 10-minute history -> IMS export CSVs

The manual IMS exports in Raw Data/Meteorological Data start 2012-06-01. The same
IMS station archive, read through the envista feed, reaches back to 1994 for Tzemach
and to 2003 for Lev Kinneret (docs/experiments/ims_pre2012_coverage.csv). On an
overlapping month the feed and the export agree value for value (Tzemach, 2013-01,
all five channels gold uses).

This writes that history as export files - the same Hebrew headers, station names
and date format as a manual export - so pipeline steps 1-4 ingest it like any other
export. One file per station and year, named data_0000_envista_* so it sorts before
the manual exports; step 2 keeps the alphabetically last file on a duplicate, so a
manual export always wins an overlap. Only rows before 2012-06-01 are written.
Wind is blanked where the archive serves temperature under the wind channel
(Tzemach 1994-01 .. 2002-06; see drop_copied_wind).

Input:  <cache_dir>/<station>_<channel>.csv  (date dd/mm/YYYY HH:MM, value; no header)
Output: <out_dir>/data_0000_envista_<station>_<year>.csv

Run:  python Automation/envista_to_ims_export.py <cache_dir> <out_dir>
"""
import csv
import importlib.util
import sys
from pathlib import Path

import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "_01_ingest", Path(__file__).resolve().parent / "01_ingest_met_data.py")
_ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ingest)

HEADER = list(_ingest.COLUMN_MAP)                         # the export's column order
HEBREW = {slug: heb for heb, slug in _ingest.COLUMN_MAP.items()}
STATION_HEBREW = {slug: heb for heb, slug in _ingest.STATION_MAP.items()}
CHANNEL_SLUG = {"TD": "temperature_C", "TDmax": "temperature_max_C", "TDmin": "temperature_min_C",
                "RH": "relative_humidity_pct", "WS": "wind_speed_ms", "Rain": "rainfall_mm",
                "Grad": "global_radiation_Wm2"}
END = pd.Timestamp("2012-06-01")                           # first day of the manual exports
# Gold takes tzamach first and falls back to the others; only these two were downloaded in full.
STATIONS = ("tzamach", "lev_kinneret")


def drop_copied_wind(df: pd.DataFrame) -> pd.DataFrame:
    """Blank wind in months where the feed's wind channel repeats temperature.

    Tzemach 1994-01 .. 2002-06 (90 months): every 10-minute "wind" value equals the
    temperature in the same slot (yearly maxima 42.5, 44.2, 41.6 ... match exactly), so
    the archive serves temperature under the wind channel there. Real wind months share
    about 1% of slots with temperature by chance, so a month with most slots equal is a copy.
    """
    ws, td = HEBREW["wind_speed_ms"], HEBREW["temperature_C"]
    if ws not in df or td not in df:
        return df
    same = (df[ws] - df[td]).abs() < 1e-9
    share = same[df[ws].notna() & df[td].notna()].groupby(lambda t: t.to_period("M")).mean()
    copied = set(share[share > 0.5].index)
    if copied:
        df = df.copy()
        df.loc[[t.to_period("M") in copied for t in df.index], ws] = float("nan")
    return df


def load_station(cache_dir: Path, station: str) -> pd.DataFrame:
    """All cached channels of one station, one row per 10-minute slot, export column names."""
    cols = {}
    for ch, slug in CHANNEL_SLUG.items():
        p = cache_dir / f"{station}_{ch}.csv"
        if not p.exists():
            continue
        s = pd.read_csv(p, header=None, names=["date", "v"], dtype={"date": str})
        s["dt"] = pd.to_datetime(s["date"], format="%d/%m/%Y %H:%M")
        s = s.drop_duplicates("dt").set_index("dt")["v"]   # a restarted scan may repeat a month
        cols[HEBREW[slug]] = s[s.index < END]
    return pd.DataFrame(cols).sort_index()


def write_years(df: pd.DataFrame, station: str, out_dir: Path) -> list:
    written = []
    for year, part in df.groupby(df.index.year):
        path = out_dir / f"data_0000_envista_{station}_{year}.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(HEADER)
            for ts, row in part.iterrows():
                rec = {HEADER[0]: STATION_HEBREW[station], HEADER[1]: ts.strftime("%d/%m/%Y %H:%M")}
                rec.update({k: ("" if pd.isna(v) else f"{v:g}") for k, v in row.items()})
                w.writerow([rec.get(h, "") for h in HEADER])
        written.append((path.name, len(part)))
    return written


def main(cache_dir: Path, out_dir: Path, stations=STATIONS):
    out_dir.mkdir(parents=True, exist_ok=True)
    for st in stations:
        for name, n in write_years(drop_copied_wind(load_station(cache_dir, st)), st, out_dir):
            print(f"{name}: {n} rows")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
