"""ADR-004: the 5-satellite fleet's deterministic, disjoint channel split (TBD-2).

Regression test for a real gap found while reviewing the Phase 5 work: ADR-004
described this split, but nothing actually implemented it (import_dataset.py's
DEFAULT_SATELLITE_FOR_SPACECRAFT only ever mapped all of SMAP to SAT-001 and
all of MSL to SAT-002, leaving SAT-003/004/005 with zero channels)."""

from app.pipeline.dataset import load_labels
from app.pipeline.fleet import (
    MSL_SATELLITES,
    SMAP_SATELLITES,
    build_fleet_channel_map,
    telemetry_source_summary,
)


def test_every_labelled_channel_is_assigned_exactly_once():
    labels = load_labels()
    fleet_map = build_fleet_channel_map()
    # dict keys are inherently unique, so this also proves "exactly once": every
    # labelled channel appears as a key, and none appears twice.
    assert set(fleet_map) == set(labels)


def test_all_five_fleet_satellites_get_at_least_one_channel():
    fleet_map = build_fleet_channel_map()
    assigned = set(fleet_map.values())
    assert assigned == set(SMAP_SATELLITES) | set(MSL_SATELLITES)


def test_smap_channels_only_go_to_smap_satellites():
    labels = load_labels()
    fleet_map = build_fleet_channel_map()
    for chan_id, satellite_id in fleet_map.items():
        if labels[chan_id].spacecraft == "SMAP":
            assert satellite_id in SMAP_SATELLITES
        else:
            assert satellite_id in MSL_SATELLITES


def test_split_is_disjoint_and_deterministic():
    first = build_fleet_channel_map()
    second = build_fleet_channel_map()
    assert first == second  # same input -> same split, every time


def test_every_satellite_channel_group_has_at_least_one_labelled_anomaly():
    """PHASES.md 5a's requirement. Trivially true (every labelled channel has >=1
    anomaly sequence), but checked directly rather than just asserted in a comment."""
    labels = load_labels()
    fleet_map = build_fleet_channel_map()
    for satellite_id in SMAP_SATELLITES + MSL_SATELLITES:
        channels = [c for c, s in fleet_map.items() if s == satellite_id]
        assert channels
        assert any(len(labels[c].anomaly_sequences) >= 1 for c in channels)


def test_telemetry_source_summary_names_real_channels():
    fleet_map = build_fleet_channel_map()
    summary = telemetry_source_summary("SAT-001", fleet_map)
    assert "SMAP channels:" in summary
    assert "total)" in summary


def test_telemetry_source_summary_for_an_unassigned_satellite():
    assert telemetry_source_summary("SAT-999", {}) == "no channels assigned"
