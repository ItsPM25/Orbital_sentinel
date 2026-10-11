"""GET/PUT /api/admin/config, POST /api/admin/datasets/import, GET /api/admin/models."""

import numpy as np
import pytest

from app.models import MonitoringConfig
from tests.conftest import ADMIN, ANALYST, EVALUATOR, login


def test_config_requires_admin(client):
    login(client, ANALYST)
    assert client.get("/api/admin/config/SAT-001").status_code == 403
    body = {"persistenceThreshold": 2, "severityThreshold": 0.5}
    assert client.put("/api/admin/config/SAT-001", json=body).status_code == 403


def test_get_config_returns_the_active_row(client):
    login(client, ADMIN)
    res = client.get("/api/admin/config/SAT-001")
    assert res.status_code == 200
    body = res.json()
    assert body["satelliteId"] == "SAT-001"
    assert body["isActive"] is True


def test_get_config_unknown_satellite_is_404(client):
    login(client, ADMIN)
    assert client.get("/api/admin/config/SAT-999").status_code == 404


def test_update_config_writes_a_new_row_and_deactivates_the_old_one(client, db_session):
    login(client, ADMIN)
    old = client.get("/api/admin/config/SAT-001").json()
    res = client.put("/api/admin/config/SAT-001", json={"persistenceThreshold": 5, "severityThreshold": 0.3})
    assert res.status_code == 200
    new = res.json()
    assert new["persistenceThreshold"] == 5
    assert new["severityThreshold"] == 0.3
    assert new["isActive"] is True
    assert new["configId"] != old["configId"]

    rows = db_session.query(MonitoringConfig).filter_by(satellite_id="SAT-001").all()
    assert len(rows) == 2  # history kept, not overwritten
    assert sum(r.is_active for r in rows) == 1


def test_update_config_rejects_persistence_below_one(client):
    login(client, ADMIN)
    res = client.put("/api/admin/config/SAT-001", json={"persistenceThreshold": 0, "severityThreshold": 0.5})
    assert res.status_code == 422


def test_dataset_import_requires_admin(client):
    login(client, EVALUATOR)
    assert client.post("/api/admin/datasets/import", json={}).status_code == 403


def test_dataset_import_succeeds_against_a_tiny_dataset(client, tmp_path, monkeypatch):
    (tmp_path / "train").mkdir()
    (tmp_path / "test").mkdir()
    np.save(tmp_path / "train" / "Z-1.npy", np.zeros((10, 1), dtype=np.float32))
    np.save(tmp_path / "test" / "Z-1.npy", np.ones((10, 1), dtype=np.float32))
    (tmp_path / "labeled_anomalies.csv").write_text(
        'chan_id,spacecraft,anomaly_sequences,class,num_values\nZ-1,SMAP,"[[1, 2]]",[point],10\n'
    )
    monkeypatch.setattr("app.pipeline.import_dataset.settings.data_dir", tmp_path)

    login(client, ADMIN)
    res = client.post("/api/admin/datasets/import", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["channelsCreated"] == 1
    assert body["includeReadings"] is False


def test_models_requires_admin_or_evaluator(client):
    login(client, ANALYST)
    assert client.get("/api/admin/models").status_code == 403


def test_models_lists_the_seeded_demo_model(client):
    login(client, EVALUATOR)
    res = client.get("/api/admin/models")
    assert res.status_code == 200
    body = res.json()
    assert any(m["modelId"] == "MDL-DEMO-1" for m in body)
    assert all("channelsTrained" in m for m in body)


@pytest.fixture()
def no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.models_dir", tmp_path)


def test_models_channels_trained_is_zero_without_a_manifest(client, no_manifest):
    login(client, ADMIN)
    res = client.get("/api/admin/models")
    body = res.json()
    assert all(m["channelsTrained"] == 0 for m in body)
