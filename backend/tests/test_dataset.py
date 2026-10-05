import numpy as np
import pytest

from app.core.settings import settings
from app.pipeline.dataset import _merge_overlapping, anomaly_mask, load_channel, load_labels, summarise

needs_data = pytest.mark.skipif(
    not (settings.data_dir / "labeled_anomalies.csv").exists(),
    reason="SMAP/MSL dataset not downloaded (run scripts/get_data)",
)


def test_merge_overlapping_sequences():
    sequences, classes = _merge_overlapping([(5350, 6575), (5300, 6420), (10, 20)], ["point"] * 3)
    assert sequences == [(10, 20), (5300, 6575)]
    assert classes == ["point", "point"]


@needs_data
def test_dataset_matches_the_published_release():
    summary = summarise()
    assert summary["train_files"] == summary["test_files"] == 82
    assert summary["labelled_channels"] == 81
    assert summary["data_without_labels"] == ["T-10"]
    assert summary["labelled_without_data"] == []
    assert summary["length_mismatches"] == []
    assert summary["per_spacecraft"]["SMAP"]["channels"] == 54
    assert summary["per_spacecraft"]["MSL"]["channels"] == 27
    assert summary["per_spacecraft"]["SMAP"]["features"] == {25}
    assert summary["per_spacecraft"]["MSL"]["features"] == {55}


@needs_data
def test_duplicate_p2_rows_are_merged():
    assert load_labels()["P-2"].anomaly_sequences == [(5300, 6575)]


@needs_data
def test_anomaly_mask_covers_labelled_ranges():
    label = load_labels()["S-1"]
    test = load_channel("S-1", "test")
    mask = anomaly_mask(label, len(test))
    assert mask.sum() == 5747 - 5300 + 1
    assert np.isfinite(test).all()
