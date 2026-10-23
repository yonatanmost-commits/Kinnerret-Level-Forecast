# Kinneret Level Forecast — Talk Script

## Opening

On my first year here at Kinneret, I walked all the way to the island in front of campus. Before I graduated, the waves took their toll on the wooden market stands on the Tiberias promenade. The lake knows its ups and downs, and right now, we are under the red line once again. So which winter is coming? One like 2018/19, taking us almost 3 m higher, or more like 2024/25, drying us 2 m lower? The lake is our national backup. And it matters: this autumn the algae bloom put us in front of hard decisions. Having a reliable forecast of the lake's level could help us know how urgently we need the water, and how much time we can dedicate to solutions directed at the source. So which will it be?

I'm not the first to ask. The field has plenty of professional work. Researchers at the lake's research center have developed a physical model, following the rain all the way to the river. The Hydrological Service takes this winter to calculate next year's water, and the Water Authority presents scenarios: what a wet winter would do, and where a dry one will leave us. The Great Lakes actually have a published level forecast, 6 months ahead. For the Kinneret I couldn't find one, and that's the small gap I happened to fit into.

It started in a data science course in my master's degree, taught by Adnan Agbaria, my co-author and the one I owe the credit for getting me here. He gave us an open project, and I chose a weekly forecast. It seemed possible, based on the IMS weather forecast being pretty good most of the time. What I didn't think was doable was a year ahead, but Adnan talked me into trying. This is the app. It collects new data every day, cleans it, trains the models and shows the forecasts, a week and a year ahead. I'm going to tell you how it works, and how much you should trust it.

## The centaur

This is a centaur, half human, half horse. In chess, a centaur is half human, half machine. It started when Kasparov, then world champion, lost to Deep Blue, an IBM machine, in 1997. What he did next was join the computer, to play as a team. In 2005 a contest was held where anyone could enroll, with any machine. Grandmasters came, supercomputers played, and the winners? A football coach and a DBA, two amateurs, with three regular computers. Well, in hydrology and machine learning I'm an amateur, like those two, so keep that in mind while I show you how it works.

## The data

So everything starts in the data sources. In this case: the level, the Jordan flow rate, and the weather. I source them by API, by scraping, and sometimes by email. By the way, send thanks to Rita of the Hydrological Service. Each source has its own shape, so you clean it and organize it in a daily table, then add any calculated columns you like. And the one thing to look out for: 2023 kept getting the worst training results, so I asked Claude to check, and it turned out to be an offline winter gauge. The whole winter looked dry. Having a good dataset must be more important than which model you use.

## The models

So which model did I use? I tried more than a dozen, and ended up with two. Classic ML: gradient boosting. It calculates hundreds of decision trees: did it rain more than 20 mm this week? Is it winter? Then it uses all those trees together to create a single prediction. And a deep learning model called a GRU, a type of neural network. It reads the values day by day, forming a type of memory that is passed all the way through and creates the prediction at the end of the line. So which one is better, and for what? And how did I check?

## How I checked

What I did is run many small comparisons, where each run is an actual model training on the data, and an error check of its prediction against real past weather. Each comparison is two identical runs: same data, same calculation methods, with one tweak. A change in the model, in its implementation, or in the dataset. The method with the smaller error persists.

A few of the more significant ones: first, comparing different models on a certain time step. For a week's prediction, GBR won. It turned out to be better where the weather forecast is closer to the actual weather. For a year ahead, based on an average of past winters, the neural network had much better results.

An example of a calculation method: do I use today's last weather reading as a benchmark for a direct prediction, with a leap in time? Or do I use each day's prediction as a basis for the next day, and risk error propagation? For a year, they tied, so I chose direct. In other cases this test did go one way or the other, and I'll show how it shaped my calculation method soon.

A big dilemma was which seasonal forecast model to use. I found Copernicus has a weak prediction, but one that was persistent over various models and methods.

## Copernicus

Let's take a deep dive into how the Copernicus data actually looks. These are their forecasts, year by year since 2012, on a Y axis relative to an average winter. And these [click] are the actual yearly rain gauge results at the Tzemach measuring station. You can see that the Copernicus forecasts are usually in the right direction, pretty good at predicting whether the winter is wet or dry, but in general they understate, falling short of the real rain. So we did what you do with a friend who always understates: we gave it a measured nudge in its own direction, and added an error range of 80%, both measured and based on actual data. Even then, we still missed 5 out of 14. [Open question: an honest 80% range should miss about 3 of 14. Is 5 a sign the range is too narrow, or just small-sample noise?] So Copernicus didn't end up as an input, but we did use it as a way to lean the result in its direction.

## Putting it together

To put it all together, we end up with two different methods for two different time gaps. To predict a week ahead, where the IMS gives a good forecast, classic ML is used to predict river flow day by day, using one prediction to make the next one, while the level prediction uses the direct method, combined with the river prediction. The river flows turned out to be highly predictable given the rain forecast, and highly correlated to the lake changes, making them a key step in between.

To make long-term predictions, from a month to a year, a direct approach is implemented, avoiding amplified error propagation, and as mentioned, a GRU neural network is the model that had the smaller error doing so. Each winter since 2012 is fed to this model's input, a method developed for the Great Lakes prediction, and the result is a range that is then leaned toward the Copernicus seasonal prediction.

## Can you trust it?

So can you trust it? And how far? Here are the measured errors on past winters. For a week ahead, the classic method is 6 millimeters better, still with a 2 cm average error. For a year ahead, the neural network has an 85 cm average error. The classic method got as low as 56 cm when given the real weather, but a year ahead we don't have that data, and with a forecast, the network is better.

## Three limits

Three things limit how far I could see. The first is the human factor: how much did people take out of the lake, by pumping, or by opening the dam? This is a kind of limit I have, as I lean on open sources, yet the decision makers don't, and this is exactly the kind of tool made to facilitate planning future consumption.

The second is the weather. Next year's rain in the Middle East is known to be unpredictable, and a changing climate isn't making it easier, so the range of uncertainty seems to be here to stay.

The third limit is the bottleneck: how well can we model the lake in relation to the weather? It's a question of knowledge, a question of tools.

[Photo] In the 1930s, our great-grandparents used a crane to build a dam, using technology to improve future water security. We have new tools in our hands, and I know some people are afraid of the leap we are living through, but I see the great potential in doing what Kasparov did: leveling up our abilities, and directing that to improve future water security.

## The forecast

I will share the forecast, but I'll start by saying I'd rather you take the intention and method, rather than the limited prediction itself.

This is where we are today, and the grey lines are every single winter since 2012. Then the teal range has the lean towards the seasonal forecast, and that's why it's slightly above. This is the middle of it all: the actual prediction the model gives for each month, if you want to see a point rather than a span. It averages 1 m above where we are right now, crossing the red line upwards in late February, and staying above. One in three winters does cross the red line downward again. That's not a promise; it's what happens if I run them all. And 2 in 10 are out of this range, meaning the prediction would be wrong. It's possible that it will be even drier, God forbid, but I hope I'm wrong the other way, and we will open the Degania dam.
