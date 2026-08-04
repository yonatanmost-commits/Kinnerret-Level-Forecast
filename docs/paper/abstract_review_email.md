**Subject:** Kinneret abstract — 4 things to fix

Hi Adnan,

Thanks for drafting this, and for the author listing. I checked it against the
Methods/Results doc I sent you — four things need correcting:

**1. R² is now 0.751, not 0.771.** The model retrains daily and it moved on Tuesday
(2021 fold .704→.651, 2023 .680→.657). We should pick a data freeze date and quote that
run everywhere, or this keeps moving under us. Also worth labelling it as R² on *volume
change*, not level (§3.1).

**2. "operational water-balance variables" — we don't have those.** No consumption,
pumping or allocation data anywhere in the pipeline; just level, meteorology and river
flow (Table 1). §3.6 says it outright: *"the one term the method cannot see is pumping
policy."* Suggest dropping "operational".

**3. The 47 mm is not a machine-learning result.** It's an anomaly-scaled seasonal
climatology (§3.6) — no learned model — and the abstract frames the study as
"machine-learning approaches". It's also 30-day only: at 60 and 90 days the method is
*worse* than plain climatology (Table B). Both worth one clause each.

**4. The 14–30-day skill comes from catchment state, not temperature.** The ablation
separates them: temperature +0.196 wet and −0.418 dry, the soil bucket +0.260 wet and
+0.279 dry (Table A). §4.3 puts it as *"the decisive ingredient is catchment state, not
temperature"* — that attribution is our actual contribution, so I'd rather not have it
read as "combining" the two.

Happy to send you revised wording once you've had a look.

Best,
Yonatan
