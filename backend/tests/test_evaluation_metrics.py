"""REQ-5: precision/recall/F1/point-FPR against ground-truth labels."""

import numpy as np

from app.evaluation.metrics import aggregate, evaluate_channel, merge_runs, runs
from app.pipeline.dataset import ChannelLabel


def label(sequences: list[tuple[int, int]]) -> ChannelLabel:
    return ChannelLabel(
        chan_id="X-1",
        spacecraft="SMAP",
        anomaly_sequences=sequences,
        anomaly_classes=["point"] * len(sequences),
        num_values=100,
    )


def test_runs_and_merge_runs():
    mask = np.zeros(100, dtype=bool)
    mask[10:15] = True
    mask[20:25] = True
    assert runs(mask) == [(10, 14), (20, 24)]
    assert merge_runs([(10, 14), (20, 24)], gap=100) == [(10, 24)]
    assert merge_runs([(10, 14), (120, 124)], gap=100) == [(10, 14), (120, 124)]


def test_evaluate_channel_perfect_detection():
    flags = np.zeros(100, dtype=bool)
    flags[10:15] = True
    row = evaluate_channel(flags, label([(10, 14)]))
    assert row["tp"] == 1
    assert row["fn"] == 0
    assert row["fp"] == 0
    assert row["fp_points"] == 0


def test_evaluate_channel_missed_anomaly_is_a_false_negative():
    flags = np.zeros(100, dtype=bool)
    row = evaluate_channel(flags, label([(10, 14)]))
    assert row["tp"] == 0
    assert row["fn"] == 1


def test_evaluate_channel_spurious_flag_is_a_false_positive():
    flags = np.zeros(100, dtype=bool)
    flags[50:55] = True  # nowhere near any label
    row = evaluate_channel(flags, label([(10, 14)]))
    assert row["fn"] == 1
    assert row["fp"] == 1
    assert row["fp_points"] == 5


def test_evaluate_channel_partial_overlap_still_counts_as_true_positive():
    """Event-level: any overlap with the labelled range counts as found (Hundman et al. rule)."""
    flags = np.zeros(100, dtype=bool)
    flags[12:13] = True  # a single point inside the 10-14 label
    row = evaluate_channel(flags, label([(10, 14)]))
    assert row["tp"] == 1
    assert row["fn"] == 0


def test_evaluate_channel_normal_points_excludes_labelled_region():
    flags = np.zeros(100, dtype=bool)
    row = evaluate_channel(flags, label([(10, 19)]))  # 10 labelled points
    assert row["normal_points"] == 90


def test_aggregate_micro_averages_across_channels():
    rows = [
        {"tp": 2, "fn": 0, "fp": 1, "fp_points": 5, "normal_points": 95},
        {"tp": 1, "fn": 1, "fp": 0, "fp_points": 0, "normal_points": 90},
    ]
    m = aggregate(rows)
    assert m["tp"] == 3
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["precision"] == round(3 / 4, 4)
    assert m["recall"] == round(3 / 4, 4)
    assert m["point_fpr"] == round(5 / 185, 5)


def test_aggregate_handles_zero_detections_without_dividing_by_zero():
    m = aggregate([{"tp": 0, "fn": 2, "fp": 0, "fp_points": 0, "normal_points": 50}])
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1"] == 0.0
