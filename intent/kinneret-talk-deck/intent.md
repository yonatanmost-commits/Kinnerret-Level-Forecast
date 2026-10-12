# Intent: Kinneret Conference talk deck
Author: Yonatan Most (process engineer, master's student). Date: 2026-10-12.
Source: idea, the "Kinneret Talk — Spine (draft v1)" written by the originator; talk accepted at the 12th Kinneret Conference for Water (acceptance mail forwarded by Adnan Agbaria, 2026-10-08).

## Problem
I present at the 12th Kinneret Conference for Water on 11 Nov 2026, in the session "Digital Infrastructure and AI Applications". The talk is in English, and the slot is 15–20 minutes including Q&A. I have a spine (draft v1) but no deck, script or rehearsal yet.

Adnan gets the slides for review by 25 Oct 2026 at the latest, a week before the organisers' deadline. The organisers need the slides as PowerPoint or PDF by 1 Nov 2026. Late slides may be left out of the program.

The audience mixes science, industry and technical people from the water sector. It is not a purely research crowd.

The message I want to land: the AI opportunity here is not AI as the predictor. It is AI as the partner that lets non-specialists build clean data foundations, and better data is what unlocks better forecasting.

The numbers I'd put on slides are stale. The training data changed on 2026-08-15, when a skipped QC filter was restored, and the champion R² has already drifted from 0.771 to 0.751. That drift could itself be interesting to show: R² over time, and how much it fluctuates.

The biggest risk is that the talk reads as AI hype, and the technical listeners dismiss it.

## Proposed outcome
Practitioners leave believing that a non-specialist can build clean data pipelines with AI, and that data, not the model, is the bottleneck.

The talk runs about 15 minutes, leaving time for Q&A inside the slot.

The talk follows the spine's arc: the red-line hook, who I am, the soft drop (Model Olympics), the pivot, the data story, the 1-week results, the long-term wall, and the close.

Every number on a slide comes from a re-run on a fixed, dated data freeze.

The slides are delivered as PPTX and PDF and, after Adnan's review, sent to the organisers by 1 Nov 2026.

The deck comes with per-slide speaker notes, a script timed to about 15 minutes.

The deck comes with a Q&A prep sheet: the likely hard questions, with prepared answers.

There is a narrated, auto-timed PPTX: the script read aloud by TTS over a timed slideshow. It is my private rehearsal aid and is not submitted. The narration uses the /TTL skill, whose API key lives in `.env`, which stays gitignored.

Adnan Agbaria is credited as co-author and reviews the draft before submission.

## Affected users and systems
- Me, the presenter.
- Adnan Agbaria, co-author and reviewer.
- The conference organisers (wateredgeil@mx.kinneret.ac.il), who receive the slides.
- The session audience.
- The project's data and models: the level series, the Model Olympics results, the champion GBR, and the long-range evaluation.

## Constraints
- The slides reach the organisers as PPTX or PDF by 1 Nov 2026.
- The talk runs about 15 minutes, within a 15–20 minute slot that includes Q&A.
- The talk is in English.
- No number appears on a slide unless it was re-measured on the stated data freeze date.
- The deck says "deep learning vs. classic ML", never "AI vs. ML".
- The "worst in a decade" level claim is checked against current data before it appears on a slide.
- Adnan is named on the title slide and sees the draft before submission.
- The slides use my own clean, chart-led style, readable in a hall. No template or branding is imposed.
- The talk is free to depart from the accepted abstract.
- The data freeze date for all re-measured numbers is 2026-10-11.
- Adnan receives the slides for review by 25 Oct 2026 at the latest.
- Storytelling is the number one concern. The talk must be fluent and interesting, hook the listener, be easy to follow, use common language, be light on the ear and calm on the eye.
- The deck holds a healthy tension, data-driven on one side and storytelling on the other: the charts earn credibility, and the pictures and metaphors carry the story.
- Some slides are a single picture with no text, carrying a metaphor to talk about (the master's technique).
- All slides are super light on text, with large fonts.
- Each slide has a single object to look at: a picture, a graph or, occasionally, a table (the least preferred). Listeners focus on the talk, not on reading the slide.

## Out of scope
- New modelling work: no new models or horizons. Existing results are only re-measured on the freeze.
- A Hebrew version.
- Changes to the publication paper.
- Conference logistics, such as confirming the 10 Nov reception.

## Open questions
These are all to be answered by self-research in the repo, memories and data before the plan, not put to me.

- Model Olympics: which models, and what R² and runtime for each, at 1 week and at longer horizons?
- At 1 week, by how much does gradient boosting beat the persistence baseline?
- Which longer horizons were tried, and how did they fail?
- Which data sources and APIs were used, and what does each medallion layer (Bronze, Silver, Gold) do?
- Which data was missing or inaccessible (inflows, upstream usage, pumping, rainfall forecasts)?
- What are the 2–3 most transferable challenges, each with a "this applies to you" line?
- What is the current Kinneret level against the red line, and what is the multi-year source for the hook graph?
- Are backup or appendix slides for Q&A wanted, or does the prep sheet cover Q&A?
- Which arc segments get trimmed to fit 15 minutes instead of 18?
