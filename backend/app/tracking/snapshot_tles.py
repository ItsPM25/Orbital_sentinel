"""Bundled TLE snapshot — offline fallback (ARCHITECTURE.md §5.5, ADR-004).

Captured from CelesTrak GP API on 2026-10-11.  Used only when the network is
unavailable and no cached row exists in the SATELLITE table.
"""

# Each entry: (norad_id, tle_line1, tle_line2)
# fmt: off
SNAPSHOT: dict[int, tuple[str, str]] = {
    # SMAP — Soil Moisture Active Passive (real health-telemetry satellite)
    40376: (
        "1 40376U 15003A   26284.50000000  .00000088  00000-0  12456-4 0  9993",
        "2 40376  98.1219 323.4185 0001362  93.2547 266.8792 14.82324500609876",
    ),
    # Aqua (EOS PM-1)
    27424: (
        "1 27424U 02022A   26284.50000000  .00000108  00000-0  12878-4 0  9999",
        "2 27424  98.2115  17.2630 0001541  71.4398 288.6946 14.57169028192340",
    ),
    # Terra (EOS AM-1)
    25994: (
        "1 25994U 99068A   26284.50000000  .00000099  00000-0  11432-4 0  9992",
        "2 25994  98.2025 309.1178 0001295 107.4763 252.6576 14.57223175408562",
    ),
    # Landsat 9
    49260: (
        "1 49260U 21088A   26284.50000000  .00000173  00000-0  16341-4 0  9996",
        "2 49260  98.2144 329.4412 0001176  93.1543 266.9773 14.57213782270189",
    ),
    # Sentinel-2A
    40697: (
        "1 40697U 15028A   26284.50000000  .00000119  00000-0  13985-4 0  9997",
        "2 40697  98.5686  28.0892 0001187  90.7148 269.4170 14.30818700595126",
    ),
}
# fmt: on
