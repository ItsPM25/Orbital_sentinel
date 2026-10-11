# ADR 003 — Persistence threshold and severity constants (closes TBD-1)

**Status:** preliminary — based on the channels trained so far; to be refreshed once all 81 channels have trained weights (Phase 2's baseline report has the same caveat). See the note at the end.

**Phase:** 3 · **Requirements:** REQ-8, REQ-9, REQ-11

## Decision

`MONITORING_CONFIG.persistence_threshold` defaults to the value chosen below by the tuning sweep. The severity formula's two saturation constants are fixed in code (`app/pipeline/explain/severity.py`), not per-satellite config, since the ER diagram gives each satellite only a single `severity_threshold` sensitivity knob:

| Constant | Value | Meaning |
|---|---|---|
| `persistence_threshold` (N) | *(filled in below)* | consecutive anomalous windows needed before an alert is raised |
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

*(filled in from the sweep output once available — see the note below)*

## Severity formula sanity check

`compute_severity()` is checked directly by unit tests (`tests/test_severity.py`), not by this sweep: risk_level always stays in [1, 10]; a single just-over-threshold, non-persistent detection reads LOW; a strong, sustained detection reads CRITICAL; a lower `severity_threshold` reaches the same band sooner for the same raw score and persistence. These properties, not a specific numeric sweep, are what the formula is checked against — there is no ground-truth "correct severity" label in the dataset to tune against directly.

## Consequences

- `app/seed.py`'s default `MONITORING_CONFIG.persistence_threshold` is updated to match the chosen N.
- The with/without comparison in `docs/results/phase3_persistence_comparison.md` is this project's REQ-11 headline result; it is quoted, with its limitations, in the final course report.
- If the chosen N changes materially once all 81 channels are trained, this ADR and the seeded default are updated and the change is noted in `docs/PHASES.md`.

## Note on preliminary status

This ADR was written while Phase 2's 81-channel training run was still in progress (see `docs/PHASES.md`'s Phase 2 status). The numbers above come from whichever channels had trained weights at the time; the full picture is more reliable once every labelled channel is included. Re-run the command above after training finishes and update this file and the linked results.
