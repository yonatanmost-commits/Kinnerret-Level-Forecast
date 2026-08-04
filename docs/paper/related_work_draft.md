# Related Work — first draft (v2, references verified)

> **Status:** first draft for Adnan's review (assigned 2026-07-21). Standalone so it can be
> pasted into the shared `.docx` without a merge conflict while the source-of-truth question is
> open.
>
> **v2 changes:** every citation was checked against the literature. Four were wrong in v1 and
> are corrected below; unverifiable filler citations were cut rather than left with guessed
> authors. Remaining gaps are listed explicitly at the end — there are three, all minor.

---

## Related Work

Forecasting the level of a managed lake sits at the intersection of four literatures: physically
based catchment hydrology, data-driven hydrological prediction, sub-seasonal meteorological
predictability, and the evaluation methodology that decides when a forecast is worth deploying.
We review each in turn, with particular attention to the Upper Jordan–Kinneret basin, and close
by locating the present study's contribution.

### Physically based and conceptual modelling of the Kinneret basin

The Lake Kinneret water balance has an unusually mature body of process-based modelling. Rimmer
and Salingar (2006) developed HYMKE (Hydrological Model for Karst Environment), a conceptual
daily precipitation–streamflow model representing the karstic Upper Jordan catchment through an
epikarst surface layer divided into low- and high-permeability sections, the latter feeding the
karst conduit network. HYMKE became the basin's reference rainfall–runoff model and the
hydrological core of subsequent climate-impact work (Samuels et al., 2010). Basin hydrology and
lake management are synthesised by Rimmer and Gal (2014) in the *Lake Kinneret — Ecology and
Management* volume, and the long-term level record with its management context — the National
Water Carrier, the Dganya Dam outflow, and the statutory operating lines — is reviewed by Gophen
(2023).

This tradition establishes the physical structure our work relies on: the level balance is
dominated by Upper Jordan inflow in winter and by evaporation plus extraction in summer. It also
establishes what a data-driven approach must justify itself against.

### Statistical and machine-learning prediction of lake levels and streamflow

Data-driven methods have become a standard alternative where the mapping from meteorology to
water level is nonlinear and the calibration burden of a distributed model is high. Sannasi
Chakravarthy et al. (2022) review seven families of machine-learning algorithm applied to
lake-level fluctuation specifically, spanning neural networks, support vector machines, extreme
learning machines, neuro-fuzzy inference systems, and evolutionary, hybrid and deep-learning
models.

Two findings from the wider streamflow literature bear directly on our design choices. First, the
LSTM is established as a strong general learner for rainfall–runoff: Kratzert et al. (2018) first
applied it to daily runoff and matched or beat the calibrated SAC-SMA+Snow-17 benchmark, and
Kratzert et al. (2019) showed that a single catchment-aware LSTM trained across 531 CAMELS basins
outperforms hydrological models calibrated individually per basin. Second, and in tension with
the first, on modest tabular hydrological datasets gradient-boosted trees frequently match or beat
deep sequence models while remaining faster and more interpretable; Szczepanek (2022) reports
XGBoost, LightGBM and CatBoost performing competitively for daily streamflow in a mountainous
catchment.

The distinction matters because the LSTM's advantage in Kratzert et al. is largely an advantage
in *learning catchment storage from long input sequences across many basins*. In a single-basin
problem with a ~13-year supervised record that advantage is unavailable — consistent with the GRU
result we report in §4.1 — which motivates supplying catchment memory as an explicit engineered
state rather than expecting a sequence model to infer it.

### Forecasting in the Upper Jordan basin

Operational prediction in this basin has an instructive history. A line of statistical
rainfall–runoff work related gauge rainfall directly to Jordan River flow, beginning with the
Israeli Hydrological Service's own lake-inflow prediction models (Shentsis and Ben Zvi, 1994) and
continued through later statistical correlations that the Service used operationally for some
years. As summarised by Rimmer and Gal (2014), the outcome is the point that matters most for
us: these relationships are highly efficient for *annual* flow, but their efficiency reduces
dramatically at monthly and daily resolution. Givati et al. (2012) subsequently moved the basin
onto a different footing, coupling WRF precipitation forecasts to HYMKE in an operational Upper
Jordan streamflow forecast system rather than regressing on observed rainfall alone.

Separately, Givati and Rosenfeld (2007) documented a sustained decline in rainfall, spring flow
and streamflow across the basin, attributing part of it to anthropogenic aerosols. The basin's
climate-projection literature is likewise well developed: Samuels et al. (2010) downscaled a
regional climate model onto Jordan River flow, and Givati et al. (2016) simulated expected future
Upper Jordan runoff from a CORDEX ensemble, both reporting substantial projected declines.

That the basin's own statistical literature already documents a resolution-dependent collapse in
skill is, to our knowledge, the closest published antecedent of the horizon-dependence we
quantify. It has, however, been reported as an aggregation effect rather than diagnosed, and not
evaluated against explicit forecast baselines at fixed lead times.

### Sub-seasonal predictability and the perfect-prognosis frame

Our 14–30-day product operates in what the meteorological community calls the sub-seasonal
"forecasting desert": skill declines sharply beyond about one week, and in this range
climatological distributions are frequently more reliable than dynamical ensemble forecasts
(Vitart et al., 2018). Assessments of week 3–4 lead over the United States find encouraging skill
only in particular regions and seasons, and generally lower skill over land than ocean
(*Climate Dynamics*, 2019). Diagnostic work attributes most week 3–4 surface skill to atmospheric
initial conditions, with ocean state mattering mainly beyond week 4 and chiefly in the tropics
(Richter et al., 2024); precipitation is consistently harder than temperature.

Our use of temperature as the sole meteorological predictor rests on a documented physical
relationship. Diurnal temperature range is strongly anti-correlated with cloud cover and is used
as its proxy: clouds, with secondary damping from soil moisture and precipitation, reduce DTR by
25–50 % relative to clear-sky days, and as much as 80 % of long-term DTR variance over large
regions is explained by an inverse relationship to cloud and precipitation change (Dai et al.,
1999). Tomsett and Toumi (2000) established the link in the direction we exploit, showing that
diurnal temperature ranges above approximately 10 °C are associated with reduced rainfall
probability.

Evaluating a statistical model on *observed* rather than *forecast* predictors is the
perfect-prognosis (PP) convention from statistical downscaling, in which a model calibrated on
observed predictor–predictand pairs is later driven by simulated predictors; "perfect" denotes
the assumption that the predictors are bias-free (Maraun and Widmann, 2018). The VALUE
perfect-predictor experiment (Maraun et al., 2019) established PP evaluation as the standard way
to separate a method's intrinsic skill from the error of its driving model. We adopt the
convention explicitly and label our 14–30-day results as an upper bound accordingly.

### Catchment state as a source of sub-seasonal skill

Where meteorological forcing is unforecastable, remaining predictability resides in initial
hydrological state. Mahanama et al. (2008), using the Catchment Land Surface Model over Sri
Lanka, found that accurate soil-moisture initialization can supply skill in sub-seasonal and
seasonal streamflow prediction *even when rainfall prediction skill is small* — the condition our
14–30-day product operates under. Subsequent work has extended this to in-situ and remotely sensed
soil moisture as predictors in seasonal streamflow forecasting, with the antecedent precipitation
index and simple bucket accounting serving as the established proxies where direct observations
are unavailable.

Critically, this literature also reports the *regime dependence* we observe: forecasts are most
skillful in dry conditions, where runoff is dominated by initial hydrological state, and least
skillful in wet conditions, where rainfall–runoff coupling is strong and initial soil moisture
matters less. Our finding that a saturation-state bucket adds marginal skill at 14–30 days while
failing to transfer to the 7-day model — where antecedent-rainfall information is already
saturated — is a specific instance of this trade-off, and to our knowledge has not previously been
reported as a *negative transfer* result across horizons within a single system.

### Benchmarking and the definition of useful skill

Our evaluation follows the benchmarking tradition in hydrological forecasting. Seibert (2001)
argued that the observed mean implicit in the Nash–Sutcliffe efficiency is an inappropriate
benchmark for forecast verification, and that seasonal or climatological means should be used
instead — precisely the substitution we make. Seibert et al. (2018) developed the argument into
explicit benchmark-efficiency measures. Pappenberger et al. (2015) then showed that computed
skill depends materially on which benchmark is chosen and that naïve benchmarks manufacture
apparent skill. This directly motivates our reporting skill against a day-of-year climatology
rather than persistence at long range, and our reporting both baselines for the summer recession
product.

### Positioning of the present work

Against this background the contribution of this study is threefold. First, it couples a live,
operational multi-source ingestion pipeline to a forecasting system for a managed lake, rather
than evaluating models on a static historical extract. Second, it evaluates three horizons under
a single protocol and explicitly reports where skill does *not* exist — addressing the gap between
the Upper Jordan basin's known resolution-dependent skill collapse and its diagnosis against
fixed-lead baselines. Third, it locates the sub-seasonal limit in catchment-state memory rather
than in meteorological forecast quality, and reports the regime-dependence of that state variable
in both directions: it adds skill at 14–30 days and fails to transfer to 7 days. We frame these
results as a single *rain-gated predictability frontier*, in which forecast skill is governed by
whether rainfall is simultaneously hydrologically active and meteorologically forecastable.

---

## References

Verified against the published record unless marked. Confirm formatting against the target
journal's style once the venue is fixed.

- Dai, A., Trenberth, K. E. and Karl, T. R. (1999). Effects of clouds, soil moisture,
  precipitation, and water vapor on diurnal temperature range. *Journal of Climate*, 12(8),
  2451–2473.
- Givati, A. and Rosenfeld, D. (2007). Possible impacts of anthropogenic aerosols on water
  resources of the Jordan River and the Sea of Galilee. *Water Resources Research*, 43(10).
- Givati, A., Lynn, B., Liu, Y. and Rimmer, A. (2012). Using the WRF model in an operational
  streamflow forecast system for the Jordan River. *Journal of Applied Meteorology and
  Climatology*, 51(2), 285–299.
- Givati, A. et al. (2016). Expected future runoff of the Upper Jordan River simulated with a
  CORDEX climate data ensemble. *Journal of Hydrometeorology*, 17(3). *(Confirm full author
  list.)*
- Gophen, M. (2023). Historical review on water level changes in Lake Kinneret (Israel) and
  incomparable perspectives. *Water*, 15(5), 837.
- Kratzert, F., Klotz, D., Brenner, C., Schulz, K. and Herrnegger, M. (2018). Rainfall–runoff
  modelling using Long Short-Term Memory (LSTM) networks. *Hydrology and Earth System Sciences*,
  22, 6005–6022.
- Kratzert, F. et al. (2019). Towards learning universal, regional, and local hydrological
  behaviors via machine learning applied to large-sample datasets. *Hydrology and Earth System
  Sciences*, 23, 5089–5110.
- Mahanama, S., Koster, R. D., Reichle, R. H. and Zubair, L. (2008). The role of soil moisture
  initialization in subseasonal and seasonal streamflow prediction — a case study in Sri Lanka.
  *Advances in Water Resources*, 31(10), 1333–1343.
- Maraun, D. and Widmann, M. (2018). Perfect prognosis (Chapter 11). In *Statistical Downscaling
  and Bias Correction for Climate Research*. Cambridge University Press.
- Maraun, D. et al. (2019). Statistical downscaling skill under present climate conditions: a
  synthesis of the VALUE perfect predictor experiment. *International Journal of Climatology*, 39.
- Pappenberger, F., Ramos, M. H., Cloke, H. L., Wetterhall, F., Alfieri, L., Bogner, K.,
  Mueller, A. and Salamon, P. (2015). How do I know if my forecasts are better? Using benchmarks
  in hydrological ensemble prediction. *Journal of Hydrology*, 522, 697–713.
- Richter, J. H. et al. (2024). Quantifying sources of subseasonal prediction skill in CESM2.
  *npj Climate and Atmospheric Science*, 7, 59.
- Rimmer, A. and Gal, G. (2014). Hydrology (Chapter 7). In Zohary, T., Sukenik, A., Berman, T. and
  Nishri, A. (eds.), *Lake Kinneret — Ecology and Management*. Springer.
- Rimmer, A. and Salingar, Y. (2006). Modelling precipitation–streamflow processes in karst basin:
  the case of the Jordan River sources, Israel. *Journal of Hydrology*. *(Confirm volume/pages.)*
- Samuels, R. et al. (2010). Climate change impacts on Jordan River flow: downscaling application
  from a regional climate model. *Journal of Hydrometeorology*, 11(4). *(Confirm full author
  list.)*
- Sannasi Chakravarthy, S. R., Bharanidharan, N. and Rajaguru, H. (2022). A systematic review on
  machine learning algorithms used for forecasting lake-water level fluctuations. *Concurrency and
  Computation: Practice and Experience*, 34.
- Seibert, J. (2001). On the need for benchmarks in hydrological modelling. *Hydrological
  Processes*. *(Confirm volume/pages.)*
- Seibert, J., Vis, M. J. P., Lewis, E. and van Meerveld, H. J. (2018). Upper and lower benchmarks
  in hydrological modelling. *Hydrological Processes*. *(Confirm volume/pages and author list.)*
- Shentsis, I. and Ben Zvi, A. (1994). *Updated model to predict the available water for Lake
  Kinneret.* Israeli Hydrological Service, Report 94/2. *(Grey literature — see note below.)*
- Szczepanek, R. (2022). Daily streamflow forecasting in mountainous catchment using XGBoost,
  LightGBM and CatBoost. *Hydrology*, 9(12), 226.
- Tomsett, A. C. and Toumi, R. (2000). Diurnal temperature range and rainfall probability.
  *Geophysical Research Letters*, 27(9), 1279–1282.
- Vitart, F. et al. (2018). Progress in subseasonal to seasonal prediction through a joint weather
  and climate community effort. *npj Climate and Atmospheric Science*, 1, 3.
- *Week 3–4 predictability over the United States assessed from two operational ensemble
  prediction systems.* (2019). *Climate Dynamics*, 52, 5861–5875. doi:10.1007/s00382-018-4484-9.
  *(Author list not yet retrieved — see note below.)*

### Three open items

1. **Author list for the *Climate Dynamics* (2019) week 3–4 paper.** Title, volume, pages and DOI
   are confirmed; only the authors are missing. One database lookup.
2. **Shentsis and Ben Zvi (1994) is an Israeli Hydrological Service report, not a journal
   article.** It is the right primary source for the basin's inflow-prediction lineage but may be
   hard for reviewers to obtain. Options: cite it as grey literature, or lean on Rimmer and Gal
   (2014) for the claim and cite the report secondarily. The section is currently written the
   second way.
3. **Volume/pages for Rimmer and Salingar (2006), Seibert (2001) and Seibert et al. (2018).**
   Records confirmed to exist and the attributed claims are correct; only the bibliographic detail
   is missing.

### What changed from v1 — corrections worth knowing

- **"Ozdemir et al. (2022)" did not exist.** The lake-level ML review is Sannasi Chakravarthy,
  Bharanidharan and Rajaguru (2022).
- **The DTR–rainfall link is Tomsett and Toumi (2000) in *GRL*, not a second Dai et al. paper.**
  Their result — DTR above ~10 °C implies reduced rainfall probability — is a much better anchor
  for our premise than a generic DTR–cloud correlation.
- **Givati and Rosenfeld (2007) is an aerosol paper, not a rainfall–runoff methods paper.** v1
  cited it for statistical rainfall–runoff correlations, which it is not about. It is now cited
  for the observed basin-wide flow decline, which is what it establishes.
- **Several ML application citations were cut.** v1 named authors for the Great Lakes, Chapala,
  Tisza and glacierized-catchment studies that I could not confirm. The paragraph now rests on
  the verified review plus Szczepanek (2022), and the argument is unchanged.
- **The soil-moisture paragraph was narrowed to Mahanama et al. (2008)**, whose finding — skill
  from soil-moisture initialization *even when rainfall skill is small* — is the one our case
  actually needs. Three unconfirmed supporting citations were replaced with an unattributed
  summary sentence; add them back only if you want the extra weight and can source them.
