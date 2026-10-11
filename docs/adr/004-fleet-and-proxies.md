# ADR-004 — Globe fleet composition and proxy channel mapping (TBD-2)

**Status:** Accepted — Phase 5  
**Date:** 2026-10-11  
**Requirement:** REQ-12 (TLE tracking), REQ-13 (globe), REQ-14 (risk colours), TBD-2 (fleet choice)

---

## Context

The NASA Telemanom dataset covers exactly two spacecraft: **SMAP** (Earth orbit, NORAD 40376)
and **MSL/Curiosity** (Mars surface, no TLE).  Only SMAP has real orbital elements, and only
SMAP/MSL channels have ground-truth anomaly labels.

The globe needs a *fleet* — multiple satellites at different orbital positions — to be a useful
situational-awareness view.  The choices are:

1. **Only SMAP** — honest but not a fleet.
2. **Fabricate fictional satellites** — dishonest (SRS §2.7).
3. **Use real Earth-orbiting satellites as *proxy hosts***, each replaying a disjoint subset
   of SMAP/MSL channels. Label them clearly in the UI.

Option 3 was chosen in Phase 0 (noted in ARCHITECTURE.md §4.3) and is confirmed here.

---

## Decision

### Fleet

| ID      | Name        | NORAD  | `is_proxy` | Replays channels from |
|---------|-------------|--------|------------|----------------------|
| SAT-001 | SMAP        | 40376  | false      | SMAP (real)          |
| SAT-002 | Aqua        | 27424  | true       | MSL (subset A)       |
| SAT-003 | Terra       | 25994  | true       | SMAP (subset B)      |
| SAT-004 | Landsat 9   | 49260  | true       | SMAP (subset C)      |
| SAT-005 | Sentinel-2A | 40697  | true       | MSL (subset D)       |

All five have real TLEs from CelesTrak's General Perturbations feed and real orbital
positions via SGP4 propagation in the browser (satellite.js).

### Channel subsets (proxy mapping)

Each proxy must contain **at least one labelled anomaly** (PHASES.md §5a requirement).
Trivially true here: every row in `labeled_anomalies.csv` has at least one anomaly
sequence by construction, so any non-empty split satisfies it.

The split is computed deterministically by `backend/app/pipeline/fleet.py`
(`build_fleet_channel_map()`): SMAP's 54 labelled channels are sorted alphabetically
and cut into 3 contiguous, near-equal chunks (SAT-001, SAT-003, SAT-004); MSL's 27
into 2 chunks (SAT-002, SAT-005). `import_dataset()` uses this as its default
`satellite_map`, keyed by `chan_id` (resolved before the coarser spacecraft-level
fallback, so a caller can still override by spacecraft, as the unit tests do).
`app/seed.py` reads the same map at seed time to fill `Satellite.telemetry_source`
with a short summary (e.g. `"SMAP channels: A-1, A-2, A-3, ... (18 total)"`) for the
health panel's "Replayed telemetry" badge.

- Subsets are **disjoint** by construction (`_chunk()` partitions the sorted list once;
  no channel is assigned twice).
- The split is alphabetical, not difficulty-balanced — a straightforward, reproducible
  choice over hand-picking a "similar difficulty mix" per satellite, which would need
  a difficulty metric this project doesn't otherwise define. Good enough for a globe
  demo; revisit if a specific satellite's detections look too sparse in practice.

### Honest-framing rules

- Every proxy satellite shows a **"Replayed telemetry"** badge in the health panel and on
  the globe popover.
- The data source (e.g., "SMAP channels T-1, T-2, …") is named explicitly in the UI.
- The globe tooltip distinguishes "Live orbital position" (real SGP4) from "Replayed health"
  (historical data).
- The risk colour reflects the detection on the *replayed channels*, not the real satellite's
  current state.  This is stated in the help overlay.

---

## TLE refresh policy

- Fetched from `https://celestrak.org/NORAD/elements/gp.php?CATNR=<norad>&FORMAT=tle`
  at most every **2 hours** (`tle_fetched_at` column in SATELLITE).
- On failure: the last cached TLE is served with `stale: true`.
- A **bundled snapshot** (`backend/app/tracking/snapshot_tles.py`) is the final fallback for
  fully offline demos.  It was captured in October 2026.

---

## SGP4 propagation

Propagation runs **in the browser** with satellite.js at 1 Hz (REQ-13).  The backend only
fetches and caches TLEs (`GET /api/tle`); it never propagates positions.  This matches
architectural decision AD-5 (ARCHITECTURE.md §2).

---

## Consequences

- The traceability row for REQ-12 (TLE + SGP4) maps to `backend/app/tracking/` and
  `web/lib/sgp4.ts` (ARCHITECTURE.md §10).
- The traceability row for TBD-2 (fleet choice) is now closed.
- Proxy badges and honest framing satisfy SRS §2.7 and the honesty rule in PHASES.md.
