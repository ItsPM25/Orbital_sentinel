from tests.conftest import ADMIN, ANALYST, EVALUATOR, login


def test_login_returns_user_and_session_cookie(client):
    res = login(client, ANALYST)
    assert res.status_code == 200
    assert res.json()["user"] == {
        "userId": "USR-001",
        "firstName": "Test",
        "lastName": "Analyst",
        "role": "Analyst",
        "email": "analyst@orbitalsentinel.test",
    }
    assert "os_session" in res.cookies


def test_login_rejects_wrong_password(client):
    res = login(client, (ANALYST[0], "wrongpass"))
    assert res.status_code == 401
    assert res.json() == {"error": "Invalid email or password"}


def test_login_rejects_empty_body(client):
    assert client.post("/api/login", json={}).status_code == 401


def test_me_requires_login(client):
    assert client.get("/api/me").status_code == 401
    login(client, ADMIN)
    assert client.get("/api/me").json()["role"] == "Administrator"


def test_logout_ends_session(client):
    login(client, ANALYST)
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_alerts_require_login(client):
    assert client.get("/api/alerts").status_code == 401


def test_req16_alerts_are_risk_ordered(client):
    login(client, ANALYST)
    alerts = client.get("/api/alerts").json()
    assert len(alerts) == 8
    assert [a["riskLevel"] for a in alerts] == sorted((a["riskLevel"] for a in alerts), reverse=True)
    assert alerts[0]["alertId"] == "ALT-001"
    assert alerts[0]["riskLabel"] == "CRITICAL"
    assert alerts[-1]["alertId"] == "ALT-005"
    # Ties on risk level are broken by age: ALT-002 (08:30) before ALT-006 (10:20).
    assert [a["alertId"] for a in alerts if a["riskLevel"] == 7] == ["ALT-002", "ALT-006"]
    assert alerts[0] == {
        "alertId": "ALT-001",
        "detectionId": "DET-101",
        "riskLevel": 10,
        "createdAt": "2026-09-23T08:12:30Z",
        "acknowledgedBy": None,
        "acknowledgedAt": None,
        "status": "AlertRaised",
        "satelliteId": "SAT-001",
        "satelliteName": "SMAP",
        "riskLabel": "CRITICAL",
        "severityLevel": "CRITICAL",
        "anomalyScore": 0.97,
        "attributedChannel": None,  # demo seed data has no ATTRIBUTION rows
    }


def test_acknowledge_moves_alert_to_acknowledged(client):
    login(client, ANALYST)
    res = client.post("/api/alerts/ALT-003/acknowledge")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "Acknowledged"
    assert body["acknowledgedBy"] == "USR-001"
    assert body["acknowledgedAt"] is not None

    # Acknowledging again changes nothing.
    again = client.post("/api/alerts/ALT-003/acknowledge").json()
    assert again["acknowledgedAt"] == body["acknowledgedAt"]

    statuses = {a["alertId"]: a["status"] for a in client.get("/api/alerts").json()}
    assert statuses["ALT-003"] == "Acknowledged"
    assert statuses["ALT-001"] == "AlertRaised"


def test_acknowledge_unknown_alert_is_404(client):
    login(client, ANALYST)
    res = client.post("/api/alerts/ALT-999/acknowledge")
    assert res.status_code == 404
    assert res.json() == {"error": "Alert ALT-999 not found"}


def test_acknowledge_requires_login(client):
    assert client.post("/api/alerts/ALT-001/acknowledge").status_code == 401


def test_evaluator_cannot_acknowledge(client):
    login(client, EVALUATOR)
    assert client.post("/api/alerts/ALT-001/acknowledge").status_code == 403
    assert client.get("/api/alerts").status_code == 200


def test_reset_restores_demo_alerts(client):
    login(client, ANALYST)
    client.post("/api/alerts/ALT-001/acknowledge")
    assert client.get("/api/reset").json() == {"ok": True}
    assert all(a["status"] == "AlertRaised" for a in client.get("/api/alerts").json())


def test_api_responses_are_not_cached(client):
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_reset_removes_alerts_written_by_monitoring(client, db_session):
    """After a replay has raised its own alerts, reset leaves exactly the 8 demo alerts."""
    from datetime import datetime, timezone

    from app.models import Alert, AlertStatus, Detection, DetectionOutcome

    db_session.add(
        Detection(
            detection_id="DET-REPLAY",
            satellite_id="SAT-002",
            model_id="MDL-DEMO-1",
            timestamp=datetime(2015, 1, 31, tzinfo=timezone.utc),
            anomaly_score=2.0,
            severity_level="LOW",
            persistence_count=3,
            outcome=DetectionOutcome.CONFIRMED,
        )
    )
    db_session.add(
        Alert(
            alert_id="ALT-REPLAY",
            detection_id="DET-REPLAY",
            risk_level=10,
            created_at=datetime(2015, 1, 31, tzinfo=timezone.utc),
            status=AlertStatus.ALERT_RAISED,
        )
    )
    db_session.commit()
    login(client, ANALYST)
    assert len(client.get("/api/alerts").json()) == 9

    client.get("/api/reset")
    alert_ids = sorted(a["alertId"] for a in client.get("/api/alerts").json())
    assert alert_ids == [f"ALT-00{i}" for i in range(1, 9)]
