from app.models import Satellite
from app.pipeline.explain.ranking import SatelliteRanking
from app.schemas.common import CamelModel, UtcDatetime


class SatelliteOut(CamelModel):
    """A satellite with its current risk, verdict and proxy flag (ARCHITECTURE.md 7)."""

    satellite_id: str
    name: str
    norad_id: int | None
    current_status: str
    is_proxy: bool
    risk_level: int | None
    verdict: str  # "Anomalous" if there's an open alert, else "Nominal"
    severity_level: str | None

    @classmethod
    def from_satellite(cls, satellite: Satellite, ranking: SatelliteRanking | None) -> "SatelliteOut":
        return cls(
            satellite_id=satellite.satellite_id,
            name=satellite.name,
            norad_id=satellite.norad_id,
            current_status=satellite.current_status,
            is_proxy=satellite.is_proxy,
            risk_level=ranking.risk_level if ranking else None,
            verdict="Anomalous" if ranking and ranking.risk_level is not None else "Nominal",
            severity_level=ranking.severity_level if ranking else None,
        )


class AttributedChannelOut(CamelModel):
    channel_id: str
    channel_name: str
    contribution_score: float


class ChannelOut(CamelModel):
    channel_id: str  # dataset_chan_id
    channel_name: str
    unit: str | None


class SatelliteHealthOut(CamelModel):
    """The health panel: latest verdict, severity and attribution for one satellite."""

    satellite_id: str
    satellite_name: str
    verdict: str
    risk_level: int | None
    severity_level: str | None
    anomaly_score: float | None
    detection_id: str | None
    detected_at: UtcDatetime | None
    attributed_channels: list[AttributedChannelOut]
    is_proxy: bool
    telemetry_source: str | None
