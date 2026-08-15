"""
longrange_phaseb_eval.py - Phase B bake-off evaluation for the long-range
temperature-only level forecast.

Answers the make-or-break question the paper needs a NUMBER for: does a
temperature-only forecast of the cumulative Kinneret level change over a 14-30 day
horizon beat a day-of-year climatology baseline?

Design (Candidate 1 - the "implicit / shortest chain" design goal in
docs/superpowers/specs/2026-06-01-longrange-temp-forecast-design.md):

  * Walk-forward by held-out year (2021-2024), matching the 7-day model's CV_FOLDS.
  * Issue a fresh forecast every 7 days through each test year.
  * Target at lead h:  cumulative volume change  V(t+h) - V(t)   [Mm3].
  * Model: GradientBoosting on temperature-derived features aggregated over the
    horizon (cloud_index, DTR, Tmax anomaly, Hargreaves ET0) plus issue-time
    season and antecedent state. Future temperature is taken as OBSERVED - a
    PERFECT-PROGNOSIS upper bound. If even perfect temperature cannot beat
    climatology, the negative result is unassailable (the live product would only
    ever have a noisier temperature forecast).
  * Baseline: day-of-year climatology of cumulative change (harmonic in issue-DOY,
    fit per lead on the training years only - no leakage).
  * Skill score per lead:  SS_h = 1 - MSE_model_h / MSE_clim_h, split wet/dry.

Headline = wet-season SS averaged over leads {14, 21, 30}. SS <= 0 means no skill
beyond climatology => the temperature-only product fails, as reported in the paper.

Climatological references (clear-sky DTR envelope, Tmax normal) are fit per fold on
the TRAIN years only. Training anchors are restricted so the target date stays
inside the train period (no test-year leakage).

Writes docs/longrange_phaseb_report.md and docs/longrange_phaseb_results.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Automation"))

from longrange_meteo import hargreaves_et0
from longrange_climatology import (fit_harmonic, eval_harmonic,
                                    clearsky_dtr_by_doy)
from longrange_meteo import cloud_index
from longrange_state import soil_moisture_bucket

GOLD_FILE = ROOT / "Gold Data" / "kinneret_gold_features.csv"
REPORT_PATH = ROOT / "docs" / "longrange_phaseb_report.md"
JSON_PATH = ROOT / "docs" / "longrange_phaseb_results.json"

# Same held-out-year protocol as 08_train_forecast_model.CV_FOLDS
CV_FOLDS = [
    ("2021", list(range(2012, 2021)), 2021),
    ("2022", list(range(2012, 2022)), 2022),
    ("2023", list(range(2012, 2023)), 2023),
    ("2024", list(range(2012, 2024)), 2024),
]

LEADS = [7, 14, 21, 30]          # forecast leads (days) to evaluate
HEADLINE_LEADS = [14, 21, 30]    # the long-range band the paper claims
WET_MONTHS = {11, 12, 1, 2, 3}   # wet season by issue date
TRAIN_ANCHOR_STEP = 2            # build train anchors every N days
TEST_ANCHOR_STEP = 7             # issue test forecasts every 7 days

# Ablation: a season + antecedent-state baseline ML model, vs the same model with
# temperature features added. The MARGINAL skill of the temperature block (not the
# raw model-vs-climatology gap) is what speaks to the paper's claim, because the
# day-of-year climatology has no season/state features to begin with.
BASE_FEATURES = ["horizon_h", "season_sin", "season_cos", "level_m", "rainfall_30d_mm"]
TEMP_BLOCK = ["mean_cloud_index", "mean_dtr", "mean_tmax_anom_z", "mean_et0_hs"]
TEMP_FEATURES = BASE_FEATURES + TEMP_BLOCK

# "Architecture J done right": the soil-moisture bucket's antecedent saturation
# state, added ON TOP of the flat rainfall_30d sum (already in BASE) it was designed
# to beat. If bucket_S / trailing-overflow add marginal skill over `temp`, the J
# negative result is finally healed; if not, it is an honest second negative.
BUCKET_BLOCK = ["bucket_S_anchor", "bucket_Q30_anchor"]
TEMPBUCKET_FEATURES = TEMP_FEATURES + BUCKET_BLOCK
BUCKET_S_MAX = 150.0   # mm, untuned mid-range (design says 100-300); v0
PREDICTORS = ("clim", "base", "temp", "tempbucket")


def _window_means(daily: np.ndarray) -> np.ndarray:
    """Prefix-sum helper: cumf[k] = sum(daily[0:k]); window sum over inclusive
    [a, b] = cumf[b+1] - cumf[a]. The daily met-derived series are dense, so any
    sparse gaps are interpolated first - a single NaN would otherwise poison every
    cumulative sum after it (np.cumsum propagates NaN forward)."""
    filled = (pd.Series(daily).interpolate(limit_direction="both")
              .fillna(0.0).values)
    return np.concatenate([[0.0], np.cumsum(filled)])


def build_daily_temp_features(df: pd.DataFrame, train_mask: np.ndarray) -> pd.DataFrame:
    """Add temperature-only daily features. Climatological references (clear-sky DTR
    envelope, Tmax normal + residual std) are fit on TRAIN rows only to avoid leakage."""
    out = df.copy()
    doy = out["date"].dt.dayofyear.values.astype(float)
    dtr = (out["temp_max_C"] - out["temp_min_C"]).values
    out["et0_hs"] = hargreaves_et0(out["temp_max_C"].values,
                                   out["temp_min_C"].values, doy)
    out["dtr"] = dtr

    tr_doy = doy[train_mask]
    tr_dtr = dtr[train_mask]
    tr_tmax = out["temp_max_C"].values[train_mask]

    clearsky_coeffs = clearsky_dtr_by_doy(tr_doy, tr_dtr)
    out["cloud_index"] = cloud_index(dtr, eval_harmonic(doy, clearsky_coeffs))

    tmax_mean_coeffs = fit_harmonic(tr_doy, tr_tmax)
    tmax_resid_tr = tr_tmax - eval_harmonic(tr_doy, tmax_mean_coeffs)
    sigma = np.nanstd(tmax_resid_tr)
    sigma = sigma if sigma > 1e-9 else 1.0
    out["tmax_anom_z"] = (out["temp_max_C"].values
                          - eval_harmonic(doy, tmax_mean_coeffs)) / sigma
    return out


def add_bucket_state(df: pd.DataFrame) -> pd.DataFrame:
    """Antecedent soil-moisture state (Group 6), strictly CAUSAL - each day's S and
    Q use only observed rain/ET up to that day, so anchor-time values are legitimately
    known at issue. bucket_S = storage [mm]; bucket_Q30 = trailing-30-day overflow
    (runoff) [mm]. v0: S_max untuned at the mid-range; ET = potential et0_mm; S0 spun
    from half capacity (early rows are dropped by the model's NaN handling anyway)."""
    out = df.copy()
    rain = out["rainfall_mm"].fillna(0.0).values
    et = out["et0_mm"].fillna(out["et0_mm"].median()).values
    S, Q = soil_moisture_bucket(rain, et, S_max=BUCKET_S_MAX, S0=0.5 * BUCKET_S_MAX)
    out["bucket_S"] = S
    out["bucket_Q30"] = pd.Series(Q).rolling(30, min_periods=1).sum().values
    return out


def build_samples(df: pd.DataFrame, anchor_positions: np.ndarray,
                  leads: list) -> pd.DataFrame:
    """For each anchor position i and lead h, assemble one feature row + target.
    target = volume_Mm3[i+h] - volume_Mm3[i]  (cumulative volume change)."""
    vol = df["volume_Mm3"].values
    doy_anchor = df["date"].dt.dayofyear.values.astype(float)

    cum_ci = _window_means(df["cloud_index"].values)
    cum_dtr = _window_means(df["dtr"].values)
    cum_z = _window_means(df["tmax_anom_z"].values)
    cum_et0 = _window_means(df["et0_hs"].values)

    rows = []
    n = len(df)
    for i in anchor_positions:
        if np.isnan(vol[i]):
            continue
        for h in leads:
            j = i + h
            if j >= n or np.isnan(vol[j]):
                continue
            a, b = i + 1, j  # inclusive window [i+1, i+h]
            rows.append({
                "anchor_pos": i,
                "doy": doy_anchor[i],
                "horizon_h": float(h),
                "season_sin": df["season_sin"].values[i],
                "season_cos": df["season_cos"].values[i],
                "level_m": df["level_m"].values[i],
                "rainfall_30d_mm": df["rainfall_30d_mm"].values[i],
                "bucket_S_anchor": df["bucket_S"].values[i],
                "bucket_Q30_anchor": df["bucket_Q30"].values[i],
                "mean_cloud_index": (cum_ci[b + 1] - cum_ci[a]) / h,
                "mean_dtr": (cum_dtr[b + 1] - cum_dtr[a]) / h,
                "mean_tmax_anom_z": (cum_z[b + 1] - cum_z[a]) / h,
                "mean_et0_hs": (cum_et0[b + 1] - cum_et0[a]) / h,
                "target": vol[j] - vol[i],
            })
    return pd.DataFrame(rows)


def fit_climatology(train_samples: pd.DataFrame, leads: list) -> dict:
    """Per-lead harmonic (K=2) of cumulative-change target vs issue-DOY."""
    clim = {}
    for h in leads:
        sub = train_samples[train_samples["horizon_h"] == h]
        clim[h] = fit_harmonic(sub["doy"].values, sub["target"].values, K=2)
    return clim


def _gbr():
    return GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, random_state=42)


def run():
    df = (pd.read_csv(GOLD_FILE, parse_dates=["date"])
          .sort_values("date").reset_index(drop=True))
    year = df["date"].dt.year.values
    month = df["date"].dt.month.values

    # Pooled squared errors across folds, keyed (lead, season), for all predictors
    keys = [(h, s) for h in LEADS for s in ("wet", "dry")]
    se = {p: {k: [] for k in keys} for p in PREDICTORS}

    for fold_name, train_yrs, test_yr in CV_FOLDS:
        train_mask = np.isin(year, train_yrs)
        feat = add_bucket_state(build_daily_temp_features(df, train_mask))

        last_train_end = pd.Timestamp(f"{test_yr}-01-01")
        train_anchor_pos = np.array(
            [i for i in np.where(train_mask)[0][::TRAIN_ANCHOR_STEP]
             if feat["date"].values[i] < np.datetime64(last_train_end)], dtype=int)
        test_anchor_pos = np.where(year == test_yr)[0][::TEST_ANCHOR_STEP]

        train_s = build_samples(feat, train_anchor_pos, LEADS).dropna(
            subset=TEMPBUCKET_FEATURES + ["target"])
        test_s = build_samples(feat, test_anchor_pos, LEADS).dropna(
            subset=TEMPBUCKET_FEATURES + ["target"]).copy()
        if len(train_s) == 0 or len(test_s) == 0:
            print(f"  Fold {fold_name}: insufficient samples, skipping")
            continue

        m_base = _gbr().fit(train_s[BASE_FEATURES].values, train_s["target"].values)
        m_temp = _gbr().fit(train_s[TEMP_FEATURES].values, train_s["target"].values)
        m_tb = _gbr().fit(train_s[TEMPBUCKET_FEATURES].values, train_s["target"].values)
        clim = fit_climatology(train_s, LEADS)

        test_s["pred_base"] = m_base.predict(test_s[BASE_FEATURES].values)
        test_s["pred_temp"] = m_temp.predict(test_s[TEMP_FEATURES].values)
        test_s["pred_tempbucket"] = m_tb.predict(test_s[TEMPBUCKET_FEATURES].values)
        test_s["pred_clim"] = [
            float(eval_harmonic(np.array([d]), clim[int(h)])[0])
            for d, h in zip(test_s["doy"].values, test_s["horizon_h"].values)]
        test_s["issue_month"] = month[test_s["anchor_pos"].values.astype(int)]

        for _, r in test_s.iterrows():
            k = (int(r["horizon_h"]),
                 "wet" if int(r["issue_month"]) in WET_MONTHS else "dry")
            se["clim"][k].append((r["target"] - r["pred_clim"]) ** 2)
            se["base"][k].append((r["target"] - r["pred_base"]) ** 2)
            se["temp"][k].append((r["target"] - r["pred_temp"]) ** 2)
            se["tempbucket"][k].append((r["target"] - r["pred_tempbucket"]) ** 2)

        print(f"  Fold {fold_name}: train={len(train_s)}  test={len(test_s)}")

    def mse(lst):
        return float(np.mean(lst)) if lst else float("nan")

    def ss(num_pred, den_pred, ks):
        m = [e for k in ks for e in se[num_pred][k]]
        d = [e for k in ks for e in se[den_pred][k]]
        return (1 - mse(m) / mse(d)) if d and not np.isnan(mse(d)) else float("nan")

    results = {"leads": LEADS, "headline_leads": HEADLINE_LEADS, "per_lead": {}}
    for s in ("wet", "dry"):
        results["per_lead"][s] = {}
        for h in LEADS:
            k = [(h, s)]
            results["per_lead"][s][h] = {
                "n": len(se["temp"][(h, s)]),
                "rmse_clim_Mm3": round(np.sqrt(mse(se["clim"][(h, s)])), 3),
                "rmse_base_Mm3": round(np.sqrt(mse(se["base"][(h, s)])), 3),
                "rmse_temp_Mm3": round(np.sqrt(mse(se["temp"][(h, s)])), 3),
                "rmse_tempbucket_Mm3": round(np.sqrt(mse(se["tempbucket"][(h, s)])), 3),
                "SS_base_vs_clim": round(ss("base", "clim", k), 4),
                "SS_temp_vs_clim": round(ss("temp", "clim", k), 4),
                "SS_temp_marginal_vs_base": round(ss("temp", "base", k), 4),
                "SS_tempbucket_vs_clim": round(ss("tempbucket", "clim", k), 4),
                "SS_bucket_marginal_vs_temp": round(ss("tempbucket", "temp", k), 4),
            }

    def headline(season):
        ks = [(h, season) for h in HEADLINE_LEADS]
        n = sum(len(se["temp"][k]) for k in ks)
        return {
            "n": n,
            "SS_base_vs_clim": round(ss("base", "clim", ks), 4),
            "SS_temp_vs_clim": round(ss("temp", "clim", ks), 4),
            "SS_temp_marginal_vs_base": round(ss("temp", "base", ks), 4),
            "SS_tempbucket_vs_clim": round(ss("tempbucket", "clim", ks), 4),
            "SS_bucket_marginal_vs_temp": round(ss("tempbucket", "temp", ks), 4),
        }

    results["headline"] = {"wet": headline("wet"), "dry": headline("dry"),
                           "note": "perfect-prognosis (observed future temperature) "
                                   "upper bound; SS_temp_marginal_vs_base isolates "
                                   "the temperature block's contribution"}
    JSON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    hw, hd = results["headline"]["wet"], results["headline"]["dry"]
    lines = [
        "# Long-Range Forecast - Phase B Bake-off (temperature-only, with ablation)",
        "",
        "**Question:** does adding a temperature block to a season + antecedent-state",
        "model improve a 14-30 day forecast of cumulative Kinneret volume change,",
        "and does either beat a day-of-year climatology baseline?",
        "",
        "**Protocol:** walk-forward by held-out year (2021-2024); fresh forecast every",
        "7 days; target = cumulative volume change V(t+h)-V(t) [Mm3]; "
        "SS = 1 - MSE_a/MSE_b. Future temperature is OBSERVED - a **perfect-prognosis",
        "upper bound** (the live product can only do worse).",
        "",
        "Four predictors: **clim** (day-of-year harmonic of cumulative change), "
        "**base** (GBR on season + level + antecedent 30-day rain), **temp** (base +",
        "cloud_index, DTR, Tmax anomaly, Hargreaves ET0 over the horizon), and "
        "**tempbucket** (temp + the soil-moisture bucket's antecedent saturation state "
        "S and trailing-30d overflow Q - 'Architecture J done right'). The two decisive "
        "numbers: **SS_temp_marginal_vs_base** (what temperature adds) and "
        "**SS_bucket_marginal_vs_temp** (what the saturation-state bucket adds ON TOP of "
        "the flat rainfall_30d sum that Architecture J could not beat).",
        "",
        f"## Headline (leads {HEADLINE_LEADS[0]}-{HEADLINE_LEADS[-1]} d, pooled)",
        "",
        "| Season | n | SS base vs clim | SS temp vs clim | **SS temp marginal (vs base)** "
        "| **SS bucket marginal (vs temp)** |",
        "|---|---|---|---|---|---|",
        f"| Wet (Nov-Mar) | {hw['n']} | {hw['SS_base_vs_clim']:+.3f} | "
        f"{hw['SS_temp_vs_clim']:+.3f} | **{hw['SS_temp_marginal_vs_base']:+.3f}** "
        f"| **{hw['SS_bucket_marginal_vs_temp']:+.3f}** |",
        f"| Dry (Apr-Oct) | {hd['n']} | {hd['SS_base_vs_clim']:+.3f} | "
        f"{hd['SS_temp_vs_clim']:+.3f} | **{hd['SS_temp_marginal_vs_base']:+.3f}** "
        f"| **{hd['SS_bucket_marginal_vs_temp']:+.3f}** |",
        "",
        f"**'Architecture J done right' verdict (wet-season {HEADLINE_LEADS[0]}-"
        f"{HEADLINE_LEADS[-1]}d): bucket marginal = {hw['SS_bucket_marginal_vs_temp']:+.3f}** "
        "(S_max=150mm, untuned v0). Positive => the saturation-state bucket beats the flat "
        "30-day sum and J is healed; <=0 => an honest second negative.",
        "",
        "## Per-lead",
        "",
        "| Lead | Season | n | RMSE clim | RMSE base | RMSE temp | RMSE tempbucket "
        "| SS base | SS temp | SS temp marginal | SS bucket marginal |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in ("wet", "dry"):
        for h in LEADS:
            r = results["per_lead"][s][h]
            lines.append(
                f"| {h} | {s} | {r['n']} | {r['rmse_clim_Mm3']} | {r['rmse_base_Mm3']} "
                f"| {r['rmse_temp_Mm3']} | {r['rmse_tempbucket_Mm3']} "
                f"| {r['SS_base_vs_clim']:+.3f} | {r['SS_temp_vs_clim']:+.3f} "
                f"| {r['SS_temp_marginal_vs_base']:+.3f} "
                f"| {r['SS_bucket_marginal_vs_temp']:+.3f} |")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("\n=== Phase B headline (14-30 d, pooled) ===")
    print(f"  WET  base-vs-clim={hw['SS_base_vs_clim']:+.3f}  "
          f"temp-vs-clim={hw['SS_temp_vs_clim']:+.3f}  "
          f"temp-marginal={hw['SS_temp_marginal_vs_base']:+.3f}  "
          f"bucket-marginal={hw['SS_bucket_marginal_vs_temp']:+.3f}  (n={hw['n']})")
    print(f"  DRY  base-vs-clim={hd['SS_base_vs_clim']:+.3f}  "
          f"temp-vs-clim={hd['SS_temp_vs_clim']:+.3f}  "
          f"temp-marginal={hd['SS_temp_marginal_vs_base']:+.3f}  "
          f"bucket-marginal={hd['SS_bucket_marginal_vs_temp']:+.3f}  (n={hd['n']})")
    print(f"  J-done-right verdict (wet 14-30d bucket marginal): "
          f"{hw['SS_bucket_marginal_vs_temp']:+.3f}")
    print(f"  Wrote {REPORT_PATH}")
    print(f"  Wrote {JSON_PATH}")
    return results


if __name__ == "__main__":
    run()
