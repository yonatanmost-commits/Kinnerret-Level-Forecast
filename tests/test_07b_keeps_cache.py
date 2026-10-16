"""Bug (2026-10-16 local refresh): 07b rebuilt precip_intensity_daily.csv from the local
met_data_wide.csv (data to 2026-04-25) BEFORE extending it from the IMS feed, so every
local run threw away the days already fetched (to 2026-10-14) and had to refetch the
whole summer - which failed on a station with no records for a month. CI never has the
wide file, so only the local 07:30 run was hit.

The cache must survive a 07b run: days already in it stay, whatever the wide file holds.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Automation"))


def load_07b():
    spec = importlib.util.spec_from_file_location("s07b", ROOT / "Automation" / "07b_precalc_precip_intensity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cache_days_survive_when_the_wide_file_is_older(tmp_path, monkeypatch):
    mod = load_07b()
    wide = tmp_path / "met_data_wide.csv"
    times = pd.date_range("2026-04-20", "2026-04-25 23:50", freq="10min")
    pd.DataFrame({"datetime": times, "lev_kinneret_rainfall_mm": 0.0}).to_csv(wide, index=False)
    cache = tmp_path / "precip_intensity_daily.csv"
    days = pd.date_range("2026-04-20", "2026-10-14").strftime("%Y-%m-%d")
    pd.DataFrame({"date": days, "precip_intensity_mm_hr": 1.5}).to_csv(cache, index=False)

    monkeypatch.setattr(mod, "IN_WIDE", wide)
    monkeypatch.setattr(mod, "OUT_FILE", cache)
    monkeypatch.setattr(mod, "update_cache", lambda path: pd.read_csv(path))   # no network
    mod.main()

    out = pd.read_csv(cache)
    assert out["date"].max() == "2026-10-14"
    assert out.set_index("date").loc["2026-10-14", "precip_intensity_mm_hr"] == 1.5
