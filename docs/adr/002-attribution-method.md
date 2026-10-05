# ADR 002 — Channel attribution method (closes TBD-3)

**Status:** accepted, 2026-10-05 · **Phase:** 1 (spike) · **Requirement:** REQ-7

## Decision

Attribute each anomaly by **ranking the satellite's channels by their own detector's error**. Each channel's smoothed prediction error is standardised by that channel's training errors, and `contribution_score` is the channel's share of the total among channels above threshold. No separate attribution model and no SHAP-style computation.

## Question

SRS TBD-3 left two options open: rank channels by reconstruction/prediction error, or use a SHAP-style attribution. Which one names the faulty channel more often, and at what cost?

## Experiment

`ml/spike/attribution.py`. Three "virtual satellites" were built by replaying four channels side by side (two SMAP groups, one MSL group). At every sampled timestep where **exactly one** of the four channels is inside a labelled anomaly, each method ranks the four channels; a hit is when the labelled channel is ranked first. A random guess scores 0.25.

| Method | What it needs |
|---|---|
| **error-rank** | Nothing extra. Reuses the per-channel LSTM predictors' errors (config 100/80, EWMA span 30). |
| **joint-recon** | One extra multivariate LSTM autoencoder per satellite; ranks channels by their share of its reconstruction error. |
| **joint-shap** | The same extra model, plus exact Shapley values over channels (16 forward passes per window; an "absent" channel is replaced by its training mean). |

Two scores are reported. **Point hit rate** is the share of sampled anomalous timesteps with the right channel on top. **Event hit rate** asks, per labelled anomaly, whether the right channel is on top at the anomaly's strongest sampled point, which is when an alert would be raised.

## Results

| Group | Events scored | error-rank (point / event) | joint-recon (point / event) | joint-shap (point / event) |
|---|---|---|---|---|
| SMAP-1 (S-1, E-1, A-2, F-1) | 4 | 0.607 / **1.000** | 0.200 / 0.000 | 0.150 / 0.000 |
| SMAP-2 (G-7, T-1, P-4, P-1) | 8 | 0.509 / **0.875** | 0.297 / 0.375 | 0.268 / 0.500 |
| MSL-1 (F-7, P-10, D-14, T-13) | 5 | 0.649 / **0.800** | 0.474 / 0.600 | 0.722 / 0.600 |
| **All events** | **17** | **15 / 17 (88%)** | 6 / 17 (35%) | 7 / 17 (41%) |

Cost per scored window: error-rank adds nothing; joint-recon about 0.2 ms; joint-shap about 3 ms, plus 2–23 s to train the extra joint model per satellite.

## Why error-rank

- **It is the most accurate here.** It named the right channel for 15 of 17 anomalies; the SHAP-style method managed 7.
- **It is free.** The detector already produces the per-channel errors, so attribution adds no model, no training and no latency. That protects the 1-second update target (SRS §5.1).
- **It is easy to explain.** "This channel's readings deviated most from what its model expected" is something an analyst can read without training (SRS §5.4, usability).

## Limits of this evidence

- **Small sample:** 17 labelled anomalies across three hand-built groups.
- **The joint model was at a disadvantage.** The grouped channels come from unrelated recordings, so there is no real cross-channel structure for a joint model to learn. On a satellite whose channels genuinely interact, a joint model with Shapley attribution could do better. That is not the data this project has.
- **Mid-anomaly accuracy is lower.** The point hit rate (0.51–0.65) is well below the event hit rate, so the top-ranked channel can change during a long anomaly. Phase 3 should fix the attribution at the alert's strongest window rather than recomputing it at every timestep.
- Only anomalies on a single channel at a time were scored. Simultaneous multi-channel anomalies are not tested.

## Consequences for Phase 3

- `explain/attribution.py` implements error-ranking; `ATTRIBUTION.contribution_score` is the channel's share of the standardised error.
- Record the **attribution hit rate** on the reporting slice as a headline result alongside the false-positive comparison.
- If no channel exceeds its threshold, record `unknown` (state diagram assumption 6).
