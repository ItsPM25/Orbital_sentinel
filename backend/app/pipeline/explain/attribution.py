"""3.1 Channel attribution (REQ-7), the error-ranking method chosen in ADR 002.

contribution_score of a flagged channel = its score / the sum of all flagged
channels' scores, so the contributions for one detection sum to 1.0. If no
channel is flagged (shouldn't happen when the satellite itself is anomalous,
since satellite_score = max(per-channel scores), but guarded defensively per
the state diagram's "attribution always raises the alert, marked unknown if
no channel can be isolated" assumption), attribute() returns [].
"""

from __future__ import annotations

from app.pipeline.types import ChannelScores

TOP_K = 3


def attribute(scores: ChannelScores, top_k: int = TOP_K) -> list[tuple[str, float]]:
    """Returns up to `top_k` (dataset_chan_id, contribution_score) pairs, ranked descending."""
    flagged = {c: scores.per_channel[c] for c in scores.flagged_channels if c in scores.per_channel}
    total = sum(flagged.values())
    if not flagged or total <= 0:
        return []
    ranked = sorted(flagged.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(chan_id, value / total) for chan_id, value in ranked]
