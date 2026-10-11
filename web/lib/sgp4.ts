/**
 * SGP4 propagation wrapper using satellite.js (REQ-12, REQ-13).
 *
 * AD-5: propagation runs entirely in the browser; the backend only caches TLEs.
 * ARCHITECTURE.md §5.5: satellite.js SGP4 propagation at 1 Hz.
 */

// satellite.js types are bundled with the package but may not be detected in all
// setups, so we import from the default export.
import * as satellite from "satellite.js";

export interface TleEntry {
  satelliteId: string;
  noradId: number | null;
  tleLine1: string | null;
  tleLine2: string | null;
  fetchedAt: string | null;
  stale: boolean;
}

export interface GeoPosition {
  /** Geodetic latitude, degrees. */
  lat: number;
  /** Geodetic longitude, degrees. */
  lng: number;
  /** Altitude above WGS-84 ellipsoid, km. */
  alt: number;
}

/**
 * Propagate a satellite's TLE to a geodetic position at `when`.
 * Returns null if the TLE is missing or the propagation errors.
 */
export function propagate(tle1: string, tle2: string, when: Date): GeoPosition | null {
  try {
    const satrec = satellite.twoline2satrec(tle1, tle2);
    const posVel = satellite.propagate(satrec, when);
    if (!posVel.position || typeof posVel.position === "boolean") return null;

    const gmst = satellite.gstime(when);
    const geo = satellite.eciToGeodetic(posVel.position as satellite.EciVec3<satellite.Kilometer>, gmst);
    return {
      lat: satellite.degreesLat(geo.latitude),
      lng: satellite.degreesLong(geo.longitude),
      alt: geo.height,
    };
  } catch {
    return null;
  }
}

/**
 * Build a short orbit trail — equally spaced points over the past `minutes` of
 * propagated orbit.  Returns an array of {lat, lng} objects.
 */
export function orbitTrail(
  tle1: string,
  tle2: string,
  now: Date,
  minutes = 30,
  steps = 60
): Array<{ lat: number; lng: number }> {
  const trail: Array<{ lat: number; lng: number }> = [];
  const msPerStep = (minutes * 60 * 1000) / steps;
  for (let i = steps; i >= 0; i--) {
    const t = new Date(now.getTime() - i * msPerStep);
    const pos = propagate(tle1, tle2, t);
    if (pos) trail.push({ lat: pos.lat, lng: pos.lng });
  }
  return trail;
}

/**
 * Risk colour mapping — matches ARCHITECTURE.md §5.6 (REQ-14).
 * The numeric riskLevel fallback bands mirror risk_label() in
 * backend/app/pipeline/explain/severity.py exactly (>=9/>=6/>=4), so a
 * missing severityLevel string still colours consistently with the backend.
 */
export function riskColour(riskLevel: number | null, severityLevel: string | null): string {
  if (!riskLevel && !severityLevel) return "#22c55e"; // green — nominal
  const severity = severityLevel?.toUpperCase();
  if (severity === "CRITICAL" || (riskLevel ?? 0) >= 9) return "#ef4444"; // red
  if (severity === "HIGH" || (riskLevel ?? 0) >= 6) return "#f97316"; // orange
  if (severity === "MEDIUM" || (riskLevel ?? 0) >= 4) return "#eab308"; // amber
  return "#22c55e"; // green — LOW
}
