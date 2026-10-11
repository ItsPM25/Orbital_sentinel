"""The 5-satellite globe fleet and its proxy channel mapping (ADR-004, TBD-2).

SMAP's 54 labelled channels are split into 3 disjoint groups (SAT-001 the
real satellite, plus proxies SAT-003 and SAT-004); MSL's 27 into 2 disjoint
groups (proxies SAT-002 and SAT-005). The split is alphabetical-chunked over
the labelled channel ids, so it's deterministic and reproducible rather than
random. Every labelled channel has at least one anomaly sequence by
construction of labeled_anomalies.csv, so every satellite gets one too
(ADR-004 / PHASES.md 5a's requirement).
"""

from __future__ import annotations

from app.pipeline.dataset import load_labels

# chan_id -> (satellite_id, readable source name used in Satellite.telemetry_source)
FleetMap = dict[str, str]

SMAP_SATELLITES = ["SAT-001", "SAT-003", "SAT-004"]  # SMAP (real), Terra, Landsat 9
MSL_SATELLITES = ["SAT-002", "SAT-005"]  # Aqua, Sentinel-2A


def _chunk(items: list[str], n: int) -> list[list[str]]:
    """Splits `items` into `n` contiguous, near-equal chunks (last chunk gets the remainder)."""
    size, remainder = divmod(len(items), n)
    chunks, start = [], 0
    for i in range(n):
        end = start + size + (1 if i < remainder else 0)
        chunks.append(items[start:end])
        start = end
    return chunks


def build_fleet_channel_map(data_dir=None) -> FleetMap:
    """Returns {chan_id: satellite_id} for every labelled channel, per the ADR-004 split."""
    labels = load_labels(data_dir)
    smap_channels = sorted(c for c, lbl in labels.items() if lbl.spacecraft == "SMAP")
    msl_channels = sorted(c for c, lbl in labels.items() if lbl.spacecraft == "MSL")

    channel_map: FleetMap = {}
    for satellite_id, group in zip(SMAP_SATELLITES, _chunk(smap_channels, len(SMAP_SATELLITES)), strict=True):
        for chan_id in group:
            channel_map[chan_id] = satellite_id
    for satellite_id, group in zip(MSL_SATELLITES, _chunk(msl_channels, len(MSL_SATELLITES)), strict=True):
        for chan_id in group:
            channel_map[chan_id] = satellite_id
    return channel_map


def telemetry_source_summary(satellite_id: str, channel_map: FleetMap) -> str:
    """A short, honest description of what a satellite actually replays, for the
    'Replayed telemetry' badge (SRS 2.7) - e.g. 'SMAP channels: A-1, A-2, A-3 (18 total)'."""
    channels = sorted(c for c, sat in channel_map.items() if sat == satellite_id)
    if not channels:
        return "no channels assigned"
    spacecraft = load_labels()[channels[0]].spacecraft
    preview = ", ".join(channels[:3])
    suffix = ", ..." if len(channels) > 3 else ""
    return f"{spacecraft} channels: {preview}{suffix} ({len(channels)} total)"


if __name__ == "__main__":
    fleet_map = build_fleet_channel_map()
    for sat_id in SMAP_SATELLITES + MSL_SATELLITES:
        print(sat_id, telemetry_source_summary(sat_id, fleet_map))
