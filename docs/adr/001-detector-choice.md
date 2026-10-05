# ADR 001 — Detector choice (SRS Increment 0 spike)

**Status:** accepted, 2026-10-05 · **Phase:** 1 (spike) · **Requirements:** REQ-3, REQ-4

## Decision

**Go.** Phase 2 builds the baseline detector as a **per-channel LSTM predictor with non-parametric dynamic thresholding**, the method the SRS names (Hundman et al., 2018), using a **smaller model than the paper's**: 100 steps of history and 2 × 80 LSTM units.

### Starting settings for Phase 2

| Setting | Value | Note |
|---|---|---|
| Model | LSTM predictor, 2 layers × 80 units, dropout 0.3 | one model per channel |
| Input | 100 timesteps × all features (telemetry + command flags) | the paper uses 250 |
| Output | next 10 telemetry values | the error uses the first predicted step only |
| Training | Adam, lr 0.001, batch 64, MSE, ≤ 20 epochs, early stopping (patience 3, min Δ 0.0003) on the last 20% of training windows | |
| Error | absolute error, EWMA-smoothed, span 105 | span to be re-tuned in Phase 3 |
| Threshold | dynamic: window 2,100 points, step 70, z from 2.5 to 12, error buffer 100, pruning p = 0.13 | paper defaults |
| Normalisation | none added | the release is already scaled to about [-1, 1] |

## Question

Which detector configuration works best on SMAP/MSL, and can it be trained on a laptop CPU? This was the project's one real technical unknown (SRS §1.1, §4.2).

## Method

Code: `ml/spike/` (throwaway). Raw results: `ml/spike/results/*.json`. Tables: [docs/results/phase1_spike.md](../results/phase1_spike.md).

- **Channels:** 16 of the 81 labelled channels. 4 **tuning** channels (P-1, E-8, T-4, C-1; 7 labelled anomalies) and 12 **held-out** channels (S-1, E-1, A-2, G-7, T-1, P-4, F-1, F-7, P-10, D-14, T-13, M-6; 22 labelled anomalies), mixing SMAP and MSL, point and contextual anomalies.
- **Candidates:**
  - **A — LSTM predictor** (SRS baseline), three sizes: 250/80 (the paper's), 100/80, 100/40.
  - **B — LSTM autoencoder**, two sizes: 100/64 and 50/32.
  - **Floors:** rolling z-score on the raw value, and an Isolation Forest over 50-point windows.
- **Thresholds tried on every error series:** the paper's dynamic threshold, and a static threshold (mean + k·std of training errors, k = 3, 5, 8), each with EWMA span 30 and 105.
- **One evaluator for all:** event-level precision, recall and F1 by the paper's overlap rule (a labelled anomaly counts as found if any flagged point falls inside it; a flagged event that overlaps no label is a false alarm), plus the **point false-positive rate** (share of normal points flagged).
- **Qualifying rule:** a variant qualifies only if it flags **at most 5% of normal points**. Event-level precision cannot catch a detector that raises one enormous alarm: static thresholds scored precision 1.0 on the tuning channels while flagging 37% of normal points.

## Results on the 12 held-out channels (22 labelled anomalies)

| Candidate (threshold) | Precision | Recall | F1 | False alarms | Point FPR | Train time / channel |
|---|---|---|---|---|---|---|
| A 250/80 (static k8, span 30) | 0.889 | 0.727 | **0.800** | 2 | 3.9% | 222 s |
| **A 100/80 (dynamic, span 105)** ← chosen | **0.938** | 0.682 | **0.789** | **1** | **3.0%** | **36 s** |
| A 100/80 (static k8, span 30) | 0.800 | 0.727 | 0.762 | 4 | 4.2% | 36 s |
| A 250/80 (dynamic, span 105) | 0.929 | 0.591 | 0.722 | 1 | 3.9% | 222 s |
| A 100/80 (dynamic, span 30) | 0.654 | 0.773 | 0.708 | 9 | 8.3% ✗ | 36 s |
| A 250/80 (dynamic, span 30) | 0.640 | 0.727 | 0.681 | 9 | 8.7% ✗ | 222 s |
| B 100/64 (static k8, span 105) — best autoencoder | 0.917 | 0.500 | 0.647 | 1 | 5.0% | 15 s |
| Isolation Forest (static k3, span 30) — best floor | 0.692 | 0.409 | 0.514 | 4 | 3.2% | 0.2 s |
| Rolling z-score (window 100, k8) | 0.317 | 0.591 | 0.413 | 28 | 0.05% | none |

✗ = fails the 5% rule. Training times are medians from the sequential tuning run on an 8-thread laptop CPU, no GPU.

## Why this choice

1. **The LSTM predictor clearly beats the alternatives.** Its qualifying variants score F1 0.72–0.80; the best autoencoder scores 0.65 and the best floor 0.51. The go condition, beating the floor, is met with a wide margin.
2. **The paper-size model is not better here.** With the same threshold (dynamic, span 105), 100/80 scores 0.789 and 250/80 scores 0.722 on the held-out channels. Over all 16 channels it is 0.723 against 0.652. The larger model takes about six times longer to train.
3. **The dynamic threshold is the steadier one.** The top held-out row uses a static threshold, but over all 16 channels that same variant flags 7.2% of normal points and fails the rule, while the chosen variant stays at 2.4% with one false alarm. Static thresholds break on channels whose test errors sit well above their training errors.
4. **Training fits easily on a CPU.** At about 36 s per channel, all 81 channels train in roughly 50 minutes; the 15–30 channels the monitored fleet needs take 10–20 minutes.

## What this evidence does not show

- **The chosen variant's score is optimistic.** The variant picked on the 4 tuning channels (A 250/80, dynamic, span 30; F1 0.727 there) dropped to 0.681 on the held-out channels and failed the 5% rule. Seven labelled anomalies were too few to choose on. The final choice was therefore made using the held-out channels, so 0.789 is not an unbiased estimate. **Phase 2 must re-measure on all 81 channels.**
- **Small samples.** 22 held-out anomalies; one more or fewer detection moves F1 by about 0.03. The gap between the two top rows (16 against 15 detections) is not meaningful.
- **One random seed.** Run-to-run variation was not measured.
- **Recall is below the paper's.** The paper reports about 88% precision and 80% recall over all channels; this re-implementation reaches 94% and 68% on 12 channels. Likely causes are the differences below and the smaller model.
- **Some channels fail outright.** F-1 was missed by every LSTM variant, and T-13 and P-4 were only partly detected.

## Differences from the reference implementation

This is a re-implementation from the paper, not a port of the Telemanom code:
- only the first predicted step is scored (no averaging over the 10-step horizon);
- no second pass over inverted errors (which catches abnormally *low* error regions);
- after the first threshold window, a whole flagged sequence is kept if it touches the newest 70 points, where the reference keeps only the newest points;
- training is capped at 20 epochs with batch 64 (the reference uses 35 and 70).

## Consequences

- **Phase 2:** move the 100/80 predictor and the dynamic threshold into `backend/app/pipeline/detect.py`; train with `ml/train.py`; report precision, recall, F1 and point FPR on all 81 labelled channels as the baseline.
- **Streaming:** the dynamic threshold decides in **batches of 70 points** using the previous 2,100 points, so one replay "window" should be 70 points. The first 2,100 points of a stream need a warm-up rule, and a channel's first 100 points cannot be scored at all.
- **Phase 3:** a 3% point false-positive rate still means frequent short false flags. That is the gap the persistence filter (REQ-8) has to close, and REQ-11 measures how much it does. Re-tune the EWMA span there on a proper tuning/reporting split.
- **ARCHITECTURE.md §5.2** is updated: history 100 instead of 250.
- **Fallback:** if the 81-channel baseline is weak, add the inverted-error pass and horizon averaging first; they are the cheapest steps towards the reference behaviour.
