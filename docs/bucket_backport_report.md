# Soil-Bucket Back-port to the 7-day Model - Ablation

Non-destructive ablation of the two-stage champion (08_train_forecast_model)
with vs without the soil-moisture bucket state (S, trailing-30d overflow Q)
added to the S1/S2 features, beside the flat rainfall_30d/45d sums that
Architecture J could not make work. Pre-registered criterion: the bucket must
SHRINK the 2021-wet / 2023-dry signed-residual gap, not merely move mean R2.

## Stage-2 R2 by fold

| Variant | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| baseline | +0.704 | +0.884 | +0.680 | +0.816 |
| with bucket | +0.643 | +0.875 | +0.690 | +0.832 |

## The pre-registered criterion: 2021-wet / 2023-dry signed-residual gap

| Variant | signed resid 2021 (Mm3) | signed resid 2023 (Mm3) | **abs gap** | mean S2 R2 |
|---|---|---|---|---|
| baseline | +0.2869 | +0.1857 | **0.1012** | 0.771 |
| with bucket | +0.3266 | +0.1294 | **0.1972** | 0.760 |

## Verdict: **FAIL - gap not shrunk**

- Abs fold-gap: 0.1012 -> 0.1972 (not shrunk).
- Mean S2 R2 change: -0.011 (secondary).

PASS => the saturation-state bucket fixes the opposite-direction wet/dry
failure that flat sums (Architecture J) could not, and is a justified addition
to the 7-day champion. FAIL => the wound is real and stays named honestly.