"""POST/DELETE/GET /api/sessions and GET /api/detections (admin-only session control,
REQ-18 detection log). Uses monkeypatched session_service functions so these tests
don't need a trained model or the dataset on disk."""

from unittest.mock import AsyncMock

from app.services import sessions as session_service
from tests.conftest import ADMIN, ANALYST, EVALUATOR, login


def test_sessions_require_admin(client):
    login(client, ANALYST)
    assert client.post("/api/sessions", json={"satelliteId": "SAT-001"}).status_code == 403


def test_sessions_require_login(client):
    assert client.post("/api/sessions", json={"satelliteId": "SAT-001"}).status_code == 401


def test_start_session_success(client, monkeypatch):
    async def fake_start(satellite_id, model_id, speed=None):
        return None

    monkeypatch.setattr(session_service, "start_session", AsyncMock(side_effect=fake_start))
    login(client, ADMIN)
    res = client.post("/api/sessions", json={"satelliteId": "SAT-001", "modelId": "MDL-LSTM-100-80"})
    assert res.status_code == 201
    assert res.json() == {
        "satelliteId": "SAT-001",
        "modelId": "MDL-LSTM-100-80",
        "running": True,
        "counters": None,
    }


def test_start_session_conflict_when_already_running(client, monkeypatch):
    async def fake_start(*a, **kw):
        raise session_service.SessionAlreadyRunning("SAT-001")

    monkeypatch.setattr(session_service, "start_session", AsyncMock(side_effect=fake_start))
    login(client, ADMIN)
    res = client.post("/api/sessions", json={"satelliteId": "SAT-001"})
    assert res.status_code == 409


def test_start_session_unknown_satellite_is_404(client, monkeypatch):
    async def fake_start(*a, **kw):
        raise ValueError("Unknown satellite SAT-999")

    monkeypatch.setattr(session_service, "start_session", AsyncMock(side_effect=fake_start))
    login(client, ADMIN)
    res = client.post("/api/sessions", json={"satelliteId": "SAT-999"})
    assert res.status_code == 404


def test_start_session_no_trained_channels_is_422(client, monkeypatch):
    async def fake_start(*a, **kw):
        raise session_service.NoTrainedChannels("SAT-001")

    monkeypatch.setattr(session_service, "start_session", AsyncMock(side_effect=fake_start))
    login(client, ADMIN)
    res = client.post("/api/sessions", json={"satelliteId": "SAT-001"})
    assert res.status_code == 422


def test_stop_session_not_running_is_404(client, monkeypatch):
    monkeypatch.setattr(session_service, "stop_session", AsyncMock(return_value=False))
    login(client, ADMIN)
    res = client.delete("/api/sessions/SAT-001")
    assert res.status_code == 404


def test_stop_session_success(client, monkeypatch):
    monkeypatch.setattr(session_service, "stop_session", AsyncMock(return_value=True))
    login(client, ADMIN)
    res = client.delete("/api/sessions/SAT-001")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_list_sessions_allows_evaluator(client, monkeypatch):
    monkeypatch.setattr(session_service, "list_running", lambda: [])
    login(client, EVALUATOR)
    assert client.get("/api/sessions").status_code == 200


def test_list_sessions_forbidden_for_analyst(client):
    login(client, ANALYST)
    assert client.get("/api/sessions").status_code == 403


# --- GET /api/detections (REQ-18) -------------------------------------------------------------


def test_detections_require_login(client):
    assert client.get("/api/detections").status_code == 401


def test_detections_lists_the_seeded_demo_detections(client):
    login(client, ANALYST)
    res = client.get("/api/detections")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 8  # one per demo alert (app/seed.py)
    assert {d["outcome"] for d in body} == {"Confirmed"}


def test_detections_any_role_can_read(client):
    login(client, EVALUATOR)
    assert client.get("/api/detections").status_code == 200
