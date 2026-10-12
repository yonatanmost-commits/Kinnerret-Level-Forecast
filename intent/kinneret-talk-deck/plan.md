# Plan: Kinneret Conference talk deck
From: intent/kinneret-talk-deck/spec.md v1.

## Design
- D1. Deck build: a single markdown source, `talk.md`, holds every slide (its one object, its on-slide text, its speaker notes). A python-pptx builder turns it into the PPTX. Chosen over a Claude Slides artifact (notes, audio and timings are hard to control and test) and over hand-building in PowerPoint (no automated checks), because re-fitting is then a rebuild, not a rewrite, and the acceptance criteria can be checked by reading the built file.
- D2. PowerPoint itself (scripted from Python) exports the PDF and produces the narrated rehearsal copy: it embeds each slide's audio and sets slide timings. Chosen over a third-party PDF converter because the real renderer is the proof for fonts and layout (global CLAUDE.md: verify with the real renderer).
- D3. The freeze measurements live in a separate script, `Automation/talk_freeze_run.py`, which imports the existing `run_cv*` functions from `08_train_forecast_model.py`, cuts the gold table at the freeze date, times each model, and writes one numbers ledger. Chosen over adding flags to the training script, so the daily production pipeline stays untouched. Follows the `Automation/redline_backtest.py` → `docs/*.json` pattern.
- D4. The GRU is revived inside the talk script by porting `run_cv_gru` from git (`4f9e553^`, the last commit before its retirement), still using `Automation/gru_model.py`. Chosen over reusing the stored June constant, so all 8 models come from one snapshot with real runtimes (R10).
- D5. Persistence means "the lake stays the same": predicted volume change = 0, scored on the same walk-forward folds and rows as the champion. Chosen over "same as last week" because it is what a listener means by persistence and is easy to say on stage.
- D6. Numbers flow only through the ledger. `talk.md` and the Q&A sheet use placeholders like `{champion_r2}`, and the builder fills them from `docs/talk/numbers_ledger.json`. The build fails on an unknown or unused placeholder. Chosen over typing numbers in and checking them by test, because a number then cannot drift or be mistyped, and moving the freeze date is a rebuild.
- D7. The ledger is the only persisted format the other parts depend on: a flat JSON of `key → {value, display, unit, source, freeze_date}`, plus one top-level `freeze_date`. Everything about how a number was measured stays hidden inside the freeze script.
- D8. Charts are drawn with matplotlib from the ledger only, never from the raw data, so every plotted value is a ledger value. Their look follows the `dataviz` skill, adapted to the light theme: muted series and one accent colour reserved for the red line and the champion.
- D9. The visual base is light, airy and minimal: a white or near-white background, dark type, generous margins, one object centred per slide, and full-bleed metaphor images. Fonts are 28 pt and up for slide text and 20 pt and up for chart labels.
- D10. Metaphor pictures are AI-generated (Gemini image generation, using the existing gitignored `.env` key). Each prompt is stored beside its image, and the speaker notes say the image is AI-made. If image generation is unavailable on the key, the fallback is free stock photos with credits, so the deck is not blocked.
- D11. The narrated rehearsal uses the /TTL skill's `tts.py` on each slide's notes separately, so each slide's audio length sets its timing (A19). The rehearsal PPTX and its audio stay out of git and out of the submission.
- D12. The talk files live in `docs/talk/`, with the builder beside its content. Follows `docs/paper/md_to_docx.py` beside `Kinneret_Forecast_Methods_Results.md`.

## Files that change
- `tests/test_talk_deck.py` (new): the acceptance tests for every machine-checkable criterion, run against the ledger and the built PPTX/PDF.
- `Automation/talk_freeze_run.py` (new): the freeze re-run of all 8 models with runtimes, the persistence score, the hook's level facts, and the R² history. Writes the ledger.
- `docs/talk/numbers_ledger.json` (new, generated): every number the talk may use, with its source and freeze date.
- `docs/talk/talk.md` (new): the source of truth for slides, on-slide text, the picture or chart per slide, and the speaker notes with placeholders.
- `docs/talk/charts.py` (new): draws the hook level chart, the Olympics R²-vs-runtime chart, the annotated R² timeline, and the 1-week-vs-persistence chart from the ledger.
- `docs/talk/make_images.py` (new): generates the metaphor images from stored prompts.
- `docs/talk/images/` (new): the generated images and their prompts.
- `docs/talk/build_deck.py` (new): talk.md + ledger + charts + images → `talk.pptx`, then `talk.pdf` via PowerPoint, and with `--rehearsal`, `talk_rehearsal.pptx` (narrated, auto-timed).
- `docs/talk/qa_prep.md` (new): the Q&A prep sheet, using ledger placeholders.
- `docs/talk/numbers_check.md` (new, generated): a readable list of every number used and where it appears, for Adnan's review.
- `.gitignore` (changed): ignore `docs/talk/talk_rehearsal.pptx` and `docs/talk/audio/`.

## Order of work
1. Write acceptance tests for A1–A13 (A3 for its term-list half only), A15–A19 and A21–A22 in `tests/test_talk_deck.py`. Run them, confirm each fails because its artefact is missing, lock them, and commit them failing.
2. Build `talk_freeze_run.py` and run it on the default freeze (2026-10-11): 8 models with timed CV, zero-change persistence, level facts, and the R² history from the 7 git snapshots plus the freeze point. The ledger is written.
3. Draw the four charts from the ledger.
4. Draft `talk.md`: the story, slide by slide, in common spoken language, in the spine's order and cut to fit 15 minutes. **Checkpoint: you read the script and the slide list before any images or design work.**
5. Generate the metaphor images, then review the picture-only slides with you.
6. Build `talk.pptx` and `talk.pdf`, and inspect the PDF pages visually.
7. Build the narrated rehearsal, check the total time is 14–16 minutes, and trim talk.md and rebuild until it fits. **Checkpoint: you listen to the rehearsal.**
8. Write `qa_prep.md`.
9. Implement until all locked acceptance tests pass, without editing them.
10. Send the draft deck plus `numbers_check.md` to Adnan by 25 Oct 2026.
11. Apply Adnan's review, rebuild, and send the PPTX and PDF to wateredgeil@mx.kinneret.ac.il by 1 Nov 2026. The send itself is your action, or done with your explicit go-ahead.

## Risks
- **Riskiest step: the story itself (step 4).** Fluency, interest and hook can't be machine-tested. The guard is the script checkpoint before any visual work, the rehearsal listen in step 7, and the outside-listener test (A3).
- The GRU port may not run as it did in June, after code drift since its retirement. The guard: port the CV function from `4f9e553^` as is. If it still fails, stop and ask, rather than quietly using the June constant.
- Zero-change persistence on volume change will likely score an R² below zero. That's correct but needs one plain sentence on stage. The guard: the script explains it, and the Q&A sheet holds the long answer.
- Gemini image generation may not be available on the free key. The guard: the fallback to stock photos in D10.
- The free-tier TTS quota could stall the rehearsal build. The guard: per-slide audio is cached, so a rebuild only re-narrates changed slides.
- Scripting PowerPoint can hang on a modal dialog. The guard: run it hidden, with a timeout, and always quit PowerPoint in a `finally` block.
- The 15-minute fit may force cutting arc segments. The guard: the trim comes out of the rehearsal timing (step 7), and any cut segment is named to you, not dropped silently.
- R² on volume change can be misheard as level R². The guard: the script says "daily volume change" the first time, and the Q&A sheet covers it (A18).

## Proof
- `pytest tests/test_talk_deck.py` covers A1 (arc markers in order, closing slide reuses the hook chart), A2 (rehearsal timing sum is between 14:00 and 16:00), A4 (one object, ≤12 words, font minimums), A5 (≥3 picture-only slides with a metaphor in the notes), A6 (evidence and story slides present, numbers sit on evidence slides), A7 and A22 (banned phrases), A8 (every number in the PPTX, notes and Q&A sheet traces to the ledger), A9 (8 models with R² and runtime in the ledger and in the chart data), A10 (persistence R² and MAE in the ledger, and the margin placeholder used in the script), A3's machine half (every technical term in the script is on the approved list and explained at its first use), A11 (timeline points and cause labels), A12 (red line, freeze level, "lowest since" claim checked against the level file), A13 (pumping plus one other named missing series), A15 (co-author on the title slide), A16 (PPTX and PDF slide counts match), A17 (notes non-empty), A18 (the four required questions in the Q&A sheet), A19 (each slide's timing equals its audio length, rehearsal file gitignored and not in the submission folder) and A21 (the Wade Storm step label and the "AI persona" wording in the script).
- `python Automation/talk_freeze_run.py --freeze 2026-10-11` prints the 8-model table with runtimes and the persistence margin, and writes the ledger. A person can compare it with `docs/olympics_results.json`.
- Manual checks, done by you: A3 (an outside listener retells the story after one listen), A14 (the challenges aren't worded as personal failure), A16 (the PDF looks right page by page), A20 (the two sends, on their dates).
- Seeing it work: open `docs/talk/talk.pdf`, and play `docs/talk/talk_rehearsal.pptx` as a slideshow.
