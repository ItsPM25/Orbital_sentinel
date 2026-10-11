"""Process 2.0 — Detect (REQ-3, REQ-4).

Per-channel LSTM predictor + non-parametric dynamic threshold (ADR 001).

The threshold runs incrementally: each replay step adds STEP smoothed errors,
and only the newest THRESHOLD_WINDOW errors are examined. Offline evaluation
replays a channel through the same StreamingThreshold, so the accuracy it
reports is the accuracy of the live detector.

PyTorch is imported only when an LstmDetector is created, so the API and its
tests run without it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from app.pipeline.ingest import HISTORY, STEP
from app.pipeline.types import ChannelScores, TelemetryWindow

EWMA_SPAN = 105
THRESHOLD_WINDOW = 2100
ERROR_BUFFER = 100
PRUNE_P = 0.13
Z_VALUES = np.arange(2.5, 12.5, 0.5)
# A channel score is smoothed error / dynamic threshold, so > 1 means anomalous (REQ-4).
GLOBAL_THRESHOLD = 1.0

THRESHOLD_HYPERPARAMS = {
    "ewma_span": EWMA_SPAN,
    "threshold_window": THRESHOLD_WINDOW,
    "threshold_step": STEP,
    "error_buffer": ERROR_BUFFER,
    "prune_p": PRUNE_P,
    "z_values": [float(Z_VALUES[0]), float(Z_VALUES[-1])],
}


class Detector(Protocol):
    def score(self, window: TelemetryWindow) -> ChannelScores: ...


def ewma(values: np.ndarray, span: int, start: float | None = None) -> np.ndarray:
    """Recursive EWMA (pandas adjust=False), identical offline and in streaming."""
    alpha = 2.0 / (span + 1.0)
    out = np.empty(len(values), dtype=np.float64)
    state = start
    for i, value in enumerate(values):
        state = value if state is None else alpha * value + (1.0 - alpha) * state
        out[i] = state
    return out


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) pairs of each run of True values."""
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(s), int(e) - 1) for s, e in zip(edges[::2], edges[1::2], strict=True)]


def _buffer(mask: np.ndarray, width: int) -> np.ndarray:
    """Dilate each True index by `width` on each side, kept at exactly len(mask).

    (np.convolve(..., mode="same") does NOT always return len(mask): when the
    kernel is longer than mask, numpy's "same" returns the kernel's length.)
    """
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return np.zeros(len(mask), dtype=bool)
    n = len(mask)
    starts = np.maximum(idx - width, 0)
    ends = np.minimum(idx + width + 1, n)
    delta = np.zeros(n + 1, dtype=np.int32)
    np.add.at(delta, starts, 1)
    np.add.at(delta, ends, -1)
    return np.cumsum(delta[:-1]) > 0


def decide_window(
    errors: np.ndarray, value_range: float, error_buffer: int = ERROR_BUFFER, prune_p: float = PRUNE_P
) -> tuple[np.ndarray, float | None]:
    """One window of the Hundman et al. (2018) threshold.

    Returns the anomalous mask (after buffering and pruning) and the chosen
    threshold epsilon, or (all False, None) if the window has no anomalies.
    """
    flagged = np.zeros(len(errors), dtype=bool)
    mu, sd = float(errors.mean()), float(errors.std())
    # Skip windows whose errors are negligible next to the channel's value range.
    if sd == 0 or not (sd > 0.05 * value_range or errors.max() > 0.05 * value_range) or errors.max() <= 0.05:
        return flagged, None

    best_score, best_mask, best_eps = 0.0, None, None
    for z in Z_VALUES:
        eps = mu + z * sd
        above = errors > eps
        n_above = int(above.sum())
        if n_above == 0 or n_above >= 0.5 * len(errors):
            continue
        buffered = _buffer(above, error_buffer)
        sequences = runs(buffered)
        if len(sequences) > 5:
            continue
        below = errors[~above]
        score = ((mu - below.mean()) / mu + (sd - below.std()) / sd) / (len(sequences) ** 2 + n_above)
        if score > best_score:
            best_score, best_mask, best_eps = score, buffered, eps
    if best_mask is None:
        return flagged, None

    # Prune sequences whose peak does not stand clear of the next-largest peak.
    peaks = sorted(((float(errors[s : e + 1].max()), (s, e)) for s, e in runs(best_mask)), reverse=True)
    heights = [p for p, _ in peaks] + [float(errors[~best_mask].max()) if (~best_mask).any() else 0.0]
    keep = 0
    for j in range(len(peaks)):
        if heights[j] > 0 and (heights[j] - heights[j + 1]) / heights[j] > prune_p:
            keep = j + 1
    for _, (s, e) in peaks[:keep]:
        flagged[s : e + 1] = True
    return flagged, best_eps


@dataclass
class StepDecision:
    flags: np.ndarray  # one flag per new point
    score: float  # > GLOBAL_THRESHOLD exactly when any new point is flagged
    epsilon: float | None


@dataclass
class StreamingThreshold:
    """Decides each new batch of smoothed errors using the last THRESHOLD_WINDOW errors."""

    value_range: float
    window: int = THRESHOLD_WINDOW
    errors: deque = field(default_factory=lambda: deque(maxlen=THRESHOLD_WINDOW))

    def update(self, new_errors: np.ndarray) -> StepDecision:
        self.errors.extend(new_errors.tolist())
        n_new = len(new_errors)
        if n_new == 0:
            return StepDecision(np.zeros(0, dtype=bool), 0.0, None)
        w = np.fromiter(self.errors, dtype=np.float64, count=len(self.errors))
        flagged, eps = decide_window(w, self.value_range)
        # Only sequences that reach into the newest points are new decisions.
        fresh_start = len(w) - n_new
        peak = 0.0
        new_flags = np.zeros(len(w), dtype=bool)
        for s, e in runs(flagged):
            if e >= fresh_start:
                new_flags[s : e + 1] = True
                peak = max(peak, float(w[s : e + 1].max()))
        flags = new_flags[fresh_start:]
        if flags.any():
            score = peak / eps  # > 1: every kept sequence contains a point above eps
        elif eps is not None:
            score = min(float(new_errors.max()) / eps, GLOBAL_THRESHOLD)
        else:
            score = 0.0
        return StepDecision(flags, float(score), eps)


def simulate_stream(raw_errors: np.ndarray, value_range: float) -> np.ndarray:
    """Anomaly flags for a whole error series, exactly as the live detector would emit them."""
    flags = np.zeros(len(raw_errors), dtype=bool)
    smoothed = ewma(raw_errors[HISTORY:], EWMA_SPAN)
    threshold = StreamingThreshold(value_range)
    for start in range(0, len(smoothed), STEP):
        decision = threshold.update(smoothed[start : start + STEP])
        flags[HISTORY + start : HISTORY + start + len(decision.flags)] = decision.flags
    return flags


@dataclass
class _ChannelState:
    model: object
    stats: dict
    threshold: StreamingThreshold
    ewma_state: float | None = None


class LstmDetector:
    """Scores replay windows with the per-channel models stored in models/<model_id>/."""

    def __init__(self, artifact_dir: Path, chan_ids: list[str]):
        from app.pipeline import lstm

        self._lstm = lstm
        self.artifact_dir = Path(artifact_dir)
        self.threshold = GLOBAL_THRESHOLD
        self._channels: dict[str, _ChannelState] = {}
        for chan_id in chan_ids:
            if not (self.artifact_dir / f"{chan_id}.pt").exists():
                continue
            model, stats = lstm.load_channel_model(self.artifact_dir, chan_id)
            self._channels[chan_id] = _ChannelState(model, stats, StreamingThreshold(stats["value_range"]))
        self.missing = sorted(set(chan_ids) - set(self._channels))

    @property
    def chan_ids(self) -> list[str]:
        return sorted(self._channels)

    def score(self, window: TelemetryWindow) -> ChannelScores:
        per_channel: dict[str, float] = {}
        standardised: dict[str, float] = {}
        for chan_id, block in window.arrays.items():
            state = self._channels.get(chan_id)
            if state is None:
                continue
            raw = self._lstm.prediction_errors(state.model, np.asarray(block, dtype=np.float32))[HISTORY:]
            smoothed = ewma(raw, EWMA_SPAN, start=state.ewma_state)
            if len(smoothed):
                state.ewma_state = float(smoothed[-1])
            decision = state.threshold.update(smoothed)
            per_channel[chan_id] = decision.score
            # Error ranking for attribution (ADR 002): newest error vs. training errors.
            if len(smoothed):
                mean = state.stats["train_error_mean"]
                std = state.stats["train_error_std"]
                standardised[chan_id] = (float(smoothed.max()) - mean) / std
        return ChannelScores.from_channel_scores(per_channel, self.threshold, standardised)


class ScriptedDetector:
    """Test double: satellite scores come from a list, never from a model."""

    def __init__(self, scores: list[float], threshold: float = GLOBAL_THRESHOLD):
        self._scores = scores
        self.threshold = threshold
        self._i = 0

    def score(self, window: TelemetryWindow) -> ChannelScores:
        value = self._scores[min(self._i, len(self._scores) - 1)]
        self._i += 1
        chan_id = next(iter(window.arrays), "scripted")
        return ChannelScores.from_channel_scores({chan_id: value}, self.threshold, {chan_id: value})
