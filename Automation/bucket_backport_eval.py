"""
bucket_backport_eval.py - Bring the soil-moisture bucket HOME to the 7-day model.

The bucket ("Architecture J done right") was vindicated in the long-range product
(longrange_phaseb_eval.py: +0.26/+0.28 marginal). But its true purpose was always to
mend the 7-day two-stage champion's weakest fold - 2023 (drought) - the failure that
birthed Architecture J. J underdelivered because flat 30/45-day rainfall SUMS cannot
encode catchment saturation: its tell was failing in OPPOSITE directions on the wet
(2021) and dry (2023) folds. The pre-registered admission criterion is therefore NOT
mean R2 (the metric J nearly passed as a null) but whether the bucket SHRINKS THE
2021-wet / 2023-dry SIGNED-RESIDUAL GAP.

This script is NON-DESTRUCTIVE: it never touches 08_train_forecast_model.py or
model_lib.py. It replicates the champion's baseline two-stage walk-forward CV exactly
(via model_lib's feature lists, GBRegressor, transforms) and runs it twice - WITHOUT
and WITH the bucket state (S, trailing-30d overflow Q) added to the S1/S2 features -
then reports per-fold S2 R2, the signed-residual fold-gap, and the verdict.

Writes docs/bucket_backport_report.md and _results.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Automation"))

from model_lib import (GBRegressor, S1_FEATURES, S1_TARGET, S2_FEATURES, S2_TARGET,
                       signed_log1p_transform, inv_signed_log1p_transform)
from longrange_state import soil_moisture_bucket

GOLD_FILE = ROOT / "Gold Data" / "kinneret_gold_features.csv"
REPORT_PATH = ROOT / "docs" / "bucket_backport_report.md"
JSON_PATH = ROOT / "docs" / "bucket_backport_results.json"

# Identical to 08_train_forecast_model.GBR_CV_PARAMS (single source of truth there;
# copied here so this ablation never imports the prefixed training script).
GBR_CV_PARAMS = dict(n_estimators=300, max_depth=4, min_leaf=10,
                     learning_rate=0.03, random_state=42)
CV_FOLDS = [
    ("2021", list(range(2012, 2021)), 2021),
    ("2022", list(range(2012, 2022)), 2022),
    ("2023", list(range(2012, 2023)), 2023),
    ("2024", list(range(2012, 2024)), 2024),
]
BUCKET_FEATURES = ["bucket_S", "bucket_Q30"]
BUCKET_S_MAX = 150.0   # mm, untuned mid-range v0 (matches longrange eval)


def r2(y, yhat):
    y, yhat = np.asarray(y), np.asarray(yhat)
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def load_data() -> pd.DataFrame:
    df = (pd.read_csv(GOLD_FILE, parse_dates=["date"])
          .sort_values("date").reset_index(drop=True))
    df["rainfall_lag1_mm"] = df["rainfall_mm"].shift(1)
    df["rainfall_lag2_mm"] = df["rainfall_mm"].shift(2)
    df["rainfall_lag3_mm"] = df["rainfall_mm"].shift(3)
    df["predicted_inflow_m3"] = np.nan
    # Causal soil-moisture bucket state (same construction as the long-range eval)
    rain = df["rainfall_mm"].fillna(0.0).values
    et = df["et0_mm"].fillna(df["et0_mm"].median()).values
    S, Q = soil_moisture_bucket(rain, et, S_max=BUCKET_S_MAX, S0=0.5 * BUCKET_S_MAX)
    df["bucket_S"] = S
    df["bucket_Q30"] = pd.Series(Q).rolling(30, min_periods=1).sum().values
    return df


def run_variant(df: pd.DataFrame, s1f: list, s2f: list) -> dict:
    """Replicate the champion baseline two-stage CV (08_train_forecast_model.run_cv)
    with the given feature lists. Returns per-fold S2 R2 and signed residual
    (mean(pred - actual)) on volume_change."""
    per_fold = {}
    for fold_name, train_yrs, test_yr in CV_FOLDS:
        tr = df[df["date"].dt.year.isin(train_yrs)].copy()
        te = df[df["date"].dt.year == test_yr].copy()

        # Stage 1
        s1_tr = tr.dropna(subset=s1f + [S1_TARGET])
        s1_te = te.dropna(subset=s1f + [S1_TARGET])
        rf1 = GBRegressor(**GBR_CV_PARAMS)
        rf1.fit(s1_tr[s1f].values, s1_tr[S1_TARGET].values)
        p1 = np.clip(rf1.predict(s1_te[s1f].values), 0, None)
        s1_r2 = r2(s1_te[S1_TARGET].values, p1)

        # Stage 2 (train on actual inflow proxy; eval with OOF Stage-1 prediction)
        tr_s2 = tr.copy()
        tr_s2["predicted_inflow_m3"] = tr_s2[S1_TARGET]
        te_s2 = te.copy()
        te_s2["predicted_inflow_m3"] = np.nan
        te_s2.loc[s1_te.index, "predicted_inflow_m3"] = p1

        s2_tr = tr_s2.dropna(subset=s2f + [S2_TARGET])
        s2_te = te_s2.dropna(subset=s2f + [S2_TARGET])
        rf2 = GBRegressor(**GBR_CV_PARAMS)
        rf2.fit(s2_tr[s2f].values, signed_log1p_transform(s2_tr[S2_TARGET].values))
        p2 = inv_signed_log1p_transform(rf2.predict(s2_te[s2f].values))

        actual = s2_te[S2_TARGET].values
        per_fold[fold_name] = {
            "n": int(len(s2_te)),
            "s1_r2": round(s1_r2, 3),
            "s2_r2": round(r2(actual, p2), 3),
            "s2_signed_resid_Mm3": round(float(np.mean(p2 - actual)), 4),
        }
    return per_fold


def summarise(per_fold: dict) -> dict:
    r2s = [per_fold[f]["s2_r2"] for f in per_fold]
    sr21 = per_fold["2021"]["s2_signed_resid_Mm3"]
    sr23 = per_fold["2023"]["s2_signed_resid_Mm3"]
    return {
        "mean_s2_r2": round(float(np.mean(r2s)), 3),
        "signed_resid_2021": sr21,
        "signed_resid_2023": sr23,
        "fold_gap_2021_2023": round(sr21 - sr23, 4),
        "abs_fold_gap": round(abs(sr21 - sr23), 4),
    }


def run():
    df = load_data()
    base = run_variant(df, S1_FEATURES, S2_FEATURES)
    buck = run_variant(df, S1_FEATURES + BUCKET_FEATURES, S2_FEATURES + BUCKET_FEATURES)
    sb, sk = summarise(base), summarise(buck)

    gap_shrunk = sk["abs_fold_gap"] < sb["abs_fold_gap"]
    r2_change = round(sk["mean_s2_r2"] - sb["mean_s2_r2"], 3)
    results = {
        "baseline": {"per_fold": base, **sb},
        "with_bucket": {"per_fold": buck, **sk},
        "verdict": {
            "abs_fold_gap_baseline": sb["abs_fold_gap"],
            "abs_fold_gap_with_bucket": sk["abs_fold_gap"],
            "fold_gap_shrunk": bool(gap_shrunk),
            "mean_r2_change": r2_change,
            "criterion": "PASS if the 2021-2023 abs signed-residual gap shrinks "
                         "(pre-registered); mean R2 is secondary.",
        },
    }
    JSON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    def fold_row(tag, pf):
        return (f"| {tag} | {pf['2021']['s2_r2']:+.3f} | {pf['2022']['s2_r2']:+.3f} "
                f"| {pf['2023']['s2_r2']:+.3f} | {pf['2024']['s2_r2']:+.3f} |")

    lines = [
        "# Soil-Bucket Back-port to the 7-day Model - Ablation",
        "",
        "Non-destructive ablation of the two-stage champion (08_train_forecast_model)",
        "with vs without the soil-moisture bucket state (S, trailing-30d overflow Q)",
        "added to the S1/S2 features, beside the flat rainfall_30d/45d sums that",
        "Architecture J could not make work. Pre-registered criterion: the bucket must",
        "SHRINK the 2021-wet / 2023-dry signed-residual gap, not merely move mean R2.",
        "",
        "## Stage-2 R2 by fold",
        "",
        "| Variant | 2021 | 2022 | 2023 | 2024 |",
        "|---|---|---|---|---|",
        fold_row("baseline", base),
        fold_row("with bucket", buck),
        "",
        "## The pre-registered criterion: 2021-wet / 2023-dry signed-residual gap",
        "",
        "| Variant | signed resid 2021 (Mm3) | signed resid 2023 (Mm3) | **abs gap** | mean S2 R2 |",
        "|---|---|---|---|---|",
        f"| baseline | {sb['signed_resid_2021']:+.4f} | {sb['signed_resid_2023']:+.4f} "
        f"| **{sb['abs_fold_gap']:.4f}** | {sb['mean_s2_r2']:.3f} |",
        f"| with bucket | {sk['signed_resid_2021']:+.4f} | {sk['signed_resid_2023']:+.4f} "
        f"| **{sk['abs_fold_gap']:.4f}** | {sk['mean_s2_r2']:.3f} |",
        "",
        f"## Verdict: **{'PASS - bucket comes home' if gap_shrunk else 'FAIL - gap not shrunk'}**",
        "",
        f"- Abs fold-gap: {sb['abs_fold_gap']:.4f} -> {sk['abs_fold_gap']:.4f} "
        f"({'shrunk' if gap_shrunk else 'not shrunk'}).",
        f"- Mean S2 R2 change: {r2_change:+.3f} (secondary).",
        "",
        "PASS => the saturation-state bucket fixes the opposite-direction wet/dry",
        "failure that flat sums (Architecture J) could not, and is a justified addition",
        "to the 7-day champion. FAIL => the wound is real and stays named honestly.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("=== Bucket back-port to 7-day model ===")
    print(f"  baseline    : mean S2 R2={sb['mean_s2_r2']:.3f}  "
          f"signed[2021]={sb['signed_resid_2021']:+.4f}  "
          f"signed[2023]={sb['signed_resid_2023']:+.4f}  absgap={sb['abs_fold_gap']:.4f}")
    print(f"  with bucket : mean S2 R2={sk['mean_s2_r2']:.3f}  "
          f"signed[2021]={sk['signed_resid_2021']:+.4f}  "
          f"signed[2023]={sk['signed_resid_2023']:+.4f}  absgap={sk['abs_fold_gap']:.4f}")
    print(f"  VERDICT: {'PASS (gap shrunk)' if gap_shrunk else 'FAIL (gap not shrunk)'}"
          f"  mean-R2 change={r2_change:+.3f}")
    print(f"  Wrote {REPORT_PATH}")
    return results


if __name__ == "__main__":
    run()
