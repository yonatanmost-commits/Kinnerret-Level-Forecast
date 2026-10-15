"""
liquid_nn_era5_long.py  -  Does the liquid network's lead hold across 20 test years?

Builds a long gold-style table 2001-2025 with ERA5 weather in every year (the
stations start only in 2012), then runs the same walk-forward race as
liquid_nn_compare.py: GBR vs a CfC society, test years 2006-2025, each trained
on 2001 .. year-1, level_m lagged one day for both.

Features are computed by 07_build_gold_features' own functions; ERA5 is handed
to them in the station-column format (as the priority station), so VPD, ET0,
rain sums and moisture balance are derived exactly as in the real gold table.
ERA5 has no rain intensity, so precip_intensity_mm_hr is left out of both
models here. Side result: on the station table (2021-2025), the GBR with and
without that input, to show what leaving it out costs.

Run:  python Automation/liquid_nn_era5_long.py [--seeds 7] [--first-test 2006]
"""
import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import liquid_nn_compare as lnc            # also loads 08 as lnc.t08
import model_lib

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("gold07", HERE / "07_build_gold_features.py")
g07 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g07)

t08 = lnc.t08
ERA5 = g07.SILVER_MET / "era5_kinneret_daily.csv"
START, END = "2001-01-01", "2025-12-31"
NO_INTENSITY = "precip_intensity_mm_hr"


def era5_as_station_met(spine: pd.DataFrame) -> pd.DataFrame:
    e = pd.read_csv(ERA5, encoding="utf-8-sig")
    e["date"] = pd.to_datetime(e["date"]).dt.strftime("%Y-%m-%d")
    p, r = g07.PRIORITY_STATION, g07.RADIATION_STATION
    met = pd.DataFrame({
        "date": e["date"],
        f"{p}_temperature_C_mean": (e["temp_max_C"] + e["temp_min_C"]) / 2,
        f"{p}_temperature_C_max": e["temp_max_C"],
        f"{p}_temperature_C_min": e["temp_min_C"],
        f"{p}_relative_humidity_pct_mean": e["humidity_pct"],
        f"{p}_wind_speed_ms_mean": e["wind_speed_ms"],
        f"{p}_rainfall_mm_sum": e["rainfall_mm"],
        f"{r}_global_radiation_MJm2": e["radiation_MJm2"],
    })
    return spine[["date"]].merge(met, on="date", how="left")


def build_long_table() -> pd.DataFrame:
    days = pd.date_range(START, END, freq="D")
    df = pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "doy": days.day_of_year})
    df = g07.add_seasonality(df)
    df, _ = g07.add_met_features(df, era5_as_station_met(df))
    level = pd.read_csv(g07.SILVER_LAKE / "kinneret_level.csv")
    level["date"] = level["date"].astype(str)
    df = g07.add_level_features(df, level, g07.build_volume_poly(g07.RAW_BATHY))
    df = g07.add_flow_features(df, pd.read_csv(g07.SILVER_FLOW / "jordan_river_daily_flow_clean.csv"))
    df = df.drop(columns="doy")
    df["date"] = pd.to_datetime(df["date"])
    for k in (1, 2, 3):                                  # as 08.load_data
        df[f"rainfall_lag{k}_mm"] = df["rainfall_mm"].shift(k)
    df["predicted_inflow_m3"] = np.nan
    return df


def set_features(drop: str | None):
    """Point 08 and the liquid race at the champion's feature lists, minus `drop`."""
    s1 = [f for f in model_lib.S1_FEATURES if f != drop]
    s2 = [f for f in model_lib.S2_FEATURES if f != drop]
    for m in (t08, lnc):
        m.S1_FEATURES, m.S2_FEATURES = s1, s2


def _mean(rows, k):
    return round(float(np.mean([r[k] for r in rows])), 3)


CKPT = t08.BASE_DIR / "docs" / "experiments" / "liquid_nn_era5_long.partial.json"


def per_fold(name: str, folds: list, run) -> tuple[list, dict]:
    """Run `run` one fold at a time; each finished fold is saved to CKPT, and a
    rerun skips folds already there (the long race was once killed for memory)."""
    done = json.loads(CKPT.read_text(encoding="utf-8")) if CKPT.exists() else {}
    rows, extra = [], {}
    for fold in folds:
        key = f"{name}/{fold[0]}"
        if key not in done:
            t08.CV_FOLDS = [fold]
            res, ex = run()
            done[key] = {"row": res[0], "extra": ex.get(fold[0]) if isinstance(ex, dict) else None}
            CKPT.write_text(json.dumps(done, indent=1), encoding="utf-8")
        rows.append(done[key]["row"])
        if done[key]["extra"] is not None:
            extra[fold[0]] = done[key]["extra"]
    return rows, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=7)
    ap.add_argument("--seq-len", type=int, default=14)
    ap.add_argument("--first-test", type=int, default=2006)
    a = ap.parse_args()
    t_start = time.time()

    # ── side result: what dropping intensity costs, on the real station table ──
    station_folds = [(str(y), list(range(2012, y)), y) for y in range(2021, 2026)]
    station = lnc.lag_level(t08.load_data())
    set_features(None)
    with_pi, _ = per_fold("station_gbr_with_pi", station_folds, lambda: t08.run_cv(station))
    set_features(NO_INTENSITY)
    without_pi, _ = per_fold("station_gbr_without_pi", station_folds, lambda: t08.run_cv(station))

    # ── the long race ──
    df = lnc.lag_level(build_long_table())
    folds = [(str(y), list(range(2001, y)), y) for y in range(a.first_test, 2026)]
    set_features(NO_INTENSITY)
    cov = df.dropna(subset=lnc.S2_FEATURES[1:] + [model_lib.S2_TARGET]).groupby(df["date"].dt.year).size()
    print("\nStage-2 usable rows per year:\n" + cov.to_string())
    gbr, _ = per_fold("era5_gbr", folds, lambda: t08.run_cv(df))
    liq, seed_r2 = per_fold(f"era5_cfc_s{a.seeds}", folds,
                            lambda: lnc.run_cv_liquid(df, a.seeds, a.seq_len, "cfc"))

    print("\n=== ERA5 long race: S2 R² (MAE Mm³/d) ===")
    for b, l in zip(gbr, liq):
        assert b["fold"] == l["fold"] and b["n_test"] == l["n_test"], (b, l)
        print(f"  {b['fold']}  n={b['n_test']:>3}  GBR {b['s2_r2']:6.3f} ({b['s2_mae_Mm3']:.3f})   "
              f"CfC {l['s2_r2']:6.3f} ({l['s2_mae_Mm3']:.3f})   {'CfC' if l['s2_r2'] > b['s2_r2'] else 'GBR'}")
    wins = sum(l["s2_r2"] > b["s2_r2"] for b, l in zip(gbr, liq))
    print(f"  mean  GBR {_mean(gbr, 's2_r2'):.3f}   CfC {_mean(liq, 's2_r2'):.3f}   "
          f"CfC wins {wins}/{len(gbr)} years   ({(time.time() - t_start) / 60:.0f} min)")

    out = t08.BASE_DIR / "docs" / "experiments" / f"liquid_nn_era5_long_cfc_s{a.seeds}.json"
    out.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "table": f"ERA5 weather {START}..{END}; level, inflow from silver; level_m lagged 1 day",
        "features": f"champion S1/S2 lists without {NO_INTENSITY}",
        "stage2_rows_per_year": {str(k): int(v) for k, v in cov.items()},
        "gbr": {"cv_results": gbr, "s2_r2_mean": _mean(gbr, "s2_r2"), "s2_mae_mean": _mean(gbr, "s2_mae_Mm3")},
        "liquid_cfc": {"cv_results": liq, "s2_r2_per_seed": seed_r2,
                       "s2_r2_mean": _mean(liq, "s2_r2"), "s2_mae_mean": _mean(liq, "s2_mae_Mm3"),
                       "config": {"units": 32, "seq_len": a.seq_len, "seeds": a.seeds}},
        "cfc_wins": f"{wins}/{len(gbr)}",
        "intensity_cost_station_table_gbr": {
            "with": {"cv_results": with_pi, "s2_r2_mean": _mean(with_pi, "s2_r2")},
            "without": {"cv_results": without_pi, "s2_r2_mean": _mean(without_pi, "s2_r2")}},
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {out.relative_to(t08.BASE_DIR)}")


if __name__ == "__main__":
    main()
