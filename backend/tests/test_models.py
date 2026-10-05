from datetime import timezone

from sqlalchemy import inspect

from app.models import Alert, Detection, Satellite, User

ER_TABLES = {
    "satellite",
    "channel",
    "telemetry_reading",
    "detection_model",
    "detection",
    "attribution",
    "alert",
    "user",
    "monitoring_config",
    # child tables for the multivalued attributes
    "satellite_mission_tag",
    "user_contact_email",
}


def test_every_er_entity_has_a_table(db_session):
    assert set(inspect(db_session.get_bind()).get_table_names()) == ER_TABLES


def test_seed_creates_one_user_per_role(db_session):
    roles = sorted(u.role for u in db_session.query(User).all())
    assert roles == ["Administrator", "Analyst", "Evaluator"]


def test_only_smap_is_a_real_telemetry_source(db_session):
    real = [s.name for s in db_session.query(Satellite).filter_by(is_proxy=False)]
    assert real == ["SMAP"]


def test_is_anomaly_is_derived_from_model_threshold(db_session):
    detection = db_session.get(Detection, "DET-101")
    assert detection.is_anomaly is True
    detection.anomaly_score = detection.model.threshold - 0.01
    assert detection.is_anomaly is False


def test_datetimes_come_back_timezone_aware(db_session):
    db_session.expire_all()
    alert = db_session.get(Alert, "ALT-001")
    assert alert.created_at.tzinfo == timezone.utc
