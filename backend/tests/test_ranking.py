"""REQ-10: satellites ordered by current severity, then risk_level, then recency."""

from app.models import Alert, AlertStatus, Detection, DetectionOutcome
from app.pipeline.explain.ranking import rank_satellites

MODEL_ID = "MDL-DEMO-1"


def add_detection_and_alert(db, detection_id, satellite_id, alert_id, risk_level, status, created_at):
    db.add(
        Detection(
            detection_id=detection_id,
            satellite_id=satellite_id,
            model_id=MODEL_ID,
            timestamp=created_at,
            anomaly_score=2.0,
            severity_level="HIGH",
            persistence_count=3,
            outcome=DetectionOutcome.CONFIRMED,
        )
    )
    db.add(
        Alert(
            alert_id=alert_id,
            detection_id=detection_id,
            risk_level=risk_level,
            created_at=created_at,
            status=status,
        )
    )
    db.commit()


def test_rank_satellites_matches_the_seeded_demo_alerts(db_session):
    """Uses app/seed.py's 8 demo alerts, already present via the db_session fixture."""
    rows = rank_satellites(db_session)
    order = [r.satellite_id for r in rows]
    assert order[:5] == ["SAT-001", "SAT-004", "SAT-002", "SAT-003", "SAT-005"]
    assert [r.risk_level for r in rows[:5]] == [10, 9, 7, 5, 2]


def test_rank_satellites_picks_highest_risk_open_alert_per_satellite(db_session):
    from datetime import datetime, timezone

    from app.models import Alert as AlertRow

    db_session.query(AlertRow).delete()
    db_session.query(Detection).delete()
    db_session.commit()

    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_detection_and_alert(db_session, "DET-X1", "SAT-001", "ALT-X1", 3, AlertStatus.ALERT_RAISED, t)
    add_detection_and_alert(db_session, "DET-X2", "SAT-001", "ALT-X2", 8, AlertStatus.ALERT_RAISED, t)

    rows = rank_satellites(db_session)
    sat1 = next(r for r in rows if r.satellite_id == "SAT-001")
    assert sat1.risk_level == 8
    assert sat1.alert_id == "ALT-X2"


def test_rank_satellites_ignores_resolved_alerts(db_session):
    from datetime import datetime, timezone

    from app.models import Alert as AlertRow

    db_session.query(AlertRow).delete()
    db_session.query(Detection).delete()
    db_session.commit()

    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_detection_and_alert(db_session, "DET-Y1", "SAT-001", "ALT-Y1", 9, AlertStatus.RESOLVED, t)

    rows = rank_satellites(db_session)
    sat1 = next(r for r in rows if r.satellite_id == "SAT-001")
    assert sat1.risk_level is None
    assert sat1.alert_id is None


def test_rank_satellites_with_no_alerts_at_all_ranks_last(db_session):
    from app.models import Alert as AlertRow

    db_session.query(AlertRow).delete()
    db_session.query(Detection).delete()
    db_session.commit()

    rows = rank_satellites(db_session)
    assert len(rows) == 5
    assert all(r.risk_level is None for r in rows)
