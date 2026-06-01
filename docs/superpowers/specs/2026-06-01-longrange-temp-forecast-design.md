# Long-Range Temperature-Only Level Forecast — Design

**Date:** 2026-06-01
**Author:** Brainstormed with the user (expert framing by the Dr. Wade Storm persona)
**Status:** Approved design, pending spec review

## Purpose

Build a **new, second forecast product** (the existing validated 7-day two-stage
GBR is untouched) that extends the Kinneret level forecast out to a **14–30 day
daily path**, driven by the only input that is reliably available that far ahead:
a long-range **min/max temperature** forecast (IMS extended forecast when up;
Open-Meteo 16-day as the live fallback).

The governing design tension the user set: **isolate the shortest chain from the
two temperatures to volume change, to minimise error propagation** — while still
*estimating* (not ignoring) the rainfall the temperature forecast cannot see
directly.

## Locked scope decisions

| Decision | Choice |
|---|---|
| Product role | **New long-horizon product**, parallel to the 7-day model |
| Horizon / output | **Daily level path, ~14–30 days** |
| Rainfall | **Estimated, not ignored** — from the signal latent in the temp forecast |
| Process | **A) deepen data → B) bake-off 2–3 approaches → C) design winner** |
| Data role split | **(B)**: full 60-yr record → climatology + stationary met relationships; modern consistent period → supervised ΔVolume target |

## The core insight (why two temperatures can reach the lake)

In this climate the temperature forecast is *already leaking rain information*:

1. **Diurnal range (Tmax − Tmin)** is a cloud/rain gauge — a cloud deck caps the
   daytime max and traps heat at night, so the range collapses before/during
   rain. (Hargreaves uses √DTR as a clear-sky radiation proxy for exactly this
   reason.)
2. **Cold Tmax anomalies in winter** are frontal signals — Israel's rain
   (Oct–May) arrives with Cyprus Lows / cold fronts that drop daytime Tmax below
   the seasonal normal.
3. **Season gates everything** — the same cold/compressed signature means rain in
   January and nothing in July.

Therefore temperature predicts rain **propensity** (odds + rough magnitude), never
the exact storm total — so every candidate must emit an **uncertainty band**, not
just a line. And evaporation is reachable *deterministically* from two
temperatures via Hargreaves (Group 2 below), because extraterrestrial radiation
is a closed-form function of date + latitude (Group 1).

## Non-stationarity strategy (decision B)

The level record runs to the 1960s, but what *drives* level change is
non-stationary: National Water Carrier pumping began 1964, plus drought-policy and
deliberate-refill regimes. Meteorological physics (temp→evaporation,
temp-signature→rain) **is** stationary. So:

- **Full 60-yr record** (ERA5/ERA5-Land reanalysis) → robust **climatology
  normals** and the **stationary met relationships** (Hargreaves ET₀, the
  temp→rain estimator, even temp→inflow where inflow history allows).
- **Modern consistent period** (≈2012+, matching the existing gold) → the
  **supervised ΔVolume target** and the **outflow climatology**.

The long record teaches the *weather*; the recent record teaches *today's lake*.

---

# Calculation reference (the hard-to-reconstruct core)

All forms follow FAO-56 Irrigation & Drainage Paper 56 so a future session can
verify against a known reference. Latitude **φ = 32.7724°N = 0.5720 rad**.

### Group 1 — Deterministic astronomy (known exactly for any future date)
For day-of-year `J` (1–366):
```
dr  = 1 + 0.033·cos(2π·J/365)                       # inverse Earth–Sun distance
δ   = 0.409·sin(2π·J/365 − 1.39)                    # solar declination [rad]
ωs  = arccos(−tan(φ)·tan(δ))                        # sunset hour angle [rad]
Ra  = (24·60/π)·Gsc·dr·[ωs·sin(φ)·sin(δ) + cos(φ)·cos(δ)·sin(ωs)]   # MJ m⁻² d⁻¹
N   = (24/π)·ωs                                      # daylight hours
```
`Gsc = 0.0820 MJ m⁻² min⁻¹` (solar constant). Every term is closed-form in
date + latitude — **no forecast required**. This is what lets two temperatures
reach all the way to evaporation.

### Group 2 — Hargreaves–Samani ET₀ (needs only Tmin, Tmax, Ra)
```
Tmean   = (Tmax + Tmin)/2                            # °C
ET0_HS  = 0.0023 · (0.408·Ra) · (Tmean + 17.8) · √(Tmax − Tmin)   # mm d⁻¹
```
`0.408 = 1/λ` (λ = 2.45 MJ kg⁻¹, latent heat of vaporisation; MJ m⁻² → mm).
**Calibration (Phase A):** regress `ET0_HS` against the existing Penman–Monteith
`et0_mm` in gold over the 2012–2024 overlap and refit the `0.0023` coefficient
(and/or add a linear bias correction) so the temp-only ET₀ matches the scale the
model is used to.

### Group 3 — Diurnal range → cloud/rain proxy
```
DTR            = Tmax − Tmin
clearness      ≈ krs·√(DTR)        # krs = 0.16 inland (Kinneret is inland)
cloud_index(t) = 1 − clip( √DTR / √DTR_clearsky(J), 0, 1 )
```
`DTR_clearsky(J)` = climatological **90th-percentile** DTR for that day-of-year
(the clear-sky envelope). Low DTR vs its envelope → high cloud_index → rain-likely.

### Group 4 — Climatology normals (harmonic fit on the 60-yr ERA5 record)
For X ∈ {Tmax, Tmin, DTR, ET₀}, fit K=3 harmonics over day-of-year `d`:
```
X_clim(d) = a0 + Σ_{k=1..3} [ a_k·cos(2πk·d/365) + b_k·sin(2πk·d/365) ]
σ_X(d)    = same harmonic fit applied to squared residuals, then √
```
Harmonic (vs windowed-mean) avoids leap-year/window-edge artefacts and is smooth.
**Rainfall = two-part (hurdle) climatology:**
```
p_wet_clim(d) = harmonic fit of wet-day indicator 1[rain > 1mm]
amt_clim(d)   = harmonic fit of mean rain amount on wet days only
```

### Group 5 — Anomaly & synoptic features ("a front is coming")
```
Tmax_anom_z(t)  = (Tmax(t)  − Tmax_clim(d))  / σ_Tmax(d)
Tmean_anom_z(t) = (Tmean(t) − Tmean_clim(d)) / σ_Tmean(d)
cold_run(t)     = consecutive days ending at t with Tmax_anom_z < −0.5
lowDTR_run(t)   = consecutive days ending at t with DTR < DTR_clim(d)
```

### Group 6 — Antecedent state (catchment memory) — see "Relationship to Arch J"
**API (Antecedent Precipitation Index):**
```
API_t = k·API_{t-1} + P_t          # k ≈ 0.90, calibrate over 0.85–0.95
```
**Soil-moisture bucket (the committed integrator):**
```
S_t = clip( S_{t-1} + P_t − ET_t, 0, S_max )
Q_t = max(0, S_{t-1} + P_t − ET_t − S_max)     # overflow = runoff → inflow
```
- `P_t` = rainfall (observed/reanalysis in history; **temp-estimated over the
  forecast horizon**).
- `ET_t` = `ET0_HS · (S_{t-1}/S_max)` (soil-limited actual ET; a simpler v0 may
  use potential `ET0_HS`).
- `S_max` = field-capacity ceiling [mm], calibrate ≈ 100–300 mm.
- Spin up `S_0` over ≥1 prior year (no cold start).
- **`Q_t` is the key output** — the overflow term is the saturation-threshold
  runoff that flat 30/45-day sums (Architecture J) could not encode. Feed both
  `S_t` (state) and recent-`Q` as features.
- **Propagation caveat:** over the horizon the bucket is driven by *estimated*
  rain, so `S_t` error compounds with lead time — monitor, it is not free.

### Group 7 — Rain estimate (Candidate 2 Stage 1; trained on all 60 yrs)
Hurdle model on `[DTR, cloud_index, Tmax_anom_z, Tmean_anom_z, cold_run,
lowDTR_run, RBF-season, S_{t-1}, API_{t-1}]`:
```
P̂(wet_t)        = GBM classifier (log-loss)
Ê[amt | wet_t]  = GBM regressor on log1p(rain), wet days only
P̂_t            = P̂(wet_t) · expm1( Ê[log1p amt | wet] )    # expected rainfall
```
Candidate 1 (implicit) skips this and feeds the Group 3/5/6 features straight into
the ΔVolume GBR. Candidate 3 (held) *samples* `P_t` from the hurdle distribution N
times instead of taking the expectation.

### Group 8 — ERA5 → station bias correction (the splice)
Per calendar month `m`, **quantile mapping** on the 2012–2024 overlap:
```
X_corr = F⁻¹_station,m ( F_era5,m ( X_era5 ) )      # empirical CDFs
```
Temperature usually fine with additive `X_corr = X_era5 + (μ_station,m −
μ_era5,m)`; rainfall needs full QM (correct wet-day frequency *and* intensity
separately). Without this the model learns a fake discontinuity at the 2012 splice.

### Group 9 — Outflow over the horizon (known-driver anchor)
Future pumping is unknown at 14–30 d, so use **modern-regime outflow climatology by
DOY** — harmonic fit on `outflow_baptism_m3`, **2012+ only** (pumping policy is
non-stationary) — rather than lag-1 persistence, which only holds at short lead.

### Group 10 — ΔVolume → level (existing, unchanged)
Cumulate predicted `ΔV` from the Day-0 anchor; map volume→level with the existing
degree-2 bathymetric polynomial (coeffs `[1.47186147, 784.458874, 103974.069]`,
R²=0.99897).

### Group 11 — Uncertainty band (Candidates 1 & 2)
Quantile GBR with pinball loss at τ = {0.1, 0.5, 0.9}:
```
L_τ(y, ŷ) = max( τ·(y−ŷ), (τ−1)·(y−ŷ) )
```
0.5 = central path; [0.1, 0.9] = 80% band. Widens in wet season automatically if
the Group 3/5 features carry the heteroscedasticity.

### Group 12 — Evaluation metrics (Phase B bake-off)
- **Point:** RMSE/MAE of level at each lead `h=1..30`, and of cumulative `ΔV`.
- **Skill vs climatology:** `SS = 1 − MSE_model / MSE_clim`, reported per-lead
  **and split wet/dry season**.
- **Probabilistic:** CRPS and CRPS skill score vs climatology for bands/ensemble.
- **Calibration:** PIT histogram (want uniform); 80%-interval empirical coverage.
- **Protocol:** walk-forward by held-out year (project standard), issuing a fresh
  30-day forecast every 7 days through each test year.

---

# Candidate architectures (the Phase B bake-off)

**Common scaffold (all candidates):** ERA5 climatology, Hargreaves-ET₀, the
soil-moisture bucket as integrating state, modern-regime ΔVolume target,
outflow-climatology anchor, quantile uncertainty band.

| Candidate | Rain estimate | Chain length | Deep record's role |
|---|---|---|---|
| **1 — Implicit / end-to-end** | none explicit; Group 3/5/6 temp features → one GBR → ΔVolume | **Shortest** (the stated goal) | robust climatology + anomaly references; rain learned internally |
| **2 — Explicit rain-propensity** | Group 7 hurdle (60-yr) → bucket → ΔVolume (modern) | medium | the rain stage gets a 60-yr / thousands-of-storms sample |
| **Baseline (must beat)** | — | — | predict the day-of-year **climatology** level path |

**Decision:** race **1 vs 2 vs baseline**. Candidate 3 (analog-ensemble / ESP) is
**held**, with a pre-registered promotion rule:

### Candidate 3 (ESP) promotion triggers — judged on the wet-season subset at 14–30 d
1. **Skill collapse** — *neither* 1 nor 2 beats climatology by ≳10% RMSE/CRPS in
   wet-season months → a point forecast can't extract the rain signal; deliver a
   calibrated distribution instead.
2. **Band miscalibration** — winner's central path fine but its band fails
   calibration (80% interval covers materially <80%, or U-shaped PIT).
3. **Bimodal residuals** — wet-season errors are bimodal (storm vs no-storm), so
   the conditional mean lands in the low-probability valley between modes.
4. **Decision pull** — the use case turns out to need dry/normal/wet scenario
   planning rather than one best path.

Any one of 1–3, or #4 as a stated need, promotes Candidate 3 from stretch to active.

---

# Relationship to Architecture J (and the guardrails it forces)

J ([[project-round3-architecture-j]]) added flat 30d/45d rolling rainfall **sums**
and underdelivered (+0.005). Diagnosed cause: flat sums can't encode catchment
**saturation state**; the tell was the two weak folds failing in *opposite*
directions — **2023 (drought) over-predicted** runoff, **2021 (wet)
under-predicted** it — the fingerprint of a runoff-efficiency **threshold** a
linear sum cannot represent. The sums were also collinear with existing
`rainfall_7d/14d/21d`.

The **soil-moisture bucket (Group 6) is "J done as the hydrology works"** and
attacks exactly those points: `S_max` = the saturation ceiling J lacked; `Q_t`
overflow = the threshold (dry soil soaks rain → little runoff, fixing 2023;
saturated soil spills → more runoff, fixing 2021); `−ET` = the drying-between-events
a sum can't represent.

**Pre-registered guardrails so the bucket must earn its place (not pass as a null
result the way J nearly did):**
1. **Collinearity gate** — VIF / correlation of `S_t` and recent-`Q` vs
   `rainfall_7d/14d/21d`. If the bucket is just a linear re-expression of existing
   windows, reject it.
2. **Targeted fold-failure test** — the bucket must **shrink the signed-residual
   gap between the 2021-wet and 2023-dry folds**, not merely nudge mean R². This is
   pass/fail, and it is the bucket's actual job.
3. **Ablation + calibration target** — tune `S_max` and decay `k` to *minimise that
   fold gap*, not global R²; run a bucket-on vs bucket-off ablation to isolate the
   marginal contribution.

If the bucket proves out here it is a natural **back-port candidate for the 7-day
model** — noted, but out of scope for this spec. See [[project-next-moisture-proxy]].

---

# Process phases

### Phase A — Data inventory & feasibility (make-or-break, before modeling)
1. **Deepen the met record** — pull ERA5/ERA5-Land via Open-Meteo's historical
   archive (→1940; back to the 1960s to match levels) for the Kinneret point:
   Tmin, Tmax, plus rain & radiation inputs for climatology.
2. **Bias-correct** the reanalysis to the IMS gold on 2012–2024 (Group 8).
3. **Validate the premise empirically** — confirm low-DTR + negative-Tmax-anomaly
   + wet-season actually correlates with rainfall/inflow in the gold table. If not,
   the premise is dead — stop here.
4. **Calibrate Hargreaves** (`0.0023`) vs Penman–Monteith `et0_mm` (Group 2).
5. **Build climatology normals** (Group 4) and the **outflow climatology** (Group 9).

### Phase B — Approach bake-off
Prototype Candidates 1 & 2 (+ climatology baseline) cheaply; evaluate per Group 12;
apply the J guardrails and the ESP promotion triggers. Output: a ranked,
documented winner with the bucket ablation and fold-failure result recorded.

### Phase C — Design the winning model
Promote the winner into a full implementation plan (→ writing-plans skill): feature
build, training on the (B)-split data, inference path to the live long-range temp
input, dashboard surface, tests.

---

# Data sources

| Source | Use | Status |
|---|---|---|
| ERA5 / ERA5-Land via Open-Meteo archive | deep met history (→1960s) | to pull (Phase A) |
| IMS gold (2012+) | bias-correction reference + modern target | have |
| IMS extended forecast | live long-range temp **input** | **down** — feasibility flag |
| Open-Meteo 16-day daily | live long-range temp **input** fallback | available (already in stack) |
| `outflow_baptism_m3` (gold) | outflow climatology (modern only) | have |
| Bathymetric polynomial | volume→level | have |

# Open feasibility flags (gate the live product, not the training)
- **Confirm the live long-range temp forecast input** — IMS extended horizon &
  archive, else Open-Meteo 16-day. The training pipeline can proceed on the deep
  historical record regardless; this gates only live operation.
- Reanalysis **rainfall** is the weakest ERA5 variable — tolerable because rain is
  *estimated* here anyway, but flag if Phase A premise-validation looks noisy.

# Out of scope (YAGNI)
- No changes to the existing 7-day two-stage model (parallel product only).
- Candidate 3 (ESP) unless a promotion trigger fires.
- Back-porting the bucket to the 7-day model (separate future work).
- Snowmelt / teleconnection indices (explicitly deferred; can re-enter only if the
  Phase A premise check shows a residual signal temperature can't explain).
