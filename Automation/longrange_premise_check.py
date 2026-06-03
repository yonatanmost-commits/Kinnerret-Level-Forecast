"""
longrange_premise_check.py - PHASE A MAKE-OR-BREAK GATE.

Quantifies whether the temperature-derived rain signature (cloud_index from low
DTR vs the clear-sky envelope, plus negative Tmax anomaly), in the wet season,
actually predicts wet days / rainfall / inflow in the gold record. If the
wet-season AUC is below threshold, the product premise fails and Phase B must not
start. Writes docs/longrange_premise_report.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from longrange_meteo import cloud_index
from longrange_climatology import (fit_harmonic, eval_harmonic, clearsky_dtr_by_doy,
                                    anomaly_zscore)

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "Gold Data" / "kinneret_gold_features.csv"
REPORT_PATH = ROOT / "docs" / "longrange_premise_report.md"
WET_SEASON_MONTHS = {11, 12, 1, 2, 3}     # Nov-Mar
REQUIRED_COLS = ["date", "temp_max_C", "temp_min_C", "rainfall_mm"]


def wet_day_auc(score, wet):
    """ROC AUC of a continuous `score` predicting a binary `wet` label, via the
    Mann-Whitney U relationship. No sklearn dependency."""
    score = np.asarray(score, dtype=float)
    wet = np.asarray(wet, dtype=bool)
    ok = ~np.isnan(score)
    score, wet = score[ok], wet[ok]
    n_pos, n_neg = wet.sum(), (~wet).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(score, return_inverse=True, return_counts=True)
    sum_ranks = np.zeros(len(counts))
    np.add.at(sum_ranks, inv, ranks)
    ranks = (sum_ranks / counts)[inv]
    auc = (ranks[wet].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def evaluate_premise(gold: pd.DataFrame, auc_threshold=0.6):
    missing = [c for c in REQUIRED_COLS if c not in gold.columns]
    if missing:
        raise ValueError(f"gold table missing required columns: {missing}")
    g = gold.copy()
    g["date"] = pd.to_datetime(g["date"])
    doy = g["date"].dt.dayofyear.values
    dtr = (g["temp_max_C"] - g["temp_min_C"]).values

    dtr_cs = eval_harmonic(doy, clearsky_dtr_by_doy(doy, dtr))
    ci = cloud_index(dtr, dtr_cs)
    tmax_mean_c = fit_harmonic(doy, g["temp_max_C"].values)
    tmax_anom_z = anomaly_zscore(doy, g["temp_max_C"].values, tmax_mean_c)
    # combined rain-propensity score: cloudier + colder-than-normal => wetter
    score = ci - 0.5 * tmax_anom_z

    wet = g["rainfall_mm"].values > 1.0
    is_wet_season = g["date"].dt.month.isin(WET_SEASON_MONTHS).values

    overall_auc = wet_day_auc(score, wet)
    wet_season_auc = wet_day_auc(score[is_wet_season], wet[is_wet_season])
    # correlation of cloud_index with same-day rainfall (wet season). Mask the
    # handful of missing-temp days (NaN DTR -> NaN ci); a single NaN would
    # otherwise make np.corrcoef return nan for the whole series.
    ws = is_wet_season
    ci_ws = ci[ws]
    rain_ws = g["rainfall_mm"].values[ws]
    cmask = ~np.isnan(ci_ws) & ~np.isnan(rain_ws)
    corr = (np.corrcoef(ci_ws[cmask], rain_ws[cmask])[0, 1]
            if cmask.sum() > 1 else float("nan"))

    verdict = "PASS" if (wet_season_auc >= auc_threshold) else "FAIL"
    return {
        "overall_auc": overall_auc,
        "wet_season_auc": wet_season_auc,
        "wet_season_cloud_rain_corr": float(corr),
        "auc_threshold": auc_threshold,
        "verdict": verdict,
    }


def main():
    gold = pd.read_csv(GOLD_PATH, encoding="utf-8-sig")
    res = evaluate_premise(gold)
    lines = [
        "# Long-Range Forecast - Premise Check (Phase A gate)", "",
        f"- Wet-season wet-day AUC: **{res['wet_season_auc']:.3f}** "
        f"(threshold {res['auc_threshold']:.2f})",
        f"- Overall wet-day AUC: {res['overall_auc']:.3f}",
        f"- Wet-season cloud_index vs rainfall corr: {res['wet_season_cloud_rain_corr']:.3f}",
        "", f"## Verdict: **{res['verdict']}**", "",
        "PASS => proceed to Phase B bake-off. FAIL => temperature does not carry"
        " enough rain signal in our data; revisit the premise before modeling.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
