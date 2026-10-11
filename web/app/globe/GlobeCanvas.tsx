"use client";
/**
 * GlobeCanvas — rendered inside a dynamic import so it never runs on the server.
 *
 * Uses globe.gl (three.js) for the 3D Earth, satellite.js SGP4 for position
 * propagation at 1 Hz.  Risk colours update from the parent's riskMap prop,
 * which is refreshed via SSE in the parent page (REQ-14).
 *
 * REQ-12: TLE + SGP4  REQ-13: globe + live motion  REQ-14: colour by risk
 * REQ-15: click → health panel (handled by onSelectSatellite callback)
 */

import { useEffect, useRef, useCallback } from "react";
import type { TleEntry, GeoPosition } from "@/lib/sgp4";
import { propagate, orbitTrail, riskColour } from "@/lib/sgp4";
import type { SatelliteRanking } from "@/lib/api";
import styles from "./globe.module.css";

interface Props {
  tles: TleEntry[];
  riskMap: Map<string, SatelliteRanking>;
  onSelectSatellite: (id: string | null) => void;
  selectedId: string | null;
}

interface SatPoint {
  satelliteId: string;
  lat: number;
  lng: number;
  alt: number;
  colour: string;
  selected: boolean;
}

interface ArcData {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  colour: string;
}

export default function GlobeCanvas({ tles, riskMap, onSelectSatellite, selectedId }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const globeRef = useRef<any>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tlesRef = useRef(tles);
  const riskMapRef = useRef(riskMap);
  const selectedRef = useRef(selectedId);

  // Keep refs in sync with props (avoids stale closure in the interval)
  useEffect(() => { tlesRef.current = tles; }, [tles]);
  useEffect(() => { riskMapRef.current = riskMap; }, [riskMap]);
  useEffect(() => { selectedRef.current = selectedId; }, [selectedId]);

  // Build satellite point data at a given timestamp
  const buildPoints = useCallback((now: Date): SatPoint[] => {
    return tlesRef.current
      .filter((t) => t.tleLine1 && t.tleLine2)
      .map((t) => {
        const pos: GeoPosition | null = propagate(t.tleLine1!, t.tleLine2!, now);
        if (!pos) return null;
        const ranking = riskMapRef.current.get(t.satelliteId);
        return {
          satelliteId: t.satelliteId,
          lat: pos.lat,
          lng: pos.lng,
          // Normalise altitude to a fraction of Earth radius for globe.gl's alt parameter
          alt: Math.max(0.01, pos.alt / 6371) * 0.5 + 0.005,
          colour: riskColour(ranking?.riskLevel ?? null, ranking?.severityLevel ?? null),
          selected: selectedRef.current === t.satelliteId,
        };
      })
      .filter((p): p is SatPoint => p !== null);
  }, []);

  // Build orbit trails for all satellites (30-minute trails, recomputed every 30s)
  const buildTrails = useCallback((): ArcData[] => {
    const now = new Date();
    const arcs: ArcData[] = [];
    for (const t of tlesRef.current) {
      if (!t.tleLine1 || !t.tleLine2) continue;
      const trail = orbitTrail(t.tleLine1, t.tleLine2, now, 30, 60);
      const ranking = riskMapRef.current.get(t.satelliteId);
      const colour = riskColour(ranking?.riskLevel ?? null, ranking?.severityLevel ?? null) + "55";
      for (let i = 0; i < trail.length - 1; i++) {
        arcs.push({
          startLat: trail[i].lat,
          startLng: trail[i].lng,
          endLat: trail[i + 1].lat,
          endLng: trail[i + 1].lng,
          colour,
        });
      }
    }
    return arcs;
  }, []);

  useEffect(() => {
    if (!mountRef.current) return;

    let trailInterval: ReturnType<typeof setInterval> | null = null;

    const initGlobe = async () => {
      // Dynamic import keeps globe.gl out of the SSR bundle
      const GlobeModule = await import("globe.gl");
      // globe.gl exports a constructor; calling it with `new` or as a factory both work
      // depending on the version. Use the default export directly as a constructor.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const GlobeGL: any = GlobeModule.default;

      const globe = new GlobeGL(mountRef.current!);
      globeRef.current = globe;

      // Earth appearance
      globe
        .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
        .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
        .atmosphereColor("rgba(63, 201, 255, 0.5)")
        .atmosphereAltitude(0.2)
        .backgroundColor("rgba(2, 8, 23, 0)")
        .width(mountRef.current!.offsetWidth || 800)
        .height(mountRef.current!.offsetHeight || 600);

      // Initial satellite points
      const now = new Date();
      const pts = buildPoints(now);
      globe
        .pointsData(pts)
        .pointLat((d: SatPoint) => d.lat)
        .pointLng((d: SatPoint) => d.lng)
        .pointAltitude((d: SatPoint) => d.alt)
        .pointRadius((d: SatPoint) => (d.selected ? 1.0 : 0.6))
        .pointColor((d: SatPoint) => d.colour)
        .onPointClick((point: unknown) => {
          const sat = point as SatPoint;
          onSelectSatellite(sat.satelliteId === selectedRef.current ? null : sat.satelliteId);
        })
        .onPointHover((point: unknown) => {
          if (!mountRef.current) return;
          mountRef.current.style.cursor = point ? "pointer" : "default";
        });

      // Orbit trails
      const trails = buildTrails();
      globe
        .arcsData(trails)
        .arcStartLat((d: ArcData) => d.startLat)
        .arcStartLng((d: ArcData) => d.startLng)
        .arcEndLat((d: ArcData) => d.endLat)
        .arcEndLng((d: ArcData) => d.endLng)
        .arcColor((d: ArcData) => d.colour)
        .arcStroke(0.25)
        .arcAltitude(0)
        .arcAltitudeAutoScale(0);

      // Start 1 Hz position update loop (REQ-13)
      tickRef.current = setInterval(() => {
        if (!globeRef.current) return;
        globeRef.current.pointsData(buildPoints(new Date()));
      }, 1000);

      // Rebuild trails every 30 s
      trailInterval = setInterval(() => {
        if (!globeRef.current) return;
        globeRef.current.arcsData(buildTrails());
      }, 30_000);
    };

    initGlobe().catch(console.error);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      if (trailInterval) clearInterval(trailInterval);
      if (globeRef.current?.renderer) {
        globeRef.current.renderer()?.dispose?.();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Intentionally empty: globe.gl is imperative; we update it via refs and the effects below.

  // When riskMap changes, refresh colours without recreating the globe
  useEffect(() => {
    if (!globeRef.current) return;
    globeRef.current.pointsData(buildPoints(new Date()));
    globeRef.current.arcsData(buildTrails());
  }, [riskMap, buildPoints, buildTrails]);

  // When selected satellite changes, update the selected point radius
  useEffect(() => {
    if (!globeRef.current) return;
    globeRef.current.pointsData(buildPoints(new Date()));
  }, [selectedId, buildPoints]);

  return <div ref={mountRef} className={styles.canvas} id="globeCanvas" />;
}
