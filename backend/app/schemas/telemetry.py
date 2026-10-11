from app.schemas.common import CamelModel


class AnomalyRange(CamelModel):
    start: int
    end: int
    detection_id: str


class TelemetrySeriesOut(CamelModel):
    satellite_id: str
    channel_id: str  # dataset_chan_id
    channel_name: str
    unit: str | None
    total_points: int
    points: list[float]  # downsampled telemetry values
    point_indices: list[int]  # original index of each downsampled point
    anomaly_ranges: list[AnomalyRange]  # REQ-17: ranges the model actually flagged, not ground truth
    is_proxy: bool
