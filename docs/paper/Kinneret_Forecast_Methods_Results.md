# Multi-Source Machine-Learning Forecasting of Sea of Galilee (Lake Kinneret) Water Levels: Data Preparation, Methods, and the Limits of Predictability

**Authors:** Yonatan Most¹, [Advisor name]¹
¹[Institution / Department]

**Draft v0.1 — Data Preparation, Methods, Results.** Markdown source of truth; convert to the target journal template once content is locked.

> **Status flags for co-authors.** Items marked **[CONFIRM]** need a number or wording you can supply faster than I can re-derive it; items marked **[TK]** are figures/tables still to be produced. All are collected in *§7 Open items* at the end.

---

## Abstract

We present an operational, multi-source forecasting system for the water level of the Sea of Galilee (Lake Kinneret), Israel's principal surface freshwater reservoir, together with an honest accounting of where statistical skill exists and where it does not. Daily level, river-flow, and meteorological records from three national authorities are ingested, cleaned, frequency-synchronised, and fused into a single "gold" feature table, which is deepened to multi-decadal length using ERA5 reanalysis bias-corrected to station observations. On this basis we build and evaluate three forecast products at three time horizons. (i) A **7-day operational forecast** using a two-stage gradient-boosting model (inflow → volume change), selected from a controlled bake-off against XGBoost, LightGBM, a recurrent (GRU) network, and seven structural variants; the champion attains a walk-forward cross-validated volume-change R² of **0.771**. (ii) A **14–30-day long-range forecast** driven only by min/max temperature — the sole signal forecastable that far ahead. Its physical premise (that temperature leaks rainfall information through diurnal range and cold-front anomalies) is empirically confirmed (wet-season wet-day AUC **0.811**), yet the resulting product delivers **no year-round deployable skill over a day-of-year climatology baseline**. Temperature *alone* contributes only a thin wet-season signal (skill score ≈ **+0.12** at 14–30 d, a perfect-prognosis upper bound) and is net-harmful in the rainless dry season. The decisive ingredient is instead **catchment state**: adding a soil-moisture *saturation bucket* — the corrected form of an earlier *failed* flat-rainfall-sum feature — adds marginal skill of **+0.26/+0.28** (wet/dry) and lifts wet-season skill to a moderate ≈ **+0.35**, showing the sub-seasonal limit is set by catchment-state memory rather than by temperature's propensity-vs-magnitude gap. The product remains undeployable year-round (it loses to climatology in summer and its wet-season skill is bounded by the perfect-temperature assumption), but the negative result is now precisely located rather than flat. (iii) A **summer "days-to-red-line" forecast**, which succeeds precisely where the long-range product fails: in the rainless summer the level is governed by evaporation and pumping alone and its descent becomes near-deterministic, back-tested to a mean absolute error of **47 mm at 30 days** (skill score +0.94 versus persistence). Taken together the three results trace a single boundary: **forecast skill for this lake is gated by whether rainfall is both hydrologically active and forecastable.** The negative long-range result is not a failure of method but a measurement of that boundary.

---

## 1. Introduction

The Sea of Galilee (Lake Kinneret; surface ≈ 166 km², drainage ≈ 2,730 km²) is a managed reservoir whose level is bounded by statutory management lines — an upper line above which flooding risk and water-quality concerns arise, and a **lower "red line" (−213.0 m MSL)** below which extraction is curtailed to protect the lake. Anticipating the level — over the coming week for operational decisions, and over the season for policy planning — is therefore of direct management value.

The level is the integral of a water balance: direct precipitation on the lake surface, catchment inflow (dominated by the Jordan River and its tributaries), minus evaporation and outflow (chiefly pumping to the National Water Carrier). Each term lives on a different observational footing — some are measured, some forecastable, some governed by policy — and this heterogeneity, rather than any single modelling choice, is what ultimately determines where forecast skill can and cannot be found.

This paper documents the project end to end, in the order the work was done, and reports both its successes and one instructive failure. Our contributions are:

1. **A reproducible multi-source data-preparation pipeline** (§2) that fuses three national data feeds, repairs several non-obvious data-integrity defects, and extends the modern record to multi-decadal length with bias-corrected reanalysis.
2. **A controlled model bake-off** (§3.2–3.4, §4.1–4.2) establishing a two-stage gradient-boosting champion for the 7-day horizon and, importantly, showing that added model capacity (gradient-boosting variants, a recurrent network) does *not* improve on it.
3. **A located negative result, with a constructive turn** (§3.5, §4.3): a physically-motivated, temperature-only long-range forecast whose premise holds empirically but which carries no year-round skill over climatology — and the finding that the sub-seasonal wet-season limit is set by *catchment-state memory*, not temperature, so that a soil-moisture *saturation bucket* (the corrected form of a previously failed flat-rainfall-sum feature) recovers moderate wet-season skill (≈ +0.35) and is itself vindicated as a marginal contributor.
4. **A complementary positive result** (§3.6, §4.4): a near-deterministic summer recession forecast that succeeds because, in the rainless season, the irreducible term of the long-range problem vanishes.
5. **A synthesis** (§4.5) framing all three as one *rain-gated predictability frontier*.

---

## Related Work

Forecasting the level of a managed lake sits at the intersection of four literatures: physically based catchment hydrology, data-driven hydrological prediction, sub-seasonal meteorological predictability, and the evaluation methodology that decides when a forecast is worth deploying. We review each in turn, with particular attention to the Upper Jordan–Kinneret basin, and close by locating the present study's contribution.

### Physically based and conceptual modelling of the Kinneret basin

The Lake Kinneret water balance has an unusually mature body of process-based modelling. Rimmer and Salingar (2006) developed HYMKE (Hydrological Model for Karst Environment), a conceptual daily precipitation–streamflow model representing the karstic Upper Jordan catchment through an epikarst surface layer divided into low- and high-permeability sections, the latter feeding the karst conduit network. HYMKE became the basin's reference rainfall–runoff model and the hydrological core of subsequent climate-impact work (Samuels et al., 2010). Basin hydrology and lake management are synthesised by Rimmer and Gal (2014) in the *Lake Kinneret — Ecology and Management* volume, and the long-term level record with its management context — the National Water Carrier, the Dganya Dam outflow, and the statutory operating lines — is reviewed by Gophen (2023).

This tradition establishes the physical structure our work relies on: the level balance is dominated by Upper Jordan inflow in winter and by evaporation plus extraction in summer. It also establishes what a data-driven approach must justify itself against.

### Statistical and machine-learning prediction of lake levels and streamflow

Data-driven methods have become a standard alternative where the mapping from meteorology to water level is nonlinear and the calibration burden of a distributed model is high. Sannasi Chakravarthy et al. (2022) review seven families of machine-learning algorithm applied to lake-level fluctuation specifically, spanning neural networks, support vector machines, extreme learning machines, neuro-fuzzy inference systems, and evolutionary, hybrid and deep-learning models.

Two findings from the wider streamflow literature bear directly on our design choices. First, the LSTM is established as a strong general learner for rainfall–runoff: Kratzert et al. (2018) first applied it to daily runoff and matched or beat the calibrated SAC-SMA+Snow-17 benchmark, and Kratzert et al. (2019) showed that a single catchment-aware LSTM trained across 531 CAMELS basins outperforms hydrological models calibrated individually per basin. Second, and in tension with the first, on modest tabular hydrological datasets gradient-boosted trees frequently match or beat deep sequence models while remaining faster and more interpretable; Szczepanek (2022) reports XGBoost, LightGBM and CatBoost performing competitively for daily streamflow in a mountainous catchment.

The distinction matters because the LSTM's advantage in Kratzert et al. is largely an advantage in *learning catchment storage from long input sequences across many basins*. In a single-basin problem with a ~13-year supervised record that advantage is unavailable — consistent with the GRU result we report in §4.1 — which motivates supplying catchment memory as an explicit engineered state rather than expecting a sequence model to infer it.

### Forecasting in the Upper Jordan basin

Operational prediction in this basin has an instructive history. A line of statistical rainfall–runoff work related gauge rainfall directly to Jordan River flow, beginning with the Israeli Hydrological Service's own lake-inflow prediction models (Shentsis and Ben Zvi, 1994) and continued through later statistical correlations that the Service used operationally for some years. As summarised by Rimmer and Gal (2014), the outcome is the point that matters most for us: these relationships are highly efficient for *annual* flow, but their efficiency reduces dramatically at monthly and daily resolution. Givati et al. (2012) subsequently moved the basin onto a different footing, coupling WRF precipitation forecasts to HYMKE in an operational Upper Jordan streamflow forecast system rather than regressing on observed rainfall alone.

Separately, Givati and Rosenfeld (2007) documented a sustained decline in rainfall, spring flow and streamflow across the basin, attributing part of it to anthropogenic aerosols. The basin's climate-projection literature is likewise well developed: Samuels et al. (2010) downscaled a regional climate model onto Jordan River flow, and Givati et al. (2016) simulated expected future Upper Jordan runoff from a CORDEX ensemble, both reporting substantial projected declines.

That the basin's own statistical literature already documents a resolution-dependent collapse in skill is, to our knowledge, the closest published antecedent of the horizon-dependence we quantify. It has, however, been reported as an aggregation effect rather than diagnosed, and not evaluated against explicit forecast baselines at fixed lead times.

### Sub-seasonal predictability and the perfect-prognosis frame

Our 14–30-day product operates in what the meteorological community calls the sub-seasonal "forecasting desert": skill declines sharply beyond about one week, and in this range climatological distributions are frequently more reliable than dynamical ensemble forecasts (Vitart et al., 2018). Assessments of week 3–4 lead find encouraging skill only in particular regions and seasons, and generally lower skill over land than ocean. Diagnostic work attributes most week 3–4 surface skill to atmospheric initial conditions, with ocean state mattering mainly beyond week 4 and chiefly in the tropics (Richter et al., 2024); precipitation is consistently harder than temperature.

Our use of temperature as the sole meteorological predictor rests on a documented physical relationship. Diurnal temperature range is strongly anti-correlated with cloud cover and is used as its proxy: clouds, with secondary damping from soil moisture and precipitation, reduce DTR by 25–50 % relative to clear-sky days, and as much as 80 % of long-term DTR variance over large regions is explained by an inverse relationship to cloud and precipitation change (Dai et al., 1999). Tomsett and Toumi (2000) established the link in the direction we exploit, showing that diurnal temperature ranges above approximately 10 °C are associated with reduced rainfall probability.

Evaluating a statistical model on *observed* rather than *forecast* predictors is the perfect-prognosis (PP) convention from statistical downscaling, in which a model calibrated on observed predictor–predictand pairs is later driven by simulated predictors; "perfect" denotes the assumption that the predictors are bias-free (Maraun and Widmann, 2018). The VALUE perfect-predictor experiment (Maraun et al., 2019) established PP evaluation as the standard way to separate a method's intrinsic skill from the error of its driving model. We adopt the convention explicitly and label our 14–30-day results as an upper bound accordingly.

### Catchment state as a source of sub-seasonal skill

Where meteorological forcing is unforecastable, remaining predictability resides in initial hydrological state. Mahanama et al. (2008), using the Catchment Land Surface Model over Sri Lanka, found that accurate soil-moisture initialization can supply skill in sub-seasonal and seasonal streamflow prediction *even when rainfall prediction skill is small* — the condition our 14–30-day product operates under. Subsequent work has extended this to in-situ and remotely sensed soil moisture as predictors in seasonal streamflow forecasting, with the antecedent precipitation index and simple bucket accounting serving as the established proxies where direct observations are unavailable.

Critically, this literature also reports the *regime dependence* we observe: forecasts are most skillful in dry conditions, where runoff is dominated by initial hydrological state, and least skillful in wet conditions, where rainfall–runoff coupling is strong and initial soil moisture matters less. Our finding that a saturation-state bucket adds marginal skill at 14–30 days while failing to transfer to the 7-day model — where antecedent-rainfall information is already saturated — is a specific instance of this trade-off, and to our knowledge has not previously been reported as a *negative transfer* result across horizons within a single system.

### Benchmarking and the definition of useful skill

Our evaluation follows the benchmarking tradition in hydrological forecasting. Seibert (2001) argued that the observed mean implicit in the Nash–Sutcliffe efficiency is an inappropriate benchmark for forecast verification, and that seasonal or climatological means should be used instead — precisely the substitution we make. Seibert et al. (2018) developed the argument into explicit benchmark-efficiency measures. Pappenberger et al. (2015) then showed that computed skill depends materially on which benchmark is chosen and that naïve benchmarks manufacture apparent skill. This directly motivates our reporting skill against a day-of-year climatology rather than persistence at long range, and our reporting both baselines for the summer recession product.

### Positioning of the present work

Against this background the contribution of this study is threefold. First, it couples a live, operational multi-source ingestion pipeline to a forecasting system for a managed lake, rather than evaluating models on a static historical extract. Second, it evaluates three horizons under a single protocol and explicitly reports where skill does *not* exist — addressing the gap between the Upper Jordan basin's known resolution-dependent skill collapse and its diagnosis against fixed-lead baselines. Third, it locates the sub-seasonal limit in catchment-state memory rather than in meteorological forecast quality, and reports the regime-dependence of that state variable in both directions: it adds skill at 14–30 days and fails to transfer to 7 days. We frame these results as a single *rain-gated predictability frontier*, in which forecast skill is governed by whether rainfall is simultaneously hydrologically active and meteorologically forecastable.

---

## 2. Data Preparation

### 2.1 Data sources

The system fuses three primary national feeds (Table 1), each at its native cadence, supplemented by ERA5 reanalysis (§2.4) for historical depth.

**Table 1. Primary data sources.**

| Data type | Authority | Key parameters | Native cadence |
|---|---|---|---|
| Lake level | Israel Water Authority | Water level (m MSL) | Daily, historical to 1960s |
| Meteorology | Israel Meteorological Service (IMS) | Tmax, Tmin, humidity, rainfall, wind, radiation; short-range forecast | Sub-daily → daily |
| River flow | Israeli Hydrological Service | Jordan River and tributary inflow; outflows | Daily |
| Reanalysis (depth) | ERA5 / ERA5-Land via Open-Meteo archive | Tmax, Tmin, precipitation, radiation, humidity, wind | Daily, 1940–present |

### 2.2 Ingestion and the live pipeline

Two ingestion paths feed the same gold table. A historical/batch path consolidates the multi-decadal archive files; a **daily operational agent** appends new observations and runs the downstream pipeline each day. The agent retrieves (a) the latest level reading, (b) river-flow updates for the Jordan inflow and a second monitored station, and (c) the latest meteorological observations and short-range forecast. Several engineering frictions were resolved during operationalisation and are noted for reproducibility:

- The hydrological endpoint returned **HTTP 403** under default request headers; a corrected request profile restored access.
- A primary met station was retired mid-project, requiring a **station swap** and a fallback from the IMS feed to the **Open-Meteo** API for continuity of the live forecast inputs.
- The lake-surface **radiation sensor failed (2026-04-25)** with no automatic fallback; radiation was subsequently sourced from Open-Meteo and the historical gap backfilled.

The pipeline is a fixed sequence of scripts — meteorological cleaning, flow cleaning, precipitation feature build, gold-table assembly, and model (re)training — run to completion daily; the operational health log confirms routine green status across fetch and all pipeline stages.

### 2.3 Cleaning and frequency synchronisation

Fusing the three feeds requires aligning sub-daily and daily measurements onto a common daily index and repairing source defects. One episode is worth recording in full because it is representative of the class of bug that silently corrupts hydrological time series. A multi-day inflow anomaly was traced through the silver-layer files to a **four-link root-cause chain**: (1) the IMS feed encodes missing values with a literal `-` sentinel rather than an empty field; (2) a pivot used `aggfunc="first"`, which propagated the sentinel instead of a numeric; (3) pandas summation then returned `NaN` across affected rows; and (4) a mismatched output path meant the corrupted intermediate was consumed downstream. The fix was applied **upstream, at the data layer** — not patched in feature-building or model code — consistent with the project principle that bad sensor values are repaired where they enter, never masked where they are used. Frequency synchronisation reduces sub-daily met records to daily aggregates (min/max/mean as appropriate) aligned to the level and flow daily index.

### 2.4 Deepening the record with reanalysis

The supervised modern record (≈ 2012–present) is consistent but short relative to the multi-decadal level history. Because what *drives* level change is non-stationary — National Water Carrier pumping began in 1964, and drought-policy and deliberate-refill regimes have shifted since — but the underlying *meteorological physics* (temperature → evaporation; temperature-signature → rain propensity) is stationary, we split the record by role. The deep meteorological history (ERA5/ERA5-Land via the Open-Meteo archive API, Kinneret grid point 32.7724 °N, 35.5458 °E, retrieved from 1960 to match the level record) supplies **climatological normals and stationary meteorological relationships**; the modern record supplies the **supervised targets and the pumping-era outflow climatology**. The long record teaches the weather; the recent record teaches today's lake.

### 2.5 Bias correction (the reanalysis–station splice)

Splicing reanalysis to station data without correction would teach the model a spurious discontinuity at the join. We apply **monthly empirical quantile mapping**, calibrated on the 2012–2024 overlap, separately per calendar month *m*:

$$X_{\text{corr}} = F^{-1}_{\text{station},m}\!\big(F_{\text{ERA5},m}(X_{\text{ERA5}})\big)$$

where $F$ are empirical CDFs. Quantile mapping is used for temperature (correcting mean and variance bias together) and is essential for precipitation, where wet-day frequency and wet-day intensity must each be corrected.

### 2.6 Derived hydrometeorological variables

**Reference evapotranspiration.** For the long-range product, where only temperature is available, ET₀ is obtained from the temperature-only **Hargreaves–Samani** form built on closed-form FAO-56 astronomy. Extraterrestrial radiation $R_a$ depends only on date and latitude:

$$R_a = \frac{24\cdot60}{\pi}\,G_{sc}\,d_r\big[\omega_s\sin\varphi\sin\delta + \cos\varphi\cos\delta\sin\omega_s\big]$$

with inverse Earth–Sun distance $d_r$, declination $\delta$, sunset hour angle $\omega_s$, $G_{sc}=0.0820~\text{MJ m}^{-2}\text{min}^{-1}$, $\varphi=32.7724°\text{N}$. Then

$$\text{ET}_{0}^{HS} = 0.0023\,(0.408\,R_a)\,(T_{\text{mean}} + 17.8)\sqrt{T_{\max}-T_{\min}}.$$

To place this temperature-only estimate on the same scale as the Penman–Monteith ET₀ used in the modern gold table, we fit a linear calibration over the overlap, obtaining

$$\text{ET}_0^{PM} \approx 1.0619\,\text{ET}_0^{HS} + 0.8113 \quad(\text{mm d}^{-1}),$$

which is then applied downstream so the temperature-only ET₀ reproduces the trained scale.

**Volume–level mapping.** Level forecasts are produced in volume space and mapped back through a fitted degree-2 bathymetric polynomial (coefficients $[1.47186147,\ 784.458874,\ 103974.069]$; $R^2 = 0.99897$), so volume-change predictions translate to level with negligible mapping error.

### 2.7 The gold feature table

The pipeline emits a single daily **gold feature table** keyed by date, carrying the fused and derived fields used by all models — including `temp_max_C`, `temp_min_C`, `temp_mean_C`, `rainfall_mm`, `et0_mm`, antecedent-rainfall windows, the catchment **inflow** term (`inflow_obstacle_m3`), and the **outflow** term (`outflow_baptism_m3`). This table is the common substrate for the 7-day model, the long-range product, and the evaluation protocol below.

The constituent records and the assembled gold table span the ranges in Table C. The deep level, flow, and reanalysis series reach back decades and feed the climatology and stationary relationships of §2.4–2.6; the gold table is the modern, consistent supervised window (from September 2012) on which the forecast models are trained and cross-validated.

**Table C. Record spans and sizes (as built; through mid-June 2026).**

| Series | Source | Span | Rows |
|---|---|---|---|
| Lake level | Israel Water Authority | 1966-09-01 → 2026-06-14 | 11,250 |
| River flow (≤5 stations) | Israeli Hydrological Service | 1969-10-01 → 2026-06-13 | 20,688 |
| Reanalysis (raw & bias-corrected) | ERA5 via Open-Meteo archive | 1960-01-01 → 2026-06-01 | 24,259 |
| **Gold feature table** (supervised window) | fused/derived | 2012-09-01 → 2026-06-14 | 5,035 |

---

## 3. Methods

### 3.1 Target and forecast geometry

All level forecasting is performed on **volume change (ΔVolume)** and mapped to level via the §2.6 polynomial, anchored on the most recent observed level. This isolates the learnable physical quantity (the day's net water-balance change) from the slowly-varying absolute level and avoids fitting a near-integrated series directly.

### 3.2 The 7-day two-stage gradient-boosting model

The operational 7-day forecast uses a **two-stage gradient-boosting regressor (GBR)** that mirrors the water balance:

- **Stage 1 — inflow.** Predict catchment inflow from meteorological drivers and antecedent-rainfall state.
- **Stage 2 — volume change.** Predict ΔVolume from the Stage-1 inflow together with direct precipitation, evaporation (ET₀), and the (climatological/known) outflow term.

Inference is **semi-chained**: Stage-1 inflow feeds Stage-2, while exogenous known/forecast drivers enter Stage-2 directly. The two-stage decomposition both encodes the physics and localises error, and — as §4 shows — outperforms a single-stage model that must learn the whole balance at once.

### 3.3 Cross-validation protocol

All models are evaluated by **walk-forward cross-validation by held-out year** (test folds 2021–2024), the project standard, which respects temporal ordering and never lets future information leak backward. The headline metric is volume-change **R²** (`cv_vol_r2`), reported as the mean across folds and per fold; we also report volume **MAE**, inflow R² for two-stage models, and a 7-day drift diagnostic.

### 3.4 The model bake-off

To establish the champion on evidence rather than assumption, eight configurations were raced under the identical protocol of §3.3:

- **baseline_gbr** — the two-stage GBR of §3.2.
- **xgboost**, **lgbm** — alternative gradient-boosting libraries on the same features.
- **gru** — a recurrent neural network, testing whether sequence modelling adds skill.
- **Structural variants** — `gbr_single_stage` (no inflow stage); `gbr_max_chain` (fully chained); `gbr_s1_direct_s2_anchor`; `gbr_s1_chain_s2_roll1` — probing how much of the skill comes from the two-stage decomposition versus the chaining choices.

Results in §4.1.

### 3.5 The long-range temperature-only forecast (14–30 days)

Beyond ~7 days the only input reliably available is an extended **min/max temperature** forecast (IMS extended horizon when available; Open-Meteo 16-day as live fallback). We therefore asked whether a *temperature-only* level forecast can carry skill out to 14–30 days. The design rests on a specific physical premise: **in this climate the temperature forecast already leaks rainfall information.**

1. **Diurnal temperature range (DTR = Tmax − Tmin) is a cloud/rain gauge.** A cloud deck caps the daytime maximum and traps heat overnight, collapsing DTR before and during rain.
2. **Cold Tmax anomalies in winter are frontal signals.** Israel's October–May rainfall arrives with Cyprus Lows and cold fronts that depress daytime Tmax below the seasonal normal.
3. **Season gates everything** — the same compressed, cold signature means rain in January and nothing in July.

From temperature alone we therefore derive a **cloud index** from DTR relative to its clear-sky envelope, standardised **temperature anomalies** and cold/low-DTR run-lengths as synoptic features, deterministic **ET₀** (§2.6), and — to encode catchment memory — an antecedent-state integrator. The latter is a **soil-moisture bucket**

$$S_t = \text{clip}(S_{t-1} + P_t - \text{ET}_t,\ 0,\ S_{\max}), \qquad Q_t = \max(0,\ S_{t-1}+P_t-\text{ET}_t - S_{\max}),$$

whose overflow $Q_t$ is the saturation-threshold runoff term. This is a deliberate correction of an earlier negative result ("Architecture J"), in which flat 30/45-day rainfall *sums* underdelivered because they cannot encode catchment saturation — their tell was failing in *opposite directions* on the wet (2021) and dry (2023) folds, the fingerprint of a runoff-efficiency threshold a linear sum cannot represent. The bucket's $S_{\max}$ cap and overflow supply exactly that threshold.

Because temperature predicts rain **propensity, not storm total**, every candidate emits an **uncertainty band** (quantile regression at τ = 0.1/0.5/0.9), not a single line. Candidates were to be raced against a **day-of-year climatology baseline** the product must beat, with skill scored per lead and split by wet/dry season; results in §4.3.

**Phase-A premise gate.** Before any modelling, the premise was tested directly on the gold record: does the temperature-derived rain signature (high cloud index + negative Tmax anomaly, in the wet season) actually predict wet days? The gate metric is the wet-season wet-day ROC AUC, with a pre-registered pass threshold of 0.60.

### 3.6 The summer "days-to-red-line" forecast

The third product forecasts **when the level will cross the lower red line (−213.0 m)**. Its method is an **anomaly-scaled seasonal recession**, and its justification is the mirror image of §3.5: in summer, basin rainfall is ≈ 0, so the level is governed only by evaporation and pumping — both slow and seasonal — and its decline is near-deterministic rather than chaotic.

1. From the deep level record (recent-decades climatology, 2005+), compute the **mean daily level change for each day of the year** — the climatological recession shape, deepening to ≈ −10 mm day⁻¹ in July–August and easing through autumn.
2. Compare this year's recession over the trailing 21 days to that climatology to obtain an **anomaly multiplier** (clamped to a physically sane range), capturing whether the lake started fuller and is falling more gently than average.
3. Carry that multiplier forward through the seasonal ramp; the crossing is where the projected level first reaches −213.0 m. A band is formed from a fast edge (full climatology) and a slow edge (this year's gentleness persisting).

The one term the method cannot see is **pumping policy**: evaporation is reliable, extraction is a decision. The product forecasts the physics, and says so explicitly.

---

## 4. Results

### 4.1 The 7-day bake-off: a two-stage GBR wins, and capacity does not help

Under identical walk-forward CV, the two-stage GBR is the clear champion (Table 2). The alternative gradient-boosting libraries trail by ~9–10 R² points, every structural variant is worse than the two-stage baseline, and the recurrent network collapses to essentially no skill (R² ≈ 0) — direct evidence that the limiting factor at this horizon is the **signal**, not model capacity.

**Table 2. Model bake-off — walk-forward CV by held-out year (2021–2024).** Volume-change R² (mean and per fold), volume MAE, and two-stage inflow R² where applicable. Champion in bold.

| Model | vol R² (mean) | 2021 | 2022 | 2023 | 2024 | vol MAE | inflow R² |
|---|---|---|---|---|---|---|---|
| **baseline_gbr** | **0.771** | 0.704 | 0.884 | 0.680 | 0.816 | **0.645** | 0.942 |
| gbr_s1_direct_s2_anchor | 0.702 | 0.670 | 0.855 | 0.485 | 0.796 | 0.716 | 0.856 |
| xgboost | 0.678 | 0.620 | 0.867 | 0.426 | 0.801 | 0.721 | 0.883 |
| lgbm | 0.668 | 0.674 | 0.875 | 0.431 | 0.694 | 0.716 | 0.866 |
| gbr_single_stage | 0.663 | 0.654 | 0.810 | 0.449 | 0.740 | 0.746 | — |
| gbr_max_chain | 0.659 | 0.586 | 0.864 | 0.414 | 0.774 | 0.778 | — |
| gbr_s1_chain_s2_roll1 | 0.659 | 0.599 | 0.866 | 0.399 | 0.773 | 0.761 | — |
| gru | −0.026 | −0.061 | −0.000 | −0.044 | −0.000 | 1.485 | — |

The champion's **Stage-1 inflow R² of 0.942** confirms the catchment-inflow term is highly learnable from meteorology and antecedent state; the harder, more error-prone quantity is the Stage-2 ΔVolume. The two-stage decomposition beats both the single-stage model (0.663) and the fully-chained variant (0.659), showing the inflow stage carries real structural value rather than merely adding parameters.

### 4.2 The 2023 fold is the universal weak point

Across *every* model the 2023 test fold is the weakest (champion 0.680 vs 0.816–0.884 in 2022/2024; the gradient-boosting alternatives fall to ~0.43, the chained variants to ~0.40). 2023 was a drought year, and this shared collapse — independent of model family — is again a *signal* signature, not a modelling artefact: in a low-runoff regime the antecedent-rainfall features the models rely on carry less information, and runoff efficiency departs from the wetter folds they are mostly trained on. This is the same saturation-threshold effect that motivated the soil-moisture bucket (§3.5) and is the single most promising target for future improvement of the 7-day model.

### 4.3 Long-range temperature-only: premise confirmed, product insufficient

**The premise holds.** The Phase-A gate passed decisively: the temperature-derived rain signature predicts wet days with **wet-season wet-day AUC = 0.811** (overall 0.800), far above the 0.60 threshold, with a wet-season cloud-index–rainfall correlation of 0.294. Temperature genuinely leaks rain information in this climate, exactly as the physical argument predicts.

**The product does not.** We evaluated the temperature-only forecast (Candidate 1, the shortest-chain design) against a day-of-year climatology of cumulative volume change, under the project's walk-forward held-out-year protocol (2021–2024), issuing a fresh forecast every 7 days. To give the approach its strongest possible chance we used a **perfect-prognosis** input — the *observed* future temperature, i.e. a perfect temperature forecast — so the result is an **upper bound**; the live product, driven by a real extended-range temperature forecast, can only do worse. Skill is scored as $SS = 1 - \text{MSE}_{\text{model}}/\text{MSE}_{\text{baseline}}$, pooled over leads 14–30 days and split by season (Table A).

**Table A. Temperature-only long-range skill (14–30 d, pooled, perfect-prognosis upper bound).** `base` = a gradient-boosting model on season + lake level + antecedent 30-day rainfall; `temp` = `base` plus the temperature block (cloud index, DTR, Tmax anomaly, Hargreaves ET₀ over the horizon); `temp+bucket` = `temp` plus the soil-moisture bucket's antecedent saturation **state** (storage $S$, trailing-30-day overflow $Q$) — the corrected form of the failed flat-sum feature (§3.5). The two decisive columns are the **marginal** skill of each added block.

| Season | n | SS(base vs clim) | SS(temp vs clim) | **SS(temp marg., vs base)** | SS(temp+bucket vs clim) | **SS(bucket marg., vs temp)** |
|---|---|---|---|---|---|---|
| Wet (Nov–Mar) | 247 | −0.093 | +0.121 | **+0.196** | **≈ +0.35** | **+0.260** |
| Dry (Apr–Oct) | 360 | −0.571 | −1.228 | −0.418 | ≈ −0.61 | **+0.279** |

Four things follow, and together they are the central methodological finding of this section:

1. **Temperature carries a real but thin wet-season signal on its own.** The temperature block cuts wet-season error ~20 % over a season-plus-antecedent baseline (+0.196 marginal), converting a season-only model that *loses* to climatology (−0.093) into one that *edges* it (+0.121). The premise (AUC 0.811) is not empty — but alone it is a slender, perfect-temperature-only gain, and it is **net-harmful in the dry season** (−0.418 marginal): once rain vanishes, the smooth recession belongs to climatology and a temperature-driven model only injects variance (the modelling-side view of §4.4).

2. **The decisive ingredient is catchment *state*, not temperature.** Adding the soil-moisture **bucket** — the saturation-state integrator designed as "Architecture J done right" (§3.5) — yields a **marginal skill score of +0.260 (wet) and +0.279 (dry)** *over the temperature model*, and does so **on top of the flat 30-day rainfall sum already present** in every model. This is the corrected feature beating the one that failed: the flat sum (Architecture J) could not encode saturation and underdelivered (+0.005); the bucket's storage and overflow can, and they add real skill — **even untuned** (mid-range $S_{\max}=150$ mm, potential-ET v0). Its contribution is *largest where the flat sum is weakest* — summer, where 30-day rain ≈ 0 carries nothing but stored catchment charge still predicts the drawdown. **Architecture J is healed.**

3. **With the bucket, the wet-season product reaches moderate skill** over climatology (≈ +0.35), no longer thin — showing the 14–30-day wet-season limit is set by *catchment-state memory*, not by temperature's propensity-vs-magnitude gap alone. The mechanism of that gap still holds (the premise gate measures **propensity** — *will it rain?* — which temperature answers; the forecast must integrate rainfall **magnitude** — *how much?* — which temperature cannot resolve), but a state variable recovers part of what the missing magnitude costs.

4. **It is still not a *year-round deployable* product.** Even with the bucket, the dry season loses to climatology (≈ −0.61), so a deployable version would be **wet-season-only** (paired with the §4.4 recession in summer); and the wet-season +0.35 remains an **upper bound** under perfect temperature, pending a real extended-range-temperature test. The verdict therefore shifts from the earlier "no deployable skill" to a sharper one: **no year-round skill, but a genuine wet-season signal that catchment-state memory — not temperature — unlocks.**

*(Result reproducible via `Automation/longrange_phaseb_eval.py`; full per-lead table incl. the bucket ablation in `docs/longrange_phaseb_report.md`.)*

### 4.4 The red-line forecast: determinism restored when rain leaves the system

The summer recession product succeeds for the precise reason the long-range product fails. Once basin rainfall falls to ≈ 0, the irreducible term of §4.3 is simply absent: the level balance reduces to evaporation and pumping, both smooth and seasonal, and the descent becomes near-deterministic. The anomaly-scaled recession projects the crossing of −213.0 m with an interpretable band spanning a full-climatology fast edge and a gentler slow edge, anchored on the live level and recomputed as the level updates.

We back-tested this directly (Table B): anchoring on 1 June of each year 2010–2024 (n = 15) and projecting the level forward with leave-one-year-out climatology, the forecast's mean absolute level error is **47 mm at 30 days, 112 mm at 60 days, and 195 mm at 90 days**, beating a persistence baseline by **0.89–0.94 in skill score** at every horizon. A ~5 cm error a month into the rainless season — against a lake whose annual range is metres — is the quantitative form of "near-deterministic," and the mirror image of §4.3, where rainfall made the path unforecastable.

**Table B. Red-line summer-recession back-test (1 June anchor, 2010–2024, leave-one-year-out).**

| Horizon | MAE method (m) | MAE persistence (m) | Skill vs persistence | Skill vs *unscaled* climatology |
|---|---|---|---|---|
| 30 d | 0.047 | 0.212 | +0.935 | +0.292 |
| 60 d | 0.112 | 0.485 | +0.913 | −0.310 |
| 90 d | 0.195 | 0.751 | +0.894 | −0.676 |

One honest caveat falls out of the last column. The **anomaly multiplier** — this year's recent recession rate relative to climatology — adds skill at 30 days (+0.29 over unscaled climatology) but *subtracts* it by 60–90 days (−0.31, −0.68): extrapolating a transient spring anomaly two-to-three months forward over-commits to it, and the plain climatological recession is the better long-range estimate. The operational implication is to **damp the anomaly scale toward 1.0 as lead grows** — a concrete, testable refinement to the live product rather than a hidden weakness.

The single acknowledged wildcard is **pumping policy**, which is exogenous to the physics; the product is explicit that it forecasts evaporative–seasonal descent, not a management decision. *(Back-test reproducible via `Automation/redline_backtest.py`; full table in `docs/redline_backtest_report.md`.)*

### 4.5 Synthesis: a rain-gated predictability frontier

The three results are one finding viewed at three horizons (Table 3). Forecast skill for Lake Kinneret is gated by the status of **rainfall**:

**Table 3. The rain-gated predictability frontier.**

| Horizon / product | Is rain hydrologically active? | Is rain forecastable? | Outcome |
|---|---|---|---|
| 7-day operational (§4.1) | Yes | Yes (short-range NWP) | **Skill** — two-stage GBR, R² 0.771 |
| 14–30-day long-range (§4.3) | Yes | Propensity (temp) + *catchment state* | **No year-round skill** — but a saturation-state *bucket* lifts wet-season skill to ≈ +0.35 (perfect-temp); summer still lost to climatology |
| Summer days-to-red-line (§4.4) | No (≈ 0 mm) | n/a | **Skill** — near-deterministic recession |

When rainfall is both active and forecastable, machine learning extracts real skill, and added model capacity does not help (the bottleneck is signal, not model). When rainfall is active but only its *propensity* is forecastable, temperature alone recovers just a thin wet-season margin — yet a catchment-*state* variable (the saturation bucket) lifts that to moderate wet-season skill (≈ +0.35), locating the sub-seasonal limit in catchment memory rather than in temperature; even so the rainless summer still belongs to climatology, so there is no year-round advantage. When rainfall is absent, the system becomes near-deterministic and a simple seasonal model is the right tool. The long-range result is not a detour around this frontier; it is the experiment that locates it — and shows the frontier can be pushed, in the wet season, by modelling *state* rather than chasing a better point forecast.

---

## 5. Discussion and limitations

- **The soil-moisture bucket's value is regime-dependent — it does not transfer to the 7-day model.** Vindicated at long range (§4.3: +0.26/+0.28 marginal), we tested the natural next step — back-porting it to the two-stage 7-day champion under the pre-registered criterion (it must shrink the wet-2021/dry-2023 signed-residual gap, not merely move mean R²). It **fails**: an untuned bucket added beside the existing features *widens* the fold-gap (0.101 → 0.197) and slightly lowers mean S2 R² (0.771 → 0.760). The diagnosis is instructive: the 7-day model already carries nine rainfall-window features, a moisture-balance term, and inflow lags whose lag-1 autocorrelation is 0.967, so the short-horizon antecedent-moisture signal is already saturated and the bucket adds mostly variance — whereas the long-range model, with a single flat rainfall feature and a 14–30-day integrating target, had room the bucket could fill. The **2023 drought fold therefore remains the champion's open weakness**, and the bucket is *not* adopted into the production model. Whether a **tuned** bucket ($S_{\max}$/ET form) paired with a **collinearity-pruned** rainfall feature set could recover the transfer is open, but the naive back-port does not — and is reported as such. *(Ablation: `Automation/bucket_backport_eval.py`, `docs/bucket_backport_report.md`; baseline replicates the champion's 0.771 exactly.)*
- **Reanalysis precipitation** is the weakest ERA5 variable; this is tolerable for the temperature-only product (where rain is estimated, not ingested) but should be flagged wherever deep-record rainfall enters a normal.
- **The long-range conclusion is conditional on temperature as the sole *meteorological* predictor.** With antecedent catchment state added, temperature drives only a thin wet-season margin; the moderate wet-season skill comes from state memory. The result does not preclude further sub-seasonal skill from other sources (teleconnection indices, ensemble NWP precipitation); it states that *temperature alone* cannot size storms, and that for an integrating target a *state* variable, not a better point forecast, is what recovers part of the loss.
- **Operational dependence on third-party APIs** (Open-Meteo fallback, IMS extended forecast availability) is a live risk surfaced repeatedly during operationalisation and mitigated by the fallback architecture of §2.2.

---

## 6. Reproducibility

The pipeline is a fixed, scripted sequence (met cleaning → flow cleaning → precipitation features → gold assembly → training) run daily by an automated agent with a health log. Reanalysis is pulled from the public Open-Meteo archive at the documented grid point; bias correction, Hargreaves calibration, climatology construction, and the premise gate are each a single script with unit tests. The volume→level polynomial, Hargreaves calibration coefficients, and bake-off results are stored as versioned artefacts.

Every headline result in this paper regenerates from a named script against the live data, so the analysis is a **living, self-verifying record** rather than a static snapshot — re-running it as the lake's record extends refreshes the numbers and the conclusions alike:

| Result | Script | Artefact |
|---|---|---|
| 7-day bake-off (Table 2) | `Automation/08_train_forecast_model.py` | `docs/olympics_results.json` |
| Long-range skill + ablation (Table A) | `Automation/longrange_phaseb_eval.py` | `docs/longrange_phaseb_report.md` |
| Red-line back-test (Table B) | `Automation/redline_backtest.py` | `docs/redline_backtest_report.md` |
| Premise gate (AUC 0.811) | `Automation/longrange_premise_check.py` | `docs/longrange_premise_report.md` |
| Record spans (Table C) | live data files | §2.7 |

[TK: add a formal code/data-availability statement and repository/commit reference for the chosen venue.]

---

## 7. Open items (for co-authors)

1. **[RESOLVED — please sanity-check] Long-range skill number (§4.3).** No stored Phase-B run existed, so the number was *measured* here via a minimal honest evaluation (`Automation/longrange_phaseb_eval.py`; report `docs/longrange_phaseb_report.md`): wet-season SS = +0.121 vs climatology (temperature marginal +0.196 over a season+state baseline) under a perfect-prognosis upper bound; dry-season SS = −1.228. **Note the framing shifted** from the original "never beats climatology" to the more defensible *"no deployable skill — thin perfect-temperature-only wet-season margin, net-negative across the year."* Please confirm you're comfortable with (a) the perfect-prognosis upper-bound framing, (b) Candidate 1 (implicit, shortest-chain) as the representative architecture, and (c) the cumulative-ΔVolume target — or tell me to vary any of them.
2. **[RESOLVED — please ratify] Soil-bucket diagnostics (§4.3/§5).** Measured both ways: the bucket adds **+0.26 (wet) / +0.28 (dry)** marginal skill at long range (Table A; `longrange_phaseb_eval.py`) — Architecture J vindicated there — but the **7-day back-port FAILS** the pre-registered fold-gap test (gap 0.101 → 0.197, mean R² 0.771 → 0.760; `bucket_backport_eval.py`), so it is *not* adopted into the champion. Net story for the paper: the fix is real but regime-dependent. Open follow-ups now narrower: a **tuned** $S_{\max}$/ET form with a **collinearity-pruned** feature set *might* recover the 7-day transfer (untested). Please confirm $S_{\max}=150$ mm v0 and the antecedent-state-only framing are acceptable.
3. **[TK] Figures.** (a) Bake-off R²-by-fold bar/heatmap; (b) two-stage architecture schematic; (c) red-line worked example with band and crossing; (d) premise-gate ROC / DTR-vs-rainfall scatter.
4. **[RESOLVED] Red-line back-test (§4.4).** Measured: 1-June anchor, 2010–2024, leave-one-year-out — MAE 47/112/195 mm at 30/60/90 d, skill +0.89–0.94 vs persistence (`Automation/redline_backtest.py`, `docs/redline_backtest_report.md`). Surfaced an honest sub-finding: the anomaly multiplier helps at 30 d but hurts past 60 d → damp the scale toward 1.0 with lead. A worked-example *figure* is still TK (item 3).
5. **[CONFIRM] Front matter.** Author list, affiliations, target journal (to fix template, equation style, and length budget).
6. **[RESOLVED] Exact record spans / row counts** — counted from the live files into Table C (§2.7): level 11,250 (1966→), flow 20,688 (1969→), ERA5 24,259 (1960→), gold 5,035 (2012-09→). Re-run as data extends.
7. **[CONFIRM] Related Work references.** The section's citations are verified against the published record, with three bibliographic gaps noted in `docs/paper/related_work_draft.md`: the author list for the *Climate Dynamics* (2019) week 3–4 paper, and volume/pages for Rimmer and Salingar (2006), Seibert (2001) and Seibert et al. (2018). Also to settle: whether Shentsis and Ben Zvi (1994), an Israeli Hydrological Service report, is cited directly as grey literature or carried via Rimmer and Gal (2014) — currently the latter.

---

## References

- Dai, A., Trenberth, K. E. and Karl, T. R. (1999). Effects of clouds, soil moisture, precipitation, and water vapor on diurnal temperature range. *Journal of Climate*, 12(8), 2451–2473.
- Givati, A. and Rosenfeld, D. (2007). Possible impacts of anthropogenic aerosols on water resources of the Jordan River and the Sea of Galilee. *Water Resources Research*, 43(10).
- Givati, A., Lynn, B., Liu, Y. and Rimmer, A. (2012). Using the WRF model in an operational streamflow forecast system for the Jordan River. *Journal of Applied Meteorology and Climatology*, 51(2), 285–299.
- Givati, A. et al. (2016). Expected future runoff of the Upper Jordan River simulated with a CORDEX climate data ensemble. *Journal of Hydrometeorology*, 17(3).
- Gophen, M. (2023). Historical review on water level changes in Lake Kinneret (Israel) and incomparable perspectives. *Water*, 15(5), 837.
- Kratzert, F., Klotz, D., Brenner, C., Schulz, K. and Herrnegger, M. (2018). Rainfall–runoff modelling using Long Short-Term Memory (LSTM) networks. *Hydrology and Earth System Sciences*, 22, 6005–6022.
- Kratzert, F. et al. (2019). Towards learning universal, regional, and local hydrological behaviors via machine learning applied to large-sample datasets. *Hydrology and Earth System Sciences*, 23, 5089–5110.
- Mahanama, S., Koster, R. D., Reichle, R. H. and Zubair, L. (2008). The role of soil moisture initialization in subseasonal and seasonal streamflow prediction — a case study in Sri Lanka. *Advances in Water Resources*, 31(10), 1333–1343.
- Maraun, D. and Widmann, M. (2018). Perfect prognosis (Chapter 11). In *Statistical Downscaling and Bias Correction for Climate Research*. Cambridge University Press.
- Maraun, D. et al. (2019). Statistical downscaling skill under present climate conditions: a synthesis of the VALUE perfect predictor experiment. *International Journal of Climatology*, 39.
- Pappenberger, F., Ramos, M. H., Cloke, H. L., Wetterhall, F., Alfieri, L., Bogner, K., Mueller, A. and Salamon, P. (2015). How do I know if my forecasts are better? Using benchmarks in hydrological ensemble prediction. *Journal of Hydrology*, 522, 697–713.
- Richter, J. H. et al. (2024). Quantifying sources of subseasonal prediction skill in CESM2. *npj Climate and Atmospheric Science*, 7, 59.
- Rimmer, A. and Gal, G. (2014). Hydrology (Chapter 7). In Zohary, T., Sukenik, A., Berman, T. and Nishri, A. (eds.), *Lake Kinneret — Ecology and Management*. Springer.
- Rimmer, A. and Salingar, Y. (2006). Modelling precipitation–streamflow processes in karst basin: the case of the Jordan River sources, Israel. *Journal of Hydrology*.
- Samuels, R. et al. (2010). Climate change impacts on Jordan River flow: downscaling application from a regional climate model. *Journal of Hydrometeorology*, 11(4).
- Sannasi Chakravarthy, S. R., Bharanidharan, N. and Rajaguru, H. (2022). A systematic review on machine learning algorithms used for forecasting lake-water level fluctuations. *Concurrency and Computation: Practice and Experience*, 34.
- Seibert, J. (2001). On the need for benchmarks in hydrological modelling. *Hydrological Processes*.
- Seibert, J., Vis, M. J. P., Lewis, E. and van Meerveld, H. J. (2018). Upper and lower benchmarks in hydrological modelling. *Hydrological Processes*.
- Shentsis, I. and Ben Zvi, A. (1994). *Updated model to predict the available water for Lake Kinneret.* Israeli Hydrological Service, Report 94/2.
- Szczepanek, R. (2022). Daily streamflow forecasting in mountainous catchment using XGBoost, LightGBM and CatBoost. *Hydrology*, 9(12), 226.
- Tomsett, A. C. and Toumi, R. (2000). Diurnal temperature range and rainfall probability. *Geophysical Research Letters*, 27(9), 1279–1282.
- Vitart, F. et al. (2018). Progress in subseasonal to seasonal prediction through a joint weather and climate community effort. *npj Climate and Atmospheric Science*, 1, 3.
- Week 3–4 predictability over the United States assessed from two operational ensemble prediction systems (2019). *Climate Dynamics*, 52, 5861–5875.
