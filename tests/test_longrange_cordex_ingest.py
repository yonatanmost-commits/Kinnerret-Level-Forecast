import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Automation"))


def _make_fake_csv(tmp_path, site, n=10):
    """Write a minimal CORDEX-shaped CSV to tmp_path."""
    rows = []
    for i in range(n):
        rows.append({
            "year": 2006, "month": 1, "day": i + 1,
            "tmin": 5.0 + i * 0.1,
            "tmax": 55.0 if i == 0 else 20.0 + i * 0.1,  # one outlier
            "model": "cnrm_cclm",
            "scenario": "rcp45",
        })
    df = pd.DataFrame(rows)
    p = tmp_path / f"{site}_tmin_tmax_12models_rcp45_rcp85_qdm.csv"
    df.to_csv(p, index=False)
    return p


def test_winsorize_clips_tmax_above_49(tmp_path, monkeypatch):
    """tmax values above 49°C must be capped at 49°C at ingestion."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    assert df["tmax"].max() <= 49.0


def test_schema_and_sites(tmp_path, monkeypatch):
    """Output must have required columns and both sites."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    for col in ["date", "model", "scenario", "site", "tmin", "tmax", "doy"]:
        assert col in df.columns, f"missing column: {col}"
    assert set(df["site"].unique()) == {"bet_zayda", "zemah"}


def test_doy_range(tmp_path, monkeypatch):
    """DOY must be in 1–366."""
    import longrange_cordex_ingest as ing
    _make_fake_csv(tmp_path, "bet-zayda")
    _make_fake_csv(tmp_path, "zemah")
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    df = ing.load_cordex(cache=False)
    assert df["doy"].between(1, 366).all()
