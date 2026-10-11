"""Process 1.0 — Ingest (REQ-1, REQ-2, REQ-6).

Replay reads the Telemanom `.npy` files (telemetry plus command flags). The
LSTM needs every feature column; TELEMETRY_READING only stores the value, so
it is filled by import for evaluation/plots, not used as the live source.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from app.pipeline.dataset import load_channel, load_labels
from app.pipeline.types import TelemetryWindow

HISTORY = 100  # ADR 001
STEP = 70  # dynamic threshold decides in batches of 70
MAX_GAP = 5  # interpolate gaps of this many samples or fewer (REQ-6)
REPLAY_EPOCH = datetime(2015, 1, 31, tzinfo=timezone.utc)  # SMAP launch week; synthetic clock


def repair_series(data: np.ndarray, max_gap: int = MAX_GAP) -> tuple[np.ndarray, int, np.ndarray]:
    """Linearly interpolate short non-finite gaps; leave long gaps as NaN.

    A row is a gap if any feature is NaN or ±inf. Returns
    (repaired array, number of interpolated rows, boolean mask of remaining gaps).
    """
    out = np.array(data, dtype=np.float64, copy=True)
    if out.ndim == 1:
        out = out[:, None]
        squeeze = True
    else:
        squeeze = False
    bad = ~np.isfinite(out).all(axis=1)
    interpolated = 0
    remaining = bad.copy()
    n = len(out)
    i = 0
    while i < n:
        if not bad[i]:
            i += 1
            continue
        j = i
        while j < n and bad[j]:
            j += 1
        gap = j - i
        left = i - 1
        right = j
        if gap <= max_gap and left >= 0 and right < n:
            for k in range(i, j):
                w = (k - left) / (right - left)
                out[k] = (1 - w) * out[left] + w * out[right]
            interpolated += gap
            remaining[i:j] = False
        i = j
    if squeeze:
        out = out[:, 0]
    return out, interpolated, remaining


@dataclass
class Normaliser:
    """Train-only statistics stored with the model (D3). Default is passthrough (ADR 001)."""

    mean: list[float]
    std: list[float]
    mode: str = "passthrough"

    @classmethod
    def fit(cls, train: np.ndarray, mode: str = "passthrough") -> Normaliser:
        arr = np.asarray(train, dtype=np.float64)
        if arr.ndim == 1:
            arr = arr[:, None]
        mean = arr.mean(axis=0)
        std = arr.std(axis=0)
        std = np.where(std < 1e-8, 1.0, std)
        return cls(mean=mean.tolist(), std=std.tolist(), mode=mode)

    def transform(self, data: np.ndarray) -> np.ndarray:
        arr = np.asarray(data, dtype=np.float32)
        if self.mode == "passthrough":
            return arr
        mean = np.asarray(self.mean, dtype=np.float32)
        std = np.asarray(self.std, dtype=np.float32)
        if arr.ndim == 1:
            return ((arr - mean[0]) / std[0]).astype(np.float32)
        return ((arr - mean) / std).astype(np.float32)

    def to_dict(self) -> dict:
        return {"mean": self.mean, "std": self.std, "mode": self.mode}

    @classmethod
    def from_dict(cls, payload: dict) -> Normaliser:
        return cls(
            mean=list(payload["mean"]),
            std=list(payload["std"]),
            mode=payload.get("mode", "passthrough"),
        )


def sliding_windows(data: np.ndarray, length: int, stride: int = 1) -> np.ndarray:
    """(n_windows, length, features) view of every `stride`-th window."""
    if data.ndim == 1:
        data = data[:, None]
    if len(data) < length:
        return np.zeros((0, length, data.shape[1]), dtype=data.dtype)
    view = np.lib.stride_tricks.sliding_window_view(data, length, axis=0)
    return np.ascontiguousarray(view[::stride].transpose(0, 2, 1))


@dataclass
class Windower:
    history: int = HISTORY
    step: int = STEP

    def starts(self, length: int) -> list[int]:
        """Start indices of the *new* points in each replay step (after warm-up)."""
        if length <= self.history:
            return []
        return list(range(self.history, length, self.step))


class ReplaySource:
    """Time-ordered stream of test-split windows for one satellite (REQ-1)."""

    def __init__(
        self,
        satellite_id: str,
        chan_ids: Sequence[str],
        data_dir: Path,
        history: int = HISTORY,
        step: int = STEP,
        max_gap: int = MAX_GAP,
        normalisers: dict[str, Normaliser] | None = None,
    ):
        self.satellite_id = satellite_id
        self.chan_ids = list(chan_ids)
        self.data_dir = data_dir
        self.history = history
        self.step = step
        self.max_gap = max_gap
        self.normalisers = normalisers or {}
        self._arrays: dict[str, np.ndarray] = {}
        self._remaining_gaps: dict[str, np.ndarray] = {}
        self.interpolated_total = 0
        self._load()

    def _load(self) -> None:
        labels = load_labels(self.data_dir)
        for chan_id in self.chan_ids:
            raw = load_channel(chan_id, "test", self.data_dir).astype(np.float64)
            repaired, n_interp, remaining = repair_series(raw, self.max_gap)
            self.interpolated_total += n_interp
            self._remaining_gaps[chan_id] = remaining
            normaliser = self.normalisers.get(chan_id)
            if normaliser is not None:
                repaired = normaliser.transform(repaired)
            else:
                repaired = repaired.astype(np.float32)
            self._arrays[chan_id] = repaired
            if chan_id in labels and len(repaired) != labels[chan_id].num_values:
                pass  # loader already records length quirks; replay uses the array we have

    def length(self) -> int:
        if not self._arrays:
            return 0
        return min(len(a) for a in self._arrays.values())

    def windows(self) -> Iterator[TelemetryWindow]:
        n = self.length()
        windower = Windower(self.history, self.step)
        for start in windower.starts(n):
            end = min(start + self.step, n)
            context_start = start - self.history
            arrays: dict[str, np.ndarray] = {}
            remaining = 0
            malformed = False
            for chan_id, series in self._arrays.items():
                chunk = series[context_start:end]
                arrays[chan_id] = chunk
                gap_chunk = self._remaining_gaps[chan_id][context_start:end]
                remaining += int(gap_chunk.sum())
                if gap_chunk.any():
                    malformed = True
            yield TelemetryWindow(
                satellite_id=self.satellite_id,
                start_index=start,
                end_index=end,
                history=self.history,
                arrays=arrays,
                timestamp=REPLAY_EPOCH + timedelta(seconds=start),
                malformed=malformed,
                interpolated=self.interpolated_total,
                skipped_gap=remaining,
            )
