from app.models import MonitoringConfig
from app.schemas.common import CamelModel, UtcDatetime


class MonitoringConfigOut(CamelModel):
    config_id: str
    satellite_id: str
    set_by_user_id: str
    persistence_threshold: int
    severity_threshold: float
    updated_at: UtcDatetime
    is_active: bool

    @classmethod
    def from_row(cls, row: MonitoringConfig) -> "MonitoringConfigOut":
        return cls(
            config_id=row.config_id,
            satellite_id=row.satellite_id,
            set_by_user_id=row.set_by_user_id,
            persistence_threshold=row.persistence_threshold,
            severity_threshold=row.severity_threshold,
            updated_at=row.updated_at,
            is_active=row.is_active,
        )


class UpdateMonitoringConfigRequest(CamelModel):
    persistence_threshold: int
    severity_threshold: float


class DatasetImportRequest(CamelModel):
    include_readings: bool = False


class DatasetImportOut(CamelModel):
    channels_created: int
    channels_updated: int
    channels: int
    readings: int
    include_readings: bool


class DetectionModelOut(CamelModel):
    model_id: str
    model_name: str
    model_type: str
    threshold: float
    trained_at: UtcDatetime | None
    channels_trained: int
