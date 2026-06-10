"""
CORDEX ensemble ingest — load both site CSVs, winsorize tmax, cache as parquet.

Winsorize at ingestion per project rule: the QDM hot-tail artifact (tmax up to
57°C, all 12 models, Aug-heavy) must be clipped before ANY downstream computation.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORDEX_FILES = {
    "bet_zayda": PROJECT_ROOT / "Raw Data" / "CORDEX" / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    "zemah":     PROJECT_ROOT / "Raw Data" / "CORDEX" / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
}
CACHE_PATH = PROJECT_ROOT / "Gold Data" / "cordex_ensemble.parquet"
TMAX_CAP = 49.0  # °C — QDM tail-inflation artifact above this threshold


def load_cordex(cache: bool = True) -> pd.DataFrame:
    """Load both CORDEX site files, winsorize tmax, return long DataFrame.

    Columns: date (datetime64[ns]), model (str), scenario (str), site (str),
             tmin (float64), tmax (float64), doy (int).
    """
    if cache and CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)
    frames = []
    for site, path in CORDEX_FILES.items():
        df = pd.read_csv(path)
        df["tmax"] = df["tmax"].clip(upper=TMAX_CAP)
        df["site"] = site
        df["date"] = pd.to_datetime(df[["year", "month", "day"]], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.drop(columns=["year", "month", "day"])
        frames.append(df[["date", "model", "scenario", "site", "tmin", "tmax"]])
    out = pd.concat(frames, ignore_index=True)
    out["doy"] = out["date"].dt.day_of_year
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE_PATH, index=False)
    return out


if __name__ == "__main__":
    df = load_cordex(cache=False)
    print(f"Loaded {len(df):,} rows | tmax max={df['tmax'].max():.1f}°C (capped at {TMAX_CAP})")
    print(df.groupby(["site", "scenario"])["model"].nunique().rename("n_models"))
