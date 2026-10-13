# Q&A prep: Kinneret Conference talk
<!-- Numbers only as ledger placeholders in braces; build_deck.py checks this file like talk.md.
     The remaining questions (LSTM / deep learning, R² on level or volume, pumping, how far ahead,
     the seasonal baseline) are written in plan step nine. -->

allow:

## Why did the neural network take so long?
Training and testing the neural network took {olympics.gru.runtime_s} on a laptop CPU with no GPU. A GPU would cut that a lot, but speed wasn't its problem: it scored {olympics.gru.r2_mean}, about zero.
