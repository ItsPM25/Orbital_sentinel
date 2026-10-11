"""REQ-1: admin dataset import (data/ -> CHANNEL + TELEMETRY_READING), idempotent."""

import numpy as np
import pytest

from app.models import Channel, TelemetryReading
from app.pipeline.import_dataset import import_dataset


@pytest.fixture()
def tiny_dataset(tmp_path):
    (tmp_path / "train").mkdir()
    (tmp_path / "test").mkdir()
    for chan_id, _spacecraft in [("Z-1", "SMAP"), ("Z-2", "MSL")]:
        np.save(tmp_path / "train" / f"{chan_id}.npy", np.zeros((20, 3), dtype=np.float32))
        np.save(tmp_path / "test" / f"{chan_id}.npy", np.ones((15, 3), dtype=np.float32))
    (tmp_path / "labeled_anomalies.csv").write_text(
        "chan_id,spacecraft,anomaly_sequences,class,num_values\n"
        'Z-1,SMAP,"[[2, 4]]",[point],15\n'
        'Z-2,MSL,"[[0, 1]]",[point],15\n'
    )
    return tmp_path


def test_import_creates_one_channel_per_dataset_channel(db_session, tiny_dataset):
    result = import_dataset(db_session, tiny_dataset)
    assert result["channelsCreated"] == 2
    assert result["includeReadings"] is False
    assert db_session.query(Channel).filter(Channel.dataset_chan_id.in_(["Z-1", "Z-2"])).count() == 2
    # Without include_readings, no TELEMETRY_READING rows are written.
    assert db_session.query(TelemetryReading).count() == 0


def test_import_maps_spacecraft_to_the_right_satellite(db_session, tiny_dataset):
    import_dataset(db_session, tiny_dataset)
    z1 = db_session.query(Channel).filter_by(dataset_chan_id="Z-1").one()
    z2 = db_session.query(Channel).filter_by(dataset_chan_id="Z-2").one()
    assert z1.satellite_id == "SAT-001"  # SMAP -> SAT-001 (the real satellite)
    assert z2.satellite_id == "SAT-002"  # MSL -> SAT-002 (proxy mapping, ADR-004 pending)


def test_import_is_idempotent(db_session, tiny_dataset):
    first = import_dataset(db_session, tiny_dataset)
    second = import_dataset(db_session, tiny_dataset)
    assert first["channelsCreated"] == 2
    assert second["channelsCreated"] == 0
    assert second["channelsUpdated"] == 2
    assert db_session.query(Channel).filter(Channel.dataset_chan_id.in_(["Z-1", "Z-2"])).count() == 2


def test_import_with_readings_writes_train_and_test_rows_with_labels(db_session, tiny_dataset):
    result = import_dataset(db_session, tiny_dataset, include_readings=True)
    assert result["readings"] == (20 + 15) * 2  # train + test, 2 channels
    z1 = db_session.query(Channel).filter_by(dataset_chan_id="Z-1").one()
    test_rows = (
        db_session.query(TelemetryReading)
        .filter_by(channel_id=z1.channel_id, split="test")
        .order_by(TelemetryReading.timestamp)
        .all()
    )
    assert len(test_rows) == 15
    assert test_rows[2].is_labeled_anomaly is True  # inside [2, 4]
    assert test_rows[0].is_labeled_anomaly is False
    train_rows = db_session.query(TelemetryReading).filter_by(channel_id=z1.channel_id, split="train").all()
    assert all(not r.is_labeled_anomaly for r in train_rows)


def test_import_rerun_with_readings_does_not_duplicate_rows(db_session, tiny_dataset):
    import_dataset(db_session, tiny_dataset, include_readings=True)
    import_dataset(db_session, tiny_dataset, include_readings=True)
    z1 = db_session.query(Channel).filter_by(dataset_chan_id="Z-1").one()
    assert db_session.query(TelemetryReading).filter_by(channel_id=z1.channel_id).count() == 20 + 15


def test_import_skips_channels_with_no_mapped_satellite(db_session, tiny_dataset):
    result = import_dataset(db_session, tiny_dataset, satellite_map={"SMAP": "SAT-001"})
    assert result["channelsCreated"] == 1  # MSL has no mapping, skipped
    assert db_session.query(Channel).filter_by(dataset_chan_id="Z-2").first() is None
