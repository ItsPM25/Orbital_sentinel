"""REQ-3, REQ-4: scoring and the dynamic threshold, offline vs. streaming."""

import numpy as np
import pytest

from app.pipeline.detect import (
    GLOBAL_THRESHOLD,
    ScriptedDetector,
    StreamingThreshold,
    decide_window,
    ewma,
    runs,
    simulate_stream,
)
from app.pipeline.ingest import HISTORY, STEP
from app.pipeline.types import ChannelScores

# --- ewma ----------------------------------------------------------------------------------


def test_ewma_first_value_is_unchanged():
    assert ewma(np.array([5.0, 5.0, 5.0]), span=10)[0] == 5.0


def test_ewma_smooths_towards_new_values():
    out = ewma(np.concatenate([[0.0], np.ones(30)]), span=5)
    assert out[1] < out[-1]  # gradually approaches 1.0
    assert out[-1] < 1.0  # never quite reaches it
    assert out[-1] > 0.9999  # but gets very close after enough steps


def test_ewma_continues_from_a_given_start_state():
    continued = ewma(np.array([1.0, 1.0]), span=5, start=5.0)
    fresh = ewma(np.array([5.0, 1.0, 1.0]), span=5)
    assert np.allclose(continued, fresh[1:])


def test_ewma_matches_pandas_adjust_false():
    pd = pytest.importorskip("pandas")
    values = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0])
    expected = pd.Series(values).ewm(span=12, adjust=False).mean().to_numpy()
    assert np.allclose(ewma(values, span=12), expected)


# --- runs ------------------------------------------------------------------------------------


def test_runs_finds_each_contiguous_true_block():
    mask = np.array([False, True, True, False, False, True, False])
    assert runs(mask) == [(1, 2), (5, 5)]


def test_runs_of_all_false_is_empty():
    assert runs(np.zeros(5, dtype=bool)) == []


def test_runs_of_all_true_is_one_block():
    assert runs(np.ones(5, dtype=bool)) == [(0, 4)]


# --- decide_window -----------------------------------------------------------------------------


def test_decide_window_flags_a_clear_spike():
    rng = np.random.default_rng(0)
    errors = rng.normal(0.1, 0.02, 500).clip(min=0)
    errors[250:260] = 2.0  # an obvious spike well above the noise floor
    flagged, eps = decide_window(errors, value_range=1.0)
    assert eps is not None
    assert flagged[250:260].all()
    # The 100-point error buffer (ADR 001) widens the flagged run on each side.
    assert not flagged[:149].any()
    assert not flagged[361:].any()


def test_decide_window_flags_nothing_on_flat_input():
    flagged, eps = decide_window(np.full(300, 0.1), value_range=1.0)
    assert not flagged.any()
    assert eps is None


def test_decide_window_ignores_noise_negligible_next_to_value_range():
    # Errors are tiny relative to a large value_range: the "0.05 * value_range" guard should skip.
    rng = np.random.default_rng(1)
    errors = rng.normal(0.001, 0.0005, 300).clip(min=0)
    flagged, eps = decide_window(errors, value_range=100.0)
    assert not flagged.any()
    assert eps is None


# --- StreamingThreshold vs. offline (ADR 001: must agree) -------------------------------------


def test_streaming_threshold_single_update_matches_offline_decide_window():
    """When one update covers the whole window (nothing committed yet), streaming == offline."""
    rng = np.random.default_rng(2)
    errors = rng.normal(0.1, 0.02, 800).clip(min=0)
    errors[500:510] = 2.0
    offline_flags, offline_eps = decide_window(errors, value_range=1.0)

    decision = StreamingThreshold(value_range=1.0).update(errors)
    assert np.array_equal(offline_flags, decision.flags)
    assert decision.epsilon == offline_eps


def test_streaming_threshold_never_revises_an_already_committed_decision():
    """Once a step's points are decided, a later update with more context must not change them.

    (A streaming detector commits as data arrives; it cannot retroactively relabel the past,
    unlike a single full-batch decide_window call over all the data at once.)
    """
    rng = np.random.default_rng(5)
    errors = rng.normal(0.1, 0.02, 1500).clip(min=0)
    errors[800:810] = 2.0
    threshold = StreamingThreshold(value_range=1.0)
    committed = np.zeros(len(errors), dtype=bool)
    for start in range(0, len(errors), STEP):
        before = committed[:start].copy()
        decision = threshold.update(errors[start : start + STEP])
        committed[start : start + len(decision.flags)] = decision.flags
        assert np.array_equal(committed[:start], before)  # nothing earlier was touched


def test_simulate_stream_flags_at_least_the_injected_anomaly():
    n = HISTORY + 3000
    rng = np.random.default_rng(3)
    raw_errors = rng.normal(0.1, 0.02, n).clip(min=0)
    raw_errors[2000:2030] = 3.0
    flags = simulate_stream(raw_errors, value_range=1.0)
    assert len(flags) == n
    assert flags[2000:2030].any()
    assert not flags[: HISTORY + 1000].any()


def test_streaming_threshold_flags_contribute_a_score_above_one():
    threshold = StreamingThreshold(value_range=1.0)
    rng = np.random.default_rng(4)
    for _ in range(20):
        threshold.update(rng.normal(0.1, 0.02, STEP).clip(min=0))
    decision = threshold.update(np.full(STEP, 3.0))
    assert decision.flags.any()
    assert decision.score > GLOBAL_THRESHOLD


# --- ChannelScores / ScriptedDetector -----------------------------------------------------


def test_channel_scores_satellite_score_is_the_max_channel_score():
    scores = ChannelScores.from_channel_scores({"A": 0.3, "B": 1.5, "C": 0.9}, threshold=1.0)
    assert scores.satellite_score == 1.5
    assert scores.is_anomaly is True
    assert scores.flagged_channels == ["B"]


def test_channel_scores_no_channels_is_not_anomalous():
    scores = ChannelScores.from_channel_scores({}, threshold=1.0)
    assert scores.satellite_score == 0.0
    assert scores.is_anomaly is False


def test_scripted_detector_returns_scores_in_order_then_holds_the_last():
    detector = ScriptedDetector([0.1, 2.0, 0.5])
    window = type("W", (), {"arrays": {"CH-1": np.zeros(5)}})()
    got = [detector.score(window).satellite_score for _ in range(4)]
    assert got == [0.1, 2.0, 0.5, 0.5]
