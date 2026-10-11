"""GET /api/evaluation/metrics (REQ-5 / REQ-11), served from precomputed JSON reports."""

import json

from tests.conftest import ADMIN, ANALYST, EVALUATOR, login


def test_metrics_requires_admin_or_evaluator(client):
    login(client, ANALYST)
    assert client.get("/api/evaluation/metrics").status_code == 403


def test_metrics_unavailable_when_no_report_exists(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.evaluation.settings.results_dir", tmp_path)
    login(client, EVALUATOR)
    res = client.get("/api/evaluation/metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert "python -m app.evaluation.baseline" in body["message"]


def test_metrics_baseline_reads_the_report(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.evaluation.settings.results_dir", tmp_path)
    report = {
        "model_id": "MDL-LSTM-100-80",
        "channels_evaluated": 10,
        "overall": {"precision": 0.9, "recall": 0.6, "f1": 0.72, "point_fpr": 0.02},
    }
    (tmp_path / "phase2_baseline.json").write_text(json.dumps(report))

    login(client, EVALUATOR)
    res = client.get("/api/evaluation/metrics?modelId=MDL-LSTM-100-80")
    body = res.json()
    assert body["available"] is True
    assert body["precision"] == 0.9
    assert body["channelsEvaluated"] == 10
    assert body["persistence"] is None


def test_metrics_persistence_on_off_reads_the_comparison_report(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.evaluation.settings.results_dir", tmp_path)
    report = {
        "channels": ["A-1", "A-2"],
        "comparison": {
            "chosen_persistence_n": 3,
            "without_filter": {"precision": 0.3, "recall": 0.8, "f1": 0.44, "point_fpr": 0.1},
            "with_filter": {"precision": 0.8, "recall": 0.6, "f1": 0.69, "point_fpr": 0.01},
        },
    }
    (tmp_path / "phase3_persistence_comparison.json").write_text(json.dumps(report))

    login(client, ADMIN)
    off = client.get("/api/evaluation/metrics?persistence=off").json()
    on = client.get("/api/evaluation/metrics?persistence=on").json()
    assert off["pointFpr"] == 0.1
    assert on["pointFpr"] == 0.01
    assert on["persistence"] == "on"


def test_metrics_rejects_an_invalid_persistence_value(client):
    login(client, ADMIN)
    assert client.get("/api/evaluation/metrics?persistence=maybe").status_code == 422
