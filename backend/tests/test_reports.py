"""slice_label() and render_markdown() for the REQ-11 report (no trained model needed)."""

from app.evaluation.reports import render_markdown, slice_label
from app.pipeline.dataset import ChannelLabel


def label(sequences, num_values=100):
    return ChannelLabel(
        chan_id="X-1",
        spacecraft="SMAP",
        anomaly_sequences=sequences,
        anomaly_classes=["point"] * len(sequences),
        num_values=num_values,
    )


def test_slice_label_keeps_sequences_starting_inside_the_slice():
    sliced = slice_label(label([(10, 14), (60, 65)]), lo=0, hi=50)
    assert sliced.anomaly_sequences == [(10, 14)]
    assert sliced.num_values == 50


def test_slice_label_reindexes_to_the_slice_origin():
    sliced = slice_label(label([(60, 65)]), lo=50, hi=100)
    assert sliced.anomaly_sequences == [(10, 15)]


def test_slice_label_drops_sequences_starting_before_the_slice():
    sliced = slice_label(label([(5, 20)]), lo=10, hi=50)
    assert sliced.anomaly_sequences == []


def test_slice_label_clips_a_sequence_that_runs_past_the_slice_end():
    sliced = slice_label(label([(10, 90)]), lo=0, hi=50)
    assert sliced.anomaly_sequences == [(10, 49)]


def test_render_markdown_includes_sweep_and_comparison():
    sweep = {
        1: {"tp": 5, "fn": 2, "fp": 10, "precision": 0.33, "recall": 0.71, "f1": 0.45, "point_fpr": 0.05},
        3: {"tp": 4, "fn": 3, "fp": 1, "precision": 0.8, "recall": 0.57, "f1": 0.67, "point_fpr": 0.01},
    }
    comparison = {
        "chosen_persistence_n": 3,
        "without_filter": {
            "tp": 3, "fn": 1, "fp": 6, "precision": 0.33, "recall": 0.75, "f1": 0.46, "point_fpr": 0.04,
        },
        "with_filter": {
            "tp": 2, "fn": 2, "fp": 0, "precision": 1.0, "recall": 0.5, "f1": 0.67, "point_fpr": 0.0,
        },
    }
    md = render_markdown(sweep, comparison, ["A-1", "A-2"])
    assert "persistence_n = 3" in md
    assert "Without (persistence_n=1)" in md
    assert "With (persistence_n=3)" in md
    assert "0.0500" in md or "0.05" in md
