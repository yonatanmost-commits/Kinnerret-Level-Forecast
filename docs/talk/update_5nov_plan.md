# Weekend runs, 6–9 Nov (planned 5 Nov; NOTHING STARTED, run only on the originator's go)

**What happened on 5 Nov (read first).**
- **SEAS5 November is not downloadable before ~13 Nov.** CDS refused it: "Restricted access to current C3S seasonal forecast ECMWF contribution" (5 Nov, 17:37 UTC). The public CDS copy opens with the C3S release around the 13th, after the talk. D1/D2 are moot; everything stays on the **October** issue. (Paper caveat: the backtest's `RELEASE_DAY = 5` is about 8 days early for a public user.)
- **Step 3 below was wrong:** `cfc_tournament.py` *skips* a test year already in `CFC_OUT`. Always run into an **empty** folder, then copy the results in.
- Done on 5 Nov (today's data, lake on 3 Nov): fan rerun from 3 Nov (`CFC_ANCHOR=2026-11-03`), app fan (local, not pushed), slide data, fan charts (labels now follow the data), lake animation + map morph (still the no-rain projection), takeaways, **new slide 9 "The choice"** (a table; Copernicus → hidden Q&A), slide 8's 6-month GRU 56 → 55 (a double rounding), rev2 rebuilt (the last build still has the earlier crossing-lines slide 9: rebuild once PowerPoint closes the file).
- The year-ahead odds are a knife-edge, not two dry winters (tested): starts from 3 Sep to 3 Nov give 32–47% under the red line, with a step between 1 and 8 Oct; dropping 2006–07 and 2007–08 only moves 47% → 44%. Notes on the horizon slide.

**Why rerun everything.** The 17 Oct backtest (`cfc_monthly`) predates ~40 filled-in days of rain and weather (2005–2011; no old value changed). Slides 8 and 9 (point errors on test years 2011–2025) should barely move; the fan's "~7.7 in 10", the track record and the red-line calibration (past-winter replays) may. One data day for every number.

**Data day D.** Saturday 7 Nov, right after the 07:30 refresh (check with `/data-dan`: the last level day, expected 5 or 6 Nov). Run R1–R9 before the next refresh (Sunday 07:30), so every run reads the same gold. If the refresh fails, use the last good gold and say so.

| # | Run | Command (repo root unless noted) | ~Time | Writes | Check | Moves |
|---|---|---|---|---|---|---|
| R1 | **Freeze the gold** | `mkdir docs/experiments/freeze_D` and copy `Gold Data/kinneret_gold_features.csv` into it as `gold.csv` | 1 min | the frozen copy | last level day, row count | every run below reads it (`CFC_GOLD`) or the unchanged gold |
| R2a | **Reproduce the old backtest first** (proves the command) | old gold: `git show b80580a:"Gold Data/kinneret_gold_features.csv"` into `<scratch>/gold_old.csv`; in `Automation/`: `CFC_GOLD=<scratch>/gold_old.csv CFC_HORIZONS=monthly CFC_YEARS=2016 CFC_OUT=<scratch>/repro python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seas5 --seeds 3` | ~1–2 min | scratch only | 2016 errors match `cfc_monthly` within seed noise (~1 cm); weathers obs/clim/seas5/seas5c/seas5s/ens all present | nothing; if it doesn't match, STOP and find the 17 Oct flags |
| R2 | **Backtest rerun**, 2011–2025, 15 years | in `Automation/`, `CFC_YEARS=2011,2012,…,2025`, `CFC_OUT=../docs/experiments/cfc_monthly_D` (empty), `CFC_GOLD=<R1>`, `CFC_HORIZONS=monthly`: GRU `python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seas5 --seeds 3`; CfC the same with `--cell cfc`; GBR `python cfc_tournament.py --table ims --method G --seas5 --seeds 3` | GRU ~15 min, CfC ~20 min (17 Oct: 53 vs 75 s a year), GBR ~10 min (est.) | `cfc_monthly_D/{B14gru_s3_ens,B14_s3_ens,G_s3,references}.json` | 15 years × 3 models; weathers as R2a | slides 8, 9; the fan's error bands; Q&A |
| R3 | **Fan evaluation + track record** | back up `docs/experiments/cfc_fan_eval/`; `CFC_GOLD=<R1> python Automation/cfc_fan_eval.py docs/experiments/cfc_monthly_D --out docs/experiments/cfc_fan_eval/fan_monthly.json`; then `python Automation/cfc_track_record.py` | ~5 min (est.) | `fan_monthly*.json/csv`, `track_record.csv`, `reliability_red.csv` | B14gru/seas5 80% coverage at 365 d (was 77%: "~7.7 in 10"); "held" at 6/12 months (was 9 of 12) | slide 10's "~7.7 in 10" and "misses mostly up", the calibration line; Q&A "Why should we believe it?" |
| R4 | **Swap the backtest in** | rename `docs/experiments/cfc_monthly` → `cfc_monthly_1017`, then `cfc_monthly_D` → `cfc_monthly` | — | — | `tests/test_talk_crossover.py` turns RED until R8 (by design: slide 8's typed table must follow the backtest) | everything that reads `cfc_monthly` |
| R5 | **Today's fan** from the last measured day L | in `Automation/`, an EMPTY `<scratch>/today`: `CFC_GOLD=<R1> CFC_HORIZONS=monthly CFC_FUTURE=1 CFC_YEARS=2026 CFC_OUT=<scratch>/today CFC_ANCHOR=L python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seeds 3`; copy `B14gru_s3_ens.json` + `references.json` into `docs/experiments/cfc_today_monthly/`; `python fan_today.py` | ~2 min | `Models/longrange_fan.json` | start = L, level0 = the measured level, seasonal init 2026-10 | app page 10, slide 10 |
| R6 | **Slide-10 data** | `python docs/talk/data/slide11_fan_build.py` | 20 s | `docs/talk/data/slide11_*` | 12-month median, p_red, crossings vs 5 Nov (−213.32, 47%, ~3 Mar up, ~2 Sep down) | slide 10, takeaway 1 |
| R7 | **Slide-1 talk day** (week model + IMS) | `python docs/talk/data/slide1_week_forecast.py --dry`, then without `--dry` | 1 min | `docs/talk/data/slide1_week_forecast.json` | `from` = L (needs L ≥ 4 Nov); measured weather for past days, IMS for the rest | slide 1's 11 Nov stop: "forecast" instead of "if no rain falls" |
| R8 | **Charts** | `chart_models.py` (type the new cells into `MODELS`; the test compares them with R2) · `chart_choice.py` · `chart_fan.py` (set "~7.7 in 10" from R3) · `chart_takeaways.py` · `chart_seas5.py` (backup; its rain dots read gold) · `make_lake_animation.py`, then `--bare`, `--cut`, then `make_map_morph.py` | ~10 min | `docs/talk/charts/*` | LOOK at every render; talk tests green except the 4 known (coverage, A4, A5, A21) | slides 1, 8, 9, 10, 11; backups |
| R9 | **Hand-in deck** | `CLEAN_OUT=Kinneret_Talk_Submission_rev2_ref.pptx python docs/talk/build_clean.py`; `python docs/talk/deck_diff.py` ref vs rev2 (fold any hand edits); `CLEAN_OUT=Kinneret_Talk_Submission_rev2.pptx python docs/talk/build_clean.py`; export slides 1 and 8–10 to PNG and look | ~5 min | rev2 | 16 slides, 13–16 hidden | the deck to send |
| R10 | *Optional:* **freeze ledger** on D | `python Automation/talk_freeze_run.py --freeze D` (GRU ~15 min; run alone, memory) | ~30 min | `docs/talk/numbers_ledger.json`, `truth_stamp.json` | truth tests; it re-stamps the deck | week-ahead numbers (Olympics, baselines, "lowest since"). **Recommendation: skip**: its folds are 2021–2024, untouched by the gap fill, and 3 truth tests already fail and would block the stamp |
| — | *After the script pass, with the originator* | `python docs/talk/build_show.py narrate` (changed slides), then `build`, then `video` | ~20 min | show deck, MP4, MP3 | click-through | the rehearsal deck |
| R11 | **Monday 9 Nov, before sending** (optional freshness) | after the 07:30 refresh: R5–R7, the R8 fan and animation charts, R9 | ~20 min | — | L moves to 7–8 Nov | slides 1, 10 |
| — | **Not possible** | SEAS5 November | — | — | — | after the talk (~13 Nov) |

**Needs the originator's OK (not runs):** push `Models/longrange_fan.json` (redeploys the app behind the QR code) · commit · send the deck (reply in the submission thread) · the script pass (every spoken number; list in the handoff).

---

# 5 November update: plan

**Goal.** After Copernicus publishes its November seasonal forecast (SEAS5, the 5th, around midday UTC), refresh everything in the talk that reads "today": the year-ahead fan (slide 13 in the hand-in deck, "The horizon"), the slide-2 lake animation and map morph, and the notes that quote them. Then send the organisers the updated deck before the talk on 11 Nov. Adnan agreed (25 Oct) that no permission is needed, and the submission mail already said an update may come.

**Unchanged (frozen backtests, not "today"):** the models table, the errors, the fan track record, the 80% backtest ("held 7.7 times in 10", 604 forecasts), the slide-8 history columns, and every other chart.

**Timetable:** Thu 5 Nov download · Fri 6 – Sat 7 run and rebuild · Sun 8 review · Mon 9 send · Tue 10 rehearse (reception in the evening) · Wed 11 talk.

---

## Decisions (all three taken as recommended, 2026-10-26)

D1 = (a), an extra start on the last measured day · D2 = keep slide 8 on the October issue, November in the notes · D3 = send only if a number said on slide 13 changes.

**D1. How the November forecast gets into the fan.** This is a real catch. Fan starts fall every 7th day from 1 Jan (`cfc_tournament.anchors_for`), so the November start is **5 Nov**. But `seas5.init_for` counts a forecast as published only *after* the 5th (`RELEASE_DAY = 5`). A plain rerun would therefore still use the **October** forecast. Options:
- **(a) Recommended: one extra start on the last measured day** (e.g. 8 Nov). A small `CFC_ANCHOR=YYYY-MM-DD` override in `cfc_tournament.py`, for future runs only. The fan then starts from the newest level and uses the November forecast, the same way the app would on that day. Cost: a few lines plus a test.
- (b) Keep the 5 Nov start, and run this one job with `RELEASE_DAY=4`, so a start on the 5th takes that day's issue. No new code, but the start is 3–4 days behind the data, and the backtest never ran that way.
- (c) Keep the 5 Nov start with the October forecast. Only the starting level updates; the forecast in the title of the update doesn't. Little value.

**D2. Slide 8 ("the forecast", seas5_track): last column.** Every column is "Copernicus's *October* forecast for that winter", and the 9-of-14 record is October-only.
- **Recommended: keep the October issue on the chart** (like with like), and add one line to the notes: "the November issue says X%".
- Or switch only this winter to November. The column is fresher, but it no longer matches its own track record.

**D3. When is it worth sending?** Recommended: send if any number you *say* on slide 13 changes (crossing month, "about 1 m", "1 in 3", the wet/dry chances). If the November run lands on the same words, update the app and the notes but keep the deck you already sent.

---

## Step 0. Before 5 Nov: make the chain rerunnable (do this week)

**Status 2026-10-26:**
- **0.1 done.** `slide11_fan_build.py` now writes all four files. `dots()` and `crossings()` reproduce the 19 Oct hand-made files from the same inputs (locked test `tests/test_talk_fan_slide_data.py`). The crossings use every horizon in the fan table, 130 and 260 days included, as the hand version did. `--run` / `--fan` point the builder at another run.
- **0.2 done.** `CFC_ANCHOR=YYYY-MM-DD` in `cfc_tournament.py` (locked test `tests/test_cfc_extra_anchor.py`). It refuses a day with no measured level.
- **Data change since the slide was made:** the gold rain history before 2012 was rebuilt on 18 Oct (Tzemach-first). The live fan (run 17 Oct) and the slide files (19 Oct) use the older table. Winter 2009–10 went from 382 to 412 mm and moves from normal to wet, and 2025–26 moves from wet to normal. The group chances hardly move (wet 46.3% → 46.4%). The 5 Nov rebuild uses one day's data throughout, so this resolves itself, but expect the group lists on the slide to change.
- **0.3 done (steps 3–4; charts not rendered).** Dry run from 25 Oct into the scratchpad: the model run takes **under 2 min**, `fan_today` 31 s, the slide builder 18 s. 43 starts (42 on the grid + 25 Oct); the fan starts on 25 Oct at −213.715. The CDS check exposed one bug (below).
- **Bug fixed: the SEAS5 fetch.** `seas5_fetch.py` asked for all 12 start months of the year. For the current year CDS failed the whole request ("MARS … Request failed", 26 Oct), so on 5 Nov the fetch would have failed. It now asks only for months already issued (locked test `tests/test_seas5_fetch_months.py`). January–October 2026 re-fetched: identical to the file on disk. CDS login works.
- **The fan moves with the 18 Oct data change, regardless of Copernicus.** Same 15 Oct start, same code, measured 26 Oct:

  | Run | 6 months | 12 months | under the red line at 12 months |
  |---|---|---|---|
  | live (17 Oct, old gold) | −212.17 | −212.56 | 33% |
  | today's code, 17 Oct gold | −212.25 | −212.68 | 37% |
  | today's code, today's gold | −212.28 | −213.38 | 41% |
  | the same again (seed noise) | −212.29 | −213.37 | 41% |

  Seed noise is about 1 cm. The rain-history rebuild lowers the 12-month most likely by about 0.7 m; the 6-month point hardly moves. The 25 Oct start gives −213.58 and 45%, and its most-likely path crosses back under the red line in late August. **Expect the slide-13 words ("about 1 m above", "1 in 3", "staying above") to change on 5 Nov even if Copernicus says the same.** Under D3 that means an updated deck is likely.
- **Open, D4:** the fan's error bars and "held 7.7 times in 10" come from the 2011–2025 backtest (`cfc_monthly`, 17 Oct), trained on the old gold. Rerunning it on today's gold takes about 30 min (15 years × ~2 min) and re-checks the 7.7. Recommended: run it into the scratchpad before 5 Nov and adopt it if the coverage holds. **Agreed 2026-10-26, waiting: run it only when you say so.**

All four fan slide inputs now come from `slide11_fan_build.py`. `seas5_ours.csv` (slide 8) still has no producer, which is fine because D2 keeps slide 8 on the October issue.

---

## Step 1. Thu 5 Nov: download (after ~14:00 Israel time)

```
mv "Raw Data/SEAS5/seas5_2026.nc" "Raw Data/SEAS5/seas5_2026_oct.nc"   # fetch skips a year already on disk
python Automation/seas5_fetch.py 2026 2026
```
- Check: the new file has init 2026-11 with 51 members and leads 1–6 (`seas5.load()`). The October rows must be unchanged.
- Needs `~/.cdsapirc` (personal token; checked 26 Oct, works). CDS updates its terms on 28 Oct, and continued use counts as accepting them.
- Before 5 Nov the fetch asks for January–October; from 6 Nov it includes November (`months_for`). Run it on the 6th, or on the 5th only after the release (the rule counts the 5th as not yet out, so a run on the 5th asks only up to October).
- C3S multi-model (`c3s_fetch.py`) is not read by the fan or any slide, so skip it.

## Step 2. Data: lake level and weather up to the start day

- The 07:30 local refresh and CI bring the gold table forward. Check the last level day with `/data-dan`. The level source lags about a day, so a start on 8 Nov needs the 9 Nov refresh.
- Gold file: `Gold Data/kinneret_gold_features.csv` (level_m, weather). Nothing to edit by hand. If a day is missing, fix it upstream (fix bad data upstream, never in the model code).

## Step 3. Model run: GRU fan from the new start (~3 min, measured 26 Oct)

```
cd Automation
CFC_HORIZONS=monthly CFC_FUTURE=1 CFC_YEARS=2026 CFC_OUT=../docs/experiments/cfc_today_monthly \
  [CFC_ANCHOR=2026-11-08]  python cfc_tournament.py --table ims --method B --enc-len 14 --cell gru --ensemble --seeds 3
python fan_today.py              # latest start -> Models/longrange_fan.json (page 10 of the app)
```
- Back up `docs/experiments/cfc_today_monthly/` first: the run overwrites `B14gru_s3_ens.json`.
- Check: `longrange_fan.json` has start = the new day, the seasonal block shows **init 2026-11**, and level0 = the measured level that day.
- Tests: `tests/test_fan_today.py`, `tests/test_fan_gru.py`.
- No retraining of the week-ahead GBR is needed; the daily refresh already does that. The backtest (cfc_monthly) is rerun only under D4.

## Step 4. Slide data

```
python docs/talk/data/slide11_fan_build.py      # fan + meta (+ dots + crossings after step 0)
```
- Compare against the 19 Oct files: groups (wet/normal/dry winters and SEAS5 chances), the 12-month most likely, the 80% band, crossings.
- If D2 = November: the 2026-27 row of `seas5_ours.csv`.

## Step 5. Charts

| Chart | Command | Slide (hand-in deck) | Changes |
|---|---|---|---|
| `fan_today.png` + `_1` … `_4` | `python docs/talk/chart_fan.py` | 13 "The horizon" (4 clicks) | new start dot, band, dots, crossing labels ("~23 Feb", "~14 Jun"), wet/dry %, "1 in 3", the autumn-2027 card, stamp "from the lake on 15 Oct 2026 · October seasonal forecast" → new date + November |
| `fan_track.png` | same run | Q&A backup | nothing (backtest) |
| `seas5_track_1..3`, `seas5_track.png` | `python docs/talk/chart_seas5.py` | 8 "the forecast" | only if D2 = November |

Look at every render before moving on: labels must not collide when the crossing dates move.

## Step 6. The two animations (slide 2)

0. **The talk day's level, from the week model (decided 31 Oct).** On 5 Nov, fetch the IMS 7-day forecast and run the GBR week forecast (the app's page 6, "Fetch from IMS"). From the last measured day it reaches 11 Nov; that value replaces the "if no rain falls" projection at the animation's 11.11.2026 stop, which now holds on its own click before the split. Needs a small change first: `make_lake_animation.stops()` takes the forecast value (and the label "forecast" instead of "if no rain falls") when given one, and falls back to the projection otherwise. Keep the run's inputs and output in the scratchpad and the number, with its date, in the slide-1 facts. If the last measured day is more than 7 days before 11 Nov, the week model can't reach it: keep the projection and say so.
1. **Lake animation:** `python docs/talk/make_lake_animation.py` → `charts/lake_years.mp4`, `_narrated.mp4`, `.gif`, last-frame `.png`. The last month to 11 Nov 2026 is now almost all measured, not projected. The printed "projection: last measured …" line gives the new 11 Nov value (it was −213.81 "if no rain falls"). Timing is fixed by the narration, so no re-recording is needed.
2. **Bare copy for native labels:** `python docs/talk/make_lake_animation.py --bare` → `charts/bare/lake_years.mp4`. Re-run after every render.
2b. **Cut before the split (31 Oct):** `python docs/talk/make_lake_animation.py --cut` → `lake_years_a/_b.mp4` (+ bare twins, `lake_split.png`). The decks play these two, so re-run after every render and bare copy.
3. **Map morph:** `python docs/talk/make_map_morph.py` → `charts/slide1_map.mp4` / `.gif`. It starts on `lake_years.png`'s last frame, so it must come after step 1.
- Check: the 11 Nov 2026 label, the dashed line and the gauge all show the new value. The 2027 split (best/worst year of the last decade) doesn't change.
- The `test_talk_lake_animation.py` tests must stay green.

## Step 7. Words: `docs/talk/review/deck.html`

- **Slide 1 (lake):** reader/notes value for 11 Nov 2026, and "projection that assumes no rain" if only a few days are projected.
- **Slide 9 facts:** "the live one is from 15 Oct" → the new date.
- **SPOKEN NUMBERS (31 Oct scripts): the charts redraw themselves, the words don't.** Check each against the new `data/slide11_fan.csv` and fix script + pointers:
  - Slide 10 (fan), click 2: "70 centimetres below today … three and a half metres above" (12-month lo_80 / hi_80 minus the new start level). "Copernicus expects this winter on the wet side" (the wet third's weighted vs unweighted chance).
  - Slide 10, click 3: "late February" (the median's upward crossing) and "about a metre above" (12-month median − start).
  - Slide 10, click 4: "one in three" (p_red at 365 d).
  - Slide 11 (takeaways), click 1: "two-in-three" (= 1 − p_red; the slide's "2 in 3" redraws itself, the spoken one doesn't).
- **Slide 10 (fan):** reader ("15 October 2026", "October forecast"), script and pointers (about 1 m, late February, one in three, 2 in 10), facts (most likely at 6 and 12 months, bands, wet/normal/dry levels and chances, highest/lowest replays). "7.7 in 10" stays.
- **Slide 8 facts:** add the November lean ("This winter: 105% … in October; November says X%").
- If any **spoken** line changes, re-narrate those slides for the show deck (`python docs/talk/build_show.py narrate`).

## Step 8. Build the decks

1. **Hand-in deck.** You edit it by hand, so first diff it against a fresh build: `CLEAN_OUT=..._ref.pptx python docs/talk/build_clean.py`, then `python docs/talk/deck_diff.py`. Fold any hand edits into the source, then `python docs/talk/build_clean.py`.
2. **Self-running show:** `python docs/talk/build_show.py build`, then `video` (MP4 + narration MP3).
3. **Tests:** talk deck tests, including `test_talk_clean_deck.py`, both click tests and `test_talk_lake_animation.py`.
4. **Click through in slide show:** slide 2 (animation → map), slide 8, slide 13 (four clicks), and a click on every video.

## Step 9. App and send

- Commit `Models/longrange_fan.json` and push. Streamlit redeploys, so the app behind the QR code shows the **same fan** as slide 13 (page 10).
- Optional: re-shoot slide 4's app video (`shoot_app_light.py`) only if it shows the fan. It shows the front page today.
- **Send by Mon 9 Nov:** reply in the submission thread (To wateredgeil@mx.kinneret.ac.il, Cc Tamar, Adnan). Subject "Updated presentation – Most & Agbaria", one line on what changed (the year-ahead forecast now uses Copernicus's November forecast and the lake on <date>), the new pptx attached (12+ MB; attach by hand).
- Bring the deck on a USB stick as well, plus the PDF export as a fallback.

## Risks

- **CDS late or queued on the 5th:** the fetch retries for up to an hour. If it fails, keep the October deck; it's valid and already submitted.
- **Level data lag:** start on the last measured day, never on a filled-in day.
- **Numbers that move the story:** e.g. the crossing moves past March, or "1 in 3" becomes "1 in 2". Rewrite the script line; don't force the old words onto new numbers.
- **The hand-edited deck:** never rebuild without the diff (step 8.1).
