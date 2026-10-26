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

1. **Lake animation:** `python docs/talk/make_lake_animation.py` → `charts/lake_years.mp4`, `_narrated.mp4`, `.gif`, last-frame `.png`. The last month to 11 Nov 2026 is now almost all measured, not projected. The printed "projection: last measured …" line gives the new 11 Nov value (it was −213.81 "if no rain falls"). Timing is fixed by the narration, so no re-recording is needed.
2. **Bare copy for native labels:** `python docs/talk/make_lake_animation.py --bare` → `charts/bare/lake_years.mp4`. Re-run after every render.
3. **Map morph:** `python docs/talk/make_map_morph.py` → `charts/slide1_map.mp4` / `.gif`. It starts on `lake_years.png`'s last frame, so it must come after step 1.
- Check: the 11 Nov 2026 label, the dashed line and the gauge all show the new value. The 2027 split (best/worst year of the last decade) doesn't change.
- The `test_talk_lake_animation.py` tests must stay green.

## Step 7. Words: `docs/talk/review/deck.html`

- **Slide 1 (lake):** reader/notes value for 11 Nov 2026, and "projection that assumes no rain" if only a few days are projected.
- **Slide 9 facts:** "the live one is from 15 Oct" → the new date.
- **Slide 12 (fan):** reader ("15 October 2026", "October forecast"), script and pointers (about 1 m, late February, one in three, 2 in 10), facts (most likely at 6 and 12 months, bands, wet/normal/dry levels and chances, highest/lowest replays). "7.7 in 10" stays.
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
