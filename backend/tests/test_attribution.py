"""REQ-7: channel attribution by error ranking (ADR 002)."""

from app.pipeline.explain.attribution import attribute
from app.pipeline.types import ChannelScores


def scores(per_channel: dict[str, float], threshold: float = 1.0) -> ChannelScores:
    return ChannelScores.from_channel_scores(per_channel, threshold)


def test_attribute_ranks_flagged_channels_by_score_descending():
    ranked = attribute(scores({"A-1": 0.5, "A-2": 2.0, "A-3": 1.5}))
    assert [c for c, _ in ranked] == ["A-2", "A-3"]  # only channels above threshold


def test_attribute_contribution_scores_sum_to_one():
    ranked = attribute(scores({"A-1": 2.0, "A-2": 1.5}))
    assert abs(sum(v for _, v in ranked) - 1.0) < 1e-9


def test_attribute_single_flagged_channel_gets_full_contribution():
    ranked = attribute(scores({"A-1": 2.0, "A-2": 0.3}))
    assert ranked == [("A-1", 1.0)]


def test_attribute_respects_top_k():
    ranked = attribute(scores({"A-1": 4.0, "A-2": 3.0, "A-3": 2.0, "A-4": 1.5}), top_k=2)
    assert [c for c, _ in ranked] == ["A-1", "A-2"]


def test_attribute_no_flagged_channel_is_unknown():
    ranked = attribute(scores({"A-1": 0.3, "A-2": 0.5}))
    assert ranked == []


def test_attribute_no_channels_at_all_is_unknown():
    ranked = attribute(scores({}))
    assert ranked == []
