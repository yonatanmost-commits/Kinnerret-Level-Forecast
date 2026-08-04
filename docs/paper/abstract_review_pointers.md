# Abstract review — correction pointers

**Re:** `kinneretLevel_abstract.docx` (draft 2026-08-03)
**Reviewed against:** `docs/paper/Kinneret_Forecast_Methods_Results.md` and the generating artefacts in the repo.

Every number in the abstract traces to a real artefact — nothing is invented, and the
perfect-prognosis caveat was kept, which I appreciate. The pointers below are places where
the compression to 442 words changed what a claim asserts. Each one cites the artefact and
proposes a minimal fix; where the call is yours, I've said so rather than pre-deciding it.

---

## P1. `R² = 0.771` is now stale — 0.751 as of this morning *(housekeeping, no fault)*

**Abstract:** "the two-stage gradient-boosting model achieved an R² of 0.771"

**Repo:** `docs/olympics_results.json`, rewritten 2026-08-04 09:03 by the daily agent
(`Reports/daily_agent_2026-08-04.txt`, all stages green):

| | draft | current |
|---|---|---|
| vol R² mean | 0.771 | **0.751** |
| 2021 fold | 0.704 | 0.651 |
| 2023 fold | 0.680 | 0.657 |
| retrained | 2026-06-06 | 2026-08-04 |

This is the pipeline working as §6 promises — the champion retrains daily, so headline
numbers drift as the record extends. It also means the paper draft quotes a number the repo
no longer produces.

**Decision needed:** we should fix a **data freeze date** for the paper and quote that run
everywhere, rather than chasing the live number. I suggest freezing at the last day of the
hydrological year in the record and stating it in §6. Do you have a preference?

---

## P2. "operational water-balance variables" claims data we do not have *(factual)*

**Abstract:** "…integrating historical lake-level observations with meteorological, rainfall,
temperature, hydrological, and **operational water-balance variables**." Preceded by the
framing sentence listing "water consumption, and management interventions" as drivers.

**Repo:** Table 1 (§2.1) lists three feeds — lake level, meteorology, river flow — plus ERA5
reanalysis. There is no consumption, pumping, extraction, or allocation series anywhere in
the pipeline. The only outflow term in the gold table is `outflow_baptism_m3`, a **measured
river gauge** (and per project notes, two stitched stations with a 332-day gap in the
record). §3.2 treats outflow as "(climatological/known)".

Our own §3.6 says it outright: *"The one term the method cannot see is pumping policy:
evaporation is reliable, extraction is a decision."*

**Why it matters:** paired with the intro sentence, a reviewer reads this as "they have the
Water Authority's abstraction data." When they find we don't, it costs us credibility on
everything else in the abstract — and it's the easiest claim in the paper to check.

**Proposed:** drop "operational" → "…meteorological, rainfall, temperature, and hydrological
variables, including measured river inflow and outflow." Keep the driver list in the framing
sentence; it's accurate as a description of the *system*, just not of our *inputs*.

---

## P3. The 47 mm result is not a machine-learning model *(attribution)*

**Abstract:** "This study evaluates **machine-learning approaches**…" → "the **30-day summer
model** achieved a mean absolute error of 47 mm."

**Repo:** §3.6 — the method is an **anomaly-scaled seasonal recession** built from a
leave-one-year-out day-of-year climatology of level change, with an anomaly multiplier from
the trailing 21 days. No learned model, no training. `Automation/redline_backtest.py`.

**Why it matters:** 47 mm is the most impressive-sounding number in the abstract, and as
written the reader credits ML for it. If that's challenged in review, our best result becomes
the thing we look evasive about. The paper is careful here and the abstract shouldn't be
less careful than the paper.

The honest version is also the *better* story — it's what makes §4.5 work. "When rain leaves
the system, a simple seasonal model is the right tool, and ML is unnecessary" is a finding.
"Our ML got 47 mm" is a number.

**Proposed:** "the summer recession, forecast by an anomaly-scaled seasonal climatology rather
than a learned model, achieved a mean absolute error of 47 mm at 30 days."

---

## P4. The 47 mm is horizon-selective — 60 and 90 d lose to plain climatology *(omission)*

**Repo:** `docs/redline_backtest_results.json` — skill vs **unscaled climatology**, the honest
baseline:

| Horizon | MAE (m) | SS vs persistence | **SS vs unscaled clim** |
|---|---|---|---|
| 30 d | 0.047 | +0.935 | **+0.292** |
| 60 d | 0.112 | +0.913 | **−0.310** |
| 90 d | 0.195 | +0.894 | **−0.676** |

Two things the abstract's single number hides:

1. **30 d is the only horizon where the method beats climatology.** Past 60 days the anomaly
   multiplier is actively harmful — extrapolating a transient spring anomaly two to three
   months forward over-commits to it. §4.4 already reports this as an honest caveat *and*
   converts it into a concrete product fix (damp the anomaly scale toward 1.0 as lead grows).
2. **The +0.89–0.94 skill scores are against persistence**, which for a monotonic rainless
   recession is a baseline anything beats. Quoting the raw MAE without a baseline lets the
   reader supply their own, and they'll supply a generous one.

**Why it matters:** reporting only the winning horizon is the pattern reviewers are trained to
look for. Volunteering the 60/90 d degradation costs us one clause and buys the reader's
trust for the rest of the abstract — and we get to present a fix, which reads as command of
the method rather than a weakness.

**Proposed:** add "…at 30 days, though the anomaly scaling degrades beyond 60 days and should
be damped with lead."

---

## P5. Temperature gets co-billing that the ablation gives to catchment state *(attribution — the important one)*

**Abstract:** "combining temperature information with catchment-state memory provided useful
predictive skill during the wet season"

**Repo:** `docs/longrange_phaseb_report.md` — the ablation was designed precisely to separate
these two, and it does:

| Season | SS temp marginal (vs base) | SS bucket marginal (vs temp) |
|---|---|---|
| Wet (Nov–Mar) | +0.196 | **+0.260** |
| Dry (Apr–Oct) | **−0.418** | **+0.279** |

§4.3, finding #2, in the paper's own words: **"The decisive ingredient is catchment *state*,
not temperature."** And §4.5: the frontier can be pushed "by modelling *state* rather than
chasing a better point forecast."

**Why it matters — this is the one I'd most like changed.** "Combining X with Y" is symmetric;
the result is not. The bucket adds more than temperature in the wet season and is the *only*
thing that helps in the dry season, where temperature is net-harmful. More importantly, the
state-vs-temperature attribution **is our methodological contribution**: it's the corrected
form of a feature that previously failed ("Architecture J"), and it identifies the
sub-seasonal limit as catchment memory rather than meteorological forecast quality. That is
the transferable finding — the part another catchment can use. Symmetrising it into
"combining" gives away the paper's idea to save four words.

**Proposed:** "at the 14–30-day horizons, useful wet-season skill came primarily from
catchment-state memory rather than from temperature, which contributed a thin margin in the
wet season and was net-harmful in the dry season."

---

## P6. "did not consistently outperform" understates a dry-season SS of −1.228 *(framing)*

**Abstract:** "but did not consistently outperform the baseline throughout the year"

**Repo:** dry-season SS(temp vs clim) = **−1.228** — more than double climatology's error
variance, across the seven months Apr–Oct. Per-lead it holds from lead 7 (−2.394) through
lead 30 (−1.240), so it isn't one bad horizon dragging a pool.

"Inconsistent" implies it sometimes wins and sometimes loses. It loses, systematically, for
most of the year — which is exactly why §4.3 concludes a deployable version would be
**wet-season-only**, paired with the summer recession product. That conclusion is the thing
the abstract's final sentence ("a season- and horizon-aware framework") is built on, so
softening the evidence here weakens our own recommendation.

**Proposed:** "…but was net-negative against climatology across the dry season, so no
year-round skill was demonstrated."

---

## P7. The bake-off negative result is dropped *(omission — worth reclaiming)*

**Abstract:** "The evaluated approaches included persistence and climatological baselines,
gradient-boosting regression, a two-stage rainfall-aware model, and models incorporating
catchment-state memory."

**Repo:** eight configurations were raced under identical walk-forward CV
(`docs/olympics_results.json`), including **a GRU that collapsed to R² ≈ 0** (−0.026, MAE 1.485
vs the champion's 0.64) and XGBoost/LGBM trailing by ~7–9 R² points. §4.1's conclusion:
*"the limiting factor at this horizon is the signal, not model capacity."*

**Why it matters:** "we tried a deep sequence model and it added nothing" is a publishable,
reviewer-pleasing negative result — it pre-empts the single most predictable review comment
("why not an LSTM?"), and it's the evidence for our framing that the frontier is set by
rainfall predictability rather than by modelling choices. Costs one clause; earns the whole
rain-gated-frontier argument.

**Proposed:** "…including a recurrent neural network, which added no skill — indicating the
limiting factor is the available signal rather than model capacity."

---

## P8. Two smaller ones

- **`R²` is on volume change, not level.** In a paper titled "…Forecasting of Water Levels,"
  an unlabelled `R² = 0.771` reads as level R². Ours is ΔVolume R² (§3.1) — which is the
  *conservative* choice (level is near-integrated and would score far higher for trivial
  reasons), so we should get credit for it rather than be asked about it. Suggest "an R² of
  0.751 on daily volume change."
- **"A season- and horizon-aware framework can therefore provide more reliable support."**
  We haven't built or validated such a framework — we've shown three products with different
  skill profiles and argued one is implied. Suggest "…motivating a season- and horizon-aware
  framework" to keep it as the forward-looking claim it is.

---

## Summary of what I'm asking

| # | Item | Type | Fix cost |
|---|---|---|---|
| P1 | 0.771 → 0.751; set a data freeze date | housekeeping | number + a decision |
| P2 | "operational water-balance variables" — we have no consumption data | **factual** | one word |
| P3 | 47 mm is climatology, not ML | **attribution** | one clause |
| P4 | 60/90 d lose to climatology | **omission** | one clause |
| P5 | Skill is from catchment state, not temperature | **attribution** | one sentence |
| P6 | Dry-season SS is −1.228, not "inconsistent" | framing | one clause |
| P7 | Reclaim the GRU/capacity negative result | omission | one clause |
| P8 | Label R² as volume-change; soften the closing claim | precision | two edits |

None of these require giving up a result, and P3/P4/P7 arguably make the abstract *stronger* —
they convert three apparent weaknesses into the rain-gated-frontier argument the paper is
actually about. Happy to take a pass at the wording once we agree on P1's freeze date and P5's
attribution, which are the two that change what the paper claims.
