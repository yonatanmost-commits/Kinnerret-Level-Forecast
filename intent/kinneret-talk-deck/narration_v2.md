# Narration v2: Kinneret talk (working draft)
Written with the originator, 2026-10-14 (session talk-deck-script). Replaces the narration in
docs/talk/talk.md once accepted; numbers are the ledger's (freeze 2026-10-11) and become
placeholders when folded back into talk.md. [DATA Dn] marks a chart or number still to be made.

Throughline: I can only see one week ahead. But I'm not a forecaster: I got there with AI tools
and data anyone can reach. Better measuring, gathering and organising of data is how all of us
will see further, maybe not today, but tomorrow.

Loops: L1 "how far ahead did I get?" (1 -> close) · L2 the amateurs / "not alone" (2, 3 -> close)
· L3 Adnan pushes (3 -> 13) · L4 the 2023 dip (6 -> 7 -> 8 -> 9) · L5 the bucket thrown out
(11 -> 13). Running phrase: "one week".

SPINE v3 (originator, 2026-10-16): slides 1-8 stay; the old 10-13 below (one week, beyond the
week, red line, close) are QUEUED, not deleted; the close may survive. New deep chunk:
- 9 iterating on the data (the click-by-click slide becomes the entry point): first model ->
  the "expert" trick catches the 2023 rain sensor read as zero (the price of not seeing all the
  data with your own eyes; credit to the machine for noticing) -> Open-Meteo vs IMS: quality
  beats quantity.
- 10 the model olympics (running alongside the data work): let's use AI; the GRU fails, CfC wins.
- 11 the lake becomes a neuron: the dripping bucket; the maths "the way you'd explain it to your mother".
- 12 credit: MIT (Rus lab, Hasani, Lechner; Grosu TU Wien), the worm, Liquid AI, "worth
  following" (NO "going public" tip). Credits from memory: VERIFY before slides.
- 13 testing it now: a streak of results, marked as early (runs continue through the weekend).
- 14 takeaways: non-programmers + AI build datasets and compare methods -> a shared collection
  of data -> better forecasts, so decision makers have more room to decide well (calm; echoes
  slide 1's "room"; not "lead us to safety").
- 15 close: maybe stays.
Held for the results: what answers slide 1's "how far ahead I could see" now that "one week"
no longer carries the spine. Held: length (15 slides; 6-8 likely tighten).

Status: slides 1-5 agreed in chat; 6 to the close is draft v2 (storytelling pass).
Parked: slide-6 order (the record: race -> Wade Storm -> 2023 fix), on-screen text
(centaur = "Centaur"), length (target about 1,800 words).

## 1. lake-years video -> "put it in context" (agreed 2026-10-16 v3 for now; next pass once slides exist)
In my first year here at Kinneret, the lake was so low that I walked all the way out to the island in front of the campus.
By the time I graduated, the waves were flooding the Tiberias promenade, taking their toll on the wooden market stands. Today, those stands stand high above the water once again.
The lake's ups and downs aren't new. But today it sits below the red line, and it is our national backup.
So which winter is coming? One like twenty eighteen to nineteen, the best of the last twenty, that lifted the lake back up? Or one like twenty twenty-four to twenty-five, the worst, that kept it falling?
Nobody knows. Certainly not me. I'm not a forecaster. I scraped data together and ran models on an old computer that kept running out of memory.
But that's exactly the point. If I could get any results this way, imagine what our best efforts could do.
And it matters right now. This autumn, algae bloomed off our southern coast and choked the desalination plants. Keeping the water flowing meant hard choices. How hard depends on that same question: can the lake carry us next year? With better forecasts, we'd know how much room we have. It deserves our best.
So I'll show you how I got here: what worked, what didn't. Maybe something in it will be useful to you. And by the end, I'll tell you honestly how far ahead I could see.

Design note for the designer (the originator's idea, 2026-10-16): ONE continuous slide, no cut, "put it in context".
- "which winter is coming?": the two lake images merge into one lake with TWO water lines (best-year and worst-year level).
- "Nobody knows ... best efforts": hold on the two lines.
- "And it matters right now.": zoom out, the lake shrinks into its place on the map of Israel.
- "algae bloomed off our southern coast": the Mediterranean appears. No plants, names or algae marked.
- "can the lake carry us next year?": lake and sea on screen together.
SENSITIVE (originator): no cause of the bloom, no chemical or "poison" words, no plant or authority names; the decision-makers may be in the room. Facts to rest on a public source before the talk.

## 2. centaur (agreed; on screen: "Centaur")
First, a picture. This is a centaur: half human, half horse.
After Garry Kasparov lost to a chess computer, he started asking a different question: what happens when a human and a computer play as one team? Chess players call those teams centaurs.
In two thousand and five there was an open freestyle chess tournament on the internet. Anyone could enter, with any computer help they liked. The winners were not grandmasters, and not the strongest machine. They were two amateur players from the United States, running three ordinary computers, with a very good way of working together with them. The process beat the raw strength.
Keep those two amateurs in mind. Because the person standing in front of you is one too.

## 3. app front (agreed 2026-10-14 v4; QR code moves to the close)
I'm a process engineer: I design wastewater treatment plants for TTT, of the WFI Group. And I owe this talk to my co-author, Adnan Agbaria, my lecturer in a data science course during my master's in water engineering, here at Kinneret.
He gave us an open data analysis task: pick a subject, gather the data, analyse it. I said: I want to build a machine learning model that forecasts the Kinneret's level, from weather data I pull off the internet.
I know what you're thinking. That's a big task. It is. I said so myself, two slides ago. But I decided to play with it. If the weather tells me the rain, how hard can it be to guess one week ahead? So I took it on.
This is what came out of it. An app. The lake's history and statistics, the model, and the best part: you can play. Pull this week's forecast from the Meteorological Service, and see where the lake is going. Or go back to any week since 2012, and see how the model would have done. You'll get the link at the end. Please don't open it now.

## 4. the pipeline (agreed 2026-10-14 v2; the whole system in one picture, sources stay general)
Here's the whole system, in one picture. A daily loop, running on my own computer.
Every morning it pulls three sources: the lake's level, the Jordan River's flow, and the weather, both the weather that was and the forecast for the week ahead.
It cleans them, lines them up in one table, one row per day, and calculates a few extra features to help the model learn.
Then the model works in two steps, the way the water does. First the river: how much water flows in, day by day. Then the lake: how much its volume changes. And finally the lake's own shape, its bathymetric curve, turns volume into level.

## 5. gather (agreed 2026-10-14 v2; speaker's point of view, no apology; Baptism Site -> Q&A)
Step one: gather the data. And the data doesn't come in one place. Weather stations change names over the years, and sometimes their numbers. Every source has its own format, its own gaps, its own story. It's a dark forest. I settled on one station: Lev Kinneret, the heart of the Kinneret.
AI is the flashlight. I pointed Claude at a website and said: find the API key. Minutes later, I had any weather station I wanted. The rivers were harder: two months of emails, always "you can't get that data." Then Claude found a Facebook post with a link to a beta site, wrote a scraper for it, and the river data has come in every day since.
The rivers go back fifty years. My weather goes back to 2012. So that's where my table starts. The weakest link in this system isn't the model. It's the data. And that's exactly where the biggest potential is.
(Measured 2026-10-14: Obstacle Bridge from 1970-10, Sede Nehemya 1969-10; weather downloads from 2012-06 (Tzemach, Beit Tzaida, Kfar Nachum); Baptism Site 2012-07; Lev Kinneret 2012-11 (multi-station mean before); gold table 2012-09. Never say the history could not go further back: Tzemach exists from 1994.)

## 6. organise (agreed 2026-10-14 for now; bronze/silver; plants the dash)
Step two: organise. Every source arrives in its own shape. The weather comes every ten minutes, all the stations stacked one under the other in a long table. The rivers come once a day, a column per station, in a wide one. The lake level, back in 1970, was read about once a week. And all of it is dirty: gaps, dashes, sensors that die.
Here's the trick: don't worry about the shape of the data you have. Decide the shape you need. Mine is simple: one row per day, from 2012, and one column per parameter.
Data people have names for this. Bronze is the raw files, as they arrive. Silver is that clean table. I asked Claude to take a hard look at the data and suggest how to clean it. It came back with tactics I would never have thought of. (beat) But there's a catch hiding in there. We'll find it soon.
(Measured 2026-10-14: weather 10-minute readings, long format before pivot; level ~50 readings in 1970, daily by 2012; river flow daily, one column per station.)

## 7. enrich (agreed 2026-10-14; gold; rain intensity held back for the better-data payoff)
Step three: enrich. Start from the end. What do I want to know? The lake's level. But a lake doesn't think in levels. (pause) It thinks in volume: water in, water out. So I forecast the change in volume, and the lake's shape, its bathymetric curve, turns that into level.
Now think like the lake. Water comes in with rain: yesterday's, two days ago, the whole last week. Water comes in with the river, and the river itself reacts to the rain. That's a chain. And water goes out: evaporation, on a hot day, with thirsty air.
None of that sits in my table yet. So I thought it through, asked Claude and Gemini what else might help, and calculated it from my own data: rain over the past days, evaporation, how dry the air is, the river yesterday and the day before. Every idea becomes one more column. That's gold: the table the model learns from.
(Q&A: the bathymetric curve file is in Raw Data/Kinneret_Level, source not recorded.)

## 8. the benchmark (agreed 2026-10-14; photo: F-55 at Jaffa port, Baruch Niv, CC BY-SA 4.0, Wikimedia Commons, B&W)
Can anyone tell me what this is? (wait)
It's at Jaffa port. In the early 1920s, British surveyors marked a point here, and from it they measured the height of the whole country. Every height you've ever heard in Israel, including the Kinneret's minus 213, is measured from this point.
And here's the part I find irritatingly fascinating: the sea didn't stay put. Today, Israel's average sea level sits about eight centimetres above that zero.
Why did they need a benchmark at all? Because if you only measure from one point to the next, you drift a little with every measurement. That's error propagation. And it was my biggest question in building the model.
Do I forecast day by day, each day off the last day's forecast, and let the errors build up? Or forecast the whole week from today, with today's true level as my benchmark, and risk bigger misses the further out I go?
I did both, where each one fits. The river I forecast one day at a time: each day starts from the river the day before, plus that day's weather forecast. The lake always starts from the benchmark: every day of the week, the change in volume is measured straight from today's real volume.
Once the method was right, training was the easy part. You let the model forecast the past, and learn from its own mistakes.
(Sources: British BN/223 nail, early 1920s, re-established 1985 as F-55, restored 2016 and named for Aviel Ron (mytelaviv.co.il; he.wikipedia Jaffa port). MSL 0.082 m above the 1995 Israeli datum, 1956-2016 data: J. Geodesy 2020, doi 10.1007/s00190-020-01430-3. Dates vary 1920/1922: say "early 1920s". Q&A: Aviel Ron dedication; sea rose 1920s, fell 1960s-90s, rose fast from the 1990s.)

## 9. the scoreboard (agreed 2026-10-14 v2; ONE chart built click by click, an object appears/disappears per attempt; replaces race, neural network, dash, better data)
[0: empty chart, 0 to 1] Here's how I scored every attempt. Zero: no better than guessing the average. One: perfect.
[1: 0.69, first model] My first model was a random forest. Claude wrote it from scratch. Then gradient boosting, in two steps, the way the water flows. 0.69.
[2: 0.67 grey, chain icon] Remember the benchmark? I tested it. Forecast the lake day by day, each day off the last guess: 0.67. The benchmark wins.
[3: 0.65 grey, XGBoost] XGBoost, the one Google told me to use. 0.65. It lost.
[4: below zero grey, stopwatch 71 min] A neural network. Seventy-one minutes of training, and worse than guessing. The plain model took four.
[5a: a dash turning into 0 — FOCUS, the biggest step] Then the biggest step of all, and it wasn't a model. Remember when I let Claude clean the data, and said there was a catch? Here it is. A rain gauge on the lake was offline for a whole year. Every missing reading was a dash. And the cleaning turned every dash into a zero. A whole winter of rain, gone. No error. No crash. I didn't know exactly what the cleaning did, so I didn't see it. Who did? I asked Claude to play an expert hydrologist and review my models. The newest oldest trick in the book. It noticed that every model stumbled in the same year, and said: when every model fails the same way, it's the data.
[5b: flood photo, line jumps to 0.76 green] Fixed, and five hundred millimetres of rain came back. Together with a few more ideas, like this one: two percent of the days, the floods, caused more than half the error. 0.69 to 0.76, in two days.
[6: 0.763 grey, 30-day calendar] Thirty days of rain, to remember wet soil. Almost nothing.
[7: 0.77 green, dead sensor] A sunlight sensor died. I swapped in another source, and the model got better: 0.77.
[8: 0.76 grey, bucket] A soil-moisture bucket, great for long range. For one week, worse. Out.
[end: the whole line, plus today's point at 0.76] From 0.69 to 0.77, in June. Today, on cleaner data: 0.76. Not a bigger model. Better data.
(All scoreboard numbers are ONE-DAY-AHEAD CV scores (run_cv). June 0.771 not reproducible: re-run 2026-10-14 on today's gold cut at 2026-06-01 = 0.762 (folds .676/.875/.673/.823), same as freeze day_ahead 0.76; gap = Aug QC fix (3796 nulls) + data corrections; June gold never committed.)
(Measured 2026-10-14 from git history of docs/olympics_results.json and commit messages: first two-stage GBR 0.689 (spec, by 23 May; first model a numpy-only random forest, model_lib RFRegressor); race 30 May baseline 0.694, full chain 0.670, XGBoost 0.646, LightGBM 0.641, GRU -0.025; 2023 rain 0 -> ~505 mm, '-' sentinel coerced to 0 (9d7c25f, 4cb15d2); rain fix + six findings measured TOGETHER 0.694 -> 0.758 (ac2ede5, 30-31 May; flood days 2.4% = 58% of variance) - one point, not two; 30/45-day rain 0.763 (56d0555); radiation via Open-Meteo 0.771 (2da9bd7); bucket back-port 0.760 rejected; GRU 71 min / champion 4 min: ledger, freeze. Cloud QC accident (Aug) left out by the originator.)

## 10. one week (agreed 2026-10-14; chart: one real week, forecast against the lake)
So, one week. This is a real one: what the model said on the first day, and what the lake did.
That 0.76 is one day ahead. Across the whole week: 0.73. "The lake stays the same" scores zero. I set out for one week, and the week holds.

## 11. beyond the week (v3; chart: skill fading with lead time)
Adnan wanted more. A season. I told him I didn't have the data. I tried anyway: the long-range forecast, temperature alone, climate models. Shots in the dark, and mostly misses. Past a few weeks, everything waits for the rain, and rain here is one of the hardest forecasts there is.

## 12. the red line (v3; chart: one summer replayed)
But one shot hit. In summer there's no rain to guess, only a lake drying in the sun. So: when will it cross the red line? A month ahead, a simple drying curve named the day within about two days. On every crossing since twenty oh eight.

## 13. close (v3; the lake video's last frame)
So what stopped me from seeing further? Not the model. A river station that went silent. A dash in a file. And the water pumped out of the lake, which my model never sees.
Each of those is a link in one chain: measuring, gathering, cleaning, sharing. Every link is in someone's hands, many of them in this room. And the tools I used are in everyone's hands now.
So, which winter is coming? I promised to tell you honestly how far ahead I got. One week. A month, in summer. Next winter, I can't see. Not today, and not alone.
But an amateur with a laptop got this far. Imagine what all of us could see, together. Maybe not today. Maybe tomorrow.
Thank you.

## Data calls (for the builder; every one measured on the freeze or dated)
- the scoreboard: one line from 0.689 to 0.771 over time (May-Jun 2026, dated), each attempt a dot: green helped (2023 rain fix + six findings, radiation restore), grey didn't (XGBoost 0.646, neural network -0.025 / 71 min, 30-45 day rain +0.005, soil bucket 0.760). Source: git history of docs/olympics_results.json.
- FACT CORRECTION (2026-10-14, measured in code): the champion DOES use the Baptism Site. outflow_lag1_m3 = outflow_baptism_m3.shift(1) is in S2_DIRECT_FEATURES (model_lib.py:136, 08_train:133), added by Finding 2 (ac2ede5), which misdescribed it as National Water Carrier pumping. Spec R14/line 114 and the Q&A answer "the champion never uses it" are wrong.
- one real week: forecast issued on day one against the lake, the week picked by a stated rule (not cherry-picked).
- skill fading with lead time: one line, from the long-range evaluation.
- one summer replayed: a month ahead, predicted crossing date against the real one (most recent crossing).
