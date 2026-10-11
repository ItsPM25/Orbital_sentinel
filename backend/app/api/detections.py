from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Detection, User
from app.schemas.detection import DetectionOut

router = APIRouter(tags=["detections"])


@router.get("/detections", response_model=list[DetectionOut])
def list_detections(
    satellite_id: str | None = Query(default=None, alias="satelliteId"),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Detection log (REQ-18), newest first."""
    stmt = select(Detection).options(joinedload(Detection.satellite)).order_by(Detection.timestamp.desc())
    if satellite_id:
        stmt = stmt.where(Detection.satellite_id == satellite_id)
    if outcome:
        stmt = stmt.where(Detection.outcome == outcome)
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [DetectionOut.from_detection(r) for r in rows]
