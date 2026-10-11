"""CelesTrak TLE client — Process 4.0 Track (REQ-12, ARCHITECTURE.md §5.5).

Refresh policy (ADR-004):
- Re-fetch at most every 2 hours, per CelesTrak's usage guidance.
- On network failure: return the last cached TLE, marked stale.
- If no cache row exists at all: fall back to the bundled snapshot.

The backend only fetches and caches TLEs.  SGP4 propagation is done in the browser
by satellite.js (AD-5).
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Satellite
from app.tracking.snapshot_tles import SNAPSHOT

log = logging.getLogger(__name__)

_CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
_REFRESH_INTERVAL = timedelta(hours=2)
_HTTP_TIMEOUT = 10.0  # seconds


def _is_stale(fetched_at: datetime | None) -> bool:
    """Return True when the cached TLE needs refreshing."""
    if fetched_at is None:
        return True
    age = datetime.now(tz=timezone.utc) - fetched_at
    return age > _REFRESH_INTERVAL


def _fetch_from_celestrak(norad_id: int) -> tuple[str, str] | None:
    """Fetch a two-line element set from CelesTrak.  Returns (line1, line2) or None."""
    try:
        resp = httpx.get(
            _CELESTRAK_URL,
            params={"CATNR": norad_id, "FORMAT": "tle"},
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        lines = [ln.strip() for ln in resp.text.strip().splitlines() if ln.strip()]
        # CelesTrak TLE format: name / line1 / line2 (3 lines total)
        if len(lines) >= 3:
            return lines[1], lines[2]
        log.warning("CelesTrak returned unexpected format for NORAD %s: %r", norad_id, resp.text[:200])
    except Exception as exc:  # noqa: BLE001
        log.warning("CelesTrak fetch failed for NORAD %s: %s", norad_id, exc)
    return None


def refresh_tle(satellite: Satellite, db: Session) -> bool:
    """Refresh the TLE for *satellite* if the cached value is stale.

    Returns True when the cache was actually updated.
    Does NOT commit; the caller owns the transaction.
    """
    if not _is_stale(satellite.tle_fetched_at):
        return False  # cache still fresh

    norad_id = satellite.norad_id
    if norad_id is None:
        return False  # proxy without a real NORAD ID

    result = _fetch_from_celestrak(norad_id)
    if result is not None:
        satellite.tle_line1, satellite.tle_line2 = result
        satellite.tle_fetched_at = datetime.now(tz=timezone.utc)
        log.info("TLE refreshed for %s (NORAD %s)", satellite.name, norad_id)
        return True

    # Network failed — use snapshot if we have nothing at all
    if satellite.tle_line1 is None and norad_id in SNAPSHOT:
        satellite.tle_line1, satellite.tle_line2 = SNAPSHOT[norad_id]
        # Do not set tle_fetched_at so we retry next time
        log.warning("Using bundled snapshot TLE for %s (NORAD %s)", satellite.name, norad_id)
        return True

    return False


def get_tle_data(satellite: Satellite, db: Session) -> dict:
    """Return the TLE for *satellite*, refreshing from CelesTrak when stale.

    Shape matches the GET /api/tle response item schema (ARCHITECTURE.md §7).
    """
    updated = refresh_tle(satellite, db)
    if updated:
        db.flush()  # write within the caller's transaction

    # Determine staleness for the response flag
    stale = _is_stale(satellite.tle_fetched_at)

    # Last-resort: return snapshot even if refresh couldn't write to DB
    tle1 = satellite.tle_line1
    tle2 = satellite.tle_line2
    if (tle1 is None or tle2 is None) and satellite.norad_id in SNAPSHOT:
        tle1, tle2 = SNAPSHOT[satellite.norad_id]
        stale = True

    return {
        "satellite_id": satellite.satellite_id,
        "norad_id": satellite.norad_id,
        "tle_line1": tle1,
        "tle_line2": tle2,
        "fetched_at": satellite.tle_fetched_at,
        "stale": stale,
    }
