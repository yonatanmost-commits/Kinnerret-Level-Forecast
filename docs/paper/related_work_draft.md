# Related Work — first draft

> **Status:** first draft for Adnan's review (assigned 2026-07-21). Standalone so it can be
> pasted into the shared `.docx` without a merge conflict while the source-of-truth question
> is open. **Every citation carries a verification tier — see the References note before
> submitting.**

---

## Related Work

Forecasting the level of a managed lake sits at the intersection of four literatures: physically
based catchment hydrology, data-driven hydrological prediction, sub-seasonal meteorological
predictability, and the evaluation methodology that decides when a forecast is worth deploying.
We review each in turn, with particular attention to the Upper Jordan–Kinneret basin, and close
by locating the present study's contribution.

### Physically based and conceptual modelling of the Kinneret basin

The Lake Kinneret water balance has been studied continuously for decades, and the basin has an
unusually mature body of process-based modelling. Rimmer and Salingar (2006) developed HYMKE
(Hydrological Model for Karst Environment), a conceptual daily precipitation–streamflow model
that represents the karstic Upper Jordan catchment through an epikarst surface layer divided
into low- and high-permeability sections, the latter feeding the karst conduit network. HYMKE
has since served as the basin's reference rainfall–runoff model, including as the hydrological
core in climate-impact studies (Samuels et al., 2009). Broader syntheses of basin hydrology and
lake management are given by Rimmer and Gal in the *Lake Kinneret — Ecology and Management*
volume (Zohary et al., 2014), and the long-term level record and its management context —
including the National Water Carrier, the Dganya Dam outflow, and the statutory operating lines
— are reviewed by Gophen (2023).

This tradition establishes the physical structure our work relies on: the level balance is
dominated by Upper Jordan inflow in winter and by evaporation plus extraction in summer. It also
establishes what a data-driven approach must justify itself against.

### Statistical and machine-learning prediction of lake levels and streamflow

Data-driven methods have become a standard alternative where the mapping from meteorology to
water level is nonlinear and the calibration burden of a distributed model is high; recent
systematic reviews survey the algorithms applied to lake-level fluctuation specifically
(Ozdemir et al., 2022 [VERIFY]). Applications span recurrent architectures for river and lake
stage (Vizi et al., 2023), interpretable ensembles for the Laurentian Great Lakes
(Sinha et al., 2025 [VERIFY]), and direct comparisons of gradient boosting against LSTM for
reservoir stage (Hernández-Ramos et al., 2024 [VERIFY]).

Two findings from this literature bear directly on our design choices. First, in rainfall–runoff
modelling the LSTM has been established as a strong general learner: Kratzert et al. (2018)
first applied it to daily runoff and matched or beat the calibrated SAC-SMA+Snow-17 benchmark,
and Kratzert et al. (2019) showed that a single catchment-aware LSTM trained across 531 CAMELS
basins outperforms hydrological models calibrated individually per basin. Second, and in tension
with the first, on modest tabular hydrological datasets gradient-boosted trees frequently match
or beat deep sequence models while remaining faster and more interpretable — XGBoost outperformed
both LSTM and random forests for monthly runoff in a glacierized catchment (Xu et al., 2025
[VERIFY]), and boosting variants perform competitively for daily streamflow in mountainous
catchments (Szczepanek, 2022).

The distinction matters because the LSTM's advantage in Kratzert et al. is largely an advantage
in *learning catchment storage from long input sequences across many basins*. In a single-basin
problem with a ~13-year supervised record, that advantage is not available — which is consistent
with the GRU result we report in §4.1, and motivates supplying catchment memory as an explicit
engineered state rather than expecting a sequence model to infer it.

### Forecasting in the Upper Jordan basin

Operational prediction in this specific basin has an instructive history. A line of statistical
rainfall–runoff work related gauge rainfall directly to Jordan River flow (Shentsis and Ben Zvi,
1994 [VERIFY]; Givati and Rozenfeld, 2007 [VERIFY]; Rimmer et al., 2011 [VERIFY]). The reported
outcome is the important one for us: these relationships are highly efficient for *annual* flow
but their efficiency falls sharply at monthly and daily resolution. Givati et al. (2012 [VERIFY])
subsequently drove an operational Jordan River streamflow forecast with WRF, coupling numerical
weather prediction to the hydrological model rather than regressing on observed rainfall alone.

The basin's climate-change literature is likewise well developed, with runoff and lake-budget
projections built on regional climate model ensembles (Givati et al., 2016; Rimmer et al., 2011
[VERIFY]; Samuels et al., 2018 [VERIFY]), reporting substantial declines in projected inflow.

That the basin's own statistical literature already documents a resolution-dependent collapse in
skill is, to our knowledge, the closest published antecedent of the horizon-dependence we
quantify — but it has been reported as an aggregation effect rather than diagnosed, and not
against explicit forecast baselines at fixed lead times.

### Sub-seasonal predictability and the perfect-prognosis frame

Our 14–30-day product operates in what the meteorological community calls the sub-seasonal
"forecasting desert": skill declines sharply beyond about one week, and in this range
climatological distributions are frequently more reliable than dynamical ensemble forecasts
(Vitart et al., 2018; Pegion et al., 2019 [VERIFY]). Diagnostic work attributes most week 3–4
surface skill to atmospheric initial conditions, with ocean state mattering mainly beyond week 4
and chiefly in the tropics (Richter et al., 2024), and precipitation is consistently harder than
temperature. Hybrid statistical–dynamical framings have been proposed for streamflow at this
range (Zhang et al., 2025 [VERIFY]), and S2S forecasts have been evaluated for hydropower
operations (Bhattacharya et al., 2021 [VERIFY]).

Our use of temperature as the sole meteorological predictor rests on a documented physical
relationship: diurnal temperature range is strongly anti-correlated with cloud cover and is
routinely used as its proxy, with clouds and associated precipitation reducing DTR by 25–50 %
relative to clear-sky days (Dai et al., 1999), and DTR relating directly to rainfall probability
(Dai et al., 1999 [VERIFY — second DTR/rainfall-probability reference]).

Evaluating a statistical model on *observed* rather than *forecast* predictors is the
perfect-prognosis (PP) convention from statistical downscaling, where a model calibrated on
observed predictor–predictand pairs is later driven by simulated predictors; the term "perfect"
denotes the assumption that predictors are bias-free (Maraun and Widmann, 2018). The VALUE
perfect-predictor experiment (Maraun et al., 2019) established PP evaluation as the standard way
to separate a downscaling method's intrinsic skill from the error of its driving model. We adopt
the same convention explicitly, and label our 14–30-day numbers as an upper bound accordingly.

### Catchment state as a source of sub-seasonal skill

A substantial literature holds that where meteorological forcing is unforecastable, remaining
predictability resides in initial hydrological state. Soil-moisture initialization contributes
between roughly 10 % and 60 % of the monthly runoff prediction skill obtainable under perfect
meteorological forcing (Mahanama et al., 2008 [VERIFY]); in-situ soil moisture improves seasonal
streamflow forecasts in rainfall-dominated watersheds (Sun et al., 2020 [VERIFY]); and remotely
sensed soil moisture and terrestrial water storage anomalies raise statistical seasonal forecast
skill substantially over antecedent precipitation alone (Wang et al., 2023 [VERIFY]). Where
direct observations are unavailable, the antecedent precipitation index and simple bucket
accounting are the established proxies (Zhang et al., 2020 [VERIFY]).

Critically, this literature also reports the *regime dependence* we observe: forecasts are most
skillful in dry conditions, where runoff is dominated by initial hydrological state, and least
skillful in wet conditions, where rainfall–runoff coupling is strong and initial soil moisture
matters less. Our finding that a saturation-state bucket adds marginal skill at 14–30 days while
failing to transfer to the 7-day model — where antecedent-rainfall information is already
saturated — is a specific instance of this trade-off, and to our knowledge has not previously
been reported as a *negative transfer* result across horizons within one system.

### Benchmarking and the definition of useful skill

Finally, our evaluation follows the benchmarking tradition in hydrological forecasting. Seibert
(2001 [VERIFY]) argued that model performance should be judged against a benchmark representing
what is achievable in a catchment given available data, an argument extended to explicit
benchmark-efficiency measures by Seibert et al. (2018 [VERIFY]). Pappenberger et al. (2015)
showed that computed skill depends materially on which benchmark is chosen, and that naïve
benchmarks can manufacture apparent skill — climatology-based benchmarks in particular produce
flat error profiles across lead times, and are weak tests. This directly motivates our reporting
skill against day-of-year climatology rather than persistence at long range, and our reporting
both baselines for the summer recession product.

### Positioning of the present work

Against this background, the contribution of this study is threefold. First, it couples an
operational, live multi-source ingestion pipeline to a forecasting system for a managed lake,
rather than evaluating models on a static historical extract. Second, it evaluates three
horizons under a single protocol and explicitly reports where skill does *not* exist —
addressing a documented gap between the Upper Jordan basin's known resolution-dependent skill
collapse and its diagnosis against fixed-lead baselines. Third, it locates the sub-seasonal limit
in catchment-state memory rather than in meteorological forecast quality, and reports the
regime-dependence of that state variable in both directions: it adds skill at 14–30 days and
fails to transfer to 7 days. We frame these results as a single *rain-gated predictability
frontier*, in which forecast skill is governed by whether rainfall is simultaneously
hydrologically active and meteorologically forecastable.

---

## References — verification status (READ BEFORE SUBMITTING)

**Tier A — located directly in search results (title, venue, and URL seen).** Still confirm the
full author list, year, volume and pages against the publisher record:

- Kratzert, F. et al. (2018). Rainfall–runoff modelling using Long Short-Term Memory (LSTM)
  networks. *Hydrology and Earth System Sciences*, 22, 6005–6022.
- Kratzert, F. et al. (2019). Towards learning universal, regional, and local hydrological
  behaviors via machine learning applied to large-sample datasets. *HESS*, 23, 5089–5110.
  (Companion: "Benchmarking a Catchment-Aware LSTM for Large-Scale Hydrological Modeling".)
- Rimmer, A. and Salingar, Y. (2006). HYMKE — Hydrological Model for Karst Environment. *(Journal
  of Hydrology — confirm volume/pages.)*
- Givati, A. et al. (2016). Expected Future Runoff of the Upper Jordan River Simulated with a
  CORDEX Climate Data Ensemble. *Journal of Hydrometeorology*, 17(3).
- Dai, A., Trenberth, K.E. and Karl, T.R. (1999). Effects of Clouds, Soil Moisture, Precipitation,
  and Water Vapor on Diurnal Temperature Range. *Journal of Climate*, 12(8), 2451–2473.
- Maraun, D. et al. (2019). Statistical downscaling skill under present climate conditions: a
  synthesis of the VALUE perfect predictor experiment. *International Journal of Climatology*, 39.
- Maraun, D. and Widmann, M. (2018). Perfect Prognosis (Chapter 11), in *Statistical Downscaling
  and Bias Correction for Climate Research*. Cambridge University Press.
- Pappenberger, F. et al. (2015). How do I know if my forecasts are better? Using benchmarks in
  hydrological ensemble prediction. *Journal of Hydrology*, 522, 697–713.
- Vitart, F. et al. (2018). Progress in subseasonal to seasonal prediction through a joint weather
  and climate community effort. *npj Climate and Atmospheric Science*, 1, 3.
- Richter, J.H. et al. (2024). Quantifying sources of subseasonal prediction skill in CESM2.
  *npj Climate and Atmospheric Science*, 7, 59.
- Szczepanek, R. (2022). Daily Streamflow Forecasting in Mountainous Catchment Using XGBoost,
  LightGBM and CatBoost. *Hydrology*, 9(12), 226.
- Gophen, M. (2023). Historical Review on Water Level Changes in Lake Kinneret (Israel).
  *Water*, 15(5), 837.
- Zohary, T., Sukenik, A., Berman, T., Nishri, A. (eds.) (2014). *Lake Kinneret — Ecology and
  Management*. Springer. (Rimmer & Gal, "Hydrology", Chapter 7.)

**Tier B — [VERIFY] — cited second-hand.** These appeared only as author-year mentions *inside*
other papers' text, not as located records. **Each must be found and read before it goes in.** In
particular the author names below are my best reconstruction and several are likely wrong:

- Shentsis & Ben Zvi (1994); Givati & Rozenfeld (2007); Rimmer et al. (2011) — the Jordan
  statistical rainfall–runoff line, and the source of the "annual good / monthly–daily poor"
  claim. **This is load-bearing for our positioning — verify it first.**
- Givati et al. (2012) — WRF operational Jordan streamflow forecast.
- Samuels et al. (2009, 2018) — HYMKE under RCM forcing / climate impacts.
- Mahanama et al. (2008); Sun et al. (2020); Wang et al. (2023); Zhang et al. (2020) — the
  soil-moisture-initialization skill numbers. Author attributions are **unconfirmed**.
- Seibert (2001); Seibert et al. (2018) — benchmark efficiency.
- Ozdemir et al. (2022); Sinha et al. (2025); Hernández-Ramos et al. (2024); Xu et al. (2025);
  Vizi et al. (2023); Pegion et al. (2019); Zhang et al. (2025); Bhattacharya et al. (2021).
- The second Dai et al. DTR/rainfall-probability paper (*Geophysical Research Letters*, 1999) —
  confirm whether it is the same authorship as the *J. Climate* paper.

**Recommended next step:** run the Tier B list through the library's database or Google Scholar,
fix authorship and full records, and drop anything that cannot be confirmed. The argument does
not depend on any single Tier B item except the Shentsis/Givati/Rimmer Jordan line.
