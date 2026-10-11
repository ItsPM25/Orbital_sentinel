import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.security import require_roles
from app.core.settings import settings
from app.models import DetectionModel, MonitoringConfig, Role, Satellite, User, new_id
from app.pipeline.import_dataset import import_dataset
from app.schemas.admin import (
    DatasetImportOut,
    DatasetImportRequest,
    DetectionModelOut,
    MonitoringConfigOut,
    UpdateMonitoringConfigRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_satellite(db: Session, satellite_id: str) -> Satellite:
    satellite = db.get(Satellite, satellite_id)
    if satellite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Satellite {satellite_id} not found")
    return satellite


@router.get("/config/{satellite_id}", response_model=MonitoringConfigOut)
def get_config(
    satellite_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    _get_satellite(db, satellite_id)
    config = db.scalar(
        select(MonitoringConfig)
        .where(MonitoringConfig.satellite_id == satellite_id, MonitoringConfig.is_active)
        .order_by(MonitoringConfig.updated_at.desc())
    )
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No monitoring config for {satellite_id}")
    return MonitoringConfigOut.from_row(config)


@router.put("/config/{satellite_id}", response_model=MonitoringConfigOut)
def update_config(
    satellite_id: str,
    body: UpdateMonitoringConfigRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    """Writes a new row rather than editing in place, so history is kept (MONITORING_CONFIG)."""
    _get_satellite(db, satellite_id)
    if body.persistence_threshold < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "persistence_threshold must be at least 1")
    current = db.scalar(
        select(MonitoringConfig)
        .where(MonitoringConfig.satellite_id == satellite_id, MonitoringConfig.is_active)
    )
    if current is not None:
        current.is_active = False
    new_config = MonitoringConfig(
        config_id=new_id("CFG"),
        satellite_id=satellite_id,
        set_by_user_id=admin.user_id,
        persistence_threshold=body.persistence_threshold,
        severity_threshold=body.severity_threshold,
        updated_at=utcnow(),
        is_active=True,
    )
    db.add(new_config)
    db.commit()
    return MonitoringConfigOut.from_row(new_config)


@router.post("/datasets/import", response_model=DatasetImportOut)
def import_datasets(
    body: DatasetImportRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    """REQ-1: admin dataset import, data/ -> CHANNEL (+ TELEMETRY_READING). Idempotent."""
    result = import_dataset(db, include_readings=body.include_readings)
    return DatasetImportOut(
        channels_created=result["channelsCreated"],
        channels_updated=result["channelsUpdated"],
        channels=result["channels"],
        readings=result["readings"],
        include_readings=result["includeReadings"],
    )


@router.get("/models", response_model=list[DetectionModelOut])
def list_models(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.EVALUATOR)),
):
    rows = db.scalars(select(DetectionModel)).all()
    out = []
    for row in rows:
        channels_trained = 0
        manifest_path = settings.models_dir / row.model_id / "manifest.json"
        if manifest_path.exists():
            channels_trained = len(json.loads(manifest_path.read_text(encoding="utf-8")).get("channels", []))
        out.append(
            DetectionModelOut(
                model_id=row.model_id,
                model_name=row.model_name,
                model_type=row.model_type,
                threshold=row.threshold,
                trained_at=row.trained_at,
                channels_trained=channels_trained,
            )
        )
    return out
