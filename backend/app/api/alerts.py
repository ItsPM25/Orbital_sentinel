from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db, utcnow
from app.core.security import get_current_user, require_roles
from app.models import Alert, AlertStatus, Detection, Role, User
from app.schemas.alert import AlertView

router = APIRouter(tags=["alerts"])

_with_satellite = joinedload(Alert.detection).joinedload(Detection.satellite)


@router.get("/alerts", response_model=list[AlertView])
def list_alerts(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Risk-ordered alert list (REQ-16): highest risk first, then oldest first."""
    alerts = db.scalars(
        select(Alert).options(_with_satellite).order_by(Alert.risk_level.desc(), Alert.created_at)
    ).all()
    return [AlertView.from_alert(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertView)
def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ANALYST, Role.ADMINISTRATOR)),
):
    """AlertRaised -> Acknowledged (state diagram, event userAck)."""
    alert = db.get(Alert, alert_id, options=[_with_satellite])
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Alert {alert_id} not found")
    if alert.status == AlertStatus.ALERT_RAISED:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user.user_id
        alert.acknowledged_at = utcnow()
        db.commit()
    return AlertView.from_alert(alert)
