from app.schemas.common import CamelModel, UtcDatetime


class TleOut(CamelModel):
    """One TLE entry as served by GET /api/tle (ARCHITECTURE.md §7)."""

    satellite_id: str
    norad_id: int | None
    tle_line1: str | None
    tle_line2: str | None
    fetched_at: UtcDatetime | None
    stale: bool
