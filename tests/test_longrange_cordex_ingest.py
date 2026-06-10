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


def test_invalid_dates_are_dropped(tmp_path, monkeypatch):
    """Feb-29 in non-leap year (360-day calendar artifact) must be silently dropped."""
    import longrange_cordex_ingest as ing
    # Feb 29 in 2006 (non-leap) — invalid, should be coerced to NaT and dropped
    rows = [
        {"year": 2006, "month": 2, "day": 28, "tmin": 5.0, "tmax": 15.0, "model": "m", "scenario": "rcp45"},
        {"year": 2006, "month": 2, "day": 29, "tmin": 5.0, "tmax": 15.0, "model": "m", "scenario": "rcp45"},  # invalid
        {"year": 2006, "month": 3, "day":  1, "tmin": 5.0, "tmax": 15.0, "model": "m", "scenario": "rcp45"},
    ]
    df = pd.DataFrame(rows)
    for site in ["bet-zayda", "zemah"]:
        p = tmp_path / f"{site}_tmin_tmax_12models_rcp45_rcp85_qdm.csv"
        df.to_csv(p, index=False)
    monkeypatch.setattr(ing, "CORDEX_FILES", {
        "bet_zayda": tmp_path / "bet-zayda_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
        "zemah":     tmp_path / "zemah_tmin_tmax_12models_rcp45_rcp85_qdm.csv",
    })
    monkeypatch.setattr(ing, "CACHE_PATH", tmp_path / "cache.parquet")
    result = ing.load_cordex(cache=False)
    # Feb 29 row must be gone; Feb 28 and Mar 1 must remain
    bet_rows = result[result["site"] == "bet_zayda"]
    assert len(bet_rows) == 2
    dates_str = bet_rows["date"].dt.strftime("%Y-%m-%d").tolist()
    assert "2006-02-28" in dates_str
    assert "2006-03-01" in dates_str
    assert "2006-02-29" not in dates_str
