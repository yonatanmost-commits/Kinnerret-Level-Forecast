# tests/test_longrange_fetch_era5.py
import sys
from datetime import date
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


def test_parse_archive_payload_to_frame(monkeypatch):
    """A daily payload maps onto tidy columns (date, temp_max_C, temp_min_C, ...)."""
    import longrange_fetch_era5 as f
    payload = {"daily": {
        "time": ["1960-01-01", "1960-01-02"],
        "temperature_2m_max": [14.0, 15.5],
        "temperature_2m_min": [6.0, 7.0],
        "precipitation_sum": [0.0, 12.3],
        "shortwave_radiation_sum": [9.1, 4.2],
        "relative_humidity_2m_mean": [70.0, 88.0],
        "wind_speed_10m_mean": [10.8, 7.2],   # km/h in Open-Meteo
    }}
    monkeypatch.setattr(f.requests, "get", lambda *a, **k: _FakeResp(payload))
    df = f.fetch_era5_daily(date(1960, 1, 1), date(1960, 1, 2))
    assert list(df["date"].astype(str)) == ["1960-01-01", "1960-01-02"]
    assert df.loc[1, "temp_max_C"] == 15.5
    assert df.loc[1, "rainfall_mm"] == 12.3
    # wind converted km/h -> m/s
    assert abs(df.loc[0, "wind_speed_ms"] - 10.8 / 3.6) < 1e-9


def test_empty_payload_returns_empty_frame(monkeypatch):
    import longrange_fetch_era5 as f
    monkeypatch.setattr(f.requests, "get", lambda *a, **k: _FakeResp({"daily": {}}))
    df = f.fetch_era5_daily(date(1960, 1, 1), date(1960, 1, 2))
    assert df.empty
