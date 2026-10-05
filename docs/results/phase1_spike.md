# Phase 1 spike — results

Run on 2026-10-05 on a laptop CPU (8 threads, no GPU), PyTorch 2.14.1. Code in `ml/spike/`; raw numbers in `ml/spike/results/`. Decisions: [ADR 001](../adr/001-detector-choice.md), [ADR 002](../adr/002-attribution-method.md).

**How to read the tables.** Precision, recall and F1 are event-level (a labelled anomaly is found if any flagged point falls inside it; a flagged event overlapping no label is a false alarm). **Point FPR** is the share of normal points flagged. A variant qualifies only if point FPR ≤ 5%. Names: `A 100/80` = LSTM predictor with 100 steps of history and 80 hidden units; `B 100/64` = LSTM autoencoder with a 100-step window and 64 hidden units; `dynamic` = the paper's threshold; `static kN` = mean + N·std of training errors; `span` = EWMA smoothing span.

## 1. Held-out channels (12 channels, 22 labelled anomalies)

| Variant | P | R | F1 | Found | Missed | False alarms | Point FPR | Qualifies |
|---|---|---|---|---|---|---|---|---|
| A 250/80 static k8 span 30 | 0.889 | 0.727 | 0.800 | 16 | 6 | 2 | 0.0392 | yes |
| **A 100/80 dynamic span 105 (chosen)** | 0.938 | 0.682 | 0.789 | 15 | 7 | 1 | 0.0297 | yes |
| A 100/80 static k8 span 105 | 0.842 | 0.727 | 0.780 | 16 | 6 | 3 | 0.0621 | no |
| A 100/80 static k8 span 30 | 0.800 | 0.727 | 0.762 | 16 | 6 | 4 | 0.0421 | yes |
| A 250/80 dynamic span 105 | 0.929 | 0.591 | 0.722 | 13 | 9 | 1 | 0.0391 | yes |
| A 100/80 dynamic span 30 | 0.654 | 0.773 | 0.708 | 17 | 5 | 9 | 0.0826 | no |
| A 100/80 static k5 span 105 | 0.600 | 0.818 | 0.692 | 18 | 4 | 12 | 0.1069 | no |
| A 250/80 dynamic span 30 | 0.640 | 0.727 | 0.681 | 16 | 6 | 9 | 0.0868 | no |
| A 100/80 static k3 span 105 | 0.525 | 0.955 | 0.677 | 21 | 1 | 19 | 0.2268 | no |
| B 100/64 static k3 span 105 | 0.800 | 0.545 | 0.649 | 12 | 10 | 3 | 0.0587 | no |
| B 100/64 static k8 span 105 | 0.917 | 0.500 | 0.647 | 11 | 11 | 1 | 0.0498 | yes |
| B 50/32 static k8 span 105 | 0.684 | 0.591 | 0.634 | 13 | 9 | 6 | 0.1206 | no |
| B 100/64 static k8 span 30 | 0.786 | 0.500 | 0.611 | 11 | 11 | 3 | 0.0375 | yes |
| B 100/64 dynamic span 30 | 0.667 | 0.545 | 0.600 | 12 | 10 | 6 | 0.0529 | no |
| Isolation Forest static k3 span 30 | 0.692 | 0.409 | 0.514 | 9 | 13 | 4 | 0.0323 | yes |
| B 100/64 dynamic span 105 | 0.778 | 0.318 | 0.452 | 7 | 15 | 2 | 0.0186 | yes |
| Rolling z-score, window 100, k8 | 0.317 | 0.591 | 0.413 | 13 | 9 | 28 | 0.0005 | yes |
| Rolling z-score, window 250, k6 | 0.345 | 0.455 | 0.392 | 10 | 12 | 19 | 0.0009 | yes |

## 2. All 16 channels (tuning + held-out, 29 labelled anomalies)

| Variant | P | R | F1 | Found | Missed | False alarms | Point FPR |
|---|---|---|---|---|---|---|---|
| **A 100/80 dynamic span 105 (chosen)** | 0.944 | 0.586 | 0.723 | 17 | 12 | 1 | 0.0238 |
| A 250/80 static k8 span 30 | 0.857 | 0.621 | 0.720 | 18 | 11 | 3 | 0.0717 |
| A 100/80 static k8 span 105 | 0.850 | 0.586 | 0.694 | 17 | 12 | 3 | 0.1229 |
| A 100/80 static k8 span 30 | 0.783 | 0.621 | 0.692 | 18 | 11 | 5 | 0.0712 |
| A 250/80 dynamic span 30 | 0.690 | 0.690 | 0.690 | 20 | 9 | 9 | 0.0741 |
| A 100/80 dynamic span 30 | 0.667 | 0.690 | 0.678 | 20 | 9 | 10 | 0.0710 |
| A 250/80 dynamic span 105 | 0.882 | 0.517 | 0.652 | 15 | 14 | 2 | 0.0332 |
| B 100/64 static k3 span 105 | 0.778 | 0.483 | 0.596 | 14 | 15 | 4 | 0.0458 |
| B 100/64 static k5 span 105 | 0.923 | 0.414 | 0.571 | 12 | 17 | 1 | 0.0427 |

## 3. Tuning channels only (4 channels, 7 labelled anomalies)

| Variant | P | R | F1 | Found | Missed | False alarms | Point FPR |
|---|---|---|---|---|---|---|---|
| A 250/80 dynamic span 30 | 1.000 | 0.571 | 0.727 | 4 | 3 | 0 | 0.0288 |
| A 100/80 dynamic span 30 | 0.750 | 0.429 | 0.545 | 3 | 4 | 1 | 0.0298 |
| B 50/32 static k3 span 105 | 1.000 | 0.286 | 0.444 | 2 | 5 | 0 | 0.0000 |
| A 100/80 dynamic span 105 | 1.000 | 0.286 | 0.444 | 2 | 5 | 0 | 0.0029 |
| A 100/40 dynamic span 105 | 1.000 | 0.286 | 0.444 | 2 | 5 | 0 | 0.0028 |
| Isolation Forest (best threshold) | 1.000 | 0.143 | 0.250 | 1 | 6 | 0 | 0.0000 |
| Rolling z-score, window 100, k4 | 0.143 | 0.286 | 0.190 | 2 | 5 | 12 | 0.0025 |

The ranking here did not carry over to the held-out channels: seven anomalies were too few to choose on.

## 4. Per-channel detail, held-out (found / missed / false alarms, point FPR)

| Channel | Labelled | A 100/80 dynamic span 105 (chosen) | A 250/80 dynamic span 105 | B 100/64 static k3 span 105 | Isolation Forest k3 span 30 |
|---|---|---|---|---|---|
| S-1 (SMAP) | 1 | 1/0/0, 0.3% | 1/0/0, 0.3% | 1/0/0, 0.0% | 0/1/0, 0.0% |
| E-1 (SMAP) | 2 | 2/0/0, 2.9% | 2/0/0, 2.9% | 1/1/0, 0.0% | 1/1/0, 0.0% |
| A-2 (SMAP) | 1 | 1/0/0, 1.8% | 1/0/0, 1.7% | 0/1/1, 0.1% | 0/1/0, 0.0% |
| G-7 (SMAP) | 3 | 3/0/0, 4.7% | 2/1/0, 3.7% | 3/0/0, 3.2% | 3/0/0, 1.8% |
| T-1 (SMAP) | 2 | 1/1/0, 2.4% | 1/1/1, 18.6% | 0/2/0, 0.0% | 0/2/0, 0.0% |
| P-4 (SMAP) | 3 | 1/2/0, 1.1% | 1/2/0, 1.1% | 3/0/0, 7.8% | 0/3/0, 0.0% |
| F-1 (SMAP) | 1 | 0/1/1, 2.5% | 0/1/0, 0.0% | 0/1/1, 0.3% | 0/1/1, 0.3% |
| F-7 (MSL) | 3 | 2/1/0, 4.5% | 2/1/0, 4.6% | 0/3/0, 0.0% | 3/0/2, 2.0% |
| P-10 (MSL) | 1 | 1/0/0, 5.2% | 1/0/0, 5.2% | 1/0/1, 25.4% | 1/0/0, 23.1% |
| D-14 (MSL) | 2 | 1/1/0, 4.5% | 1/1/0, 4.5% | 2/0/0, 37.5% | 0/2/0, 0.0% |
| T-13 (MSL) | 2 | 1/1/0, 8.7% | 0/2/0, 0.0% | 0/2/0, 0.0% | 1/1/1, 29.0% |
| M-6 (MSL) | 1 | 1/0/0, 3.0% | 1/0/0, 3.0% | 1/0/0, 45.9% | 0/1/0, 0.0% |

## 5. Training time per channel (sequential run, 8 CPU threads)

| Model | Median | Per tuning channel (P-1, E-8, T-4, C-1) |
|---|---|---|
| A 250/80 | 222 s | 268, 176, 145, 350 |
| A 100/80 | 36 s | 42, 35, 36, 27 |
| A 100/40 | 26 s | 29, 21, 24, 575* |
| B 100/64 | 15 s | 13, 18, 8, 606* |
| B 50/32 | 7 s | 7, 7, 6, 10 |
| Isolation Forest | 0.2 s | — |

\* The laptop stalled for about 10 minutes while idle during these two runs; they are not representative.

## 6. Attribution (TBD-3)

Share of labelled anomalies where the method ranked the faulty channel first at the anomaly's strongest sampled point. Four channels per group, so a random guess scores 25%.

| Group | Anomalies scored | Error ranking | Joint model, error share | Joint model, Shapley |
|---|---|---|---|---|
| SMAP-1 (S-1, E-1, A-2, F-1) | 4 | 4 | 0 | 0 |
| SMAP-2 (G-7, T-1, P-4, P-1) | 8 | 7 | 3 | 4 |
| MSL-1 (F-7, P-10, D-14, T-13) | 5 | 4 | 3 | 3 |
| **Total** | **17** | **15 (88%)** | **6 (35%)** | **7 (41%)** |

Share of sampled anomalous timesteps with the faulty channel ranked first: error ranking 0.51–0.65; joint error share 0.20–0.47; joint Shapley 0.15–0.72.

## Reproduce

```powershell
cd ml\spike
..\..\backend\.venv\Scripts\python -m pip install -r ..\requirements.txt
..\..\backend\.venv\Scripts\python run_spike.py tune
..\..\backend\.venv\Scripts\python run_spike.py eval --a 250,80 100,80 --b 50,32 100,64
..\..\backend\.venv\Scripts\python attribution.py --a 100,80
```

A full run takes about 1.5–2 hours on a laptop CPU; the paper-size model accounts for most of it.
