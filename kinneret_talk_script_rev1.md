# Kinneret Level Forecast — Talk Script (rev 1, data-checked 23 Oct 2026)

Your words, with only the facts fixed. Changed words are in **bold**; the numbers in [brackets] point to the list at the end. Your original is untouched in `kinneret_talk_script.md`.

## Opening

On my first year here at Kinneret, I walked all the way to the island in front of campus. Before I graduated, the waves took their toll on the wooden market stands on the Tiberias promenade. The lake knows its ups and downs, and right now, we are under the red line once again. So which winter is coming? One like 2018/19, taking us almost 3 m higher, or more like 2024/25, drying us 2 m lower? The lake is our national backup. And it matters: this autumn the algae bloom put us in front of hard decisions. Having a reliable forecast of the lake's level could help us know how urgently we need the water, and how much time we can dedicate to solutions directed at the source. [1] So which will it be?

I'm not the first to ask. The field has plenty of professional work. Researchers at the lake's research center have developed a physical model, following the rain all the way to the river. The Hydrological Service takes this winter to calculate next year's water, and the Water Authority presents scenarios: what a wet winter would do, and where a dry one will leave us. The Great Lakes actually have a published level forecast, 6 months ahead. For the Kinneret I couldn't find one, and that's the small gap I happened to fit into.

It started in a data science course in my master's degree, taught by Adnan Agbaria, my co-author and the one I owe the credit for getting me here. He gave us an open project, and I chose a weekly forecast. It seemed possible, based on the IMS weather forecast being pretty good most of the time. What I didn't think was doable was a year ahead, but Adnan talked me into trying. This is the app. It collects new data every day, cleans it, **retrains the weekly model every morning,** and shows the forecasts, a week and a year ahead. [2] I'm going to tell you how it works, and how much you should trust it.

## The centaur

This is a centaur, half human, half horse. In chess, a centaur is half human, half machine. It started when Kasparov, then world champion, lost to Deep Blue, an IBM machine, in 1997. What he did next was join the computer, to play as a team. In 2005 a contest was held where anyone could enroll, with any machine. Grandmasters came, supercomputers played, and the winners? A football coach and a DBA, two amateurs, with three regular computers. Well, in hydrology and machine learning I'm an amateur, like those two, so keep that in mind while I show you how it works.

## The data

So everything starts in the data sources. In this case: the level, the Jordan flow rate, and the weather. I source them by API, by scraping, and sometimes by email. By the way, send thanks to Rita of the Hydrological Service. Each source has its own shape, so you clean it and organize it in a daily table, then add any calculated columns you like. And the one thing to look out for: 2023 kept getting the worst training results, so I asked Claude to check, and it turned out to be **a rain gauge that was offline all year, and every missing day had turned into zero rain.** The whole winter looked dry. [3] **Fixing that, with six smaller problems, was the biggest single step forward.** [4]

## The models

So which model did I use? I tried more than a dozen, and ended up with two. [5] Classic ML: gradient boosting. It calculates hundreds of decision trees: did it rain more than 20 mm this week? Is it winter? Then it uses all those trees together to create a single prediction. And a deep learning model called a GRU, a type of neural network. It reads the values day by day, forming a type of memory that is passed all the way through and creates the prediction at the end of the line. So which one is better, and for what? And how did I check?

## How I checked

What I did is run many small comparisons, where each run is an actual model training on the data, and an error check of its prediction against **what the lake really did, in years the model never saw.** [6] Each comparison is two identical runs: same data, same calculation methods, with one tweak. A change in the model, in its implementation, or in the dataset. The method with the smaller error persists.

A few of the more significant ones: first, comparing different models on a certain time step. For a week's prediction, GBR won. It turned out to be better where the weather forecast is closer to the actual weather. For a year ahead, based on an average of past winters, the neural network had much better results.

An example of a calculation method: do I use **the last two weeks of data** as a benchmark for a direct prediction, with a leap in time? Or do I use each day's prediction as a basis for the next day, and risk error propagation? For a year, they tied, so I chose direct. **The trees were different: run day by day for a whole year, and handed the real weather, they drifted further off, so the year runs direct.** [7]

A big dilemma was which seasonal forecast model to use. I found Copernicus has a weak prediction, but one that was persistent over various models and methods. **I even tried averaging nine of the world's seasonal forecasts, and the European one alone did just as well.** [8]

## Copernicus

Let's take a deep dive into how the Copernicus data actually looks. These are their forecasts, year by year since 2012, on a Y axis relative to an average winter. And these [click] are the actual yearly rain gauge results at the Tzemach measuring station. You can see that the Copernicus forecasts are usually in the right direction, pretty good at predicting whether the winter is wet or dry, but in general they understate, falling short of the real rain. So we did what you do with a friend who always understates: we gave it a measured nudge in its own direction, and added an error range of 80%, both measured and based on actual data. Even then, we still missed 5 out of 14. **Over 19 winters, it's 5 out of 19, about what an 80% range should miss.** [9] So Copernicus didn't end up as an input **to the forecast you'll see at the end**, but we did use it as a way to lean the result in its direction. [10]

## Putting it together

To put it all together, we end up with two different methods for two different time gaps. To predict a week ahead, where the IMS gives a good forecast, classic ML is used to predict river flow day by day, using one prediction to make the next one, while the level prediction uses the direct method, combined with the river prediction. The river flows turned out to be highly predictable given the rain forecast, and highly correlated to the lake changes, making them a key step in between. [11]

To make long-term predictions, from a month to a year, a direct approach is implemented, **the simpler of the two,** and as mentioned, a GRU neural network is the model that had the smaller error doing so. [12] Each winter since **2002** is fed to this model's input, **a method borrowed from river forecasting, also used for the Great Lakes,** and the result is a range that is then leaned toward the Copernicus seasonal prediction. [13]

## Can you trust it?

So can you trust it? And how far? Here are the measured errors on past winters. For a week ahead, the classic method is 6 millimeters better, still with a 2 cm average error. For a year ahead, the neural network has an 85 cm average error. The classic method got **down to 78 cm** when given the real weather, **slightly better,** but a year ahead we don't have that data, and with a forecast, the network is better. [14]

## Three limits

Three things limit how far I could see. The first is the human factor: how much did people take out of the lake, by pumping, or by opening the dam? This is a kind of limit I have, as I lean on open sources, yet the decision makers don't, and this is exactly the kind of tool made to facilitate planning future consumption.

The second is the weather. Next year's rain in the Middle East is known to be unpredictable, and a changing climate isn't making it easier, so the range of uncertainty seems to be here to stay. [15]

The third limit is the bottleneck: how well can we model the lake in relation to the weather? It's a question of knowledge, a question of tools.

[Photo] In the 1930s, our great-grandparents used a crane to build a dam, using technology to improve future water security. We have new tools in our hands, and I know some people are afraid of the leap we are living through, but I see the great potential in doing what Kasparov did: leveling up our abilities, and directing that to improve future water security.

## The forecast

I will share the forecast, but I'll start by saying I'd rather you take the intention and method, rather than the limited prediction itself.

This is where we are today, and the grey lines are every single winter since **2002**. [13] Then the teal range **is those winters, blurred by the model's own past errors, with** the lean towards the seasonal forecast, and that's why it's slightly above. [16] This is the middle of it all: the actual prediction the model gives for each month, if you want to see a point rather than a span. It **ends about** 1 m above where we are right now, crossing the red line upwards in late February, and staying above. **In one in three, the lake is still under the red line next October.** [17] That's not a promise; it's what happens if I run them all, **and when it said one in three before, it happened about one in three.** And 2 in 10 are out of this range, meaning the prediction would be wrong, **mostly on the wet side.** [18] It's possible that it will be even drier, God forbid, but I hope I'm wrong the other way, and we will open the Degania dam.

---

## What was checked, and why each change

Everything not listed checked out: below the red line today (−213.72 m on 22 Oct); 2018/19 +2.82 m and 2024/25 −2.13 m; the earlier work and the Great Lakes' 6-month forecast; the 1997/2005 chess story; 300 trees per stage; the GBR winning the week only when the weather is known (2.0 vs 2.6 cm); the year 85 vs 121 cm; Copernicus right in 10 of 14 winters and timid; 9 of 14 inside its range; the week method (river chained day by day, about 0.94 R², the level direct); about 1 m higher and crossing up around 23 Feb; 2 in 10 outside the range (it held 77%); the dam in the early 1930s.

1. **Not a number, a sensitivity flag.** Earlier ruling: no cause of the bloom. "Solutions directed at the source" may sound like you're naming one. Your call.
2. Only the weekly trees retrain every morning. The year forecast is rebuilt by hand after Copernicus publishes each month (on the 5th).
3. The gauge (Lev Kinneret) was offline for all of 2023, not just the winter, and its missing days became zeros. That's why the winter looked dry.
4. "More important than which model" was ruled out before, because the year-ahead model choice saved 36 cm. "The biggest single step" is the accepted wording (one-day R² 0.69 → 0.76).
5. OK if you count set-ups: 8 in the June olympics plus 7–8 in the October tournament, across six model types (GBR, XGBoost, LightGBM, GRU, LSTM, liquid network).
6. The check is against the lake's real level, not the weather. "Years it never saw" is the point that makes the test honest.
7. **Your flag.** The October tournament (15–17 Oct): relay vs direct tied for the network (0.370 vs 0.366). The only one-sided case was the trees' day-by-day chain: given the real weather it got *worse* at a year (1.13 m vs 0.87 m with average weather), drifting on the real extremes. The old line promised a later example that doesn't exist; this replaces it. The direct method also used "the last 14 days of lake, river and weather", not just the last weather reading.
8. Optional, but it backs your "persistent" claim (17 Oct): nine systems averaged tied SEAS5 alone. SEAS5 helped all three models by about 1–3 cm a year ahead.
9. **Your open question.** If the range is honest, 14 winters should miss about 3, and 5 or more happens 13% of the time: unlucky, not damning. Over 2007/08–2025/26 it held 74%, which is 5 of 19 (5 or more happens 33% of the time). Plain climate held 79%. One of the 14 misses (2013/14) was by a hair. Verdict: small-sample noise, not a broken range.
10. Careful. In the fan, Copernicus is not an input, only weights. But the 85 cm on the trust slide was measured with the network told Copernicus's raw lean (85 cm with it, 87 without). "The forecast you'll see at the end" keeps both true.
11. Checked: stage-1 river R² 0.94 in today's retrain.
12. **Your flag.** "Avoiding amplified error propagation" contradicts the tie. "The simpler of the two" is what actually decided it.
13. **Wrong year, twice.** The fan replays every winter since 2002 (22 winters; 15 have complete weather a full year out). 2012 is the Copernicus chart. **Checked (23 Oct, web):** replaying past weather is ESP, developed by the US National Weather Service for river forecasting (program from 1975, in official use since 1984; Day 1985, J. Water Resources Planning & Management). NOAA GLERL's Great Lakes system ran historical meteorology through its models, and a Great Lakes paper describes "weighted repetitions of historical water flux sequences" (seen only in summary). Whether the official US Army Corps 6-month forecast is an ESP ensemble is unconfirmed. Weighting the years by a seasonal forecast is our own step: the NWS listed it as future work. So "developed for the Great Lakes" is wrong; "borrowed from river forecasting, also used for the Great Lakes" holds. If asked: "ESP, from the US Weather Service, 1980s".
14. The 56 cm is real (final run cfc_monthly, G_s3): the trees with the real weather, **averaged over 130/260/365 days** = 55.9 cm. But the 85 cm before it is the network at **365 days**. Same measure, real weather: at 365 d the trees 78 vs the network 86; on the 4–12-month average the trees 56 vs the network 66. In both, the trees' edge isn't clear. **Decided (23 Oct): 78 cm, "slightly better"** (365 d, same column as the slide's 85). If asked: the 8 cm edge over the network's 86 isn't statistically clear.
15. Fine as said. If asked: Copernicus' skill here is about 0.5 (weak but real), and climate indices like ENSO show almost none (|ρ| ≤ 0.33).
16. Most of the band's width is the model's own error (about 2.6 m of the 4.3 m at 12 months), not the spread of the winters.
17. **Wrong meaning.** 1 in 3 is the chance the lake is still below the red line in Oct 2027 (33%), including winters that never get above it. It isn't "crosses down again". The dry third is the one that pops over in March and slips back by June.
18. When it missed at 12 months, it was above the range 16% of the time and below 7%. That fits your "I hope I'm wrong the other way".

Not checked here (your own knowledge): the island and promenade memories, how each source is fetched, Rita, Adnan talking you into the year.
Forecast numbers (1 m, late Feb, 1 in 3, 2 in 10) are from the 15 Oct run and change after the 5 Nov update.
