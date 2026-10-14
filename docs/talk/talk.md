# Kinneret Conference talk: the script
<!-- Source of truth for the deck. Numbers only as ledger placeholders in braces; build_deck.py
     fills them from numbers_ledger.json and stops on any digit typed outside a placeholder or the
     allow line below. Budget: about fifteen minutes spoken. The speaker's journey in ten beats,
     as the spec and plan rule. -->

allow: 2023 | 2005 | 1960

## slide title
object: picture:images/title.png
text: Better data, not bigger models | Yonatan Most · Adnan Agbaria
notes:
This is the Kinneret, as our app draws it. The water is filled to the lake's level, and the orange dashed line is the lower red line.
This morning the lake stood at [today's level, from the app]. Under the red line.
accepted:

## slide hook
object: chart:hook
text: Which winter is coming?
notes:
Here is every year since twenty twenty, laid on top of each other. The teal one is this year. It's the lowest line on the chart, and it's still going down.
What happens next depends on one thing: the winter.
If this winter is like {scenario.dry.season}, the worst of the last twenty, the lake keeps falling. It ends the spring {scenario.dry.change_m} lower, at {scenario.dry.spring_m}, deeper under the red line. That means leaning even harder on desalination, a lake under stress, with worse water quality and more risk of algae, and pressure that spreads out in wider circles, to farming and to everyone who depends on this water.
If it's like {scenario.wet.season}, the best, the lake climbs {scenario.wet.change_m}, to {scenario.wet.spring_m}, back above the red line. Then the whole conversation changes.
Both of those are real winters, not forecasts. So which one is coming? And wouldn't it help every decision in this room to know a little earlier?
accepted:

## slide centaur
object: photo:images/centaur_photo.jpg
text: The Centaur Model | Expert judgement and AI, working together
credit: Photo: James Frid / Pexels
notes:
Before I answer, a picture. This is a centaur, half human and half horse.
After Garry Kasparov lost to a chess computer, he started asking a different question: what happens when a human and a computer play as one team? Chess players call those teams centaurs.
In 2005 there was an open freestyle chess tournament on the internet. Anyone could enter, with any computer help they liked. The winners were not grandmasters, and not the strongest machine. They were two amateur players from the United States, running three ordinary computers, with a very good way of working together with them. The process beat the raw strength.
And today Terence Tao, one of the great mathematicians alive, works on real research problems with AI tools at his side. AI tools suggest and explore, proof-checking software verifies, and he decides what matters.
Keep the centaur in mind. We'll come back to it.
accepted:

## slide who
object: picture:images/qr.png
text: Yonatan Most · Adnan Agbaria
notes:
So who am I? Let me start with what I'm not. I'm not a meteorologist. I'm not a data analyst. I'm not a software engineer. I can't write Python, or R.
I'm a process engineer in water treatment, and a student in a data science master's. My first data pipeline was for treatment-plant data at work: thousands of copy-pastes between Gemini and a notebook, until Claude rebuilt the whole thing, better, in about an hour.
This work is joint with my co-author, Adnan Agbaria, from Kinneret Academic College.
This code opens the app we built, so you can see today's level and this week's forecast for yourself.
accepted:

## slide week
object: picture:images/week.png
text:
notes:
The lake is our national backup, and it's thinning. Knowing where it's heading could help decisions about the backbone of our life on this land. But can it be done?
I limited the challenge to one week: seven steps of one day, each built on the one before. Why a week? Because the model has to be told the weather, and a weather forecast is good for about a week.
One honest note before any score. When I test the models, I give them the weather that actually happened, as if the forecast were perfect. So every score you'll see today is a best case. A real forecast would do worse.
accepted:

## slide sources
object: chart:coverage_slide
text:
notes:
Then the hunt for data. Three sources: the Kinneret Drainage and Streams Authority's site for the lake's level, the Hydrological Service for the rivers, above all the Jordan, and the Meteorological Service's records for the rain, the heat, the wind and the sun, kept current through Open-Meteo.
Finding them took a while; the river data was the hardest to find. Three agencies, three formats, and none of it made to be used together.
Here is every record against time. The lake level goes back to {data.level.start}, the Jordan at Obstacle Bridge to {data.flow.obstacle_bridge.start}. Some records stopped, some paused, some changed source. The weather downloads start in {data.weather.start}. Only from {data.gold.start} do all the sources line up, so that is where my model's table starts.
accepted:

## slide pipeline
object: picture:images/pipeline.png
text:
notes:
You all know this picture better than I do. Raw water comes in, you treat it in stages, and clean water comes out.
Data works the same way. I already knew the stages from my first pipeline: collect the raw data, line it up in one table, clean it, then compute what matters. So building this one took hours, not weeks.
The days went into choosing what the model sees: which past days to show it, and where. I asked more than one AI about that.
accepted:

## slide model
object: picture:images/model.png
text:
notes:
Then the model. I searched the web for the best one, and the answer was XGBoost. So I asked Claude to build it. After a while I noticed it was building something else: gradient boosting. Many small decision trees, each one fixing the mistakes of the one before. Rather than argue, I said: let's race them.
In plain words, the model works in two steps, the way the water does. First rain and river: how much water the Jordan will carry in. Then the lake: how much it gains or loses each day, for each of the next seven days.
accepted:

## slide olympics
object: chart:olympics
text: Eight models, one race
notes:
From here on, every number was measured on one data freeze, {freeze_date}. Only today's level comes from the app.
Eight models, each forecasting how many cubic metres the lake gains or loses each day, over the next week. The score is R squared: one is perfect, zero is no better than guessing the average.
Gradient boosting won. Every run, however I tweaked the data, it came back on top. Here it scores {champion.r2}, trained and tested in {champion.runtime_s}.
So I tried to out-smart the AI at its own game, with a neural network. It scored {olympics.gru.r2_mean}. About zero, after {olympics.gru.runtime_s} of training and testing. A big defeat. So I decided to trust the AI's lead.
accepted:

## slide persona
object: picture:images/persona.png
text: The newest oldest trick in the book
notes:
That's when I reached for the newest oldest trick in the book. You tell the AI: "You are a hydrology and meteorology specialist." It's role-play. The AI is not a hydrologist. But it reads your results differently. I called this persona Doctor Wade Storm.
Wade Storm noticed what I hadn't: every model that learned anything scored worst in 2023. Maybe not a model problem. Maybe a data problem. Even a great chef can't fix spoiled vegetables.
accepted:

## slide rain
object: picture:images/rain.png
text:
notes:
Wade Storm was right. In 2023 the rain gauge at the lake went offline, and four small bugs in my pipeline quietly turned the missing readings into zero.
A whole year of rain became a dry year. No crash, no error. That's the scariest kind of bad data: the kind that looks fine.
accepted:

## slide lesson
object: picture:images/lesson.png
text: Ride the flow, or take the wheel
notes:
Here's the lesson I'd pass on. I didn't dive deep into every one of Wade Storm's pointers. I'm not a meteorologist; I rode the flow.
But you have to learn when to ride the agentic flow, letting the AI run the work step after step on its own, and when to take it into your own hands, or it drifts. What decided which changes stayed was measurement, not trust.
That's the centaur again: the machine explores, the person decides.
accepted:

## slide one_day
object: chart:one_day
text: One day ahead
notes:
So what came out of it? Start with a simpler question: tomorrow. Given today's real lake and the real weather, how well can we tell tomorrow's change?
The model scores {day_ahead.model.r2}. The usual change for the season scores {day_ahead.seasonal.r2}, and "the lake stays the same" scores {day_ahead.zero_change.r2}. Same days, same ruler, and again a best case.
accepted:

## slide timeline
object: chart:timeline
text: What moved the score
notes:
This is the history of that one-day score, and every step is labelled with what caused it.
It started at {history.c3a72b3.r2}. The rain fix, and then six simple fixes Wade Storm suggested, took it to {history.ac2ede5.r2}. One example: tell the model not just how much it rained, but how hard. A downpour runs off into the river; a drizzle soaks into the ground. I credit both, and every fix earned its place by measurement.
That was the biggest step by far, and it was both: a data fix and six model changes, together. After it the moves were small, and mostly data. On our freeze it scores {day_ahead.model.r2}.
accepted:

## slide one_week
object: chart:one_week
text: One week ahead
notes:
Now the week. Seven days ahead, starting from one real day and never peeking inside the week, the champion scores {champion.r2}, as a best case. "The lake stays the same" scores {baseline.zero_change.r2}. The margin is {margin.zero_change.r2}. Skill fades with distance, but a week holds.
One caveat for the technical people: this is daily volume change, not the level. The level moves slowly, so a score on level would look flattering.
And this week's forecast is in the app, for you to check against the lake.
accepted:

## slide push
object: picture:images/push.png
text:
notes:
Then Adnan pushed me further: what about the long term? I warned him I didn't expect good results, and I tried anyway.
These were shots in the dark, and I'll say so. The weather service's extended forecast, as an input, which turned out not to be available. A forecast driven by temperature alone. A set of regional climate models under two global-warming scenarios, which you can see on the app's climate page. And to rebuild the past back to 1960: the sun's radiation above the atmosphere, computed from astronomy, with the gap between day and night temperatures as a clue to cloud and rain.
Most missed. One partly hit: a simple soil-moisture bucket, the ground's memory of rain, gave some skill in winter, two to four weeks ahead.
accepted:

## slide frontier
object: chart:frontier
text: How far ahead can we see?
notes:
Here is the frontier on one slide. Each panel is measured its own way.
One week: skilful. Two to four weeks: some skill in winter, thanks to that soil memory, and none in summer. Both are best cases.
On the right, the summer red line, with a seasonal method, not machine learning. Replayed for every crossing since {crossing.first_year}: with two weeks' to a month's warning, it misses the date by about {crossing.paired.scaled.mae_14_30} days. With two to three months, by about {crossing.paired.scaled.mae_60_90}, and there the plain seasonal average does better, at {crossing.paired.unscaled.mae_60_90}. And {crossing.never_crossed} of its {crossing.issued} forecasts never reached the line at all, every one issued two months or more ahead.
The frontier is where the data runs out.
accepted:

## slide silent
object: picture:images/silent.png
text:
notes:
So what's missing? Three challenges, and each one applies to you.
First: bad data hides silently. A single dash in a weather file became a zero, and a whole year of rain disappeared.
This applies to you: when a number looks wrong, fix it at the source, where it entered. Don't patch it downstream.
accepted:

## slide sensors
object: picture:images/sensors.png
text:
notes:
Second: records start, stop and change names. The Sede Nehemya station on the Jordan stopped in {data.flow.sede_nehemya.end}, and the Yarmuk record ends in {data.flow.yarmuk.end}. The station I first took as the lake's outflow, the Baptism Site, turned out to be on the lower Jordan, near the Dead Sea, not at the lake's outlet. The champion doesn't use it, but some of the other Olympics models do.
My model's table starts in {data.gold.start}, where the files I could download line up. Some of the weather stations go back further, so an earlier start may well be possible.
This applies to you: every data feed needs a backup source, and an alarm that rings when it goes quiet.
accepted:

## slide share
object: picture:images/share.png
text:
notes:
Third, and most critical: human consumption. Pumping and abstraction from the lake. That data wasn't available to me at all. The human hand on the water balance is invisible to my model.
This applies to you: if you hold data like this, share it.
And that's my first takeaway: more people handling data, in more advanced ways, and sharing it, is a much better starting point than any model.
accepted:

## slide brain
object: picture:images/brain.png
text:
notes:
The second takeaway: build expertise. Dive deep into fields that aren't yours, and keep improving your own model: the human brain.
accepted:

## slide close
object: chart:close
qr: app
text: Better data, not bigger models
notes:
Back to where we started. The lake, under the red line, waiting to see which winter comes.
My results are modest. They're nothing compared to what time, progress, and real cooperation between industry and institutions can reach, at scale: better decisions, and better care for the environment we all live in.
That's the centaur. Not the strongest player, not the strongest machine, but a good process, with people deciding what matters.
The code in the corner opens the app, with today's level. Thank you.
accepted:
