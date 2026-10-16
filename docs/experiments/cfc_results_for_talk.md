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

## 3. Is this an experienced field? A quick check of similar work (2026-10-16)
Two web searches, not a full literature review. Verify before quoting on a slide.

**The Kinneret**
- Water balance and climate projections (Rimmer et al., Kinneret Limnological Laboratory):
  inflow regression plus a Penman-type evaporation model; projected about 10% less usable
  water for 2015-2035. Annual and long-term, not an operational forecast.
  https://meetingorganizer.copernicus.org/EGU2010/EGU2010-6424.pdf
- Upper Jordan "systems hydrology" (Rimmer, 2006): monthly water, salt and heat balances.
  https://www.lakescientist.com/?p=11466
- A coupled SWAT+ / MODFLOW catchment model (surface plus groundwater), described by its
  authors as still in development. https://swat.tamu.edu/media/vjkhp1i4/elad.pdf
- WEAP water-planning model of the Kinneret system. https://weap.sei.org/downloads/Kinneret.pdf
- A 2023 multi-model study ran 1-D lake models (FLake, GLM, GOTM, Simstrat) under climate
  projections for future evaporation. The summary found gives an inconsistent model count;
  check the paper before citing.
- The Water Authority's operational outlooks are scenario statements, e.g. "with average rain
  the lake ends the season at -210.80 m", alongside a dry-winter scenario. This is our
  past-winters fan done by hand with 2-3 scenarios.
  https://en.globes.co.il/en/article-1000807186
- No published daily machine-learning forecast of the Kinneret level at several horizons was found.

**Lakes in general**
- Great Lakes, 2024: linear regression vs NARX vs Prophet vs LSTM; the simpler NARX was best on
  every lake, and the LSTM struggled on some.
  https://research.itu.edu.tr/en/publications/model-based-prediction-of-water-levels-for-the-great-lakes-a-comp/
- 2020 study: much of the lake-level machine-learning literature leaks future data (the
  "future data" problem). https://meetingorganizer.copernicus.org/EGU2020/EGU2020-4233.html
- From general knowledge, not checked in this search: the US Army Corps of Engineers and
  Environment Canada issue official 6-month Great Lakes level outlooks from seasonal climate
  forecasts. There are similar efforts for the Caspian Sea, Lake Victoria and Lake Urmia.

**What it means for the talk**
1. "Simple models match deep ones" is a known result, so our GBR tying the CfC is credible.
2. Look-ahead is the field's known trap. Every result here uses only what was known at the
   start day (average weather from training years, bands from already-observed errors,
   seasonal forecasts only once published).
3. Seasonal forecasts driving 6-month lake outlooks is what the Great Lakes agencies do, so
   the SEAS5 test (running, results expected 2026-10-17) is on established ground.
4. What looks new for the Kinneret: daily data-driven forecasts at 7-365 days, scored honestly
   over 16 years; skill limited by the coming winter; calibrated uncertainty; a liquid
   network in the role.

## 4. GBR champion on the IMS table, with rain intensity (sha 4e8c214)
The fair fight: the GBR gets all its inputs. IMS test years 2021-2024 (2025 has no 365 d outcome yet).

| model | 7 d | 13 d | 26 d | 130 d | 260 d | 365 d | 130-365 d |
|---|---|---|---|---|---|---|---|
| GBR (G) | 0.028 | 0.046 | 0.089 | 0.404 | 0.726 | 0.866 | 0.667 |
| CfC direct (B14) | 0.028 | 0.047 | 0.086 | 0.387 | 0.609 | 0.759 | 0.587 |
| average change | 0.033 | 0.055 | 0.101 | 0.433 | 0.745 | 0.885 | 0.689 |

Short range: a tie. Long range: B14 is 0.08 m better on 2021-24 (90% interval -0.01..+0.16).
Including the 2025 starts, 0.13 m better with an interval clear of zero (+0.03..+0.34).
Only 4-5 test years, so "the liquid network is ahead at long range on IMS" is fair; "proven" is not.
Given the actual weather, the GBR chain gets WORSE at long range (365 d 1.13 vs 0.87 with
average weather) while B14 improves (0.75): the GBR relay drifts when fed real extremes.

## 5. Forecast ranges (fan) and how honest they are (sha 20807ff module, 0696cb4 report)
Method: run the past winters' weather through B14 (one scenario per earlier year), widen by
B14's own error when the weather is known, self-correcting as outcomes arrive. 16 test years.

| range | 7 d | 13 d | 26 d | 130 d | 260 d | 365 d |
|---|---|---|---|---|---|---|
| 50% range: outcomes inside | 49% | 50% | 48% | 47% | 46% | 48% |
| 80% range: outcomes inside | 81% | 81% | 79% | 78% | 75% | 72% |
| 80% range: typical width | 0.05 m | 0.09 m | 0.18 m | 1.2 m | 2.4 m | 3.4 m |

Talk lines: "a week ahead we know the level to within about 5 cm; six months ahead the honest
range is over a metre, because it depends on a winter nobody can forecast yet." At 260-365 d
the 80% range still misses the record winters (2018-19 wet, 2024-25 dry) more often than
promised. The report has three example fans (autumn 2018, 2020, 2024).

## 6. T1 - weather source alone: ERA5 vs IMS, same model, same span, same test years (sha below)
B14 trained on ERA5 cut to the IMS period (from 2012-09-01) vs B14 on IMS. Test years 2021-2024.

| B14 trained on | weather ahead | 7 d | 26 d | 130 d | 260 d | 365 d | 130-365 d |
|---|---|---|---|---|---|---|---|
| IMS stations | average | 0.028 | 0.086 | 0.387 | 0.609 | 0.759 | **0.587** |
| ERA5, same span | average | 0.028 | 0.089 | 0.427 | 0.760 | 0.955 | 0.716 |
| ERA5, from 2001 | average | 0.026 | 0.081 | 0.385 | 0.696 | 0.962 | 0.683 |
| IMS stations | actual | 0.021 | 0.073 | 0.300 | 0.575 | 0.753 | 0.544 |
| ERA5, same span | actual | 0.027 | 0.085 | 0.291 | 0.624 | 0.649 | 0.523 |

- Short range: a tie.
- Long range, average weather ahead: IMS ahead by 0.13 m, but the 90% interval crosses zero
  (-0.08..+0.36). With only 4 test years, not significant.
- Given the actual weather, ERA5 is as good or slightly better (0.52 vs 0.54). The station
  data's edge does not come from describing the weather better.
- More ERA5 years (2001+ vs 2012+) help a little (0.68 vs 0.72), also not significant.

Talk: **"quality beats quantity" is NOT supported by this test.** A safe line: "on the same
years, the station-trained model forecast the next year better with average weather (0.59 vs
0.72 m), but four years can't settle it, and given the actual weather the satellite-era
reanalysis does as well." The earlier "0.10 m" figure mixed several differences (see section Q6
of the message history); prefer this test.
