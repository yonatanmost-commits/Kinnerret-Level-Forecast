# Kinneret Conference talk: the script
<!-- Source of truth for the deck. Numbers only as ledger placeholders in braces; build_deck.py
     fills them from numbers_ledger.json and stops on any digit typed outside a placeholder or the
     allow line below. Budget: about fifteen minutes spoken. -->

allow: 2023 | 2005

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
Here is every year since twenty twenty, laid on top of each other. The red one is this year. It's the lowest line on the chart, and it's still going down.
What happens next depends on one thing: the winter.
If this winter is like {scenario.dry.season}, the driest of the last twenty, the lake keeps falling. It ends the spring {scenario.dry.change_m} lower, at {scenario.dry.spring_m}, deeper under the red line. That means leaning even harder on desalination, a lake under stress, with worse water quality and more risk of algae, and pressure that spreads out in wider circles, to farming and to everyone who depends on this water.
If it's like {scenario.wet.season}, the wettest, the lake climbs {scenario.wet.change_m}, to {scenario.wet.spring_m}, back above the red line. Then the whole conversation changes.
Both of those are real winters, not forecasts. So which one is coming? And wouldn't it help every decision in this room to know a little earlier?
accepted:

## slide centaur
object: picture:images/centaur.png
text:
notes:
Before I answer, a picture. This is a centaur, half human and half horse. The picture is AI-made.
After Garry Kasparov lost to a chess computer, he started asking a different question: what happens when a human and a computer play as one team? Chess players call those teams centaurs.
In 2005 there was an open freestyle chess tournament on the internet. Anyone could enter, with any computer help they liked. The winners were not grandmasters, and not the strongest machine. They were two amateur players from the United States, running three ordinary computers, with a very good way of working together with them. The process beat the raw strength.
And today Terence Tao, one of the great mathematicians alive, works on real research problems with AI tools at his side. The AI explores and checks; he decides what matters.
Keep the centaur in mind. We'll come back to it.
accepted:

## slide who
object: picture:images/qr.png
text: Yonatan Most · Adnan Agbaria
notes:
So who am I? Let me start with what I'm not. I'm not a meteorologist. I'm not a data analyst. I'm not a software engineer.
I'm a process engineer. I work with water treatment, pumps and pipes. This work is joint with my co-author, Adnan Agbaria, from Kinneret Academic College.
This code opens the app we built. It shows today's level and this week's forecast, so you can check everything I say against today's numbers.
accepted:

## slide olympics
object: chart:olympics
text: Eight models, one race
notes:
From here on, every number I show you was measured on one data freeze, {freeze_date}, so they all agree with each other. Only today's level comes from the app.
So I did what everyone does. I held a Model Olympics.
Eight models, each one trained to forecast the lake's daily volume change: how many cubic metres the lake gains or loses each day, over the next week.
To score them I use R squared. It's a score where one is a perfect forecast and zero means you did no better than guessing the average.
On the right of this chart are the slow models, and higher is better.
The winner, in red, is the champion: classic machine learning, called gradient boosting. Think of many small decision trees, each one fixing the mistakes of the one before. It scored {champion.r2}, and was trained and tested in {olympics.baseline_gbr.runtime_s}.
And the neural network? The one you'd expect to win in an AI session? It scored {olympics.gru.r2_mean}. About zero. Training and testing it took {olympics.gru.runtime_s}, to learn nothing.
This is the soft drop. The fancy model didn't save me.
accepted:

## slide pivot
object: picture:images/pivot.png
text:
notes:
Here is a picture I keep in my head. A brilliant chef, and a basket of spoiled vegetables.
It doesn't matter how good the chef is. The dish is only as good as what goes into the pot.
After the Olympics I stopped asking "which model?" and started asking "what am I feeding it?"
That is the pivot of this talk. The bottleneck was never the model. It was the data.
accepted:

## slide pipeline
object: picture:images/pipeline.png
text:
notes:
You all know this picture better than I do. Raw water comes in, you treat it in stages, and clean water comes out.
Data works the same way. Raw files from the Water Authority, the Hydrological Service and the weather service come in dirty: gaps, broken sensors, odd codes.
I built a treatment train for them. The first stage keeps the raw data exactly as it came. The second cleans it and lines every source up on the same day. The last stage blends it into one table the model can drink.
And I built it with an AI at my side. I described what I needed in plain words, and it wrote the code with me, step by step. I checked every step.
accepted:

## slide persona
object: picture:images/persona.png
text: The newest oldest trick in the book
notes:
Now I want to show you the newest oldest trick in the book.
You tell the AI: "You are a hydrology and meteorology specialist." That's it. It's role-play. The AI is not a hydrologist, and I'll be honest about that. But it reads your results in a different way.
I called this persona Doctor Wade Storm.
Wade Storm looked at my results and said something no one else had: every single model scored worst in 2023. Maybe that's not a model problem. Maybe it's a data problem.
accepted:

## slide rain
object: picture:images/rain.png
text:
notes:
So I followed it up. And Wade Storm was right.
In 2023 the rain gauge at the lake went offline. That happens. But four small bugs in my pipeline, one after the other, quietly turned those missing readings into zero.
A whole year of rain had become a dry year. Nothing crashed. No error. The model simply learned from a year that never happened.
That is the scariest kind of bad data: the kind that looks fine.
accepted:

## slide timeline
object: chart:timeline
text: What moved the score
notes:
This chart is the honest history of my champion's score, and every step is labelled with what caused it.
In May the champion scored {history.c3a72b3.r2}. We fixed the missing rain, and then made six simple fixes Wade Storm suggested. One example: tell the model not just how much it rained, but how hard. A downpour runs off into the river; a drizzle soaks into the ground.
Together, the rain fix and the six fixes took the score to {history.ac2ede5.r2}. I credit both, and every fix earned its place by measurement, not by the persona's authority.
Notice the blue steps. Most of the movement here came from data, not from the model. Even a skipped quality filter shows up in the score, and so does putting it back.
On our data freeze the champion scores {champion.r2}.
accepted:

## slide one_week
object: chart:one_week
text: One week ahead
notes:
So how good is it, really, one week ahead?
The honest test is to compare it with the simplest forecast there is: the lake stays the same. No change tomorrow, no change next week.
That simple forecast scores {baseline.zero_change.r2}. The champion scores {champion.r2}. The margin is {margin.zero_change.r2}.
One plain caveat for the technical people: this score is on daily volume change, not on the level itself. The level changes slowly, so a score on level would look flattering. Volume change is the hard part, and it is the part that matters.
accepted:

## slide wall
object: picture:images/wall.png
text:
notes:
Then I tried to look further. Two weeks, a month, the whole summer.
And I hit a wall.
I want to be clear about what this wall is. It is not where the model failed. It's where the data runs out.
accepted:

## slide frontier
object: chart:frontier
text: How far ahead can we see?
notes:
This is the frontier, on one slide. Each panel is measured its own way, so read them side by side, not as one scale.
On the left, one week: the champion is skilful.
In the middle, two to four weeks. In winter we keep some skill, because the ground remembers recent rain. In summer, none. And these bars are a best case: they were measured as if we knew the weather ahead. A real forecast would do worse.
On the right, the summer red line. This one is not machine learning. It's a seasonal method: the usual summer decline, scaled to the last few weeks.
We replayed it for every crossing of the red line since {crossing.first_year}, issuing a forecast every day from the last rain. With two weeks' to a month's warning, it misses the crossing date by, on average, about {crossing.paired.scaled.mae_14_30} days. With two to three months' warning it's off by, on average, about {crossing.paired.scaled.mae_60_90} days, and there the plain seasonal average does better, at about {crossing.paired.unscaled.mae_60_90}. And {crossing.never_crossed} of its {crossing.issued} forecasts never reached the line at all, every one of them issued two months or more ahead.
The frontier is where the data runs out.
accepted:

## slide silent
object: picture:images/silent.png
text:
notes:
So here is what's missing, as three lessons you can take home.
First: bad data hides silently. A single dash in a weather file became a zero, and a whole year of rain disappeared.
This applies to you: when a number looks wrong, fix it at the source, where it entered. Don't patch it downstream.
accepted:

## slide sensors
object: picture:images/sensors.png
text:
notes:
Second: sensors and stations die. During this project a river station was retired and replaced, and the lake's radiation sensor went dark.
This applies to you: every live data feed needs a backup source, and an alarm that rings when it goes quiet.
accepted:

## slide share
object: picture:images/share.png
text:
notes:
Third: the data you need most is often someone else's.
I have no pumping data at all. Not from the lake, not from the catchment upstream. The biggest human hand on the water balance is invisible to my model.
This applies to you: the most valuable thing you can do for forecasting may be to share the data you already have.
accepted:

## slide close
object: chart:hook
qr: app
text: Better data, not bigger models
notes:
Let's go back to where we started. The lake, under the red line, waiting to see which winter comes.
I didn't get a better forecast by finding a bigger model. I got it by cleaning the data, and a non-specialist can do that now, with an AI as a partner, not as an oracle.
That's the centaur. Not the strongest player, not the strongest machine, but a good process, with the person deciding what matters.
What would move this line further? Pumping and abstraction data. And the rain forecast for the weeks ahead, which today we simply don't have.
The AI opportunity here is not AI as the predictor. It's AI as the partner that helps us build clean data. Better data is what unlocks better forecasting.
The code in the corner opens the app, with today's level. Thank you.
accepted:
