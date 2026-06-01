# Expert Commentary Page — Design

**Date:** 2026-06-01
**Author:** Brainstormed with the user
**Status:** Approved design, pending spec review

## Purpose

Add a new Streamlit dashboard page (`8_Expert_Commentary.py`) in which the
project's hydraulic & meteorological modeling specialist tells the **data
story** of the Kinneret level-forecast model in his own voice — the full
honest arc, wins and dead-ends alike. The page is the narrative complement to
the quantitative Model Olympics page (page 7): page 7 shows *what* the scores
are; this page explains *how we got here and why*.

## Persona & voice

- **Named persona, first person.** Byline at top, signature at bottom.
- Identity: **Dr. Wade Storm — Hydraulic & Meteorological Modeling
  Specialist** (Australian, punning name per user: "Wade" = hydraulics,
  "Storm" = meteorology).
- Dateline: 2026-06-01.
- Tone: rigorous, warm, opinionated; a scientist honest about dead-ends.

## Story arc (the full honest version)

Prose essay in titled movements, using existing WATERLINE typography
(`.kn-label`, `.kn-subtitle`, `.kn-divider`, `bone-dim`). Folds in context from
project memory beyond the original `Meteo Models Expert Notes.md`:

1. **"What I was asked to do"** — two-stage GBR (met → inflow → ΔVolume →
   level). Worked but plateaued at R² **0.694**.
2. **"First, the data lied"** — the 2023 pipeline bug chain (IMS `-` sentinel,
   `aggfunc=first`, pandas NaN sums, wrong output path). Fixing corrupted data
   came *before* fixing the model. (Source: `project-pipeline-2023-fix`.)
3. **"Reading the residuals"** — diagnostic detective work: S2 target
   skew=4.82 / kurtosis=49; 116 flood days = 2.4% of days but **58% of
   variance**; outflow (r=0.606) the strongest unused signal sitting in the
   gold table. (Source: `Meteo Models Expert Notes.md`.)
4. **"The Signal Harvest"** — six fixes: signed-log1p target transform,
   outflow_lag1 anchor, dvol lag2/lag3 anchors, RBF seasonality, precip
   intensity, gentler hyperparameters (lr 0.05→0.03). **0.694 → 0.758**.
   (Source: `project-error-prop-olympics`.)
5. **"When a sensor dies"** — radiation/ET₀ sensor death 2026-04-25, Open-Meteo
   backfill. Honest caveat: backfill data is 2026-only, outside the 2021–2024
   CV folds, so the move to **0.771** reflects gap-free live inputs + run-to-run
   noise, not a CV gain. (Source: `project-met-pipeline-architecture`,
   `project-error-prop-olympics`.)
6. **"The honest failure: Architecture J"** — antecedent moisture (30/45-day
   rolling rainfall sums). Right hypothesis (soil-moisture state-blindness:
   2023 drought over-predicts, 2021 wet under-predicts), wrong instrument —
   flat sums can't encode catchment **saturation**. **+0.005**, below the
   +0.02 target. Reported as a negative result. (Source:
   `project-round3-architecture-j`.)
7. **"What's still unsolved"** — the open thread: the catchment needs a *state*
   variable (a decaying/saturating soil-moisture bucket, P−ET), not flat sums.
   (Source: `project-next-moisture-proxy`.)

## Signature visual (one live chart)

**R² progression timeline:** Baseline `0.694` → Signal Harvest `0.758` →
Architecture J `0.763` → Radiation backfill `0.771`.

- Milestones 1–3 are historical module constants.
- The **final point reads live** from `docs/olympics_results.json`
  (`models.baseline_gbr.cv_vol_r2_mean`), so the story self-corrects on retrain.
- Plotly line+marker chart, styled via `theme.style_plotly`, WATERLINE palette.

## Technical design

- **File:** `kinneret_app/pages/8_Expert_Commentary.py`.
- `st.set_page_config(page_title="Expert Commentary", page_icon="🌊",
  layout="wide")`, then `inject_theme()` — same import-guard pattern as page 7.
- **Live data:** read `docs/olympics_results.json` via `PROJECT_ROOT`. If
  missing, page still renders the full essay; the final timeline point falls
  back to the last-known `0.771` constant. **No `st.stop()`** — the prose is the
  point (differs from page 7, which stops when results are absent).
- **Prose:** `st.markdown(..., unsafe_allow_html=True)` reusing existing
  classes. A styled byline block at top and signature at bottom. Reuse existing
  CSS first; add at most one small helper class (e.g. `.expert-byline`) only if
  needed, in `theme.py`.
- **No changes** to any other file — purely additive new page.

## Testing / verification

- Run the new page through `streamlit.testing.v1.AppTest.from_file(...).run()`
  and confirm `.exception is None` (project convention from
  `project-kinneret-dashboard`).
- Confirm the live R² value renders from `docs/olympics_results.json` and the
  fallback path works when the file is absent.

## Out of scope (YAGNI)

- No new model training, no pipeline changes, no data regeneration.
- No new charts beyond the single R² progression timeline.
- No edits to other pages or navigation config (Streamlit auto-discovers
  `pages/8_*.py`).
