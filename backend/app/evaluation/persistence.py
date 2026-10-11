"""Applies a persistence filter to an offline per-point anomaly mask, so REQ-11
("with and without the persistence filter") can be measured with the same
evaluate_channel() used for the Phase 2 baseline.

The live MonitoringSession enforces persistence per *window* (STEP points
decided together, ARCHITECTURE.md 5.1/5.3): a run of windows is only
Confirmed once `persistence_n` consecutive windows have each been anomalous.
This groups the raw per-point flags into the same STEP-sized windows and
reproduces that rule, so "without the filter" (persistence_n=1) reduces to
exactly the Phase 2 baseline flags.
"""

from __future__ import annotations

import numpy as np

from app.pipeline.ingest import STEP


def apply_persistence_filter(flags: np.ndarray, persistence_n: int, step: int = STEP) -> np.ndarray:
    """Clears flagged points in any run of windows shorter than persistence_n."""
    if persistence_n <= 1:
        return flags
    n = len(flags)
    n_windows = (n + step - 1) // step
    window_anomalous = np.zeros(n_windows, dtype=bool)
    for w in range(n_windows):
        window_anomalous[w] = flags[w * step : (w + 1) * step].any()

    confirmed = np.zeros(n_windows, dtype=bool)
    consecutive = 0
    for w in range(n_windows):
        consecutive = consecutive + 1 if window_anomalous[w] else 0
        confirmed[w] = consecutive >= persistence_n

    out = np.zeros(n, dtype=bool)
    for w in range(n_windows):
        if confirmed[w]:
            out[w * step : (w + 1) * step] = flags[w * step : (w + 1) * step]
    return out
