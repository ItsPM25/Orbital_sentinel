from app.models import Alert
from app.pipeline.explain.severity import risk_label
from app.schemas.common import CamelModel, UtcDatetime

__all__ = ["AlertView", "risk_label"]


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
    attributed_channel: str | None  # REQ-16: the top attributed channel, if any (else "unknown")

    @classmethod
    def from_alert(cls, alert: Alert) -> "AlertView":
        detection = alert.detection
        top_attribution = max(detection.attributions, key=lambda a: a.contribution_score, default=None)
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
            attributed_channel=(top_attribution.channel.channel_name if top_attribution else None),
        )
