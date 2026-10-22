# ADR 003 — Persistence threshold and severity constants (closes TBD-1)

**Status:** accepted, 22 Oct 2026. Measured on all 81 labelled channels with `MDL-LSTM-100-80`.

**Phase:** 3 · **Requirements:** REQ-8, REQ-9, REQ-11

## Decision

`MONITORING_CONFIG.persistence_threshold` defaults to the value chosen below by the tuning sweep. The severity formula's two saturation constants are fixed in code (`app/pipeline/explain/severity.py`), not per-satellite config, since the ER diagram gives each satellite only a single `severity_threshold` sensitivity knob:

| Constant | Value | Meaning |
|---|---|---|
| `persistence_threshold` (N) | 2 | consecutive anomalous windows needed before an alert is raised |
| `SCORE_CAP` | 3.0 | a satellite score of 3× the detection threshold or more counts as maximally severe on its own |
| `PERSISTENCE_SATURATE` | 5 | 5 consecutive confirmed windows or more counts as maximally persistent on its own |
| `severity_threshold` (default, per satellite) | 0.5 | the sensitivity knob `severity_index` is divided by before banding; lower = escalates sooner |

## Question

What value of N (REQ-8) rejects the most transient noise while losing the least real recall, and does the severity formula (REQ-9) produce sensible, monotonic bands? TBD-1 left both open for empirical tuning once real detections existed.

## Method

`app/evaluation/reports.py`. Each labelled channel's test split is cut in half by index (not by anomaly, to avoid leakage): the **tuning half** (first) is used only to sweep N; the **reporting half** (second) is used only for the final with/without comparison (REQ-11). The same event-level precision/recall/F1 and point-FPR definitions as the Phase 1 spike and the Phase 2 baseline are used throughout, via `apply_persistence_filter()`, which reproduces the live `MonitoringSession`'s per-window persistence rule (STEP-sized windows, N consecutive anomalous windows required) on the offline point-level flags.

```
python -m app.evaluation.reports --model-id MDL-LSTM-100-80 --sweep 1 2 3 5 8 \
    --out docs/results/phase3_persistence_comparison
```

## Results

See [docs/results/phase3_persistence_comparison.md](../results/phase3_persistence_comparison.md) for the full tables. Summary:

Run on 22 Oct 2026 (81 channels, about 90 s on the laptop because inference is shared between the sweep and the comparison).

**Tuning half.** N = 2 gave the best F1 (0.509). It kept the same 14 of 20 anomalies as N = 1 and cut false alarms from 26 to 21. From N = 3 upwards recall collapses (6 of 20 at N = 3, none at N = 5), because many labelled anomalies in this dataset only last two or three 70-step windows.

**Reporting half (REQ-11), held out from tuning:**

| | Found | Missed | False alarms | Precision | Recall | F1 | Point FPR |
|---|---|---|---|---|---|---|---|
| Without filter (N = 1) | 56 | 28 | 12 | 0.824 | 0.667 | 0.737 | 3.23% |
| With filter (N = 2) | 53 | 31 | 13 | 0.803 | 0.631 | 0.707 | 2.83% |

What this shows, plainly:

- The filter lowers the share of normal points that get flagged from 3.23% to 2.83%, about 12% fewer falsely flagged points.
- It does **not** lower the number of false-alarm *events*: 12 without, 13 with. Removing single windows from inside a longer flagged run can split one run into two, which the event metric counts twice.
- It costs 3 real anomalies (recall 0.667 to 0.631).
- So on this dataset the persistence filter is a small, mixed trade. Its main value in the live system is suppressing one-window blips so that an alert is not raised by a single noisy window, which the point FPR reflects, rather than a large accuracy gain.

The two halves are unbalanced: only 20 labelled anomalies fall in the tuning halves and 84 in the reporting halves, because anomalies in the NASA test splits sit mostly towards the end of each channel. N was therefore chosen on a small sample, which is a limitation of this result.

## Severity formula sanity check

`compute_severity()` is checked directly by unit tests (`tests/test_severity.py`), not by this sweep: risk_level always stays in [1, 10]; a single just-over-threshold, non-persistent detection reads LOW; a strong, sustained detection reads CRITICAL; a lower `severity_threshold` reaches the same band sooner for the same raw score and persistence. These properties, not a specific numeric sweep, are what the formula is checked against — there is no ground-truth "correct severity" label in the dataset to tune against directly.

## Consequences

- `app/seed.py`'s default `MONITORING_CONFIG.persistence_threshold` is now 2 (was 3). A database seeded earlier keeps its old rows until an administrator saves a new config on the Admin page.
- The with/without comparison in `docs/results/phase3_persistence_comparison.md` is this project's REQ-11 headline result; it is quoted, with its limitations, in the final course report.
