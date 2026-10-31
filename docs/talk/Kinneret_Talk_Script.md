# Kinneret talk: the script, by slide

*11 Nov 2026 · Beit Gavriel · 12 slides, 1946 words (about 15 min) · **[click]** marks the next click*

## Slide 1 · Lake Kinneret

*Why should I care? · 150 words*

In my first year here at Kinneret, The water level was so low, I walked all the way to the island in front of campus. By the time I graduated, the water had risen and the waves were taking their toll on the wooden market stands on the Tiberias promenade. The lake knows its ups and downs, and right now, we are under the red line once again.

**[click]**

So which winter is coming? One like 2018/19, taking us almost 3 m higher, or more like 2024/25, drying us to 2 m lower?

**[click]**

The lake is our national backup. And it matters: this autumn the algae bloom forced us to make hard decisions. Having a reliable forecast of the Kinneret's level could help us know how urgently we need the water, and how much time we can dedicate to long term solutions directed at the source. So which will it be?

## Slide 2 · The gap

*Hasn't anyone done this already? · 118 words*

I'm not the first to ask. The field has plenty of professional work. Researchers at the lake's research center have developed a physical model, following the rain all the way to the river. The Hydrological Service takes this winter to calculate next year's water, and later added a weather forecast, to see the Jordan's flow a few days ahead.

**[click]**

And the Water Authority presents scenarios: what a wet winter would do, and where a dry one will leave us.

**[click]**

The Great Lakes in the US actually have a published level forecast, 6 months ahead. The Kinneret does not have such a detailed forecast, at least to my knowledge, and that's the small gap I happened to fit into.

## Slide 3 · The project

*What did you build? · 127 words*

So, I'm Yonatan. I'm a process engineer, not a hydrologist: I design wastewater treatment plants. I took a data science course taught by my co-author, Adnan Agbaria, the one I owe the credit to for being here, and that's how I found myself training models to forecast the lake's level. I started with a week ahead, which seemed possible using the weekly weather forecast. Adnan talked me into going further. I wasn't sure it was possible, and I'm glad I tried. This is the web app's front page. It collects new data every day, cleans it, retrains the weekly model every morning, and shows the forecasts, a week and a year ahead. I'm going to tell you how it works, and how much you should trust it.

## Slide 4 · Centaur

*How can an amateur do this? · 126 words*

This is a centaur, half human, half horse. In chess, a centaur is half human, half machine. Kasparov really set this stage. He was world champion when he lost to Deep Blue, an IBM machine, in 1997. What he did next was join the computer, to play as a team. In 2005 a contest was held where anyone could enroll, with any machine. Grandmasters came, supercomputers played, and the winners? A football coach and a DBA, two amateurs, with three regular computers. Well, in hydrology and machine learning I'm an amateur, I see myself like those two, not as a world champion but as a regular guy with an interest and some dedication. Let that reference give you context while I show you how it works.

## Slide 5 · The sources

*What data did we use? · 145 words*

So everything starts in the data sources. In this case: the level, the Jordan flow rate, the weather, and the seasonal forecast. I source them by API, by scraping, and sometimes by email. By the way, sending thanks to Rita of the Hydrological Service. Each source has its own shape, so you clean it and organize it in a daily table, then add any calculated columns you like. And the one thing to look out for: 2023 kept getting the worst training results, so I asked Claude to check, and it turned out to be a rain gauge that was offline all year, and every missing day had turned into zero rain. The whole winter looked dry. Once missing days were marked as missing instead of zero, 2023 got its real rain back. Fixing that, plus six smaller improvements, was the biggest single step forward.

## Slide 6 · The models

*What are the two models? · 236 words*

So which model did I use? I tried more than a dozen, and ended up with two. The first is Classic ML: gradient boosting. It calculates hundreds of decision trees: did it rain more than 20 mm this week? Is it winter? Then it uses all those trees together to create a single prediction. The second is a deep learning model called a GRU, a type of neural network. It reads the values day by day, forming a type of memory that is passed all the way through and finally results in creating the prediction. The rest were cousins of these two, other tree methods and other neural networks, and none beat them on years they hadn't seen. So of the two model finalists, which one is better, and for what? And how did I check?

**[click]**

What I did is run many small comparisons, where each run is an actual model training on the data, and an error check of its prediction against what the lake really did, in years the model never saw. Each comparison is two identical runs, with one tweak, and the method with the smaller error persists.

**[click]**

For a week's prediction, gradient boosting, the classic ML model, won. It turned out to be better where the weather forecast is closer to the actual weather.

**[click]**

For a year ahead, based on an average of past winters, the neural network had much better results.

## Slide 7 · The forecast

*Can we trust the seasonal forecast? · 242 words*

A big dilemma was which seasonal forecast to use. Copernicus, the European climate service, publishes one every month. Let's take a deep dive into how its data actually looks. These are their forecasts, year by year since 2012, on a Y axis relative to an average winter.

**[click]**

And these are the actual yearly rain gauge results at the Tzemach measuring station. You can see that the Copernicus forecasts are usually in the right direction, pretty good at predicting whether the winter is wet or dry, but in general they understate, falling short of the actual rain values.

**[click]**

So we did what you do with a friend who always understates: we gave it a measured nudge in its own direction,

**[click]**

and added an error range of 80%, both measured and based on actual data. Even then, we still missed 5 out of 14. Those are the red rings. Over 19 winters, it's 5 out of 19, about what an 80% range should miss. So Copernicus didn't end up as an input to the forecast you'll see at the end, but we did use it as a way to lean the result in its direction.

**[click]**

And did it help? A year ahead, it beat an average year by only about two centimetres: a weak forecast, but one that was persistent over various models and methods. I even tried averaging nine of the world's seasonal forecasts, and the European one alone did just as well.

## Slide 8 · The method

*How does it work? · 177 words*

To put it all together, we end up with two different methods for two different time gaps. To predict a week ahead, where the IMS gives a good forecast, classic ML is used to predict river flow day by day, using one prediction to make the next one, while the level prediction uses the direct method, combined with the river prediction. The river flows turned out to be highly predictable given the rain forecast, and highly correlated to the lake changes, making them a key step in between.

**[click]**

To make long-term predictions, from a month to a year, a direct approach is implemented, the simpler of the two, and as mentioned, a GRU neural network is the model that had the smaller error doing so. The model is fed the rain and weather of each winter since 2002, as if that winter were coming again: a method borrowed from river forecasting called ESP, ensemble streamflow prediction, also used for the Great Lakes, and the result is a range that is then leaned toward the Copernicus seasonal prediction.

## Slide 9 · The errors

*Which model won? · 80 words*

So can you trust it? And to what extent? Here are the measured errors on past winters. For a week ahead, the classic method is 6 millimeters better, still with a 2 cm average error. For a year ahead, the neural network has an 85 cm average error. The classic method got down to 78 cm when given the real weather, slightly better, but a year ahead we don't have that data, and with a forecast, the network is better.

## Slide 10 · The horizon

*So which winter is coming? · 220 words*

I will share the forecast, but I'll start by saying I'd rather you take the intention and method, rather than the limited prediction itself. This is where we are today, and each grey line is today's lake, run through the rain and weather of one past winter since 2002, as if it were coming again.

**[click]**

Then the teal range is those winters, blurred by the model's own past errors, with the lean towards the seasonal forecast, and that's why it's slightly above.

**[click]**

The dark dots are the middle of it all: one per month, the single most likely level, if you want a point rather than a span. They end about 1 m above where we are now, and the dot on the red line marks late February, where it crosses upward and stays above.

**[click]**

In one in three, the lake is still under the red line next October. That's not a promise; it's what happens if I run them all, and when it said one in three before, it happened about one in three. And 2 in 10 are out of this range, meaning the prediction would be wrong, mostly on the wet side. It's possible that it will be even drier, God forbid, but I hope I'm wrong the other way, and we will open the Degania dam.

## Slide 11 · The takeaways

*So what do I take home? · 73 words*

So, two takeaways. The first: I'm a process engineer, and I built this model outside my own field. What it shows today is about a two-in-three chance that a year from now the lake is back above the red line.

**[click]**

The second: this technological leap holds real potential. With agentic AI tools, more of us can build new models, models that improve how we decide, and through that, the conditions we live in.

## Slide 12 · The limiting factor

*Why can't you just tell us? · 252 words*

Three things limit how far I could see. The first is the human factor: how much did people take out of the lake, by pumping, or by opening the dam? This is a kind of limit I have, as I lean on open sources, yet the decision makers don't, and this is exactly the kind of tool made to facilitate planning future consumption. With the real pumping and dam data, which the Water Authority has, that's the natural next research step, and I'd be glad to work on it with anyone here.

**[click]**

The second is the weather. Next year's rain in the Middle East is known to be unpredictable, and a changing climate isn't making it easier, so the range of uncertainty seems to be here to stay.

**[click]**

The third limit is our understanding. Even if we knew exactly how much rain will fall, how much of it reaches the lake? That depends on how wet the soil already is, on springs and groundwater. It's a question of knowledge and tools, and it's where research can still move the needle.

**[click]**

In the 1930s, our great-grandparents used a crane to build a dam, using technology to improve future water security. We have new tools in our hands, and I know some people are afraid of the leap we are living through, but I see the great potential in doing what Kasparov did: leveling up our abilities, and directing that to improve future water security.

Thank you, and I'm glad to take up questions.

### Backup · The benchmark

*Why from today, and not day by day? · 157 words*

This stone is at Jaffa port: the national height point. Every height in Israel, the Kinneret's minus 213 included, is measured from it. Measure only from one point to the next, and you drift a little with every step: that's error propagation. A forecast has the same choice: jump straight from today's measured value, the benchmark, or keep going day by day, each step off the last forecast. A year ahead, for the network, it was a tie, so it jumps from today.

**[click]**

For the week's change in the lake, starting from today's real volume was clearly better: an R squared of 0.77, against 0.66 when it rolled day by day.

**[click]**

The river was the other way round. Forecasting its flow one day at a time, each day from the day before plus that day's weather, was better: 0.94 against 0.86. So the week ahead runs the river day by day, and the lake from the benchmark.

### Backup · Why should we believe it?

*82 words*

Before this winter, here's how the forecast did every autumn I could test. The bar is what it said in October. The dot is where the lake was a year later.

**[click]**

An honest eighty-percent range should miss about one autumn in five. It missed three in twelve. These three: the biggest rise in twenty years, the wet winter after it, and the driest. Record winters still surprise it. But it tells you how sure it is, and mostly, it's right about that.
