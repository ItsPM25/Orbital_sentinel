from app.pipeline.explain.ranking import SatelliteRanking
from app.schemas.common import CamelModel, UtcDatetime


class SatelliteRankingOut(CamelModel):
    satellite_id: str
    satellite_name: str
    risk_level: int | None
    severity_level: str | None
    status: str | None
    alert_id: str | None
    last_detection_at: UtcDatetime | None

    @classmethod
    def from_ranking(cls, row: SatelliteRanking) -> "SatelliteRankingOut":
        return cls(
            satellite_id=row.satellite_id,
            satellite_name=row.satellite_name,
            risk_level=row.risk_level,
            severity_level=row.severity_level,
            status=row.status,
            alert_id=row.alert_id,
            last_detection_at=row.last_detection_at,
        )
