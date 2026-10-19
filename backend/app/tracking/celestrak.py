"""CelesTrak TLE client — Process 4.0 Track (REQ-12, ARCHITECTURE.md §5.5).

Refresh policy (ADR-004):
- Re-fetch at most every 2 hours, per CelesTrak's usage guidance.
- On network failure: return the last cached TLE, marked stale.
- If no cache row exists at all: fall back to the bundled snapshot.

Network calls never happen while a database write is open. fetch_due() talks
to CelesTrak only; the caller then applies the results and commits in one
short transaction. (Holding a write across slow fetches locked SQLite for
about a minute on a network where CelesTrak was unreachable, and crashed a
running MonitoringSession that tried to log a detection in that window.)

The backend only fetches and caches TLEs.  SGP4 propagation is done in the browser
by satellite.js (AD-5).
"""

import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import Satellite
from app.tracking.snapshot_tles import SNAPSHOT

log = logging.getLogger(__name__)

_CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
_REFRESH_INTERVAL = timedelta(hours=2)
_HTTP_TIMEOUT = 5.0  # seconds
# After a failed fetch, don't retry that satellite for this long: on a machine
# that can't reach CelesTrak, every /api/tle call would otherwise wait out the
# timeout again before falling back to the snapshot.
_FAILURE_BACKOFF = timedelta(minutes=10)
_last_failure: dict[int, datetime] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _is_stale(fetched_at: datetime | None) -> bool:
    """Return True when the cached TLE needs refreshing."""
    if fetched_at is None:
        return True
    return _now() - fetched_at > _REFRESH_INTERVAL


def _backing_off(norad_id: int) -> bool:
    failed_at = _last_failure.get(norad_id)
    return failed_at is not None and _now() - failed_at < _FAILURE_BACKOFF


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
            _last_failure.pop(norad_id, None)
            return lines[1], lines[2]
        log.warning("CelesTrak returned unexpected format for NORAD %s: %r", norad_id, resp.text[:200])
    except Exception as exc:  # noqa: BLE001
        log.warning("CelesTrak fetch failed for NORAD %s: %s", norad_id, exc)
    _last_failure[norad_id] = _now()
    return None


def fetch_due(satellites: Iterable[Satellite]) -> dict[int, tuple[str, str]]:
    """Fetch fresh TLEs for every satellite whose cache is stale (and that isn't
    in failure backoff). Network only, no database access. Fetches run in
    parallel, so an offline machine waits one timeout, not one per satellite."""
    due = sorted(
        {
            s.norad_id
            for s in satellites
            if s.norad_id is not None and _is_stale(s.tle_fetched_at) and not _backing_off(s.norad_id)
        }
    )
    if not due:
        return {}
    with ThreadPoolExecutor(max_workers=len(due)) as pool:
        results = dict(zip(due, pool.map(_fetch_from_celestrak, due), strict=True))
    return {norad_id: tle for norad_id, tle in results.items() if tle is not None}


def apply_fetched(satellite: Satellite, fetched: dict[int, tuple[str, str]]) -> bool:
    """Store a freshly fetched TLE on the row. Returns True if anything changed."""
    tle = fetched.get(satellite.norad_id)
    if tle is None:
        return False
    satellite.tle_line1, satellite.tle_line2 = tle
    satellite.tle_fetched_at = _now()
    log.info("TLE refreshed for %s (NORAD %s)", satellite.name, satellite.norad_id)
    return True


def tle_payload(satellite: Satellite) -> dict:
    """The GET /api/tle item for a satellite (ARCHITECTURE.md §7). Falls back to the
    bundled snapshot when nothing is cached; the snapshot is served, not stored."""
    stale = _is_stale(satellite.tle_fetched_at)
    tle1, tle2 = satellite.tle_line1, satellite.tle_line2
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


def get_tle_data(satellite: Satellite, db: Session) -> dict:
    """Single-satellite convenience: fetch if due, store, and return the payload."""
    if apply_fetched(satellite, fetch_due([satellite])):
        db.flush()
    return tle_payload(satellite)
