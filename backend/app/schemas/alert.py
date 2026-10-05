from app.models import Alert, SeverityLevel
from app.schemas.common import CamelModel, UtcDatetime


def risk_label(risk_level: int) -> SeverityLevel:
    if risk_level >= 9:
        return SeverityLevel.CRITICAL
    if risk_level >= 6:
        return SeverityLevel.HIGH
    if risk_level >= 4:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


class AlertView(CamelModel):
    """An Alert joined with its Detection and Satellite (same shape as the Exp 9 API)."""

    alert_id: str
    detection_id: str
    risk_level: int
    created_at: UtcDatetime
    acknowledged_by: str | None
    acknowledged_at: UtcDatetime | None
    status: str
    satellite_id: str
    satellite_name: str
    risk_label: str
    severity_level: str | None
    anomaly_score: float

    @classmethod
    def from_alert(cls, alert: Alert) -> "AlertView":
        detection = alert.detection
        return cls(
            alert_id=alert.alert_id,
            detection_id=alert.detection_id,
            risk_level=alert.risk_level,
            created_at=alert.created_at,
            acknowledged_by=alert.acknowledged_by,
            acknowledged_at=alert.acknowledged_at,
            status=alert.status,
            satellite_id=detection.satellite_id,
            satellite_name=detection.satellite.name,
            risk_label=risk_label(alert.risk_level),
            severity_level=detection.severity_level,
            anomaly_score=detection.anomaly_score,
        )
