from app.schemas.common import CamelModel


class StartSessionRequest(CamelModel):
    satellite_id: str
    model_id: str = "MDL-LSTM-100-80"


class SessionCountersOut(CamelModel):
    windows: int
    normal: int
    detections: int
    malformed: int
    interpolated: int
    last_score_ms: float
    max_score_ms: float


class SessionStatusOut(CamelModel):
    satellite_id: str
    model_id: str
    running: bool
    counters: SessionCountersOut | None = None
