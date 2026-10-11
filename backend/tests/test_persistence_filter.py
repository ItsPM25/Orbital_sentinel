"""REQ-11 support: apply_persistence_filter() mirrors the live per-window rule."""

import numpy as np

from app.evaluation.persistence import apply_persistence_filter


def test_persistence_n_1_is_a_no_op():
    flags = np.array([False, True, False, True, True])
    assert np.array_equal(apply_persistence_filter(flags, persistence_n=1, step=1), flags)


def test_short_run_is_suppressed():
    # One anomalous window out of a run requirement of 3: suppressed entirely.
    flags = np.zeros(10, dtype=bool)
    flags[3:4] = True
    out = apply_persistence_filter(flags, persistence_n=3, step=1)
    assert not out.any()


def test_run_meeting_the_threshold_is_kept_from_the_nth_window_onward():
    flags = np.ones(5, dtype=bool)
    out = apply_persistence_filter(flags, persistence_n=3, step=1)
    # Windows 0,1 haven't reached 3 consecutive yet; windows 2,3,4 have.
    assert not out[0] and not out[1]
    assert out[2] and out[3] and out[4]


def test_a_normal_window_resets_the_consecutive_count():
    flags = np.array([True, True, False, True, True])
    out = apply_persistence_filter(flags, persistence_n=3, step=1)
    assert not out.any()  # neither run of 2 ever reaches 3


def test_windowed_grouping_with_step_greater_than_one():
    # step=2: windows are flags[0:2], flags[2:4], flags[4:6]; persistence_n=2 needs 2 anomalous windows.
    flags = np.array([True, False, True, True, False, False])
    out = apply_persistence_filter(flags, persistence_n=2, step=2)
    # Window 0 (0:2) anomalous (consecutive=1), window 1 (2:4) anomalous (consecutive=2, kept),
    # window 2 (4:6) not anomalous.
    assert not out[0] and not out[1]
    assert out[2] and out[3]
    assert not out[4] and not out[5]


def test_without_filter_matches_the_unfiltered_input_exactly():
    rng = np.random.default_rng(0)
    flags = rng.random(500) > 0.9
    assert np.array_equal(apply_persistence_filter(flags, persistence_n=1), flags)
