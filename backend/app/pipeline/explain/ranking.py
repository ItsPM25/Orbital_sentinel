"""3.4 Risk ranking (REQ-10): satellites ordered by current severity, then
risk_level, then recency.

"Current severity" is the highest-risk open alert (status != Resolved) for
that satellite; a satellite with no open alert ranks after every satellite
that has one, since it currently has nothing to report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Alert, AlertStatus, Satellite
from app.pipeline.explain.severity import risk_label


@dataclass
class SatelliteRanking:
    satellite_id: str
    satellite_name: str
    risk_level: int | None
    severity_level: str | None
    status: str | None  # the open alert's status, or None if nominal
    alert_id: str | None
    last_detection_at: datetime | None


def rank_satellites(db: Session) -> list[SatelliteRanking]:
    satellites = db.scalars(select(Satellite)).all()
    open_alerts = db.scalars(
        select(Alert).options(joinedload(Alert.detection)).where(Alert.status != AlertStatus.RESOLVED)
    ).all()

    best_per_satellite: dict[str, Alert] = {}
    for alert in open_alerts:
        satellite_id = alert.detection.satellite_id
        current = best_per_satellite.get(satellite_id)
        if current is None or (alert.risk_level, alert.created_at) > (current.risk_level, current.created_at):
            best_per_satellite[satellite_id] = alert

    rows = []
    for satellite in satellites:
        alert = best_per_satellite.get(satellite.satellite_id)
        if alert is None:
            rows.append(
                SatelliteRanking(satellite.satellite_id, satellite.name, None, None, None, None, None)
            )
            continue
        rows.append(
            SatelliteRanking(
                satellite_id=satellite.satellite_id,
                satellite_name=satellite.name,
                risk_level=alert.risk_level,
                # The alert's current band, not its first detection's: an episode's
                # risk_level only escalates, so the opening detection's label goes
                # stale (it read LOW next to risk 10).
                severity_level=risk_label(alert.risk_level),
                status=alert.status,
                alert_id=alert.alert_id,
                last_detection_at=alert.detection.timestamp,
            )
        )

    rows.sort(key=lambda r: (r.risk_level is None, -(r.risk_level or 0), r.satellite_name))
    return rows
