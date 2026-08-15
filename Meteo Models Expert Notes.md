Diagnosis: What's Limiting the Baseline

  Finding 1 — The transform exists but is never called (most
  important)

  signed_log1p_transform is defined in model_lib.py but not
  applied anywhere in run_cv or the final training. The S2
  target has skew=4.82, kurtosis=49. Worse: the 116 flood days
  where dvol > 5 Mm³ (2.4% of days) account for 58% of total
  variance. This means MSE is spending most of its gradient
  budget fighting a handful of extreme January floods, while
  systematically leaving accuracy on the table for the 97.6% of
   normal days. After the transform: skew drops to 0.88,
  kurtosis to 0.18. This is the most impactful fix available
  and costs zero new data.

  Finding 2 — Outflow is the strongest unused feature

  outflow_baptism_m3 — water pumped south out of the lake by
  the National Water Carrier — has 0.606 correlation with dvol
  and is present in the gold table at 92.4% fill. It is in none
   of the feature sets. It is pump-controlled and therefore
  highly predictable: lag-1 autocorrelation is 0.981, meaning
  today's outflow predicts tomorrow's almost perfectly.
  Yesterday's actual outflow is always known at inference time,
   so it can be added as an anchor feature without chaining.
  It's roughly 0.25–0.71 Mm³/day — material against an MAE of
  0.666.

  Finding 3 — Volume autocorrelation extends to lag 7 but S2
  only uses lag1/lag2

  volume_change autocorrelations: lag1=0.79, lag2=0.67,
  lag3=0.61, lag7=0.50. The S2 anchor only uses
  dvol_lag1_anchor. Lag2 and lag3 are available as additional
  anchor features at zero cost.

  Finding 4 — RBF seasonality features computed but never used

  The gold table contains rbf_spring_equinox,
  rbf_summer_solstice, rbf_autumn_equinox, rbf_winter_solstice
  — Gaussian bumps around each solstice/equinox. These provide
  seasonal resolution that sin/cos cannot: sin/cos gives a
  smooth symmetric curve; RBFs can localize the wet-season
  onset (roughly Nov–Mar) independently from the summer
  evaporation peak. They are in the gold table, in
  add_seasonality(), but absent from both S1_FEATURES and
  S2_FEATURES.

  Finding 5 — Precipitation intensity unused

  precip_intensity_mm_hr (peak 1-hour intensity derived from
  10-minute data) has 0.31 correlation with dvol and 99.3%
  fill. Flash flooding is driven by intensity, not just total
  daily rainfall — a 50mm/hr burst generates far more runoff
  than 50mm spread over 12 hours. This matters specifically for
   the extreme events identified above.

  Finding 6 — Hyperparameters conservative, never tuned

  CV uses 150 rounds / lr=0.05 / max_depth=4. Final training
  uses 250 rounds. No learning rate schedule, no early
  stopping, no column subsampling tuning. XGBoost and LightGBM
  in Round 2 were run with default settings — the 0.05 R² gap
  vs. baseline may be largely attributable to the two-stage OOF
   stacking advantage, not to the GBR algorithm being
  fundamentally superior.

  ---
  Round 3 Proposal: "Signal Harvest"

  Theme: four clean experiments, each testing one diagnostic in
   isolation, plus one combined. Every candidate reuses the
  direct S2 / semi-chained S1 inference architecture — no new
  data sources needed.

  ---
  Architecture F — signed_log1p target transform

  Hypothesis: The model is distorted by extreme events.
  Transforming the S2 target before fitting and inverting after
   prediction lets the gradient treat a 37 Mm³ flood as 3.6,
  not 37, so normal days receive proper gradient attention.

  What changes: In run_cv and train_final_gbr, wrap S2 fitting
  with:
  y_train = signed_log1p_transform(s2_tr[S2_TARGET].values)
  rf2.fit(s2_tr[S2_FEATURES].values, y_train)
  p2 = inv_signed_log1p_transform(rf2.predict(s2_te[S2_FEATURES
  ].values))
  Nothing else changes. The functions already exist in
  model_lib.py.

  Expected impact: HIGH — addressing skew=4.82 / kurtosis=49 is
   the textbook fix for this situation. The transform won't
  hurt the good days and should significantly reduce systematic
   underprediction on moderate-inflow days that happen to sit
  in the heavy tail's shadow.

  Risk: None — the inverse is applied before any evaluation, so
   metrics are still in original Mm³.

  ---
  Architecture G — outflow anchor in S2

  Hypothesis: The pump at Baptism Site removes 0.25–0.71
  Mm³/day. This is the largest unused physical driver of net
  volume change. Adding yesterday's actual outflow as an anchor
   feature gives S2 a direct lever to adjust for "heavy pumping
   weeks" that otherwise look identical to non-pumping weeks
  from the weather alone.

  What changes:
  - New feature constant: S2_DIRECT_FEATURES_WITH_OUTFLOW =
  S2_DIRECT_FEATURES + ["outflow_lag1_m3"]
  - Build training data from df["outflow_baptism_m3"].shift(1)
  as outflow_lag1_m3
  - At inference: always use yesterday's actual outflow (it's
  measured, not forecast)
  - Requires updating 09_weekly_forecast.py to pull last
  outflow from history

  Expected impact: MEDIUM-HIGH — 0.606 correlation is the
  second strongest signal in the gold table not already in the
  model. outflow autocorrelation of 0.98 means using lag1 as an
   anchor is almost as good as knowing today's outflow.

  Risk: Low — only 92.4% fill (vs 99% for inflow). The
  remaining 7.6% is imputed by the model's NaN median fill.
  Could add noise on missing rows.

  ---
  Architecture H — enriched feature set

  Hypothesis: Several complementary signals are sitting unused
  in the gold table. Adding them together should compound.

  What changes:
  - Add to both S1 and S2: precip_intensity_mm_hr,
  rbf_spring_equinox, rbf_summer_solstice, rbf_autumn_equinox,
  rbf_winter_solstice
  - Add to S2 anchor state: dvol_lag2_anchor, dvol_lag3_anchor
  (today we only anchor on lag1; lag2 and lag3 autocorr are
  0.67 and 0.61)
  - No architecture change — same direct/semi-chained inference

  Expected impact: MEDIUM — each individual feature is modest,
  but 7+ new features covering intensity, richer seasonality,
  and deeper momentum should add 0.01–0.03 R². The RBF features
   alone should help the model distinguish early winter onset
  from mid-summer heatwaves, which sin/cos cannot.

  Risk: Low — all features have ≥99% fill except lag3 (96%).
  The GBRegressor's NaN imputation handles the rest.

  ---
  Architecture I — F + G + H combined

  Everything above together. Tests whether the improvements
  compound or cannibalize each other. If F is the dominant
  effect, adding G and H on top should still help. If they
  don't combine well, the comparison isolates which individual
  change drove the result.

  ---
  Expected Ranking Prediction

  Architecture I  (F+G+H)     R² ~0.73–0.75  [if all three
  compound]
  Architecture F  (transform) R² ~0.72–0.74  [single biggest
  lever]
  Architecture H  (features)  R² ~0.70–0.72
  Architecture G  (outflow)   R² ~0.70–0.71
  baseline_gbr                R² = 0.694     [current winner]

  The transform (F) is the most confident prediction. The
  outflow (G) and feature enrichment (H) have higher
  uncertainty because they depend on how much the model was
  already implicitly capturing those signals through correlated
   features. The combined (I) is the most likely to set a new
  record.

  ---
  One caution

  The 2023 fold consistently scores the worst (R² ≈ 0.50 across
   all architectures). Worth checking whether 2023 had abnormal
   meteorological conditions (drought year? atypical flood
  pattern?) that all models fail on equally — if so, it's a
  data/labeling issue, not a model issue. This affects whether
  reported mean R² is the right summary metric.
