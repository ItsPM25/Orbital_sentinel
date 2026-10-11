from app.schemas.common import CamelModel


class EvaluationMetricsOut(CamelModel):
    """REQ-5 / REQ-11: served from the precomputed report JSON (app/evaluation/baseline.py
    and app/evaluation/reports.py), never recomputed live - running inference over every
    labelled channel on each request would blow the ~1s budget (SRS 5.1)."""

    available: bool
    model_id: str | None = None
    persistence: str | None = None  # "on" | "off" | None when unfiltered baseline
    generated_at: str | None = None
    channels_evaluated: int | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    point_fpr: float | None = None
    message: str | None = None
