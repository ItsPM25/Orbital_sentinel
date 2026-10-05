"""Shared harness for the Phase 1 model-selection spike.

Every candidate detector turns a channel's test split into a boolean mask
(True = anomalous point). The same evaluator then scores every candidate, so
the comparison is like for like.

This code is throwaway (SRS section 4.2): only the decision and the chosen
settings move on to backend/app/pipeline.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.pipeline.dataset import ChannelLabel, load_channel, load_labels  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Hyperparameters are chosen on TUNING channels and reported on EVAL channels,
# so the reported numbers are not tuned on the channels they are measured on.
TUNING_CHANNELS = ["P-1", "E-8", "T-4", "C-1"]
EVAL_CHANNELS = ["S-1", "E-1", "A-2", "G-7", "T-1", "P-4", "F-1", "F-7", "P-10", "D-14", "T-13", "M-6"]

# Predicted runs closer together than this count as one alarm (the paper's error buffer).
EVENT_GAP = 100


@dataclass
class Channel:
    chan_id: str
    label: ChannelLabel
    train: np.ndarray  # (timesteps, features); column 0 is telemetry, the rest are commands
    test: np.ndarray


def load(chan_id: str) -> Channel:
    return Channel(
        chan_id=chan_id,
        label=load_labels()[chan_id],
        train=load_channel(chan_id, "train").astype(np.float32),
        test=load_channel(chan_id, "test").astype(np.float32),
    )


def ewma(values: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(values).ewm(span=span).mean().to_numpy()


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of each run of True values."""
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(s), int(e) - 1) for s, e in zip(edges[::2], edges[1::2], strict=True)]


def merge_runs(sequences: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sequences:
        if merged and start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def evaluate(pred: np.ndarray, label: ChannelLabel) -> dict:
    """Event-level counts (Hundman et al. 2018) plus point-level false positives.

    - true positive: a labelled sequence that at least one predicted point falls inside
    - false negative: a labelled sequence with no predicted point inside it
    - false positive: a predicted event that overlaps no labelled sequence
    """
    truth = np.zeros(len(pred), dtype=bool)
    for start, end in label.anomaly_sequences:
        truth[start : end + 1] = True
    tp = sum(bool(pred[start : end + 1].any()) for start, end in label.anomaly_sequences)
    events = merge_runs(runs(pred), EVENT_GAP)
    fp = sum(not truth[start : end + 1].any() for start, end in events)
    return {
        "tp": tp,
        "fn": len(label.anomaly_sequences) - tp,
        "fp": fp,
        "fp_points": int((pred & ~truth).sum()),
        "normal_points": int((~truth).sum()),
    }


def aggregate(rows: list[dict]) -> dict:
    """Micro-averaged metrics over channels."""
    tp, fn, fp = (sum(r[k] for r in rows) for k in ("tp", "fn", "fp"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "point_fpr": round(sum(r["fp_points"] for r in rows) / sum(r["normal_points"] for r in rows), 4),
    }


def static_threshold(train_errors: np.ndarray, test_errors: np.ndarray, k: float) -> np.ndarray:
    """Flags test errors above mean + k * std of the training errors."""
    return test_errors > train_errors.mean() + k * train_errors.std()


def dynamic_threshold(
    errors: np.ndarray,
    value_range: float,
    window: int = 2100,
    step: int = 70,
    error_buffer: int = 100,
    prune_p: float = 0.13,
) -> np.ndarray:
    """Non-parametric dynamic thresholding, re-implemented from Hundman et al. (2018).

    For each sliding window of smoothed errors it picks the threshold mean + z*std
    (z from 2.5 to 12) that most reduces the mean and std of the remaining errors
    per anomaly found, then prunes anomalies that are not clearly separated from
    the largest normal error. This follows the paper, not the reference code line
    by line; the differences are listed in docs/adr/001-detector-choice.md.
    """
    n = len(errors)
    result = np.zeros(n, dtype=bool)
    if n <= window:
        starts = [0]
    else:
        starts = list(range(0, n - window + 1, step))
        if starts[-1] != n - window:
            starts.append(n - window)

    for i, a in enumerate(starts):
        w = errors[a : a + window]
        mu, sd = float(w.mean()), float(w.std())
        # Skip windows whose errors are negligible next to the channel's value range.
        if sd == 0 or not (sd > 0.05 * value_range or w.max() > 0.05 * value_range) or w.max() <= 0.05:
            continue

        best_score, best_mask = 0.0, None
        for z in np.arange(2.5, 12.5, 0.5):
            above = w > mu + z * sd
            n_above = int(above.sum())
            if n_above == 0 or n_above >= 0.5 * len(w):
                continue
            buffered = above.copy()
            for idx in np.flatnonzero(above):
                buffered[max(0, idx - error_buffer) : idx + error_buffer + 1] = True
            sequences = runs(buffered)
            if len(sequences) > 5:
                continue
            below = w[~above]
            score = ((mu - below.mean()) / mu + (sd - below.std()) / sd) / (len(sequences) ** 2 + n_above)
            if score > best_score:
                best_score, best_mask = score, buffered
        if best_mask is None:
            continue

        # Prune: keep only sequences whose peak stands clear of the next-largest peak.
        sequences = runs(best_mask)
        peaks = sorted(((float(w[s : e + 1].max()), (s, e)) for s, e in sequences), reverse=True)
        normal_max = float(w[~best_mask].max()) if (~best_mask).any() else 0.0
        heights = [p for p, _ in peaks] + [normal_max]
        keep = 0
        for j in range(len(peaks)):
            if (heights[j] - heights[j + 1]) / heights[j] > prune_p:
                keep = j + 1
        kept = np.zeros(len(w), dtype=bool)
        for _, (s, e) in peaks[:keep]:
            kept[s : e + 1] = True

        # After the first window, only the newest `step` points are newly decided.
        if i > 0:
            fresh = np.zeros(len(w), dtype=bool)
            fresh[-step:] = True
            for s, e in runs(kept):
                if not fresh[s : e + 1].any():
                    kept[s : e + 1] = False
        result[a : a + window] |= kept
    return result
