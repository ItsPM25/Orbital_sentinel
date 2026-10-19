/**
 * SGP4 propagation with satellite.js (REQ-12, REQ-13).
 *
 * AD-5: propagation runs entirely in the browser; the backend only caches TLEs.
 * The globe propagates every animation frame (ARCHITECTURE.md §5.5 asked for at
 * least 1 Hz); five satellites cost microseconds per frame.
 */

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
  /** Altitude above the WGS-84 ellipsoid, km. */
  alt: number;
}

export interface SatState extends GeoPosition {
  /** Inertial speed, km/s. */
  speed: number;
}

export interface OrbitInfo {
  inclinationDeg: number;
  periodMin: number;
  perigeeKm: number;
  apogeeKm: number;
}

export type SatRec = satellite.SatRec;

export const EARTH_RADIUS_KM = 6371;
const MU = 398600.4418; // km^3/s^2, Earth's gravitational parameter
const EQUATORIAL_RADIUS_KM = 6378.137;

export function makeSatrec(tle: TleEntry): SatRec | null {
  if (!tle.tleLine1 || !tle.tleLine2) return null;
  try {
    return satellite.twoline2satrec(tle.tleLine1, tle.tleLine2);
  } catch {
    return null;
  }
}

export function stateAt(satrec: SatRec, when: Date): SatState | null {
  const pv = satellite.propagate(satrec, when);
  if (!pv.position || typeof pv.position === "boolean" || !pv.velocity || typeof pv.velocity === "boolean") return null;
  const geo = satellite.eciToGeodetic(pv.position, satellite.gstime(when));
  const v = pv.velocity;
  return {
    lat: satellite.degreesLat(geo.latitude),
    lng: satellite.degreesLong(geo.longitude),
    alt: geo.height,
    speed: Math.hypot(v.x, v.y, v.z),
  };
}

/** Mean orbital elements straight from the TLE (no propagation needed). */
export function orbitInfo(satrec: SatRec): OrbitInfo {
  const meanMotionRadPerSec = satrec.no / 60; // satrec.no is rad/min
  const semiMajorKm = Math.cbrt(MU / (meanMotionRadPerSec * meanMotionRadPerSec));
  return {
    inclinationDeg: (satrec.inclo * 180) / Math.PI,
    periodMin: (2 * Math.PI) / satrec.no,
    perigeeKm: semiMajorKm * (1 - satrec.ecco) - EQUATORIAL_RADIUS_KM,
    apogeeKm: semiMajorKm * (1 + satrec.ecco) - EQUATORIAL_RADIUS_KM,
  };
}

/** Earth-fixed path over one orbital period centred on `centre`, as
 * [lat, lng, altitude in Earth radii] points for globe.gl's paths layer. */
export function orbitPath(satrec: SatRec, centre: Date, periodMin: number, steps = 180): [number, number, number][] {
  const points: [number, number, number][] = [];
  const spanMs = periodMin * 60_000;
  for (let i = 0; i <= steps; i++) {
    const t = new Date(centre.getTime() - spanMs / 2 + (spanMs * i) / steps);
    const s = stateAt(satrec, t);
    if (s) points.push([s.lat, s.lng, s.alt / EARTH_RADIUS_KM]);
  }
  return points;
}

/** Position at `when`, or null when the TLE is missing or propagation fails. */
export function propagate(tle: TleEntry, when: Date): SatState | null {
  const satrec = makeSatrec(tle);
  return satrec ? stateAt(satrec, when) : null;
}
