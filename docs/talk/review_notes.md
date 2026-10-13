# Review notes: Kinneret Conference talk deck
<!-- Claude's two review passes after each full build (plan D13): the style checklist (A8) and
     the claims-against-evidence read (A18). One line per finding: open, fixed, or overruled by
     the originator. Review notes, not tests: they never block a build. -->

## Build 1: 2026-10-13, 22 slides (talk.md at cb51760 + the fix below)

Build warnings (A9): the PPTX and PDF both have 22 slides in the same order. Georgia and Segoe UI
are embedded, and every chart and picture slide carries an image. Twelve pictures are not made yet,
so those slides show a labelled placeholder. None of the 22 slides is accepted yet (A12).

### Style checklist (A8)

| # | Item | Status | Finding |
|---|---|---|---|
| 1 | Arc in R1's ten beats, last slide shows the hook graph | holds | D20's 22 slides in order; the close is chart:hook with the QR. |
| 2 | One object per slide | holds | |
| 3 | At most 12 words of slide text | holds | The builder warns above 12; no warning. |
| 4 | 28 pt and up for slide text, 20 pt and up in charts | holds | Slide text 28-48 pt; chart labels 20 pt at full slide width. |
| 5 | At least 3 picture-only slides, each with its metaphor in the notes | open | 12 of the 13 metaphor pictures are not made yet (prompts ready). The notes name the metaphor on the centaur, persona (the chef), lesson and push slides. On week, sources, model, rain, silent, sensors, share and brain the picture is not mentioned in the notes. Fine if the picture speaks for itself; decide in the walk-through. |
| 6 | Technical terms explained at first use | fixed | R squared (olympics) and gradient boosting (model) are explained. "Agentic flow" (lesson) is now explained: "letting the AI run the work step after step on its own" (planner review of 142708e). "GRU" appears on the Olympics chart next to "Neural network"; it is never spoken. |
| 7 | No "AI vs. ML", no "deep learning" | holds | |
| 8 | Wade Storm: AI persona, the 2023 warning, the missing year of rain, one fix in plain words, the combined gain with its date | holds | The fix in plain words ("how hard it rained") and the gain are on the timeline slide. The dates come from the ledger displays ("0.694 (May 2026)" style). |
| 9 | Human consumption named as the most critical missing data, with no trend claim | holds | On the share slide, not the close. R37 now puts the close on the takeaways and the scale line. |
| 10 | River-record limits and the Baptism Site, told honestly | holds | Sensors slide, with the R14 wording (fixed at cb51760). |
| 11 | Three challenges, each with a "this applies to you" line | fixed | Silent and sensors have the line. Share ends on "my first takeaway" instead (D20 makes share double as takeaway one). Share now has its own line: "if you hold data like this, share it". |
| 12 | Title names Adnan; no introduction before the year-over-year slide; QR on who and close | holds | |
| 13 | No level number on any slide | ruled: allowed | The hook chart's y-axis shows level ticks (-209 to -213 m) and the red-line label. Today's level is never printed, which is R13's point. Planner ruling: the axis ticks are allowed. R13 bars today's level because it goes stale; scale ticks don't. The originator can overrule. |
| 14 | The freeze date named where the data begins | holds | Olympics notes, the first measured number. |
| 15 | Chart slides | note | The chart's own headline is the slide's point, so the builder does not draw the `text:` line on chart slides (hook, olympics, one_day, timeline, one_week, frontier, close). Ruled: chart slides keep their headlines. The close draws the hook's graph under the headline "Better data, not bigger models" (chart:close), with the QR moved to the empty top-right corner. |

### Claims against evidence (A18)

| # | Slide | Claim | Status | Evidence / finding |
|---|---|---|---|---|
| 1 | persona | "every model scored worst in 2023" | fixed | At the first snapshot (c3a72b3, 30 May 2026), 7 of 8 models had their worst fold in 2023. The neural network was worst in 2021, at about zero every year. Now reads "every model that learned anything". |
| 2 | olympics | "Every run, however I tweaked the data, it came back on top" | holds | baseline_gbr is the winner in all 7 committed Olympics files (c3a72b3 to 6b27d62) and on the freeze's weekly ruler (0.733 against 0.707). |
| 3 | week | "a weather forecast is good for about a week" | ruled | Kept as the speaker's reasoning, with no citation on the slide. The Q&A sheet answers "why one week?" and says it is reasoning, not a measurement. |
| 4 | week | "seven steps of one day, each built on the one before" | holds | The weekly champion is run_cv's models chained through _simulate_7d_chain (D19). |
| 5 | timeline | "Most of the movement came from data, not from the model" | fixed | The claim is dropped. The Wade Storm step is mixed: the rain fix is data, and the six fixes are mostly model-side (target transform, GBR parameters, features). Its point now has a half-and-half "both" dot (ledger cause_mix). The chart is retitled "What moved the score", and the notes say it was the biggest step, both data and model, and that later moves were small and mostly data. |
| 6 | one_week | the app line | holds | It says the forecast is in the app, not that the app runs the champion (the app runs Stage 1 plus a direct Stage 2; see the Q&A sheet). |
| 7 | push | the long-range attempts | holds | Only the attempts recorded in D20 are named, as "the sun's radiation above the atmosphere"; 1960 has a source on the allow line. |
| 8 | silent | "A single dash in a weather file became a zero" | holds | The IMS "-" sentinel, the first of the four bugs fixed on 2026-05-30. |
| 9 | who, sources, pipeline, model | the first-pipeline story, "hours, not weeks", XGBoost then gradient boosting | holds | The originator's own account (2026-10-13). There is no record in the repo, and none is needed for a personal story. |
| 10 | hook | the two winters | holds | A20 locked test. |
| 11 | hook | "The red one is this year" | fixed | The chart draws this year in teal. The notes now say "The teal one". |
| 12 | olympics | chart headline "The neural network learned nothing" | fixed | An R² near zero on test data doesn't prove it learned nothing. The headline now reads "did no better than average". |
