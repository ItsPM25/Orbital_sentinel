"""Seed data: one user per role, the demo fleet, and demo alerts.

The detections and alerts here are placeholders so the dashboard has data
before the real pipeline exists. Phases 2-3 replace them with detections
produced from replayed telemetry.

Run with:  python -m app.seed
"""

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Alert,
    AlertStatus,
    Detection,
    DetectionModel,
    DetectionOutcome,
    MonitoringConfig,
    Role,
    Satellite,
    SatelliteMissionTag,
    User,
    UserContactEmail,
)

USERS = [
    ("USR-001", "Test", "Analyst", Role.ANALYST, "analyst@orbitalsentinel.test", "sentinel123"),
    ("USR-002", "Test", "Administrator", Role.ADMINISTRATOR, "admin@orbitalsentinel.test", "admin123"),
    ("USR-003", "Test", "Evaluator", Role.EVALUATOR, "evaluator@orbitalsentinel.test", "evaluator123"),
]

# SMAP is the real spacecraft behind the dataset; the others are proxies that will
# replay SMAP/MSL channels (docs/ARCHITECTURE.md section 4.3).
SATELLITES = [
    ("SAT-001", "SMAP", 40376, False, "Earth observation"),
    ("SAT-002", "Aqua", 27424, True, "Earth observation"),
    ("SAT-003", "Terra", 25994, True, "Earth observation"),
    ("SAT-004", "Landsat 9", 49260, True, "Earth observation"),
    ("SAT-005", "Sentinel-2A", 40697, True, "Earth observation"),
]

DEMO_MODEL_ID = "MDL-DEMO-1"

# (detection_id, alert_id, satellite_id, time, anomaly_score, severity, persistence, risk_level)
DEMO_ALERTS = [
    ("DET-101", "ALT-001", "SAT-001", "08:12", 0.97, "CRITICAL", 9, 10),
    ("DET-102", "ALT-002", "SAT-002", "08:30", 0.81, "HIGH", 6, 7),
    ("DET-103", "ALT-003", "SAT-003", "09:05", 0.55, "MEDIUM", 4, 5),
    ("DET-104", "ALT-004", "SAT-004", "09:40", 0.91, "CRITICAL", 8, 9),
    ("DET-105", "ALT-005", "SAT-005", "10:02", 0.38, "LOW", 3, 2),
    ("DET-106", "ALT-006", "SAT-001", "10:20", 0.72, "HIGH", 5, 7),
    ("DET-107", "ALT-007", "SAT-003", "11:15", 0.47, "MEDIUM", 3, 4),
    ("DET-108", "ALT-008", "SAT-002", "11:48", 0.33, "LOW", 3, 3),
]


def _demo_time(hhmm: str, second: int) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(2026, 9, 23, hour, minute, second, tzinfo=timezone.utc)


def _telemetry_sources() -> dict[str, str]:
    """ADR-004's fleet channel split, summarised per satellite for the honest-framing
    badge (SRS 2.7). Falls back to a generic note if the dataset isn't downloaded yet
    (scripts/get_data) - seeding must not fail just because data/ is missing."""
    try:
        from app.pipeline.fleet import build_fleet_channel_map, telemetry_source_summary

        fleet_map = build_fleet_channel_map()
        return {sat_id: telemetry_source_summary(sat_id, fleet_map) for sat_id, *_ in SATELLITES}
    except (FileNotFoundError, OSError):
        return {}


def seed_reference(db: Session) -> None:
    """Users, satellites, the demo model and default monitoring configs. Safe to rerun."""
    for user_id, first, last, role, email, password in USERS:
        if db.get(User, user_id) is None:
            db.add(
                User(
                    user_id=user_id,
                    first_name=first,
                    last_name=last,
                    role=role,
                    password_hash=hash_password(password),
                    contact_emails=[UserContactEmail(contact_email=email)],
                )
            )

    telemetry_sources = _telemetry_sources()
    for satellite_id, name, norad_id, is_proxy, tag in SATELLITES:
        existing = db.get(Satellite, satellite_id)
        source = telemetry_sources.get(satellite_id, "dataset not imported yet")
        if existing is not None:
            # Refreshable on rerun: the fleet channel split (ADR-004) can change
            # across versions, and a satellite seeded before data/ was imported
            # would otherwise be stuck showing "dataset not imported yet" forever.
            existing.telemetry_source = source
        else:
            db.add(
                Satellite(
                    satellite_id=satellite_id,
                    name=name,
                    norad_id=norad_id,
                    is_proxy=is_proxy,
                    telemetry_source=source,
                    mission_tags=[SatelliteMissionTag(mission_tag=tag)],
                )
            )
            db.add(
                MonitoringConfig(
                    config_id=f"CFG-{satellite_id[4:]}",
                    satellite_id=satellite_id,
                    set_by_user_id="USR-002",
                    persistence_threshold=3,
                    severity_threshold=0.5,
                )
            )

    if db.get(DetectionModel, DEMO_MODEL_ID) is None:
        db.add(
            DetectionModel(
                model_id=DEMO_MODEL_ID,
                model_name="demo-placeholder",
                model_type="placeholder",
                threshold=0.3,
            )
        )
    db.commit()


def seed_demo_alerts(db: Session) -> None:
    """Deletes and recreates the demo detections and alerts (all back to AlertRaised)."""
    detection_ids = [row[0] for row in DEMO_ALERTS]
    db.execute(delete(Alert).where(Alert.detection_id.in_(detection_ids)))
    db.execute(delete(Detection).where(Detection.detection_id.in_(detection_ids)))
    for detection_id, alert_id, satellite_id, hhmm, score, severity, persistence, risk in DEMO_ALERTS:
        db.add(
            Detection(
                detection_id=detection_id,
                satellite_id=satellite_id,
                model_id=DEMO_MODEL_ID,
                timestamp=_demo_time(hhmm, 0),
                anomaly_score=score,
                severity_level=severity,
                persistence_count=persistence,
                outcome=DetectionOutcome.CONFIRMED,
            )
        )
        db.add(
            Alert(
                alert_id=alert_id,
                detection_id=detection_id,
                risk_level=risk,
                created_at=_demo_time(hhmm, 30),
                status=AlertStatus.ALERT_RAISED,
            )
        )
    db.commit()


def seed_all(db: Session) -> None:
    seed_reference(db)
    seed_demo_alerts(db)


if __name__ == "__main__":
    from app.core.db import SessionLocal

    with SessionLocal() as session:
        seed_all(session)
    print("Seeded users, satellites, monitoring configs and demo alerts.")
