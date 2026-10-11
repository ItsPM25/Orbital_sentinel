"""GET /api/ranking (REQ-10)."""

from tests.conftest import ANALYST, login


def test_ranking_requires_login(client):
    assert client.get("/api/ranking").status_code == 401


def test_ranking_matches_the_seeded_demo_alerts(client):
    login(client, ANALYST)
    res = client.get("/api/ranking")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 5
    assert [r["satelliteId"] for r in body[:3]] == ["SAT-001", "SAT-004", "SAT-002"]
    assert body[0]["riskLevel"] == 10
