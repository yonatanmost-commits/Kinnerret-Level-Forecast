# Spec: Kinneret Conference talk deck
From: intent/kinneret-talk-deck/intent.md v1.

## Behaviour
- R1. The talk tells one story along the spine's arc: the red-line hook, who I am, the soft drop (Model Olympics), the pivot, the data story, the 1-week results, the long-term wall, and the close that returns to the hook.
- R2. Spoken at a calm pace, the talk runs about 15 minutes, leaving at least 3 minutes of the 20-minute slot for Q&A.
- R3. The language is common and spoken. No unexplained jargon reaches the audience. Any technical term that stays (R², persistence, gradient boosting) is explained in plain words the first time it is used.
- R4. Every slide has exactly one object to look at: a picture, a graph or, occasionally, a table.
- R5. Some slides are a single picture with no text, carrying a metaphor the speaker talks about.
- R6. Slides are super light on text, set in large fonts readable from the back of a hall.
- R7. The deck holds a data-driven storytelling tension: "a data-driven, truthful tale, told by a master storyteller". Every claim is true to the data, and the telling is a story, not a report.
- R8. The deck says "neural network vs. classic ML", never "AI vs. ML", and not "deep learning", which is less familiar to this audience.
- R9. Every number shown or spoken is re-measured on one data freeze, with a single stated date used for all numbers, and traces to a stored result from that run. The date is flexible: 2026-10-11 is the default, and it may move when that is convenient (for example, to reuse a run that already exists), as long as everything moves together.
- R10. All 8 Model Olympics configurations are run on the same freeze, with each model's training runtime measured. The Olympics slide shows R² against runtime.
- R11. At the 1-week horizon, the champion is compared against a persistence baseline scored under the same walk-forward CV. The talk states the margin.
- R12. One slide shows the champion's R² over time as an annotated timeline. Each step is labelled with its cause (model change or data change).
- R22. The talk tells the Dr. Wade Storm episode as evidence for the pivot, under the name "the newest oldest trick in the book": telling the AI "you are an X specialist…". An AI expert persona (Claude in the role of a hydrology and meteorology specialist) read the model's residuals and proposed the "Signal Harvest" fixes, which raised the champion's R² from 0.694 to 0.758. The persona is presented honestly as AI role-play, and the fixes as validated by measurement, not by the persona's authority.
- R13. The hook shows the multi-year level record with the red line and the level on the freeze date. Any "worst in N years" claim matches the data.
- R14. The close names the specific data that was missing or inaccessible.
- R15. The long-term wall is framed as "here's what's missing", not "here's where I failed". It carries 2–3 transferable challenges, each with a "this applies to you" line.
- R16. The title slide names Adnan Agbaria as co-author.
- R17. The deck exists as PPTX and as PDF, with the same content in both.
- R18. Every slide carries speaker notes, and together the notes form the full spoken script.
- R19. A Q&A prep sheet lists the likely hard questions, each with a prepared answer that matches the freeze numbers.
- R20. A narrated rehearsal PPTX plays the script as TTS audio (via /TTL) on auto-timed slides. Each slide's timing matches its narration, and it is kept private.
- R21. Adnan receives the draft by 25 Oct 2026 at the latest. After his review, the slides go to the organisers by 1 Nov 2026.

## Acceptance criteria
- A1 (R1). Given the speaker notes, when the slides are read in order, then every arc segment appears in spine order, and the last slide shows the hook's graph again.
- A2 (R2, R20). Given the narrated rehearsal PPTX, when its total auto-timing is summed, then it is between 14:00 and 16:00.
- A3 (R3). Given the script, when it is scanned for technical terms, then each one is either in an approved list explained at first use or absent. A listener outside data science (a reviewer the user picks) can retell the story in three sentences after one listen to the narrated run.
- A4 (R4, R6). Given each slide, when it is inspected, then it holds exactly one picture, graph or table, has at most 12 words of on-slide text (excluding chart axis labels), and uses no font smaller than 28 pt for slide text or 20 pt for chart labels.
- A5 (R5). Given the deck, when slides are counted, then at least 3 are picture-only, with no text, and each has a metaphor written in its speaker notes.
- A6 (R7). Given the deck, when slides are classified, then both evidence slides (charts or tables) and story slides (pictures) are present, and every number in the script sits on or next to an evidence slide.
- A7 (R8). Given the slides and script, when they are searched for "AI vs. ML", "AI versus machine learning" or an equivalent, then there are no hits.
- A22 (R8). Given the slides and script, when they are searched for "deep learning", then there are no hits outside the Q&A sheet, and the Olympics slide labels the GRU as a "neural network".
- A8 (R9). Given every number in the slides, notes and Q&A sheet, when each is looked up, then it maps to a stored result produced from the one stated freeze, recorded in a numbers ledger with its source and the freeze date.
- A9 (R10). Given the freeze re-run, when it completes, then all 8 configurations have an R² (mean and per fold) and a measured runtime, and the Olympics chart plots exactly those values.
- A10 (R11). Given the freeze data, when persistence is scored under the champion's walk-forward CV, then its R² and MAE are recorded, and the slide or script states the champion-minus-persistence margin from them.
- A11 (R12). Given the R² history (the 7 git snapshots plus the freeze run), when the timeline is drawn, then every point is plotted at its date and value, and every step carries a cause label.
- A21 (R22, R12). Given the R² timeline, when the 0.694 → 0.758 step is shown, then it is labelled as the Wade Storm / Signal Harvest step. The script names at least one of the six fixes in plain words (for example, "it noticed the lake's outflow was being ignored"), says Wade Storm is an AI persona, and gives the measured gain. Both numbers are re-checked against the freeze or labelled with their original date.
- A12 (R13). Given the level record through the freeze date, when the hook is drawn, then it shows the red line at −213.0 m and the freeze-date level. Any "lowest in N years" claim is true for that calendar date. At 2026-10-11 the level is −213.655 m, which supports "lowest since 2018" and refutes "worst in a decade".
- A13 (R14). Given the close slide's script, when it is read, then it names at least pumping/abstraction data and one other specific missing series.
- A14 (R15). Given the long-term wall section, when it is read, then it has 2–3 challenges, each followed by a "this applies to you" line, and none is worded as a personal failure.
- A15 (R16). Given the title slide, when it is inspected, then it shows Adnan Agbaria as co-author.
- A16 (R17). Given the PPTX and the PDF, when they are compared, then they have the same slide count and slide order, and the PDF renders every chart and font correctly.
- A17 (R18). Given each slide, when its notes are opened, then they are non-empty, and the notes in order read as one continuous script.
- A18 (R19). Given the Q&A sheet, when it is read, then it covers at least: "why not an LSTM / deep learning?", "is R² on level or on volume?", "how do you handle pumping?", and "how far ahead can you actually see?". Every number in it is in the numbers ledger.
- A19 (R20). Given the rehearsal PPTX, when it plays, then each slide advances when its narration ends. The file is not in the submission email, and the TTS key stays in the gitignored `.env`.
- A20 (R21). Given the calendar, when 25 Oct 2026 ends, then the draft has been sent to Adnan. When 1 Nov 2026 ends, then the reviewed PPTX/PDF has been sent to wateredgeil@mx.kinneret.ac.il.

## Out of scope
- New modelling work. The freeze re-run and the persistence scoring are measurements of existing models and a standard baseline, not new models or horizons.
- A Hebrew version.
- Changes to the publication paper (the freeze numbers may later feed it, but not in this lane).
- Conference logistics, such as confirming the 10 Nov reception.
- Backup or appendix slides. The Q&A prep sheet covers Q&A. (Recommended answer to the intent's open question, for review.)

## Concerns
- The re-run and the persistence scoring sit right at the edge of "no new modelling work". I read them as measurement, not modelling. Reject this point if you see it differently.
- The champion retrains daily, so the working-tree `docs/olympics_results.json` (R² 0.762, retrained 2026-10-12, uncommitted) keeps moving. Since the date is flexible, the plan can either pin a dated run like that one or re-run all 8 models on one cut. Mixing runs from different dates is the one thing to avoid.
- The R² timeline mixes three kinds of change: model improvements (0.694 → 0.771, May–June), a stale-data reading (0.751), and the QC fix (0.764). Without labels it reads as instability, so its labels must be right.
- The Wade Storm gain (0.694 → 0.758) is historical. It was measured on 2026-05-31, and the 0.694 baseline was partly scored on corrupted 2023 rainfall data. It can't be re-measured on the freeze without rebuilding the pre-fix pipeline, so it conflicts with R9 unless it's labelled with its date. I recommend treating it as a dated historical step on the timeline (as A21 allows) rather than reconstructing it.
- The GRU was retired from the training pipeline on 2026-06-01 (about 15 min per run on CPU). Its stored result is a frozen historical constant. Re-running it on the freeze (R10) means reviving the retired code path. The alternative is keeping its June result, labelled with its date. Both keep the punchline (R² ≈ 0).
- R² is on daily volume change, not level. Stated loosely, technical listeners will ask about it (see A18).
- The 47 mm summer-recession result comes from a climatology method, not ML. If it's used in the long-term wall, it must be attributed that way.
- The 15-minute budget is tight for 8 segments. Trimming from the spine's 18 minutes is a design choice for the plan.

## Open questions
- Intent: which data freeze date? Answered: 2026-10-11 by default, and flexible as needed (originator). The plan fixes the final date, and all numbers share it.
- Intent: Model Olympics models, R² and runtime? Answered in part: 8 configurations; R² from June/Oct runs exists (champion 0.762 today, GRU −0.026). Runtimes were never recorded and get measured on the freeze run (R10).
- Intent: gradient boosting vs persistence at 1 week? Never measured for the 7-day model (persistence appears only in the red-line back-test). Resolved by R11 on the freeze run.
- Intent: longer horizons and how they failed? Answered: 14–30 days, temperature only, has no year-round skill (dry season −1.23 vs climatology). The soil-moisture bucket lifts the wet season to about +0.35, a perfect-temperature upper bound. The summer red-line recession is skilful at 30 days (47 mm) but loses to plain climatology at 60–90 days. Source: paper §4.3–4.5.
- Intent: data sources and medallion layers? Answered: Water Authority level (1966–), Hydrological Service river flow (1969–), IMS meteorology with Open-Meteo fallback, and ERA5 reanalysis (1960–). Bronze = `Raw Data/`, Silver = `Silver Data/` (cleaned, daily-synchronised), Gold = `Gold Data/kinneret_gold_features.csv` (the fused model table, 2012–). Source: paper §2.
- Intent: missing or inaccessible data? Answered: no pumping, consumption or abstraction series at all. Also a 332-day outflow-station gap (Baptism Site 46105 → 316), a river-flow station gap (Obstacle Bridge, April 2026), a dead lake radiation sensor (25 Apr 2026), and dependence on third-party forecast APIs.
- Intent: 2–3 transferable challenges? Proposed for review: (1) bad data hides silently: a "-" sentinel corrupted inflow through a four-link chain, so you fix it at the source; (2) sensors and stations die: a retired station and a dead radiation sensor, so you build fallbacks; (3) the data you most need is often someone else's: pumping, so you share it. Resolved in the script, reviewed by the originator.
- Intent: current level vs red line, and the hook source? Answered: −213.655 m on 2026-10-11, 0.66 m below the −213.0 red line. The source is `Silver Data/Kinneret Level/kinneret_level.csv` (1966-09-01 → 2026-10-11).
- Intent: backup slides? Answered by recommendation: none, the Q&A sheet covers it (see Out of scope).
- Intent: which arc segments get trimmed to fit 15 minutes? Carried to the plan, which sets a per-segment time budget checked by A2.
- New: who is the outside listener for A3? Resolvable by the originator before rehearsal.
