# CfC tournament results for the talk (from session data-science-project-be)

Append-only log of results the talk-deck session asked to track. Errors are mean absolute
lake-level errors (m), 16 test years (2010-2025) on the ERA5 bench, "average weather" ahead
unless stated. 130-365 d = mean of the 130, 260 and 365 day horizons.

## 1. GBR champion on the same bench (sha ec06e3d)
| model | 7 d | 13 d | 26 d | 130 d | 260 d | 365 d | 130-365 d |
|---|---|---|---|---|---|---|---|
| GBR (G) | 0.025 | 0.046 | 0.091 | 0.41 | 0.745 | 0.954 | 0.699 |
| CfC relay (A) | 0.024 | 0.044 | 0.086 | 0.399 | 0.744 | 0.964 | 0.699 |
| CfC direct (B14) | 0.026 | 0.046 | 0.090 | 0.42 | 0.723 | 0.933 | 0.688 |
| no change | 0.058 | 0.107 | 0.213 | 0.889 | 1.016 | 0.997 | 0.966 |

Known weather, 130-365 d: G 0.489, B14 0.446. All G-vs-CfC differences have 90% intervals
crossing zero: **the liquid network matches the champion; it does not beat it.** Caveat:
ERA5 has no rain intensity, so this GBR lacks one input; the GBR on IMS is next.

## 2. What the model needs to remember (sha 1d9d406) - CORRECTS an earlier line
Do NOT say "the lake's level is its own memory" as first phrased. 130-365 d error by what
the model sees of the past days:

| history | 7 days | 60 days |
|---|---|---|
| everything (weather, inflow, level/volume) | 0.686 | 0.694 |
| no level/volume | 0.751 | 0.752 |
| level/volume only | 0.744 | 0.755 |
| LSTM instead of CfC (7 / 60 / 120 d) | 0.700 | 0.684 (120 d: 0.690) |

Either half alone loses about 0.06 m. Safe line: **"a few days of the lake's own trend plus
the latest rain and river flow is all the memory it needs; longer history adds nothing, for
the liquid net and an LSTM alike."**
