"""GET /api/tle — cached TLE data for all monitored satellites (REQ-12).

Returns TLEs for every satellite that has a NORAD ID.  The endpoint is read-only
and available to any authenticated user (same access level as /api/satellites).
The browser uses the TLEs to propagate positions with satellite.js (SGP4) at 1 Hz.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Satellite, User
from app.schemas.tle import TleOut
from app.tracking.celestrak import apply_fetched, fetch_due, tle_payload

router = APIRouter(tags=["tle"])


@router.get("/tle", response_model=list[TleOut])
def list_tle(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Return the current TLE for every satellite with a NORAD ID.

    TLEs are refreshed from CelesTrak when the cache is older than 2 hours.
    Each entry includes a `stale` flag indicating whether the TLE is from the
    live feed (false) or a cached/snapshot fallback (true).
    """
    satellites = db.scalars(
        select(Satellite).where(Satellite.norad_id.is_not(None)).order_by(Satellite.satellite_id)
    ).all()
    # Network first, with no write open; then one short write (see app/tracking/celestrak.py).
    fetched = fetch_due(satellites)
    changed = [s for s in satellites if apply_fetched(s, fetched)]
    if changed:
        db.commit()
    return [TleOut(**tle_payload(s)) for s in satellites]
