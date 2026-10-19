import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.settings import settings
from app.models import Alert, AlertStatus, Attribution, Channel, Detection, DetectionOutcome, Satellite, User
from app.pipeline.dataset import load_channel
from app.pipeline.explain.ranking import rank_satellites
from app.schemas.satellite import AttributedChannelOut, ChannelOut, SatelliteHealthOut, SatelliteOut
from app.schemas.telemetry import AnomalyRange, TelemetrySeriesOut

router = APIRouter(tags=["satellites"])

MAX_POINTS = 2000  # server-side downsampling cap (ARCHITECTURE.md 5.6)


def _get_satellite(db: Session, satellite_id: str) -> Satellite:
    satellite = db.get(Satellite, satellite_id)
    if satellite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Satellite {satellite_id} not found")
    return satellite


@router.get("/satellites", response_model=list[SatelliteOut])
def list_satellites(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    satellites = db.scalars(select(Satellite)).all()
    rankings = {row.satellite_id: row for row in rank_satellites(db)}
    return [SatelliteOut.from_satellite(s, rankings.get(s.satellite_id)) for s in satellites]


@router.get("/satellites/{satellite_id}/health", response_model=SatelliteHealthOut)
def get_satellite_health(
    satellite_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    """The health panel: latest verdict, severity and attribution (REQ-15's target view)."""
    satellite = _get_satellite(db, satellite_id)
    open_alert = db.scalar(
        select(Alert)
        .join(Detection)
        .options(joinedload(Alert.detection))
        .where(Detection.satellite_id == satellite_id, Alert.status != AlertStatus.RESOLVED)
        .order_by(Alert.risk_level.desc(), Alert.created_at.desc())
    )
    if open_alert is None:
        return SatelliteHealthOut(
            satellite_id=satellite.satellite_id,
            satellite_name=satellite.name,
            verdict="Nominal",
            risk_level=None,
            severity_level=None,
            anomaly_score=None,
            detection_id=None,
            detected_at=None,
            attributed_channels=[],
            is_proxy=satellite.is_proxy,
            telemetry_source=satellite.telemetry_source,
        )
    detection = open_alert.detection
    attributions = db.scalars(
        select(Attribution)
        .options(joinedload(Attribution.channel))
        .where(Attribution.detection_id == detection.detection_id)
        .order_by(Attribution.contribution_score.desc())
    ).all()
    return SatelliteHealthOut(
        satellite_id=satellite.satellite_id,
        satellite_name=satellite.name,
        verdict="Anomalous",
        risk_level=open_alert.risk_level,
        severity_level=detection.severity_level,
        anomaly_score=detection.anomaly_score,
        detection_id=detection.detection_id,
        detected_at=detection.timestamp,
        attributed_channels=[
            AttributedChannelOut(
                channel_id=a.channel.dataset_chan_id or a.channel_id,
                channel_name=a.channel.channel_name,
                contribution_score=a.contribution_score,
            )
            for a in attributions
        ],
        is_proxy=satellite.is_proxy,
        telemetry_source=satellite.telemetry_source,
    )


@router.get("/satellites/{satellite_id}/channels", response_model=list[ChannelOut])
def list_satellite_channels(
    satellite_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    _get_satellite(db, satellite_id)
    rows = db.scalars(
        select(Channel).where(Channel.satellite_id == satellite_id).order_by(Channel.channel_name)
    ).all()
    return [
        ChannelOut(
            channel_id=row.dataset_chan_id or row.channel_id, channel_name=row.channel_name, unit=row.unit
        )
        for row in rows
    ]


def downsample_min_max(series: np.ndarray, lo: int, hi: int, max_points: int) -> list[int]:
    """Indices into series[lo:hi], at most max_points of them, keeping each bucket's
    minimum and maximum in index order. Plain striding (every k-th point) drops short
    spikes, and a short spike is often exactly the anomaly the chart is there to show."""
    n = hi - lo
    if n <= max_points:
        return list(range(lo, hi))
    buckets = max_points // 2
    edges = np.linspace(lo, hi, buckets + 1).astype(int)
    indices: list[int] = []
    for start, end in zip(edges[:-1], edges[1:], strict=True):
        if end <= start:
            continue
        chunk = series[start:end]
        pair = sorted({start + int(np.argmin(chunk)), start + int(np.argmax(chunk))})
        indices.extend(pair)
    return indices


@router.get("/satellites/{satellite_id}/telemetry", response_model=TelemetrySeriesOut)
def get_satellite_telemetry(
    satellite_id: str,
    channel: str = Query(..., description="dataset_chan_id, e.g. A-1"),
    frm: int = Query(default=0, alias="from", ge=0),
    to: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Downsampled telemetry plus the ranges the model actually flagged (REQ-17)."""
    satellite = _get_satellite(db, satellite_id)
    channel_row = db.scalar(
        select(Channel).where(Channel.satellite_id == satellite_id, Channel.dataset_chan_id == channel)
    )
    if channel_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Channel {channel} not found on {satellite_id}")

    series = load_channel(channel, "test", settings.data_dir)[:, 0]
    total_points = len(series)
    hi = min(to, total_points) if to is not None else total_points
    lo = min(frm, hi)
    indices = downsample_min_max(series, lo, hi, MAX_POINTS)
    points = [float(series[i]) for i in indices]

    ranges = db.execute(
        select(Detection.detection_id, Detection.window_start, Detection.window_end)
        .join(Attribution, Attribution.detection_id == Detection.detection_id)
        .where(
            Detection.satellite_id == satellite_id,
            Detection.outcome == DetectionOutcome.CONFIRMED,
            Attribution.channel_id == channel_row.channel_id,
        )
        .order_by(Detection.timestamp)
    ).all()

    return TelemetrySeriesOut(
        satellite_id=satellite_id,
        channel_id=channel,
        channel_name=channel_row.channel_name,
        unit=channel_row.unit,
        total_points=total_points,
        points=points,
        point_indices=indices,
        anomaly_ranges=[
            AnomalyRange(start=r.window_start or 0, end=r.window_end or 0, detection_id=r.detection_id)
            for r in ranges
        ],
        is_proxy=satellite.is_proxy,
    )
