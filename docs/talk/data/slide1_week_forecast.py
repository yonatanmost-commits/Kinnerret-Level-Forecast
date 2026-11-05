"""
slide1_week_forecast.py - the talk day's level (11 Nov 2026) for slide 1's lake animation, from the
week model with the IMS forecast (decided 31 Oct; originator 5 Nov). Writes
docs/talk/data/slide1_week_forecast.json, which make_lake_animation.stops() uses only if it was made
from the LAST measured level (else the animation keeps its no-rain projection).

The same two-stage GBR the app runs (page 6, "Fetch from IMS"; Automation/09_weekly_forecast.py),
with two differences from the page, on purpose:
  - it starts from the last MEASURED level and its own day, not from the gold table's last row
    (gold carries weather a day or two past the level; the page would skip those days);
  - days already past use the MEASURED weather from gold; only the rest come from IMS.
The engine forecasts 1-7 days ahead, so 11 Nov needs a measured level from 4 Nov or later.

Run (planned for the weekend, after the 07:30 refresh; see docs/talk/update_5nov_plan.md):
    python docs/talk/data/slide1_week_forecast.py            # writes the json, prints the path
    python docs/talk/data/slide1_week_forecast.py --dry      # prints only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "kinneret_app"))
OUT = HERE / "slide1_week_forecast.json"
TALK_DAY = pd.Timestamp("2026-11-11")
WEATHER = ["temp_max_C", "temp_min_C", "rainfall_mm", "humidity_pct", "wind_speed_ms", "radiation_MJm2"]
MAX_DAYS = 7                                      # the week model's horizons


def inputs(gold: pd.DataFrame, ims: pd.DataFrame | None) -> tuple[pd.Timestamp, pd.DataFrame, pd.DataFrame]:
    """(last measured day, history up to it, the weather for every day after it up to the talk day:
    gold's measured weather where gold has the day, else the IMS forecast; column 'source')."""
    measured = gold.dropna(subset=["level_m", "volume_Mm3"])
    last = measured["date"].max()
    days = pd.date_range(last + pd.Timedelta(days=1), TALK_DAY, freq="D")
    if not 1 <= len(days) <= MAX_DAYS:
        raise SystemExit(f"last measured level {last.date()}: {len(days)} days to {TALK_DAY.date()}, "
                         f"the week model reaches 1-{MAX_DAYS}")
    rows = []
    for d in days:
        g = gold[gold["date"] == d]
        if len(g) and g[WEATHER[:3]].notna().all(axis=None):
            rows.append({"date": d, **g.iloc[0][WEATHER].to_dict(), "source": "measured"})
        else:
            if ims is None or not (ims["date"] == d).any():
                raise SystemExit(f"{d.date()}: no measured weather and no IMS forecast")
            rows.append({"date": d, **ims[ims["date"] == d].iloc[0][WEATHER].to_dict(), "source": "IMS"})
    return last, gold[gold["date"] <= last].reset_index(drop=True), pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    from app_utils import load_gold, load_models, run_forecast_from_df
    from ims_forecast import fetch_tiberias_7day
    gold = load_gold().sort_values("date").reset_index(drop=True)
    today = pd.Timestamp(date.today())
    ims = fetch_tiberias_7day([today + pd.Timedelta(days=i) for i in range(7)])
    ims["date"] = pd.to_datetime(ims["date"])
    last, history, weather = inputs(gold, ims)
    gb1, gb2_direct, meta = load_models()
    res, s_lvl, _, e_lvl, _ = run_forecast_from_df(weather[["date"] + WEATHER], history.tail(21), gb1,
                                                   gb2_direct, meta)
    levels = {pd.Timestamp(r["date"]).strftime("%Y-%m-%d"): float(r["pred_level_m"]) for r in res}
    out = {"from": str(last.date()), "made_on": str(date.today()), "start_level": float(s_lvl),
           "levels": levels, "talk_day": levels[TALK_DAY.strftime("%Y-%m-%d")],
           "weather": [{**{k: (None if pd.isna(v) else v) for k, v in r.items() if k != "date"},
                        "date": r["date"].strftime("%Y-%m-%d")} for r in weather.to_dict("records")],
           "model": "two-stage GBR (09_weekly_forecast.run_forecast), Models/stage1_inflow_rf.pkl + "
                    "stage2_direct_gb.pkl"}
    print(weather.to_string(index=False))
    print(f"from {last.date()} at {s_lvl:.3f} m -> 11 Nov {out['talk_day']:.3f} m")
    if not a.dry:
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
