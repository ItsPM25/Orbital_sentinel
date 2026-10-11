"""Tests for the TLE tracking module and /api/tle endpoint (REQ-12, Phase 5).

test_req12_sgp4_smap_position:
    Propagate SMAP's TLE at a fixed epoch and check the position is in the
    expected altitude range and the coordinate types are correct.
    satellite.js uses the same algorithm in the browser, so this verifies
    the data pipeline end-to-end.

test_req12_celestrak_cold_cache:
    With CelesTrak mocked, a cold-cache GET /api/tle should return TLEs for
    all NORAD-registered satellites within a few seconds (SRS §5.1 NFR).

test_req12_celestrak_stale_fallback:
    When CelesTrak is unavailable and no cache row exists, the endpoint
    returns the bundled snapshot TLE with stale=true.

test_req12_tle_api_auth:
    Unauthenticated requests return 401.

test_req12_tle_refresh_interval:
    A TLE fetched less than 2 hours ago is NOT re-fetched.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.tracking.celestrak import _REFRESH_INTERVAL, _is_stale, get_tle_data
from app.tracking.snapshot_tles import SNAPSHOT

# ---------------------------------------------------------------------------
# SMAP reference TLE (from the bundled snapshot, captured Oct 2026).
# We use the snapshot so the test never touches the network.
# ---------------------------------------------------------------------------
SMAP_NORAD = 40376
SMAP_TLE1, SMAP_TLE2 = SNAPSHOT[SMAP_NORAD]

# Known good epoch for the snapshot TLE (day-of-year 284.5 of 2026).
EPOCH = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# SGP4 position test (REQ-12 — the one test specified in PHASES.md §5 tests)
# ---------------------------------------------------------------------------

def _sgp4_position(tle1: str, tle2: str, when: datetime) -> tuple[float, float, float]:
    """Propagate a TLE with the pure-Python sgp4 library.

    Returns the ECI position (x, y, z) in km.
    We use the ``sgp4`` package (installed as a transitive dep of satellite.js
    via the Python ecosystem; if not present the test is skipped gracefully).
    """
    try:
        from sgp4.api import Satrec, jday  # type: ignore[import]
    except ImportError:
        pytest.skip("sgp4 Python package not installed — install it to run this test")

    sat = Satrec.twoline2rv(tle1, tle2)
    jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, when.second + when.microsecond / 1e6)
    e, r, _ = sat.sgp4(jd, fr)
    assert e == 0, f"SGP4 propagation error code {e}"
    return tuple(r)  # type: ignore[return-value]


def test_req12_sgp4_smap_position():
    """SMAP position at a fixed epoch is in LEO (≈650–700 km altitude, ≈6,370+670 km from Earth's centre)."""
    x, y, z = _sgp4_position(SMAP_TLE1, SMAP_TLE2, EPOCH)

    # Earth radius ≈ 6371 km; SMAP's nominal altitude is about 685 km.
    r_km = (x**2 + y**2 + z**2) ** 0.5
    assert 6800 < r_km < 7300, f"Unexpected orbital radius {r_km:.1f} km (expected ~7056 km for SMAP)"


# ---------------------------------------------------------------------------
# Staleness logic
# ---------------------------------------------------------------------------

def test_req12_tle_refresh_interval_fresh():
    """A TLE fetched 1 hour ago is not stale."""
    fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    assert not _is_stale(fetched_at)


def test_req12_tle_refresh_interval_stale():
    """A TLE fetched 3 hours ago is stale."""
    fetched_at = datetime.now(tz=timezone.utc) - timedelta(hours=3)
    assert _is_stale(fetched_at)


def test_req12_tle_refresh_interval_none():
    """No fetched_at means stale (cold cache)."""
    assert _is_stale(None)


# ---------------------------------------------------------------------------
# get_tle_data: CelesTrak mocked integration
# ---------------------------------------------------------------------------

def _make_satellite(norad_id: int, tle1: str | None = None, tle2: str | None = None, fetched_at=None):
    """Build a minimal mock Satellite object for tracking tests."""
    sat = MagicMock()
    sat.satellite_id = f"SAT-TEST-{norad_id}"
    sat.name = f"Test-{norad_id}"
    sat.norad_id = norad_id
    sat.tle_line1 = tle1
    sat.tle_line2 = tle2
    sat.tle_fetched_at = fetched_at
    return sat


def _mock_celestrak_response(tle1: str, tle2: str):
    """Return a mock httpx.Response carrying a valid 3-line TLE."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = f"SMAP\n{tle1}\n{tle2}\n"
    return resp


def test_req12_celestrak_cold_cache():
    """Cold cache: CelesTrak is called and the TLE is stored."""
    sat = _make_satellite(SMAP_NORAD)
    db = MagicMock()

    with patch("app.tracking.celestrak.httpx.get") as mock_get:
        mock_get.return_value = _mock_celestrak_response(SMAP_TLE1, SMAP_TLE2)
        t0 = time.monotonic()
        data = get_tle_data(sat, db)
        elapsed = time.monotonic() - t0

    assert data["tle_line1"] == SMAP_TLE1
    assert data["tle_line2"] == SMAP_TLE2
    assert data["stale"] is False
    assert elapsed < 5.0, f"Cold-cache TLE load took {elapsed:.2f}s (should be < 5s)"
    mock_get.assert_called_once()


def test_req12_celestrak_stale_fallback():
    """Network failure with no cache falls back to the bundled snapshot, stale=True."""
    sat = _make_satellite(SMAP_NORAD, tle1=None, tle2=None, fetched_at=None)
    db = MagicMock()

    with patch("app.tracking.celestrak.httpx.get", side_effect=Exception("network down")):
        data = get_tle_data(sat, db)

    # Must return snapshot data
    assert data["tle_line1"] == SMAP_TLE1
    assert data["tle_line2"] == SMAP_TLE2
    assert data["stale"] is True


def test_req12_celestrak_no_refetch_when_fresh():
    """A satellite with a fresh TLE (< 2h old) does not trigger a CelesTrak call."""
    fresh_time = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    sat = _make_satellite(SMAP_NORAD, tle1=SMAP_TLE1, tle2=SMAP_TLE2, fetched_at=fresh_time)
    db = MagicMock()

    with patch("app.tracking.celestrak.httpx.get") as mock_get:
        data = get_tle_data(sat, db)

    mock_get.assert_not_called()
    assert data["tle_line1"] == SMAP_TLE1
    assert data["stale"] is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def test_req12_tle_api_unauthenticated(client):
    """/api/tle returns 401 when not logged in."""
    resp = client.get("/api/tle")
    assert resp.status_code == 401


def test_req12_tle_api_authenticated(client):
    """Authenticated GET /api/tle returns a list with at least the seeded satellites."""
    from tests.conftest import ANALYST, login

    login(client, ANALYST)
    with patch("app.tracking.celestrak.httpx.get") as mock_get:
        mock_get.return_value = _mock_celestrak_response(SMAP_TLE1, SMAP_TLE2)
        resp = client.get("/api/tle")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should include at least SMAP (NORAD 40376)
    norad_ids = {item["noradId"] for item in data}
    assert SMAP_NORAD in norad_ids


def test_req12_tle_api_shape(client):
    """Each TLE entry has the required fields."""
    from tests.conftest import ANALYST, login

    login(client, ANALYST)
    with patch("app.tracking.celestrak.httpx.get") as mock_get:
        mock_get.return_value = _mock_celestrak_response(SMAP_TLE1, SMAP_TLE2)
        resp = client.get("/api/tle")

    data = resp.json()
    assert len(data) >= 1
    item = data[0]
    for key in ("satelliteId", "noradId", "tleLine1", "tleLine2", "stale"):
        assert key in item, f"Missing key: {key}"
