"""GET /api/satellites, /satellites/{id}/health, /satellites/{id}/telemetry."""

from datetime import datetime, timezone

import numpy as np
import pytest

from app.models import Alert, AlertStatus, Attribution, Channel, Detection, DetectionOutcome
from tests.conftest import ANALYST, login

MODEL_ID = "MDL-DEMO-1"


def test_satellites_require_login(client):
    assert client.get("/api/satellites").status_code == 401


def test_satellites_lists_all_with_risk_from_seeded_alerts(client):
    login(client, ANALYST)
    res = client.get("/api/satellites")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 5
    sat1 = next(s for s in body if s["satelliteId"] == "SAT-001")
    assert sat1["riskLevel"] == 10
    assert sat1["verdict"] == "Anomalous"


def test_satellite_health_nominal_when_no_open_alert(client, db_session):
    db_session.query(Alert).delete()
    db_session.query(Detection).delete()
    db_session.commit()
    login(client, ANALYST)
    res = client.get("/api/satellites/SAT-001/health")
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "Nominal"
    assert body["riskLevel"] is None
    assert body["attributedChannels"] == []


def test_satellite_health_unknown_satellite_is_404(client):
    login(client, ANALYST)
    assert client.get("/api/satellites/SAT-999/health").status_code == 404


def test_satellite_health_includes_attribution(client, db_session):
    # Clear the seeded demo alert for SAT-001 (risk 10) so it doesn't outrank the one below.
    db_session.query(Alert).filter(Alert.detection_id == "DET-101").delete()
    db_session.query(Detection).filter(Detection.detection_id == "DET-101").delete()
    db_session.commit()

    db_session.add(
        Channel(channel_id="CHN-A-1", satellite_id="SAT-001", channel_name="A-1", dataset_chan_id="A-1")
    )
    db_session.add(
        Detection(
            detection_id="DET-X",
            satellite_id="SAT-001",
            model_id=MODEL_ID,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            anomaly_score=3.0,
            severity_level="HIGH",
            persistence_count=5,
            outcome=DetectionOutcome.CONFIRMED,
        )
    )
    db_session.add(
        Attribution(
            attribution_id="ATB-X", detection_id="DET-X", channel_id="CHN-A-1", contribution_score=1.0
        )
    )
    db_session.add(
        Alert(
            alert_id="ALT-X",
            detection_id="DET-X",
            risk_level=9,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=AlertStatus.ALERT_RAISED,
        )
    )
    db_session.commit()

    client_login = login(client, ANALYST)
    assert client_login.status_code == 200
    res = client.get("/api/satellites/SAT-001/health")
    body = res.json()
    assert body["verdict"] == "Anomalous"
    assert body["riskLevel"] == 9
    assert len(body["attributedChannels"]) == 1
    assert body["attributedChannels"][0]["channelId"] == "A-1"


@pytest.fixture()
def tiny_channel(tmp_path, monkeypatch):
    (tmp_path / "test").mkdir()
    values = np.linspace(0, 1, 500).astype(np.float32)
    np.save(tmp_path / "test" / "Z-1.npy", values[:, None])
    monkeypatch.setattr("app.api.satellites.settings.data_dir", tmp_path)
    return tmp_path


def test_telemetry_requires_login(client):
    assert client.get("/api/satellites/SAT-001/telemetry?channel=A-1").status_code == 401


def test_telemetry_unknown_channel_is_404(client):
    login(client, ANALYST)
    res = client.get("/api/satellites/SAT-001/telemetry?channel=NOPE")
    assert res.status_code == 404


def test_telemetry_returns_downsampled_series_with_anomaly_ranges(client, db_session, tiny_channel):
    db_session.add(
        Channel(
            channel_id="CHN-Z-1", satellite_id="SAT-001", channel_name="Z-1", dataset_chan_id="Z-1", unit="V"
        )
    )
    db_session.add(
        Detection(
            detection_id="DET-Z",
            satellite_id="SAT-001",
            model_id=MODEL_ID,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            anomaly_score=2.0,
            severity_level="HIGH",
            persistence_count=3,
            window_start=100,
            window_end=170,
            outcome=DetectionOutcome.CONFIRMED,
        )
    )
    db_session.add(
        Attribution(
            attribution_id="ATB-Z", detection_id="DET-Z", channel_id="CHN-Z-1", contribution_score=1.0
        )
    )
    db_session.commit()

    login(client, ANALYST)
    res = client.get("/api/satellites/SAT-001/telemetry?channel=Z-1")
    assert res.status_code == 200
    body = res.json()
    assert body["totalPoints"] == 500
    assert len(body["points"]) <= 2000
    assert len(body["points"]) == len(body["pointIndices"])
    assert body["unit"] == "V"
    assert body["anomalyRanges"] == [{"start": 100, "end": 170, "detectionId": "DET-Z"}]


def test_telemetry_respects_from_and_to(client, db_session, tiny_channel):
    db_session.add(
        Channel(channel_id="CHN-Z-1", satellite_id="SAT-001", channel_name="Z-1", dataset_chan_id="Z-1")
    )
    db_session.commit()
    login(client, ANALYST)
    res = client.get("/api/satellites/SAT-001/telemetry?channel=Z-1&from=100&to=200")
    body = res.json()
    assert min(body["pointIndices"]) >= 100
    assert max(body["pointIndices"]) < 200


def test_channels_lists_channels_for_a_satellite(client, db_session):
    db_session.add(
        Channel(
            channel_id="CHN-A-1", satellite_id="SAT-001", channel_name="A-1", dataset_chan_id="A-1", unit="V"
        )
    )
    db_session.add(
        Channel(channel_id="CHN-A-2", satellite_id="SAT-001", channel_name="A-2", dataset_chan_id="A-2")
    )
    db_session.commit()
    login(client, ANALYST)
    res = client.get("/api/satellites/SAT-001/channels")
    assert res.status_code == 200
    body = res.json()
    assert [c["channelId"] for c in body] == ["A-1", "A-2"]
    assert body[0]["unit"] == "V"


def test_channels_requires_login(client):
    assert client.get("/api/satellites/SAT-001/channels").status_code == 401


def test_channels_unknown_satellite_is_404(client):
    login(client, ANALYST)
    assert client.get("/api/satellites/SAT-999/channels").status_code == 404


def test_downsampling_keeps_short_spikes():
    """A one-sample spike in 10,000 points must survive downsampling to 2,000: plain
    striding (every 5th point) dropped it, and with it the anomaly the chart should show."""
    from app.api.satellites import downsample_min_max

    series = np.ones(10_000, dtype=np.float32)
    series[4_321] = -1.0
    indices = downsample_min_max(series, 0, len(series), 2000)
    assert len(indices) <= 2000
    assert indices == sorted(indices)
    assert 4_321 in indices


def test_downsampling_returns_every_point_when_under_the_cap():
    from app.api.satellites import downsample_min_max

    assert downsample_min_max(np.arange(50, dtype=np.float32), 10, 40, 2000) == list(range(10, 40))
