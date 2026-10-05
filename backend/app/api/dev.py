from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.seed import seed_demo_alerts

router = APIRouter(tags=["dev"])


# GET as well as POST so Selenium IDE can reset state with a plain `open`.
@router.api_route("/reset", methods=["GET", "POST"])
def reset_demo_alerts(db: Session = Depends(get_db)):
    """Restores the demo alerts so test suites can be rerun. Dev only (OS_ENABLE_TEST_RESET)."""
    seed_demo_alerts(db)
    return {"ok": True}
