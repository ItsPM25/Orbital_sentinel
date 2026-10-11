"""REQ-1, REQ-2, REQ-6: ingestion, windowing, malformed-data handling."""

import numpy as np
import pytest

from app.pipeline.ingest import Normaliser, ReplaySource, Windower, repair_series

# --- repair_series: REQ-6 malformed-data handling ---------------------------------------------


def test_repair_series_interpolates_a_short_nan_gap():
    data = np.array([0.0, 1.0, np.nan, np.nan, 4.0, 5.0])
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert np.allclose(repaired, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    assert n_interp == 2
    assert not remaining.any()


def test_repair_series_interpolates_inf_values_too():
    data = np.array([0.0, 1.0, np.inf, -np.inf, 4.0, 5.0])
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert np.isfinite(repaired).all()
    assert n_interp == 2


def test_repair_series_leaves_a_long_gap_as_nan_and_counts_it():
    data = np.array([0.0] + [np.nan] * 10 + [4.0])
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert n_interp == 0
    assert remaining.sum() == 10
    assert np.isnan(repaired[1:11]).all()


def test_repair_series_cannot_interpolate_a_gap_at_the_start_or_end():
    # No left neighbour for the leading gap, no right neighbour for the trailing gap.
    data = np.array([np.nan, np.nan, 1.0, 2.0, 3.0, np.nan])
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert remaining[0] and remaining[1] and remaining[-1]
    assert n_interp == 0


def test_repair_series_never_raises_on_an_all_nan_channel():
    data = np.full(20, np.nan)
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert remaining.all()
    assert n_interp == 0


def test_repair_series_handles_multivariate_arrays():
    data = np.array([[0.0, 1.0], [np.nan, 1.0], [2.0, 1.0]])
    repaired, n_interp, remaining = repair_series(data, max_gap=5)
    assert repaired.shape == (3, 2)
    assert n_interp == 1


# --- Normaliser --------------------------------------------------------------------------------


def test_normaliser_passthrough_mode_does_not_change_values():
    train = np.array([1.0, 2.0, 3.0])
    norm = Normaliser.fit(train, mode="passthrough")
    assert np.allclose(norm.transform(np.array([5.0, -5.0])), [5.0, -5.0])


def test_normaliser_zscore_mode_uses_train_statistics_only():
    train = np.array([0.0, 2.0, 4.0])  # mean 2, std ~1.63
    norm = Normaliser.fit(train, mode="zscore")
    transformed = norm.transform(train)
    assert abs(transformed.mean()) < 1e-6


def test_normaliser_guards_against_zero_std():
    train = np.array([5.0, 5.0, 5.0])
    norm = Normaliser.fit(train, mode="zscore")
    assert norm.std[0] == 1.0  # not 0, which would divide by zero
    assert np.isfinite(norm.transform(np.array([5.0, 6.0]))).all()


def test_normaliser_roundtrips_through_dict():
    norm = Normaliser.fit(np.array([1.0, 2.0, 3.0]), mode="zscore")
    restored = Normaliser.from_dict(norm.to_dict())
    assert restored.mean == norm.mean
    assert restored.std == norm.std
    assert restored.mode == norm.mode


# --- Windower ------------------------------------------------------------------------------


def test_windower_starts_after_history_and_steps_by_step():
    w = Windower(history=100, step=70)
    assert w.starts(100) == []  # no new points yet
    assert w.starts(101) == [100]
    assert w.starts(300) == [100, 170, 240]


def test_windower_handles_a_channel_shorter_than_history():
    w = Windower(history=100, step=70)
    assert w.starts(50) == []


# --- ReplaySource: end-to-end on a tiny synthetic channel -----------------------------------


@pytest.fixture()
def tiny_channel(tmp_path, monkeypatch):
    """A 1-feature channel with one short gap, small enough to replay in a couple of windows."""
    import pandas as pd  # noqa: F401  (ensure pandas is importable in this env; unused otherwise)

    (tmp_path / "test").mkdir()
    (tmp_path / "train").mkdir()
    values = np.sin(np.linspace(0, 20, 220)).astype(np.float32)
    values[50:58] = np.nan  # a gap longer than MAX_GAP (5): stays malformed, not interpolated
    np.save(tmp_path / "test" / "Z-1.npy", values[:, None])
    np.save(tmp_path / "train" / "Z-1.npy", values[:, None])
    (tmp_path / "labeled_anomalies.csv").write_text(
        "chan_id,spacecraft,anomaly_sequences,class,num_values\nZ-1,SMAP,\"[[10, 12]]\",[point],220\n"
    )
    return tmp_path


def test_replay_source_streams_windows_in_order_and_flags_the_malformed_one(tiny_channel):
    source = ReplaySource("SAT-TEST", ["Z-1"], tiny_channel, history=10, step=10)
    windows = list(source.windows())
    assert len(windows) > 1
    assert [w.start_index for w in windows] == sorted(w.start_index for w in windows)
    assert all(w.end_index - w.start_index <= 10 for w in windows)
    malformed = [w for w in windows if w.malformed]
    assert len(malformed) >= 1
    # The gap at [50, 58) should surface in a window whose context or new range touches it.
    assert any(w.start_index - w.history <= 57 and w.end_index > 50 for w in malformed)


def test_replay_source_session_never_stops_on_malformed_data(tiny_channel):
    """REQ-6: malformed samples are skipped/interpolated, the session (here, the full replay) completes."""
    source = ReplaySource("SAT-TEST", ["Z-1"], tiny_channel, history=10, step=10)
    windows = list(source.windows())
    assert len(windows) == len(Windower(10, 10).starts(source.length()))


def test_replay_source_applies_the_given_normaliser(tiny_channel):
    norm = Normaliser(mean=[0.0], std=[2.0], mode="zscore")
    source = ReplaySource("SAT-TEST", ["Z-1"], tiny_channel, history=10, step=10, normalisers={"Z-1": norm})
    window = next(source.windows())
    assert np.abs(window.arrays["Z-1"]).max() <= 1.0  # values were halved by std=2
