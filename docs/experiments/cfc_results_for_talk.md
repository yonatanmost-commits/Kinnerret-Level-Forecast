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

## 6. T1 - weather source alone: ERA5 vs IMS, same model, same span, same test years (sha 4eb0788)
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

## 7. T3 - the GRU on the same bench (sha acb6877)
B14 with a GRU encoder (75 units, ~21k weights, about the CfC cell's size), 16 test years,
average weather.

| model | 7 d | 13 d | 26 d | 130 d | 260 d | 365 d | 130-365 d |
|---|---|---|---|---|---|---|---|
| GRU direct (B14gru) | 0.024 | 0.043 | 0.082 | 0.394 | 0.726 | 0.938 | 0.682 |
| CfC direct (B14) | 0.026 | 0.046 | 0.090 | 0.420 | 0.723 | 0.933 | 0.688 |
| CfC relay (A) | 0.024 | 0.044 | 0.086 | 0.399 | 0.744 | 0.964 | 0.699 |
| GBR champion (G) | 0.025 | 0.046 | 0.091 | 0.410 | 0.745 | 0.954 | 0.699 |

- 7-26 d: the GRU is slightly better than the CfC direct model (-0.005 m, 90% interval
  -0.006..-0.003) and than the GBR (-0.004, -0.008..-0.001). It ties the CfC relay.
- 130-365 d: all tie.
- **This bends the talk's "the GRU fails, the CfC wins" spine.** In the earlier one-day
  olympics the GRU failed; set up like the CfC here (same inputs, same direct multi-horizon
  head), it does as well or a few millimetres better. Safe line: "any good recurrent network
  matches the champion once it is set up right; the liquid network's edge is not accuracy
  alone." Don't claim the CfC beats the GRU.

## 8. The three models on the longer IMS station record, 2011-2025 (sha d19384b)
Gold rebuilt Tzemach-first from 2002-07 by the IMS session (branch tzemach-gold-1998 @ 81a2082,
not on master/live yet). 15 test years, each trained on all earlier years.

| model | weather ahead | 7 d | 26 d | 130 d | 260 d | 365 d | 130-365 d |
|---|---|---|---|---|---|---|---|
| CfC | average | 0.030 | 0.105 | 0.475 | 0.766 | 0.919 | **0.716** |
| GRU | average | 0.029 | 0.103 | 0.456 | 0.765 | 0.972 | 0.727 |
| GBR | average | 0.027 | 0.102 | 0.491 | 0.938 | 1.262 | 0.891 |
| CfC | actual | 0.023 | 0.073 | 0.410 | 0.773 | 0.899 | 0.690 |
| GRU | actual | 0.021 | 0.073 | 0.403 | 0.768 | 0.944 | 0.701 |
| GBR | actual | 0.020 | 0.071 | 0.299 | 0.570 | 0.776 | **0.545** |
| average change | - | 0.035 | 0.115 | 0.490 | 0.869 | 1.139 | 0.828 |

- 7-26 d: a three-way tie (all within 3 mm).
- 130-365 d, the real case (average weather ahead): the CfC and GRU tie; the GBR is clearly worse
  (+0.20 m, 90% interval +0.04..+0.37) and even worse than "average change".
- Given the ACTUAL weather, the GBR is best (0.55 vs 0.69). On this station data the networks
  barely use the weather of the window ahead; the GBR does, but only pays off with a good forecast.
- Talk: "with no forecast of the winter, the liquid network (and the GRU) give the best year-ahead
  outlook; the gradient-boosting champion only wins if someone hands it the coming winter's weather."

## 9. The PROCESS - how we got here, step by step (tactics, wrong turns, corrections)
Errors are mean absolute lake-level errors in metres. "Year ahead" = mean of the 130/260/365-day
horizons. "Average weather" = no forecast of the weather ahead; "actual weather" = a perfect one.

**0. Starting point (before the tournament)**
- The live champion: a two-stage gradient-boosting model (GBR), 7 days ahead, R² 0.77.
- The June "model olympics": the GRU scored R² ≈ 0 and was retired.
- A liquid network (CfC) relay on IMS station data, 2021-24: 365 days 0.57 m given the actual
  weather, 0.92 with average weather. That 0.57 looked like the number to beat, but it assumed a
  perfect weather forecast.

**1. Build one fair bench.** IMS station data only started in 2012 (too few winters), so we built
a 25-year ERA5 reanalysis table (2001-2025) and tested 16 years (2010-2025):
- a forecast every 7 days, at 7/13/26/130/260/365 days ahead
- every forecast run twice, with average and with actual weather
- 3 seeds per network
- the winner rule written down BEFORE any result
- every comparison paired (same start days) with a 90% interval over test years

**2. Round 1: how should a liquid network forecast far ahead?**
- A = relay (predict tomorrow, feed it back, 365 times)
- A1 = one-step relay
- B = direct (read the recent past, predict all horizons at once)

All-horizon errors: A 0.370, A1 0.374, B14 0.366 (winner), B60 0.368. All inside each other's
intervals: the architecture barely matters.

**3. Round 2: the elegant option fails.** C = a continuous-time decoder (the liquid network's
"natural" form):
- 0.442, worse than simply assuming an average year's change (0.423)
- a fair rerun (trained like B) was worse again, so C was retired

Lesson: the most elegant design was not the best one.

**4. How much past does it need?** History tested from 1 to 120 days, plus "blanking" old days
at test time:
- 3 days is as good as 120 (year ahead 0.686-0.697); 1 day is a bit worse (0.703)
- Why, tested rather than assumed: hiding the lake level/volume history costs 0.065 m, and a
  history of ONLY level/volume costs as much. The model needs both the lake's recent trend and
  the latest rain and river flow.
- We first claimed "the level is its own memory", then corrected it (section 2).
- An LSTM (an additive memory path) does use 60 days, but only reaches the 7-day CfC.

**5. Where the error really comes from.**
- Year-by-year errors track the coming winter's rain (Spearman 0.90 for autumn starts): record
  wet 2018-19 under-called by 2.3 m, dry 2024-25 over-called by 1.8 m.
- Given the actual weather, the year-ahead error drops from 0.93 to 0.55 at 365 days: 0.38 m of
  the error is simply not knowing the winter. From then on the question was the weather, not
  the network.

**6. Honesty checks that changed things.**
- Bug found and fixed: on the IMS table the relay could read the real future rain intensity
  under "average weather". No published number used that path.
- The "ERA5 costs 0.10 m" figure turned out to mix several differences.
- T1 (same model, same years, only the data source differs) does NOT support "quality beats
  quantity".

**7. The champion on the same bench.** The GBR on the 16-year ERA5 bench ties both CfC variants
at every horizon.

**8. The GRU, given a fair setup.**
- The June GRU predicted ONE day's change with no weather for that day.
- Set up like the CfC, it ties or edges it: 7-26 days 4-5 mm better.
- Lesson: the setup and the information decide, not the cell type.

**9. Ranges you can trust.**
- Ranges from past errors alone were too narrow: an "80%" range held only 61-72%.
- Adding a self-correction helped at short range but ballooned to 4 m at a year.
- Final method: run the past winters' weather through the model (one scenario per past winter),
  widen by the model's own error, then self-correct. The 80% range holds 81/79/78/75/72% at
  7/26/130/260/365 days, widths 5 cm .. 3.4 m.

**10. Can anyone forecast the winter?**
- Climate indices (ENSO, NAO, EA ...) from September-October: no (|rho| <= 0.33, 24 winters).
- Copernicus/ECMWF SEAS5 seasonal forecast, issued in September-November: weak but real skill
  (0.30-0.46). It picked 2018-19 wet and 2024-25 dry, and missed 2019-22.

**11. The longer station record (IMS, Tzemach-based, 2002-2025; 15 test years)**
- Week ahead: all three tie.
- Year ahead with average weather: CfC 0.72 = GRU 0.73, both better than GBR 0.89.
- With actual weather the GBR is best (0.55): the trees use the coming weather; the networks
  lean on the lake's state and the season.
- Dropping the humidity inputs (a station step in 2012-13) makes the networks 5 mm better at
  short range and the GBR worse.

**12. Using the seasonal forecast** (running; results 2026-10-16/17)
- Raw SEAS5 into the CfC: year ahead 0.688 -> 0.665 (about 2 cm of a possible 24).
- Calibration: SEAS5's monthly rain signal, fitted to what actually fell, should be SHRUNK
  (trust about 0.9 in the first month, 0.3-0.6 after), not stretched.
- GRU and GBR results to follow; the GBR is the one that might gain.

**13. Plumbing that had to work for any of this to go live.** The 07:30 daily refresh was fixed
on 2026-10-16 (two bugs, each pinned by a locked test), and live data is current again.

**Tactics worth saying on stage**
1. Write the winner rule before the results.
2. Compare paired forecasts, with intervals over years, not single numbers.
3. Bracket every result between "no forecast" (average weather) and "perfect forecast" (actual
   weather).
4. Use only what was knowable on the start day.
5. Test the "why", don't assert it, and publish the corrections.
6. Compare every idea against the champion and the GRU, not just against itself.

## 10. The seasonal forecast on the station record, and the decision for the 6-month product (sha b944504)
CfC, GRU and GBR on IMS 2011-2025 (15 test years), each with no forecast, raw Copernicus SEAS5,
and a perfect forecast. Year ahead = mean error at 130/260/365 days.

| model | no forecast | SEAS5 | perfect | autumn starts, SEAS5 |
|---|---|---|---|---|
| CfC | 0.718 | **0.701** | 0.688 | **0.854** |
| GRU | 0.726 | 0.706 | 0.703 | 0.892 |
| GBR | 0.891 | 0.860 | 0.545 | 0.956 |

- SEAS5 helps all three. The GBR gains most (-3.2 cm, because it leans hardest on the weather),
  but it still trails the CfC by 0.18 m (interval clear of zero). The CfC and GRU tie.
- **Decision: the 6-month product is the CfC with the raw SEAS5 forecast.**
- Calibrating SEAS5 did not beat raw. Month by month it lost half the gain; on the season total
  it equals raw (SEAS5's season signal is already the right size). Calibration is parked.

## 11. The fan and the red-line odds, tested (sha 1b95245, report v9)
- The fan: run the past winters' weather through the CfC, widen by the model's own error, and
  WEIGHT each past winter by how well it matches the SEAS5 forecast.
- The 80% range holds 82/81/79/78/78% at 7/13/26/130/260 days and 73% at a year; 50% holds
  about 50% everywhere.
- Red line -213 m, "chance the lake is below it in N days", scored against what happened.
  Skill against quoting the average odds (0 = no better, 1 = perfect):

| | 7 d | 26 d | 130 d | 260 d | 365 d |
|---|---|---|---|---|---|
| past winters equally likely | 0.98 | 0.93 | 0.68 | 0.40 | 0.27 |
| weighted by SEAS5 | 0.98 | 0.93 | **0.69** | **0.44** | **0.32** |

- Weighting by SEAS5 improves the red-line odds with an interval clear of zero (CfC Brier -0.006
  [-0.012, -0.001]; GRU the same). Honest at the ends: when it said under 10%, it happened 3% of
  the time; over 90%, 100%. Weighting fixed the 70-90% bin (said 78%, happened 79%, vs 68%
  unweighted). In the 30-50% bin it is too cautious (said 38%, happened 61%).
- The upper red line (-208.8 m) was never crossed in 2011-2025, so it can't be scored.
- Talk line: "we don't just say where the lake will be; we say how sure we are, and when we say
  80%, it happens about 80% of the time. A week ahead we know the level to within 5 cm; at six
  months the honest range is over a metre wide, and the seasonal forecast sharpens the odds of
  crossing the red line."

The report page (https://claude.ai/artifact/1WcstqPzV3bmoJHrhGwmnZ, v9) now opens with "How we
got here", a 14-step timeline, and ends with these charts: the three models on the station record,
what a seasonal forecast is worth, the fan calibration, the red-line reliability and skill, and
three autumn fans with the red line drawn.

## 12. A forecast from today - DRY RUN for the closing slide (2026-10-17)
Product 2 as chosen: the CfC on the IMS station record (Tzemach gold @ 81a2082), trained on
2002-2025, past winters' weather weighted by the October 2026 SEAS5 forecast. The latest weekly
start is **8 Oct 2026, level -213.65 m**, already below the lower red line (-213 m). "6 months" is
interpolated between the 130- and 260-day horizons. Refresh before 1 Nov.

| from 8 Oct 2026 | median | 80% range | chance still below -213 m |
|---|---|---|---|
| in 6 months (early April 2027) | -212.5 | -213.3 .. -210.6 | 21% |
| in 12 months (October 2027) | -212.7 | -214.2 .. -209.9 | **28%** (34% if every past winter counted equally) |

If the coming winter is like:
- **2018-19 (record wet):** about -211.0 m in 6 months, -210.5 m in 12 months
- **2024-25 (record dry):** about -213.5 m in 6 months, -214.5 m in 12 months

These two are single scenarios through the model, without its own error band.

SEAS5 leans **slightly wet**: an Oct-Mar season rain ratio of 1.06, 25th of 34 Octobers since
1993. Mostly early: October +57%, November +19%, December-February normal, March +14%. A weak
lean, so it tilts the odds only a little: 28% instead of 34%.
Plain phrase: "the seasonal forecast leans a little wetter than normal, mostly early in the winter."
