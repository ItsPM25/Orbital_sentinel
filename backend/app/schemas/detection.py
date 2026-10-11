from app.models import Detection
from app.schemas.common import CamelModel, UtcDatetime


class DetectionOut(CamelModel):
    detection_id: str
    satellite_id: str
    satellite_name: str
    model_id: str
    timestamp: UtcDatetime
    anomaly_score: float
    severity_level: str | None
    persistence_count: int
    outcome: str | None

    @classmethod
    def from_detection(cls, detection: Detection) -> "DetectionOut":
        return cls(
            detection_id=detection.detection_id,
            satellite_id=detection.satellite_id,
            satellite_name=detection.satellite.name,
            model_id=detection.model_id,
            timestamp=detection.timestamp,
            anomaly_score=detection.anomaly_score,
            severity_level=detection.severity_level,
            persistence_count=detection.persistence_count,
            outcome=detection.outcome,
        )
