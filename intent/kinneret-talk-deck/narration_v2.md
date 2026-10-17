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
(2026-10-16: the line "So I'll show you how I got here ..." moved to the end of the NEW slide 2, the field; slide 1 now ends on "It deserves our best.")

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

## SPINE v3 DRAFT: slides 9-13 (proposed by talk-deck-script 2026-10-16, NOT yet reviewed by the originator)
Mother test: every line in plain words. [WAITS x] = a run the CfC tournament session is doing (it messages talk-deck-script as each lands).

### 9. feeding it better (scoreboard line, May-Oct, data dots blue, click by click)
The first model I trained was already decent. But a model is only as good as what you feed it.
So I tried an old trick: I asked the AI to play an expert, a seasoned hydrologist, and check my work. The newest oldest trick in the book. And the expert said: something's wrong with twenty twenty-three.
It was right. A rain sensor had failed, and its silence had been read as "no rain." A whole winter, dry on paper. That's the price of not looking at every number with your own eyes, and the credit goes to the machine for noticing. Fixed, and the model jumped.
[WAITS T1] Then I tried more data: twenty-five years of global weather instead of a dozen years from our own stations. And the models trained on our stations did better.
(Peer, measured: "IMS-trained beat ERA5-trained by 0.1-0.2 m on the same test years" is SAFE; crediting it all to quality is NOT until T1 (ERA5 trimmed to the IMS span). The jump 0.694->0.758 = rain fix + six findings together.)

### 10. the olympics (same scoreboard, model dots orange; grey = didn't help; GRU falls off the bottom; CfC rises above the line)
At the same time, I let the models compete. The famous ones first. And the neural network, the most fashionable of all, came last: worse than simply guessing that nothing changes. And it took an hour to train.
Then I found a different kind of neural network. A liquid one. It took the lead: in seventeen of twenty years, it beat my best model.
(17/20 = one-day S2, ERA5 table, 1d1388e. [WAITS G-ERA5, G-IMS] same-bench head-to-head at long range; GRU 71 min dated May; [WAITS T3] GRU on the CfC bench.)

### 11. the lake becomes a neuron (animation: lake as bucket -> shrinks to one circle -> many circles = a network)
Here's how it works. Think of the lake as a bucket. Rain pours in, the sun and the pumps drain it. What's in it today depends on what came before.
A liquid network is made of little buckets like that. Each one fills with what comes in, and slowly drains. That's how it remembers, and how it forgets.
The clever part is that how fast each one drains changes with what's flowing in. A storm and a dry spell move at different speeds. Ordinary networks keep one fixed rhythm. This one adapts its own clock.
So I'm forecasting a lake... with a network made of little lakes.
The first liquid networks had to watch every bucket drip, step by tiny step. Slow and heavy. The newer version, called CfC, found a shortcut: tell it how much time has passed, and it tells you how full the bucket is. No dripping to simulate. That's why it runs on small chips... and on my old computer, where the heavier versions kept crashing.
(True: LTC and mix 7-seed runs were killed for RAM 2026-10-14; only CfC finished.)

### 12. credit (photo: C. elegans under a microscope, Wikimedia, licence to check)
This idea didn't come from me. It came from MIT, from Daniela Rus's lab, with researchers from Vienna. And it started with this worm. About three hundred neurons, yet it gets around just fine. They built networks inspired by it, and a handful of those neurons learned to keep a car in its lane.
They've since started a company, Liquid AI. They're worth following. And the tools are open: anyone can try them.
(ALL FROM MEMORY, VERIFY: names (Hasani, Lechner, Amini, Rus; Grosu TU Wien), ~19-neuron lane-keeping demo, CfC paper Nature Machine Intelligence ~2022, ncps open-source, photo licence. No "going public" tip.)

### 13. testing it now (click by click, one object at a time)
1 three arrows (hop / jump / flow): Three ways to look far ahead. The simplest one won: jump straight there.
2 memory: How far back does it need to look? A few days. Today's level already holds every winter before it. The lake remembers for you. [WAITS level-only run] (peer, measured 029fe90: 3-120 d history within ~0.01 m; hiding level costs ~0.065 m; say "a few days" not "a week")
3 the two winters: A year ahead, it's off by about a metre. And it's blindest exactly on the extreme winters, like the two I opened with. Given an ordinary winter, it expects an ordinary winter. Give it the real weather, and the error drops to about half a metre. The rest belongs to the rain.
  (peer, measured: row = start year; 2018 -2.28 m (missed the rise), 2024 +1.84 m (too high); 2019-20 equally bad (-2.11), so "like the two", not "only". B14 365 d 0.93 typical / 0.55 known; no-change 1.00.)
4 the fan: So I can't tell you which winter is coming. But tell me the winter, and I'll tell you the lake. [WAITS fan; needs the originator's choice of band method in the CfC session]
5 stamp: "Still running this weekend."
Open: slide 13 crowded (fan may become the close and answer slide 1's promise); the chunk is ~5 min, so slides 6-8 tighten later.

## SPINE v3 DRAFT v2 (2026-10-16 later; SUPERSEDES the draft above for slides 9-13; adds a NEW slide 2)
Originator rulings this pass: 👤 new slide 2 = existing work in the field; 👤 "the small gap I happened to fill"; 👤 the olympics arc "the name mattered less than the comparison" is IN.
Numbering: new 2 = the field; the centaur and everything after shift by one. Below, the slide numbers are the OLD v3 ones (9-13), to avoid churn until the deck is renumbered.

### NEW 2. standing on shoulders (picture: the lake in the middle, quiet labels around it: water balance · catchment models · scenario outlooks · lakes elsewhere; one empty spot: daily, learned from data. No names or paper covers on screen.)
I'm not the first to ask this question. Researchers here at Kinneret have spent decades on the lake's water balance: what flows in, what the sun takes, what's left, and what a warmer climate will do to it. The Water Authority thinks in scenarios: if the winter is average, the lake ends here; if it's dry, here.
Further away, the Great Lakes get an official forecast every month, six months ahead, given as a range: a high case, a most likely case, a low case. And studies that compare models often find that the fanciest one isn't the best.
What I couldn't find was a daily forecast learned from data, from a week to a year ahead. That's the small gap I happened to fill.
So I'll show you how I got here: what worked, what didn't. Maybe something in it will be useful to you. And by the end, I'll tell you honestly how far ahead I could see.
(Literature check 2026-10-16, web searches in English and Hebrew; abstracts, not full texts:
- Kinneret: Assouline 1993 (water/heat/salt balance, Kalman filter); Rimmer et al. 2011 J. Hydrology (inflow regression + modified Penman evaporation + salinity under climate models, 1979-2060); a 2022 J. Hydrology study (evaporation +9-22% by 2070-99, water-balance deficit 14-40%); WEAP and SWAT+/MODFLOW models. All annual/climate or planning, none an operational daily forecast.
- The Water Authority's scenario practice is real, but the only number found (-210.80 m with average rain) is from 2012, DATED; an older press figure says an average winter adds ~1.6 m. Keep numbers off the slide, or measure the average winter rise from our own data.
- Great Lakes VERIFIED: USACE Detroit + Environment and Climate Change Canada issue a joint 6-month coordinated forecast monthly, with high / most probable / low (5/50/95% exceedance), the same idea as our fan.
- Lake-level ML is a field of its own (2020 systematic review; 69 Polish lakes: a simple network matched deep learning; Vrana Lake: LSTM best; a Great Lakes transformer at 4-7 cm, 6 months). Results are mixed, hence "often", not "keep finding".
- No Kinneret-specific ML level forecast was found in English or Hebrew. Say "couldn't find", never "first".
- Names: 🤖 lean towards naming the lab (Kinneret Limnological Laboratory), not individuals. The originator decides.)

### 9. feeding it better (scoreboard line, May-Oct, data dots blue)
The first model I trained was already decent. But a model is only as good as what you feed it.
So I tried an old trick: I asked the AI to play an expert, a seasoned hydrologist, and check my work. The newest oldest trick in the book. And the expert said: something's wrong with twenty twenty-three.
It was right. A rain sensor had failed, and its silence had been read as "no rain." A whole winter, dry on paper. That's the price of not looking at every number with your own eyes, and the credit goes to the machine for noticing. Fixed, and the model jumped.
(DROPPED: "quality beats quantity". T1, peer section 6: not supported; given the actual weather, ERA5 does as well.)

### 10. the olympics (same scoreboard, model dots orange; the GRU drops in May, then every model lands together)
At the same time, I let the models compete. The famous ones first. And the neural network, the most fashionable of all, came last: worse than simply guessing that nothing changes. I almost wrote neural networks off.
Then a liquid network showed me a better way to set up the problem. And when I gave the old network the same setup, it caught up. Every one of them landed in the same place, my best model included.
The lesson surprised me: the name of the model mattered less than how fairly I compared them. Same data, same years, same test, for everyone.
(Peer, measured: G-ERA5 ec06e3d all tie; G-IMS 4e8c214 short-range tie, B14 ahead by 0.08-0.13 m at long range on 4-5 years (not proven); T3 GRU acb6877 ties at long range, +4-5 mm better at 7-26 d. Optional, if wanted: "far ahead, on our own station data, the liquid one pulled slightly in front", only with the caveat. The one-day "17 of 20 years" (1d1388e) stays true but is no longer the headline.)

### 11. the lake becomes a neuron (animation: lake as bucket -> one circle -> many circles = a network)
Here's how it works. Think of the lake as a bucket. Rain pours in, the sun and the pumps drain it. What's in it today depends on what came before.
A liquid network is made of little buckets like that. Each one fills with what comes in, and slowly drains. That's how it remembers, and how it forgets.
The clever part is that how fast each one drains changes with what's flowing in. A storm and a dry spell move at different speeds. Ordinary networks keep one fixed rhythm. This one adapts its own clock.
So I'm forecasting a lake... with a network made of little lakes.
The first liquid networks had to watch every bucket drip, step by tiny step. Slow and heavy. The newer version, called CfC, found a shortcut: tell it how much time has passed, and it tells you how full the bucket is. No dripping to simulate. Its makers measured it at ten to ten thousand times faster. That's why the newer kind runs on small devices... and on my old computer, where the older liquid versions kept crashing.
(VERIFIED: CfC paper, "1 to 5 orders of magnitude faster" than its ODE-based counterparts; "ten to ten thousand" understates the top end, which is deliberate. NOT lighter than a GRU of the same size, so never compare it with other networks on weight.)

### 12. credit (photo: C. elegans under a microscope; licence to check)
This idea didn't come from me. It came from Daniela Rus's lab at MIT, working with researchers in Austria. And it started with this worm. About three hundred neurons, yet it gets around just fine. Inspired by it, they built a network where nineteen neurons learned to steer a car.
In twenty twenty-three they started a company, Liquid AI, building models that run on your phone and your laptop rather than in the cloud. They're worth following. And the tools are open: anyone can try them.
(VERIFIED: Neural Circuit Policies, Nature Machine Intelligence 2020 (Lechner, Hasani, Amini, Henzinger, Rus, Grosu): 19 control neurons, 253 synapses, steering, C. elegans-inspired. CfC, Nature Machine Intelligence 4, 992-1003 (2022) (Hasani, Lechner, Amini, Liebenwein, Ray, Tschaikowski, Teschl, Rus). Liquid AI founded 2023 by Hasani, Lechner, Amini, Rus; on-device models. Grosu = TU Wien, Henzinger/Lechner = IST Austria. Still to check: "302 neurons" (general knowledge), the ncps licence, the photo licence.)

### 13. testing it now (click by click)
1 three arrows (hop / jump / flow): Three ways to look far ahead. The simplest one won: jump straight there.
2 memory: How far back does it need to look? A few days of the lake's own trend, plus the latest rain and river flow. That's all the memory it needs. Looking further back adds nothing. (Peer section 2, 1d9d406: either half alone loses ~0.06 m; true for the CfC and an LSTM.)
3 the two winters: A year ahead, it's off by about a metre. And it's blindest on the extreme winters, like the two I opened with. Given an ordinary winter, it expects an ordinary winter. Give it the real weather, and the error drops to about half a metre. The rest belongs to the rain.
4 the fan: So I can't tell you which winter is coming. But tell me the winter, and I'll tell you the lake. The professionals already think in scenarios. I just ran all of them.
5 the honest answer (may become the close): A week ahead, it's usually off by two or three centimetres. That's less than half of what the lake itself moves in a typical week. Six months ahead, the honest answer is a range more than a metre wide, because it depends on a winter nobody can forecast yet.
  (Peer, inherited: 7 d error 0.024-0.026 m vs no-change 0.058; 80% range 7 d 0.05 m wide, 130 d 1.2 m; calibrated 47-50% / 72-81%. All on the 16-year ERA5 bench, average weather. Flood weeks are worse than the average.)
6 stamp: "Still running this weekend." [WAITS SEAS5, 2026-10-17: seasonal forecasts may narrow the six-month range.]


## SCRIPT v4: FULL RUN (2026-10-16 night; talk-deck-script; SUPERSEDES the order of everything above)
Originator, this pass: the abstract is the spine (three horizons, "the rain sets the limit"); the liquid network and the new numbers are a bonus; Adnan MUST be credited (slide 4 keeps him, slide 11 brings him back); Adnan reviews the slideshow by 25 Oct. X = a number still waiting on data-science-project-be. [brackets] = slide design.
Thread: "which winter is coming, and how far ahead can we see?" Asked in 1, answered in 15 and 17.

1. the lake: unchanged (see "## 1." above). [one continuous slide: the two lake years merge into one lake with two water lines; zoom out to the map; the Mediterranean appears; lake and sea together]
2. the field: as in SPINE v3 DRAFT v2 "NEW 2". Source to switch to the originator's own Related Work section (sent to Adnan 2026-08-04). [the lake in the middle, quiet labels around it: water balance, catchment models, scenario outlooks, lakes elsewhere; one empty spot: daily, learned from data]
3. centaur: unchanged. [a centaur; on screen: "Centaur"]
4. app front + Adnan: unchanged, except "I said so myself, two slides ago" -> "I said so myself, at the start." [the app's front page]
5. pipeline: unchanged. [the whole system in one picture]
6. gather: unchanged. [a dark forest, a flashlight beam]
7. organise: unchanged. [bronze -> silver: the messy shapes become one clean table]
8. enrich: unchanged. [gold: the table grows new columns]
9. benchmark: unchanged. [photo: F-55 at Jaffa port, B&W]
10. scoreboard: unchanged (click 4, the neural network "worse than guessing", now sets up slide 14). [one chart built click by click, 0.69 -> 0.77]

### 11. how far? [one picture: a horizon ladder from a week to a year; the error bar grows left to right; a blue rain-wall stands at the winter; a sun marks the summer month]
So how far ahead can it see? A week ahead, it's usually off by two or three centimetres. That's less than half of what the lake itself moves in a typical week. The week holds.
Adnan wanted more. A season. I told him I didn't have the data. I tried anyway: temperature alone, climate models. Shots in the dark, and mostly misses. Past a few weeks, everything waits for the rain, and rain here is one of the hardest forecasts there is.
But one shot hit. In summer there's no rain to guess, only a lake drying in the sun. So: when will it cross the red line? A month ahead, a simple drying curve named the day within about two days.
No rain, and we see far. Rain, and we go blind. In our abstract we called it a rain-gated frontier. Simply put: the rain sets the limit.

### 12. the lake becomes a neuron [animation: the lake as a bucket -> shrinks to one circle -> many circles = a network]
After we sent the abstract, I couldn't let the winter go. I went looking for a different kind of model.
Think of the lake as a bucket. Rain pours in, the sun and the pumps drain it. What's in it today depends on what came before.
A liquid network is made of little buckets like that. Each one fills with what comes in, and slowly drains. That's how it remembers, and how it forgets. And how fast each one drains changes with what's flowing in: a storm and a dry spell move at different speeds. It adapts its own clock.
So I'm forecasting a lake... with a network made of little lakes.
The first versions had to watch every bucket drip, step by tiny step, and kept crashing my old computer. The newer one, called CfC, found a shortcut: tell it how much time has passed, and it tells you how full the bucket is. Fast enough for a phone. Or for my old computer.

### 13. credit [photo: C. elegans under a microscope; licence to check]
This idea didn't come from me. It came from Daniela Rus's lab at MIT, working with researchers in Austria. And it started with this worm. About three hundred neurons, yet it gets around just fine. Inspired by it, they built a network where nineteen neurons learned to steer a car.
In twenty twenty-three they started a company, Liquid AI, building models that run on your phone rather than in the cloud. They're worth following. And the tools are open: anyone can try them.

### 14. a fair race [one chart, a year ahead: three pairs of bars (champion, plain network, liquid network); light bar = winter unknown, dark bar = winter handed to it]
My first liquid result looked brilliant. Then I saw why: it had quietly been handed the real winter. Without it, it was ordinary.
So I set the rules first. Decide how to judge before you look. Same years, same test, for everyone.
Remember the neural network that came last, worse than guessing? I gave it a second chance, and noticed what I'd done: I'd asked it to forecast the lake without telling it the weather. Given the same information, it caught up. A week ahead, all three land together.
A year ahead, they split. With no idea which winter is coming, the two networks guess better. Hand them the real winter, and my old champion wins. Different tools for different jobs, just as our abstract said. The name of the model mattered less than how fairly I compared them.
(X: "the networks guess better without the winter" holds on the station record, 15 years (sha d19384b); on the ERA5 bench all three tie. Confirm with the peer which bench is final before this line stands.)

### 15. this winter [the fan from the morning of the talk: one thin line per past winter, 2018-19 and 2024-25 highlighted, the red line dashed; still image from late October as fallback]
So, which winter is coming? I can't tell you. But I can show you what each one would do.
This is the lake, from this morning. Every line is one past winter, run through the model. A winter like twenty eighteen to nineteen lifts it to about X. One like twenty twenty-four to twenty-five keeps it falling, to about X. Most likely, around X. The chance it's still below the red line next autumn: about X in ten.
A year ahead, about a third of my error is simply not knowing the winter. Can anyone forecast it? The European seasonal forecast helps a little: in autumn it trims about five centimetres off my error (X: calibrated version pending). This year, it leans X.
The professionals already think in scenarios. I just ran all of them. One more voice beside theirs, not instead of them.

### 16. three rules [three icons, no words: a sealed envelope, a balance scale, a magnifying glass]
What I take from all this isn't a model. It's three rules, and anyone here can use them, with an AI at their side.
One: decide how you'll judge before you see the results.
Two: compare against the best you have, and against doing nothing.
Three: when you're wrong, find out why, and say so. I was wrong more than once: a rain gauge, a number that looked brilliant, a network I nearly threw away.
With rules like these, someone who isn't a programmer can build a dataset with AI and test ideas honestly. And honest forecasts give the people who decide more room to decide well.

### 17. close [the lake video's last frame; the QR code; a small live fan]
So what stops us from seeing further? Partly the winter: nobody can see it yet. And partly the chain: measuring, gathering, cleaning, sharing. A river station that went silent. A dash in a file. The water pumped from the lake, which my model never sees. Every link is in someone's hands, many of them in this room. And the tools I used are in everyone's hands now.
I promised to tell you honestly how far ahead I got. A week: a few centimetres. A month, in summer. Next winter: a range, updated every morning. Here it is.
An amateur with a laptop got this far. Imagine what all of us could see, together. Maybe not today. Maybe tomorrow.
Thank you.

LENGTH: about 3,000 spoken words, roughly 21-22 minutes at a calm pace. Over the 15-20 limit; tighten 6-8 (merge to one slide) and the scoreboard before adding anything.
Waiting (X): the fan values for this winter, the red-line chance, the seasonal lean, the calibrated seasonal gain, which bench is final.
Backup / Q&A: relay vs direct, memory length, calibration percentages, ERA5 vs stations, humidity, the elegant continuous version that came last, the 14-30 day soil bucket.


## SCRIPT v5: 15 MINUTES, ONE CROWD QUESTION PER SLIDE (2026-10-16 night; SUPERSEDES v4)
Originator: never say "our abstract"; cut to 15 minutes; every slide answers a question the crowd would ask. About 1,500 spoken words, about 13 minutes plus pauses. X = waiting on data-science-project-be. [brackets] = slide design.
Cut to backup / Q&A: the benchmark (F-55), the pipeline, organise/enrich (bronze/silver/gold), most scoreboard clicks, relay vs direct, memory length, calibration percentages, ERA5 vs stations, the elegant continuous version, the 14-30 day soil bucket.

### 1. Why should I care? [one continuous slide: two lake years merge into one lake with two water lines -> zoom out to the map -> the Mediterranean appears -> lake and sea together]
In my first year here at Kinneret, the lake was so low that I walked out to the island in front of the campus. By the time I graduated, the waves were flooding the Tiberias promenade, taking their toll on the wooden market stands. Today, those stands stand high above the water once again.
The lake's ups and downs aren't new. But today it sits below the red line, and it is our national backup.
So which winter is coming? One like twenty eighteen to nineteen, the best of the last twenty? Or one like twenty twenty-four to twenty-five, the worst?
Nobody knows. Certainly not me. I'm not a forecaster. I scraped data together and ran models on an old computer that kept running out of memory. But if I could get any results this way, imagine what our best efforts could do.
And it matters right now. This autumn, algae bloomed off our southern coast and choked the desalination plants. Keeping the water flowing meant hard choices. How hard depends on that same question: can the lake carry us next year? With better forecasts, we'd know how much room we have.

### 2. Hasn't anyone done this already? [the lake in the middle, quiet labels around it: water balance, catchment models, scenario outlooks, lakes elsewhere; one empty spot: daily, learned from data]
I'm not the first to ask. Researchers here at Kinneret have spent decades on the lake's water balance: what flows in, what the sun takes, what a warmer climate will do. The Water Authority thinks in scenarios: an average winter ends here, a dry one here. The Great Lakes get an official forecast every month, six months ahead, as a range.
What I couldn't find was a daily forecast learned from data, from a week to a year ahead. That's the small gap I happened to fill. And by the end, I'll tell you honestly how far ahead I could see.

### 3. How can an amateur do this? [a centaur; on screen: "Centaur"]
This is a centaur: half human, half horse. After Kasparov lost to a chess computer, players started teaming up with machines. In two thousand and five, an open tournament let anyone enter, with any computer help they liked. The winners weren't grandmasters, and not the strongest machine. They were two amateurs with three ordinary computers, and a very good way of working with them.
Keep them in mind. Because the person in front of you is one too.

### 4. Who are you, and what did you build? [the app's front page]
I'm a process engineer: I design wastewater treatment plants for TTT, of the WFI Group. And I owe this talk to my co-author, Adnan Agbaria, my lecturer in a data science course during my master's here at Kinneret. He gave us an open task, and I said: I'll forecast the Kinneret's level from weather data off the internet. One week ahead. How hard can it be?
This is what came out of it. An app that runs every morning on my own computer. It pulls the lake's level, the Jordan's flow and the weather, both what fell and the forecast for the week, and forecasts the lake. You can play: take this week's forecast, or go back to any week since twenty twelve and see how the model would have done. The link comes at the end.

### 5. Where does the data come from? [a dark forest, a flashlight beam]
Not from one place. Stations change names, every source has its own format, its own gaps. It's a dark forest. AI is the flashlight. I pointed Claude at a website and said: find the API key. Minutes later, I had any weather station I wanted. The rivers took two months of emails, always "you can't get that data." Then Claude found a Facebook post with a link to a beta site, wrote a scraper, and the river data has come in every day since.
Then I asked it to clean everything into one table, one row per day. It came back with tactics I'd never have thought of. But there was a catch hiding in there.

### 6. Can you trust it? [the scoreboard line, 0 to 1: one dot per attempt; grey dots for the fancy models; the 2023 dot jumps]
My first model scored zero point six nine, where one is perfect and zero is just guessing the average. Then I tried what everyone tries: fancier models. Worse. A neural network: seventy-one minutes of training, and worse than guessing.
The biggest step wasn't a model. I asked Claude to play an expert hydrologist and review my work. The newest oldest trick in the book. It noticed every model stumbled in the same year, and said: when every model fails the same way, it's the data.
A rain gauge had been offline, and the cleaning had turned every missing reading into a zero. A whole winter, dry on paper. Fixed, and the score jumped to zero point seven six. Not a bigger model. Better data.

### 7. How far ahead can it see? [a horizon ladder from a week to a year; the error bar grows left to right; a blue rain wall at the winter; a sun over the summer month]
A week ahead, it's usually off by two or three centimetres. That's less than half of what the lake itself moves in a typical week.
Adnan wanted more. A season. I tried: temperature alone, climate models. Mostly misses. Past a few weeks, everything waits for the rain, and rain here is one of the hardest forecasts there is.
But one shot hit. In summer there's no rain to guess, only a lake drying in the sun. A month ahead, a simple drying curve named the day it would cross the red line, within about two days.
No rain, and we see far. Rain, and we go blind. The rain sets the limit.

### 8. Could a smarter model see past the rain? [animation: the lake as a bucket -> one circle -> many circles = a network]
I couldn't let it go. So I tried a new kind of model: a liquid network.
Think of the lake as a bucket. Rain pours in, the sun and the pumps drain it. What's in it today depends on what came before.
A liquid network is made of little buckets like that. Each one fills and slowly drains: that's how it remembers, and how it forgets. And how fast it drains changes with what flows in. A storm and a dry spell move at different speeds.
So I'm forecasting a lake... with a network made of little lakes. And a newer version, called CfC, does it fast enough to run on a phone. Or on my old computer.

### 9. Where did that idea come from? [photo: C. elegans under a microscope; licence to check]
Not from me. From Daniela Rus's lab at MIT, with researchers in Austria, and from this worm. About three hundred neurons, and it gets around just fine. Inspired by it, they built a network where nineteen neurons learned to steer a car. They've since started a company, Liquid AI. Worth following. And the tools are open: anyone can try them.

### 10. So which model is best? [one chart, a year ahead: three pairs of bars (champion, plain network, liquid network); light = winter unknown, dark = winter handed to it]
My first liquid result looked brilliant. Then I saw why: it had quietly been handed the real winter.
So I set the rules first: same years, same test, for everyone. And I gave the neural network that came last a second chance. I'd been asking it to forecast the lake without telling it the weather. Given the same information, it caught up.
A week ahead, all three land together. A year ahead, on the station record, with no idea which winter is coming, the networks guess better. Hand them the real winter, and my old champion wins. Different tools for different jobs. The name of the model mattered less than how fairly I compared them.
(CONFIRMED 2026-10-17: the IMS station record, 15 test years, is the final bench; CfC 0.72, GRU 0.73, GBR 0.89 m, GBR interval clear of zero. Say "on the station record": on the ERA5 bench all three tie. The CfC is the chosen 6-month product with raw SEAS5; it ties the GRU, so slides 8-9 stay or go by the originator's call.)

### 11. So which winter is coming? [the fan from the morning of the talk: one thin line per past winter, 2018-19 and 2024-25 highlighted, the red line dashed; a late-October still as fallback]
I can't tell you. But I can show you what each one would do.
This is the lake, from this morning. Every line is one past winter, run through the model. A winter like twenty eighteen to nineteen lifts it two and a half metres by spring. One like twenty twenty-four to twenty-five barely moves it, and by next autumn it's lower than today.
Can anyone forecast the winter? The European seasonal forecast helps a little. This year it leans slightly wet, mostly early on. A weak lean. So the chance the lake is still below the red line next autumn: about three in ten.
And I don't just tell you where the lake will be. I tell you how sure I am. When I say eighty percent, it happens about eighty percent of the time.
The professionals already think in scenarios. I just ran all of them. One more voice beside theirs, not instead of them.
(DRY RUN 2026-10-17, peer section 12, refresh before 1 Nov and again on the day: start 8 Oct -213.65; wet scenario -211.0 at 6 mo / -210.5 at 12; dry -213.5 / -214.5; median -212.5 / -212.7; 80% range at 12 mo -214.2..-209.9; P(below -213 in a year) 28% with SEAS5 weighting (34% equal weights), 21% at 6 mo; SEAS5 Oct-Mar ratio 1.06, Oct +57%, Nov +19%. 80% range held 78-82% to 8 months, 73% at a year. Scenario lines are single runs without the error band.)

### 12. What do I take home? [three icons, no words: a sealed envelope, a balance scale, a magnifying glass]
Not a model. Three rules, and anyone here can use them, with an AI at their side.
Decide how you'll judge before you see the results.
Compare against the best you have, and against doing nothing.
When you're wrong, find out why, and say so. I was, more than once: a rain gauge, a brilliant number, a network I nearly threw away.
Rules like these let someone who isn't a programmer build data with AI and test ideas honestly. And honest forecasts give the people who decide more room to decide well.

### 13. So how far did you get? [the lake video's last frame; the QR code; a small live fan]
I promised to tell you honestly. A week: a few centimetres. A month, in summer. Next winter: a range, and how sure I am of it, updated every morning. Here it is.
(2026-10-17: the originator shipped the long-range fan to the app; "updated every morning" is true. How the app shows forecasts is still open, and the slide 11 chart must match it so the QR lands on a familiar picture.)
What stops us from seeing further? Partly the winter. And partly the chain: measuring, gathering, cleaning, sharing. Every link is in someone's hands, many of them in this room. And the tools I used are in everyone's hands now.
An amateur with a laptop got this far. Imagine what all of us could see, together. Maybe not today. Maybe tomorrow.
Thank you.

### 11b. Why should we believe it? (NEW 2026-10-17, between 11 and 12) [one row of 15 autumns, 2011-2025: each year a vertical bar = the range forecast in October for the coming spring, a dot = where the lake got to; inside = hit, hollow red outside = miss; bars tinted by that winter's rain, dry to wet; 2018-19 and 2024-25 labelled]
Here's every autumn since twenty eleven. The bar is what the forecast said in October. The dot is what the lake did by spring. Most dots land inside, in dry winters and wet ones. And these didn't: X. Record winters can still surprise it. It tells you how sure it is, and mostly, it's right about that.
(Originator: struck "I'm an amateur, so don't take my word for it." X = the missed years, waiting on the peer's per-year autumn fans from the shipped product on the merged 1994+ gold. The said-vs-happened bins chart goes to backup. Check "three in ten" on slide 11 against the 10-30% band before it is said.)


## SCRIPT v6: FILLED (2026-10-17; SUPERSEDES v5 and 11b above)
All numbers checked with data-science-project-be in three turns (talk log sections 8-13, track record 67d9ad1). One run for everything: the IMS station-record bench (gold from 2002) and the forecast from 8 Oct 2026 with the October SEAS5. 12-MONTH numbers only: the app's 6-month card is biased low (interpolation under the spring peak; peer reporting the bug to the originator). [brackets] = slide design.

### 1. Why should I care? [one continuous slide: two lake years merge into one lake with two water lines -> zoom out to the map -> the Mediterranean appears -> lake and sea together]
In my first year here at Kinneret, the lake was so low that I walked out to the island in front of the campus. By the time I graduated, the waves were flooding the Tiberias promenade, taking their toll on the wooden market stands. Today, those stands stand high above the water once again.
The lake's ups and downs aren't new. But today it sits below the red line, and it is our national backup.
So which winter is coming? One like twenty eighteen to nineteen, the biggest rise in twenty years? Or one like twenty twenty-four to twenty-five, the driest?
Nobody knows. Certainly not me. I'm not a forecaster. I scraped data together and ran models on an old computer that kept running out of memory. But if I could get any results this way, imagine what our best efforts could do.
And it matters right now. This autumn, algae bloomed off our southern coast and choked the desalination plants. Keeping the water flowing meant hard choices. How hard depends on that same question: can the lake carry us next year? With better forecasts, we'd know how much room we have.
(2018-19 rose +3.47 m, the biggest since 2005-06; 2024-25 rose +0.19 m, the smallest and the driest (56%). Not "the wettest": 2023-24 had more rain (148%) on dry ground.)

### 2. Hasn't anyone done this already? [the lake in the middle, quiet labels around it: water balance, catchment models, scenario outlooks, lakes elsewhere; one empty spot: daily, learned from data]
I'm not the first to ask. Researchers here at Kinneret have spent decades on the lake's water balance: what flows in, what the sun takes, what a warmer climate will do. The Water Authority thinks in scenarios: an average winter ends here, a dry one here. The Great Lakes get an official forecast every month, six months ahead, as a range.
What I couldn't find was a daily forecast learned from data, from a week to a year ahead. That's the small gap I happened to fill. And by the end, I'll tell you honestly how far ahead I could see.

### 3. How can an amateur do this? [a centaur; on screen: "Centaur"]
This is a centaur: half human, half horse. After Kasparov lost to a chess computer, players started teaming up with machines. In two thousand and five, an open tournament let anyone enter, with any computer help they liked. The winners weren't grandmasters, and not the strongest machine. They were two amateurs with three ordinary computers, and a very good way of working with them.
Keep them in mind. Because the person in front of you is one too.

### 4. Who are you, and what did you build? [the app's front page]
I'm a process engineer: I design wastewater treatment plants for TTT, of the WFI Group. And I owe this talk to my co-author, Adnan Agbaria, my lecturer in a data science course during my master's here at Kinneret. He gave us an open task, and I said: I'll forecast the Kinneret's level from weather data off the internet. One week ahead. How hard can it be?
This is what came out of it. An app that runs every morning on my own computer. It pulls the lake's level, the Jordan's flow and the weather, both what fell and the forecast for the week, and forecasts the lake. You can play: take this week's forecast, or go back to any week since two thousand and two and compare the model with what happened. The link comes at the end.
(Page 5 runs the final model on all years: a fit, not a test. Never call it a test.)

### 5. Where does the data come from? [the forest; on "AI is the flashlight" a beam sweeps across and reveals the coverage chart: one bar per source, its start, its gaps, where it changed; station weather from 1994 (models use 2002 on), ERA5 from 2001, the seasonal forecast's record from 1993; a red notch on the 2023 rain]
Not from one place. Stations change names, every source has its own format, its own gaps. It's a dark forest. AI is the flashlight. I pointed Claude at a website and said: find the API key. Minutes later, I had any weather station I wanted. The rivers took two months of emails, always "you can't get that data." Then Claude found a Facebook post with a link to a beta site, wrote a scraper, and the river data has come in every day since.
Then I asked it to clean everything into one table, one row per day. It came back with tactics I'd never have thought of. But there was a catch hiding in there.

### 6. Can you trust it? [the short scoreboard, 0 to 1: four dots: first model 0.69; grey dots for the fancy models, the neural network below zero; the jump to 0.76 with a rain-gauge icon; today's dot 0.77]
My first model scored zero point six nine, where one is perfect and zero is just guessing the average. Then I tried what everyone tries: fancier models. Worse. A neural network: seventy-one minutes of training, and worse than guessing.
The biggest step wasn't a model. I asked Claude to play an expert hydrologist and review my work. The newest oldest trick in the book. It noticed every model stumbled in the same year, and said: when every model fails the same way, it's the data.
A rain gauge had been offline, and the cleaning had turned every missing reading into a zero. A whole winter, dry on paper. Fixing that, and six other problems, lifted it to zero point seven six. Today, zero point seven seven. Not a bigger model. Better data.
(0.694 c3a72b3; XGBoost 0.646; GRU -0.025, 71 vs 4 min (freeze ledger); 0.758 ac2ede5 = rain fix + six fixes in one step; today 0.769 on the merged gold. These are one-day-ahead scores on volume change; never put 0.73 (weekly) beside them.)

### 7. How far ahead can it see? [click 1: "every year is a dot": each test year's 12-month miss (actual minus forecast) against that winter's rain; dots climb from dry-and-over-called to wet-and-under-called; 2018-19 and 2024-25 labelled. Click 2: a sun; one summer replayed, the drying curve meeting the red line]
A week ahead, it's off by about three centimetres. That's less than half of what the lake itself moves in a typical week.
Adnan wanted more. A season. Past a few weeks, everything waits for the rain. Here's every year I tested, a year ahead. In wet winters, it guessed too low. In dry ones, too high. The further from an ordinary winter, the bigger the miss.
But in summer there's no rain to guess, only a lake drying in the sun. A month ahead, a simple drying curve named the day it would cross the red line, on average within about two days, across all eight crossings since two thousand and eight.
No rain, and we see far. Rain, and we go blind. The rain sets the limit.
(Week: 2.6-3.0 cm typical error; the 80% range is ~5.5 cm wide, keep them distinct. Dots: track_record.csv, 12 months, Spearman 0.69 signed error vs Oct-Mar rain, n = 15. Summer: numbers_check.md hindcast, mean 1.8 days at 15-30 days' warning, 112 forecasts, 8 crossings; level silver + ERA5. The 47 mm stays off the slide.)

### 8. Could a smarter model see past the rain? [animation: the lake as a bucket -> one circle -> many circles = a network]
I couldn't let it go. So I tried a new kind of model: a liquid network.
Think of the lake as a bucket. Rain pours in, the sun and the pumps drain it. What's in it today depends on what came before.
A liquid network is made of little buckets like that. Each one fills and slowly drains: that's how it remembers, and how it forgets. And how fast it drains changes with what flows in. A storm and a dry spell move at different speeds.
So I'm forecasting a lake... with a network made of little lakes. The older versions wouldn't run on my computer. The newer one, called CfC, found a shortcut, and it trains in minutes on an ordinary computer.
(Measured 16 Oct, this computer: CfC 20 min, GRU 7, GBR 6 for 15 years x 3 seeds. NEVER say faster than the GRU or "runs on a phone". "Wouldn't run on my computer" is the originator's own memory, with no log record: confirm.)

### 9. Where did that idea come from? [photo: C. elegans under a microscope; licence to check]
Not from me. From Daniela Rus's lab at MIT, with researchers in Austria, and from this worm. About three hundred neurons, and it gets around just fine. Inspired by it, they built a network where nineteen neurons learned to steer a car. They've since started a company, Liquid AI. Worth following. And the tools are open: anyone can try them.
(Still to verify: 302 neurons, the ncps licence, the photo licence.)

### 10. So which model is best? [one chart, a year ahead, station record: three pairs of bars (champion, plain network, liquid network); light = no winter forecast 0.89 / 0.73 / 0.72, dark = the real winter 0.55 / 0.70 / 0.69; dashed line "doing nothing" 0.83]
My first liquid result looked brilliant, until I saw it had been given the real winter's weather. No forecast has that. Without it, it was ordinary.
So I set the rules first: same years, same test, for everyone. And I gave the neural network that came last a second chance. I'd been asking it to forecast the lake without telling it the weather. Given the same information, it caught up.
A week ahead, all three land together. A year ahead, on the station record, with no idea which winter is coming, the two networks guess better. Hand them the real winter, and my old champion wins. Different tools for different jobs. The name of the model mattered less than how fairly I compared them.
(Section 8/10, IMS 15 test years: networks beat the GBR by ~0.18 m, interval clear of zero; CfC = GRU, never say the CfC beats the GRU. On ERA5 all three tie: always "on the station record".)

### 11. So which winter is coming? [the fan from 8 Oct 2026 out to 12 months: thin grey line per past winter, 80% band, 2018-19 and 2024-25 in colour, the red line dashed, today's dot; stamp: "as of the October seasonal forecast"]
I can't tell you. But I can show you what each one would do.
This is the lake, as of this autumn. Every line is one past winter, run through the model. A winter like twenty eighteen to nineteen lifts it about three metres by next autumn, maybe more. A winter like twenty twenty-four to twenty-five leaves it almost a metre lower than today.
Can anyone forecast the winter? The European seasonal forecast helps a little. This year it leans slightly wet, mostly early on. A weak lean. So the chance the lake is still below the red line a year from now: about three in ten. And at a year ahead, forecasts like this one have, if anything, overstated the risk a little.
The professionals already think in scenarios. I just ran all of them. One more voice beside theirs, not instead of them.
(Peer section 12, one run: start 8 Oct 2026 -213.65; 12 mo median -212.7, 80% -214.2..-209.9; wet -210.5 (+3.15; the real 2018-19 rose 3.47, under-called by 0.85), dry -214.5 (-0.85; weather only, not that year's pumping); P(below -213 at 12 mo) 28% (34% unweighted); SEAS5 Oct-Mar 1.06. Autumn medians ran 0.45 m low; the 10-30% band said 19, happened 12; above 30% the opposite (38 vs 61, 7 winters). Never "28%", never "unlikely". NO 6-month numbers. Refresh after the 5 Nov SEAS5 only if the originator decides; then switch EVERY number to that run.)

### 11b. Why should we believe it? [12 autumns, 2014-2025, one bar each = the 80% range forecast in October for a year later; a dot = what happened; inside = hit, hollow red outside = miss; bars tinted by that winter's rain; 2018-19 and 2024-25 labelled; footnote: the first three test years had no range yet]
Here's every autumn I could test. The bar is what the forecast said in October. The dot is where the lake was a year later. An honest eighty-percent range should miss about one autumn in five. It missed three in twelve. These three: the biggest rise in twenty years, the wet winter after it, and the driest. Record winters still surprise it.
It tells you how sure it is, and mostly, it's right about that.
(track_record.csv 67d9ad1: 9 of 12 held at 12 months; misses 2018 above by 0.85 m, 2019 above by 0.31, 2024 below by 0.28; both wet misses above, matching the cautious lean. Up to 260 d the 80% range holds 78-82%.)

### 12. What do I take home? [three icons, no words: a sealed envelope, a balance scale, a magnifying glass]
Not a model. Three rules, and anyone here can use them, with an AI at their side.
Decide how you'll judge before you see the results.
Compare against the best you have, and against doing nothing.
When you're wrong, find out why, and say so. I was, more than once: a rain gauge, a brilliant number, a network I nearly threw away.
Rules like these let someone who isn't a programmer build data with AI and test ideas honestly. And honest forecasts give the people who decide more room to decide well.

### 13. So how far did you get? [the app's fan card (page 10) as a screenshot, the QR code]
I promised to tell you honestly. A week: a few centimetres. A month, in summer. Next winter: a range, and how sure I am of it, updated every month when the new seasonal forecast comes out. Here it is.
What stops us from seeing further? Partly the winter. And partly the chain: measuring, gathering, cleaning, sharing. Every link is in someone's hands, many of them in this room. And the tools I used are in everyone's hands now.
An amateur with a laptop got this far. Imagine what all of us could see, together. Maybe not today. Maybe tomorrow.
Thank you.
(The fan file is rebuilt by hand after each SEAS5 release (the 5th). The 7-day forecast is the one updated every morning. The app card's 6-month number must be fixed before the QR is shown.)

Backup / Q&A: nine seasonal forecasts averaged did no better than the European one alone; climate indices can't forecast the winter; the seasonal forecast's hits and misses; memory, a few days; the ERA5 bench where all three tie; the Jaffa benchmark (error propagation); the champion's 4 minutes vs the network's 71; the 47 mm summer result; the said-vs-happened bins chart.
