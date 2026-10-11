"""Shared types for pipeline stages (ARCHITECTURE.md §5)."""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class TelemetryWindow:
    """One replay step: `history` context plus `step` new points per channel."""

    satellite_id: str
    start_index: int  # first new test-split index in this step
    end_index: int  # exclusive
    history: int
    # dataset_chan_id -> array of shape (history + step, features)
    arrays: dict[str, np.ndarray]
    timestamp: datetime
    malformed: bool = False
    interpolated: int = 0
    skipped_gap: int = 0


@dataclass
class ChannelScores:
    """Per-channel scores plus the satellite score (ARCHITECTURE.md §5.2)."""

    per_channel: dict[str, float]
    satellite_score: float
    threshold: float
    is_anomaly: bool
    flagged_channels: list[str] = field(default_factory=list)
    # Smoothed error standardised by training errors, per channel (attribution, ADR 002).
    standardised_error: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_channel_scores(
        cls, per_channel: dict[str, float], threshold: float, standardised: dict[str, float] | None = None
    ) -> "ChannelScores":
        satellite_score = max(per_channel.values()) if per_channel else 0.0
        flagged = [cid for cid, score in per_channel.items() if score > threshold]
        return cls(
            per_channel=per_channel,
            satellite_score=satellite_score,
            threshold=threshold,
            is_anomaly=satellite_score > threshold,
            flagged_channels=flagged,
            standardised_error=standardised or {},
        )


@dataclass
class SessionCounters:
    windows: int = 0
    normal: int = 0
    detections: int = 0
    malformed: int = 0
    interpolated: int = 0
    last_score_ms: float = 0.0
    max_score_ms: float = 0.0
