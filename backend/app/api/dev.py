from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Alert, Attribution, Detection
from app.seed import seed_demo_alerts

router = APIRouter(tags=["dev"])


# GET as well as POST so Selenium IDE can reset state with a plain `open`.
@router.api_route("/reset", methods=["GET", "POST"])
def reset_demo_alerts(db: Session = Depends(get_db)):
    """Restores the demo state so test suites can be rerun: the 8 demo alerts, back to
    AlertRaised, and nothing else. Detections and alerts written by monitoring replays
    are removed too, or every test asserting on the alert list would depend on what
    happened to be replayed beforehand. Dev only (OS_ENABLE_TEST_RESET)."""
    db.execute(delete(Attribution))
    db.execute(delete(Alert))
    db.execute(delete(Detection))
    db.commit()
    seed_demo_alerts(db)
    return {"ok": True}
