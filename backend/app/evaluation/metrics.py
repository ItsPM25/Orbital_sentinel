"""Accuracy metrics against ground-truth labels (REQ-5, REQ-11).

Event-level precision/recall (a labelled anomaly counts as found if any
flagged point falls inside it; a flagged run overlapping no label is a false
alarm) plus the point-level false-positive rate, using the same definitions
as the Phase 1 spike (ml/spike/common.py) so the numbers are comparable.
"""

from __future__ import annotations

import numpy as np

from app.pipeline.dataset import ChannelLabel

# Predicted runs closer together than this count as one alarm (the paper's error buffer).
EVENT_GAP = 100


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of each run of True values."""
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(s), int(e) - 1) for s, e in zip(edges[::2], edges[1::2], strict=True)]


def merge_runs(sequences: list[tuple[int, int]], gap: int = EVENT_GAP) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sequences:
        if merged and start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def evaluate_channel(flags: np.ndarray, label: ChannelLabel) -> dict:
    """Event-level counts for one channel's flagged mask against its labels."""
    truth = np.zeros(len(flags), dtype=bool)
    for start, end in label.anomaly_sequences:
        truth[start : min(end, len(flags) - 1) + 1] = True
    tp = sum(
        bool(flags[start : min(end, len(flags) - 1) + 1].any()) for start, end in label.anomaly_sequences
    )
    events = merge_runs(runs(flags))
    fp = sum(not truth[start : end + 1].any() for start, end in events)
    return {
        "chan_id": label.chan_id,
        "spacecraft": label.spacecraft,
        "tp": tp,
        "fn": len(label.anomaly_sequences) - tp,
        "fp": fp,
        "fp_points": int((flags & ~truth).sum()),
        "normal_points": int((~truth).sum()),
        "total_points": len(flags),
    }


def aggregate(rows: list[dict]) -> dict:
    """Micro-averaged precision/recall/F1/point-FPR over a list of per-channel rows."""
    tp = sum(r["tp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fp_points = sum(r["fp_points"] for r in rows)
    normal_points = sum(r["normal_points"] for r in rows)
    return {
        "channels": len(rows),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "point_fpr": round(fp_points / normal_points, 5) if normal_points else 0.0,
    }
