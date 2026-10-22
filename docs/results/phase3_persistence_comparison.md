# Phase 3 — persistence filter: tuning sweep and REQ-11 comparison

Channels: 81. Each channel's test split is cut in half by index: the first half tunes persistence_n (this section), the second half is the held-out report (the next section). Nothing here is tuned on the data it is reported on.

## Tuning sweep (first half of each channel)

| persistence_n | TP | FN | FP | Precision | Recall | F1 | Point FPR |
|---|---|---|---|---|---|---|---|
| 1 | 14 | 6 | 26 | 0.350 | 0.700 | 0.467 | 0.0147 |
| 2 | 14 | 6 | 21 | 0.400 | 0.700 | 0.509 | 0.0097 |
| 3 | 6 | 14 | 18 | 0.250 | 0.300 | 0.273 | 0.0044 |
| 5 | 0 | 20 | 2 | 0.000 | 0.000 | 0.000 | 0.0004 |
| 8 | 0 | 20 | 0 | 0.000 | 0.000 | 0.000 | 0.0000 |

**Chosen persistence_n = 2** (highest F1 on the tuning half).

## REQ-11: with vs. without the filter (second half of each channel, held out from tuning)

| | TP | FN | FP | Precision | Recall | F1 | Point FPR |
|---|---|---|---|---|---|---|---|
| Without (persistence_n=1) | 56 | 28 | 12 | 0.824 | 0.667 | 0.737 | 0.0323 |
| With (persistence_n=2) | 53 | 31 | 13 | 0.803 | 0.631 | 0.707 | 0.0283 |

Point FPR change: 0.0323 -> 0.0283 (-0.0040). Recall change: 0.667 -> 0.631 (-0.036).
