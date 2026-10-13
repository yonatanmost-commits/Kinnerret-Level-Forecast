# Q&A prep: Kinneret Conference talk
<!-- Numbers only as ledger placeholders in braces; build_deck.py checks this file like talk.md.
     The remaining questions (LSTM / deep learning, R² on level or volume, pumping, how far ahead,
     the seasonal baseline) are written in plan step nine. -->

allow:

## Why did the neural network take so long?
Training and testing the neural network took {olympics.gru.runtime_s} on a laptop CPU with no GPU. A GPU would cut that a lot, but speed wasn't its problem: it scored {olympics.gru.r2_mean}, about zero.

## Is the forecast in the app your champion?
Not exactly. The app runs the same two-stage gradient boosting idea, but its second step is the direct version: it predicts each of the next seven days straight from today's state, instead of chaining day to day. That is a close relative of the Olympics runners, not the weekly champion's chain, so the app's forecast and the champion's score are not the same thing.

## The Baptism Site is near the Dead Sea. Are your results wrong?
Not the champion's. The champion never uses the Baptism Site. Some of the other Olympics models use it as yesterday's outflow, so their scores carry that mistake, and I say so in the talk.

## Why does your data start where it does?
The model's table starts in {data.gold.start}, where the files I could download line up: the weather downloads start a few months earlier, and so does the Baptism Site record. Some weather stations around the lake go back further, so an earlier start may well be possible. The river stations that stopped, the Yarmuk in {data.flow.yarmuk.end} and Sede Nehemya in {data.flow.sede_nehemya.end}, are records that end; they are not the reason for the start date.

## Why one week? Where does "good for about a week" come from?
It's my reasoning, not something I measured. The model needs the weather of the coming days, and weather forecasts lose most of their skill after about a week: further out, they are not much better than the usual weather for the season. That is the common experience of weather services. And every score in the talk uses the weather that actually happened, so it is a best case: a real forecast would only do worse.
