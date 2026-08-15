# Deployment

The Kinneret dashboard runs on [Streamlit Community Cloud](https://share.streamlit.io),
deployed from `master`. A scheduled GitHub Actions job refreshes the data daily.

---

## Architecture

Community Cloud serves the app but **cannot run a scheduler**, and its filesystem is
rebuilt from the repository on every deploy — nothing written at runtime survives.
So the data has to arrive through git:

```
  GitHub Actions (cron, 04:10 UTC)
        │
        │  runs Automation/daily_agent.py  ("dan")
        │    fetch level / flow / met  →  clean  →  build gold  →  train champion
        ▼
  commits Gold Data/, Silver Data/, Models/  →  push to master
        │
        ▼
  Streamlit Community Cloud sees the push  →  redeploys  →  dashboard is current
```

The push is what triggers the redeploy. There is no other refresh mechanism.

---

## First-time setup

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **New app** → **Deploy a public app from GitHub**.
3. Fill in:
   - Repository: `yonatanmost-commits/Kinnerret-Level-Forecast`
   - Branch: `master`
   - Main file path: `kinneret_app/app.py`
4. Under **Advanced settings**, set Python version to **3.13**.
5. **Deploy.** The first build takes a few minutes while it installs the pinned stack.

No secrets need to be configured — every data source the app calls is public and
unauthenticated.

### Enabling the daily refresh

The workflow needs permission to push its own commits:

- Repository **Settings → Actions → General → Workflow permissions**
- Select **Read and write permissions**, then Save.

Trigger a first run by hand from the **Actions** tab
(*Daily data refresh (dan)* → *Run workflow*) rather than waiting for the cron.

---

## What is committed, and why

The dashboard reads its inputs from disk, so those inputs live in the repository
(~68 MB). `.gitignore` excludes each data directory *by contents* — `Gold Data/*`,
not `Gold Data/` — because git cannot re-include a file that sits under an excluded
directory.

**Committed** — the files the app opens:

| Path | Used by |
|---|---|
| `Gold Data/kinneret_gold_features.csv` | `app_utils.load_gold()`, most pages |
| `Gold Data/longrange_climatology.csv` | long-range baseline |
| `Gold Data/cordex_waterbalance.parquet`, `cordex_hindcast.parquet` | page 9, Climate Scenarios |
| `Silver Data/Kinneret Level/kinneret_level.csv` | pages 1, 10 |
| `Silver Data/Jordan River Silver/jordan_river_daily_flow*.csv` | page 1, dan's append target |
| `Silver Data/Meteorological/met_data_daily*.csv`, `*_qc_log.csv` | page 1, pipeline |
| `Silver Data/Meteorological/precip_intensity_daily.csv` | step 07 feature build |
| `Models/*.pkl`, `Models/model_metadata.json` | `app_utils.load_models()`, pages 4–6 |

**Deliberately excluded:**

- `Silver Data/Meteorological/met_data_wide.csv` — 207 MB, over GitHub's 100 MB
  hard per-file limit. Nothing in `kinneret_app` reads it. See the caveat below.
- `Raw Data/` — 431 MB, never read by the app.
- `Gold Data/cordex_ensemble.parquet` — 28 MB intermediate; page 9 reads only the
  water-balance and hindcast files.
- `Models/gru_multitask.pt` — the GRU was retired 2026-06-01, and shipping it would
  drag `torch` into the image.
- `Reports/` — dan's run logs and draft correspondence to the Water Authority. This
  repository is public.

---

## Dependency pinning

`requirements.txt` pins exact versions on purpose. `Models/*.pkl` are pickled
scikit-learn estimators, and unpickling under a different scikit-learn or numpy
build can fail outright or, worse, load and predict subtly differently.

**If you retrain on an upgraded stack, re-pin `requirements.txt` in the same commit
as the new `.pkl` files.** They are a matched set.

`torch`, `xgboost` and `lightgbm` are *not* in the app's requirements — the app never
imports them; they appear only as label strings on page 7, which reads
`docs/olympics_results.json`. The training pipeline does need xgboost and lightgbm
(`08_train_forecast_model.py` imports them at module level), so CI installs
`Automation/requirements-pipeline.txt`, which layers them on top.

---

## Known caveat: precipitation intensity is frozen

`precip_intensity_daily.csv` is derived from the 207 MB 10-minute wide table, which
is **not** in the repository and which dan never extends — dan appends to
`met_data_daily.csv`, not to the wide table. The cached file therefore stops at
**2026-05-18**, while the gold feature table runs to the present.

`07b_precalc_precip_intensity.py` skips cleanly when the wide file is absent instead
of raising, because the hard failure used to cascade into skipping model training
entirely. But the underlying staleness is real: the `precip_intensity_mm_hr` feature
is not being updated for recent dates.

To refresh it, run locally where the wide table exists:

```bash
python Automation/02_pivot_wide_met_data.py
python Automation/07b_precalc_precip_intensity.py
python Automation/07_build_gold_features.py
```

then commit the updated `precip_intensity_daily.csv`.

---

## Repository growth

The daily job commits changed CSVs, and CSVs do not delta-compress well — expect
roughly 10 MB of new objects per run, on the order of a few GB per year. If the
clone gets uncomfortable, the options are to squash the accumulated data commits,
or to move the snapshot to release assets and have the app download it at startup.
Neither is needed at first; just don't be surprised by the growth.

---

## Local development

Unchanged — `run_app.bat` still starts the app against your full local data,
including the files that are excluded from the repository.
