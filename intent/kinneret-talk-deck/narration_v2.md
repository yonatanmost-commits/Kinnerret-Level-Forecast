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

Status: slides 1-5 agreed in chat; 6 to the close is draft v2 (storytelling pass).
Parked: slide-6 order (the record: race -> Wade Storm -> 2023 fix), on-screen text
(centaur = "Centaur"), length (target about 1,800 words).

## 1. lake-years video (agreed)
In my first year here at Kinneret, the lake was so low that I walked all the way out to the island in front of the campus.
By the time I graduated, the waves were flooding the Tiberias promenade, taking their toll on the wooden market stands. Today, those stands stand high above the water once again.
The lake's ups and downs aren't new. But today it sits below the red line, and it is our national backup. A low lake means leaning harder on desalination, water quality and algae at risk, and pressure that spreads out in wider circles.
So which winter is coming? One like twenty eighteen to nineteen, the best of the last twenty, that lifted the lake back up? Or one like twenty twenty-four to twenty-five, the worst, that kept it falling?
Imagine knowing that a year ahead. Hold on to that thought: by the end of this talk, I'll tell you honestly how far ahead I got.

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

## 4. the pipeline (agreed)
I'm a process engineer, so let me draw this like a treatment plant. Three stages.
One: gather. Most sources have an API: you ask, and the data comes back. That was much easier than I expected. Most. One had no API at all, and one refused to talk to me.
Two: treat. Each source gets its own treatment, for its own format and its own noise. Then it all goes into one table, one row per day, cut to the dates where every source is full.
Three: enrich. Add what the data doesn't say on its own. How thirsty the air is. How much water the lake loses to evaporation. What happened yesterday, and the day before.
Data people call these stages bronze, silver and gold. Then run a model, look at the score, and go back to one, two and three. Again and again.

## 5. gather (agreed)
The lake's level comes from the Kinneret Authority's website. No API, so I scraped it: ask the page for a date, read one number off it. Works perfectly from my laptop. From a cloud server, the site slams the door. So to this day, the daily update runs on my own computer.
The rivers were the real hunt. The Hydrological Service's live site only answers you if you look like a web browser. And it only remembers the last two days. Anything older, you ask for by email.
Is anyone here from the Hydrological Service? (wait) Thank you. You answered all my emails.
I was sure the Baptism Site was Yardenit, where the Jordan leaves the lake. Then I asked Claude to draft one more email to them, and there it was, in the draft: near Jericho. There are two baptism sites on the Jordan. I had the one by the Dead Sea.
(pause) My champion model never used it. Some of the others did.
Line it all up, and the table where every source is full starts in September 2012.

## 6. the race (v3; chart: the race)
Now the model. The web said: use XGBoost. Claude quietly built something plainer: gradient boosting. Many small decision trees, each one fixing the mistakes of the one before.
It forecasts the way water flows: the river first, then the lake, one day at a time. And every morning it restarts from the last real measurement, so the errors don't snowball.
So I raced them. Eight models, scored from zero, no better than guessing the average, to one, perfect. And always a best case: the models get the weather that really happened.
The plain one won. Every time.

## 7. the neural network (v3; chart: two stopwatches)
Then I tried to beat it with the AI everyone talks about: a neural network. Seventy-one minutes of training. Its score: zero. The plain model took four minutes.
That's when I understood. The answer wasn't a bigger model.

## 8. the dash (v3; picture)
Because something else was on that race chart. Every model that worked stumbled in the same year: twenty twenty-three. I didn't see it. My AI hydrologist did, a persona I called Doctor Wade Storm. If every model fails the same way, he wrote, it's the data, not the model.
He was right. That year, the lake's rain gauge was offline. It wrote a dash for every missing reading, and my pipeline quietly turned each dash into a zero. A whole winter of rain, gone. No error. No crash.

## 9. better data (v3; chart: score before and after)
I fixed it, and added a few of his simple ideas, like telling the model how hard it rained, not just how much. The score went from 0.69 to 0.76, in two days. Not a new model. Better data.
I didn't check every idea he had. I rode the flow. But I kept one hand on the wheel: nothing stayed unless the score said so. That's the centaur. The machine explores; the person decides.

## 10. one week (v3; chart: one real week, forecast against the lake)
So, one week. This is a real one: what the model said on the first day, and what the lake did.
A week ahead, it scores 0.73. "The lake stays the same" scores zero. I set out for one week, and the week holds.

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
- the race: eight models, score per test year, at the first Olympics (30 May 2026, before the fix), dated; 2023 must visibly dip.
- two stopwatches: gradient boosting 4 min / 0.73 against the neural network 71 min / about zero (freeze).
- score before and after: 0.694 -> 0.758 (May 2026), dated.
- one real week: forecast issued on day one against the lake, the week picked by a stated rule (not cherry-picked).
- skill fading with lead time: one line, from the long-range evaluation.
- one summer replayed: a month ahead, predicted crossing date against the real one (most recent crossing).
