"use client";
/**
 * GlobeCanvas: the 3D Earth (globe.gl / three.js) with the fleet on it.
 * Only ever loaded client-side, through next/dynamic with ssr: false.
 *
 * Each animation frame propagates every satellite with SGP4 at the page's
 * simulation time (live, or sped up) and re-submits the objects layer, the
 * pattern globe.gl's own satellites example uses. Orbit paths cover one period
 * centred on the satellite and are recomputed as it moves along.
 *
 * REQ-12 TLE + SGP4, REQ-13 globe + live motion, REQ-14 colour by risk,
 * REQ-15 click -> health panel (via onSelect).
 */

import { useEffect, useRef, useState } from "react";
import type * as Three from "three";
import { BAND_HEX, type RiskBand } from "@/lib/risk";
import { EARTH_RADIUS_KM, makeSatrec, orbitInfo, orbitPath, stateAt, type SatRec, type TleEntry } from "@/lib/sgp4";

export interface GlobeSatellite {
  satelliteId: string;
  name: string;
  band: RiskBand;
  tle: TleEntry;
}

interface Props {
  satellites: GlobeSatellite[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Current simulation time; read every frame. */
  getSimTime: () => Date;
}

interface SatDatum {
  id: string;
  name: string;
  satrec: SatRec;
  periodMin: number;
  lat: number;
  lng: number;
  alt: number; // Earth radii above the surface
}

interface SatVisual {
  body: Three.MeshLambertMaterial;
  ring: Three.Mesh;
  ringMat: Three.MeshBasicMaterial;
  group: Three.Group;
}

interface PathDatum {
  id: string;
  points: [number, number, number][];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type GlobeInstance = any; // globe.gl's chained accessor types are not worth fighting here

const SAT_SIZE = 2.6; // globe radius is 100 units; exaggerated so the models read at this zoom
const PATH_REFRESH_FRACTION = 1 / 12; // recompute paths after 1/12 of an orbit

function rgba(hex: string, alpha: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export default function GlobeCanvas({ satellites, selectedId, onSelect, getSimTime }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance>(null);
  const threeRef = useRef<typeof Three | null>(null);
  const datumsRef = useRef<SatDatum[]>([]);
  const visualsRef = useRef(new Map<string, SatVisual>());
  const bandsRef = useRef(new Map<string, RiskBand>());
  const selectedRef = useRef(selectedId);
  const onSelectRef = useRef(onSelect);
  const simTimeRef = useRef(getSimTime);
  const pathsCentreRef = useRef(0);
  const [ready, setReady] = useState(false);

  onSelectRef.current = onSelect;
  simTimeRef.current = getSimTime;

  function rebuildPaths(centre: Date) {
    const globe = globeRef.current;
    if (!globe) return;
    pathsCentreRef.current = centre.getTime();
    const paths: PathDatum[] = datumsRef.current.map((d) => ({ id: d.id, points: orbitPath(d.satrec, centre, d.periodMin) }));
    globe.pathsData(paths);
  }

  function applyStyles() {
    const globe = globeRef.current;
    if (!globe) return;
    for (const [id, v] of visualsRef.current) {
      const colour = BAND_HEX[bandsRef.current.get(id) ?? "none"];
      v.body.color.set(colour);
      v.body.emissive.set(colour);
      v.ringMat.color.set(colour);
      const selected = selectedRef.current === id;
      v.ring.visible = selected;
      v.group.scale.setScalar(selected ? 1.2 : 1);
    }
    // Re-submit the paths so their colour and width accessors run again.
    globe.pathsData([...(globe.pathsData() as PathDatum[])]);
  }

  // Create the globe once.
  useEffect(() => {
    let cancelled = false;
    let raf = 0;
    let resize: ResizeObserver | null = null;

    (async () => {
      const [{ default: Globe }, THREE] = await Promise.all([import("globe.gl"), import("three")]);
      // Cleanup can run before the imports resolve (React StrictMode mounts effects
      // twice in dev); without this check that first globe would render forever, unowned.
      if (cancelled || !mountRef.current) return;
      const el = mountRef.current;
      threeRef.current = THREE;

      const globe: GlobeInstance = new Globe(el, { rendererConfig: { antialias: true, powerPreference: "high-performance" } })
        .width(el.clientWidth)
        .height(el.clientHeight)
        .globeImageUrl("/textures/earth-blue-marble.jpg")
        .bumpImageUrl("/textures/earth-topology.png")
        .backgroundImageUrl("/textures/night-sky.jpg")
        .showAtmosphere(true)
        .atmosphereColor("#a9c8e8")
        .atmosphereAltitude(0.14)
        // Satellites
        .objectLat("lat")
        .objectLng("lng")
        .objectAltitude("alt")
        .objectFacesSurface(true)
        .objectThreeObject((obj: object) => {
          const d = obj as SatDatum;
          const s = SAT_SIZE;
          const colour = BAND_HEX[bandsRef.current.get(d.id) ?? "none"];
          const group = new THREE.Group();
          const body = new THREE.MeshLambertMaterial({ color: colour, emissive: colour, emissiveIntensity: 0.45 });
          group.add(new THREE.Mesh(new THREE.BoxGeometry(s, s, s * 1.3), body));
          const panelMat = new THREE.MeshLambertMaterial({ color: "#33496b", emissive: "#101c30", side: THREE.DoubleSide });
          const panelGeo = new THREE.BoxGeometry(s * 2.4, s * 0.9, s * 0.06);
          for (const side of [-1, 1]) {
            const panel = new THREE.Mesh(panelGeo, panelMat);
            panel.position.x = side * (s * 0.5 + s * 1.3);
            group.add(panel);
          }
          const ringMat = new THREE.MeshBasicMaterial({ color: colour, transparent: true, opacity: 0.95, side: THREE.DoubleSide });
          const ring = new THREE.Mesh(new THREE.RingGeometry(s * 2.5, s * 2.8, 48), ringMat);
          ring.visible = selectedRef.current === d.id;
          group.add(ring);
          // Invisible, larger hit target: a 2px-wide model is hard to click.
          group.add(new THREE.Mesh(new THREE.SphereGeometry(s * 3.2, 12, 12), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })));
          visualsRef.current.set(d.id, { body, ring, ringMat, group });
          return group;
        })
        .objectLabel((obj: object) => {
          const d = obj as SatDatum;
          return `<div class="globe-tip"><strong>${escapeHtml(d.name)}</strong> <span>${escapeHtml(d.id)}</span></div>`;
        })
        .onObjectClick((obj: object) => onSelectRef.current((obj as SatDatum).id))
        .onGlobeClick(() => onSelectRef.current(null))
        // Orbit paths
        .pathPoints("points")
        .pathPointLat((p: [number, number, number]) => p[0])
        .pathPointLng((p: [number, number, number]) => p[1])
        .pathPointAlt((p: [number, number, number]) => p[2])
        .pathColor((obj: object) => {
          const id = (obj as PathDatum).id;
          const hex = BAND_HEX[bandsRef.current.get(id) ?? "none"];
          return rgba(hex, selectedRef.current === id ? 0.95 : 0.55);
        })
        .pathStroke((obj: object) => (selectedRef.current === (obj as PathDatum).id ? 1.6 : 0.7))
        .pathTransitionDuration(0);

      globe.renderer().setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      globe.pointOfView({ lat: 20, lng: 10, altitude: 1.9 });
      const controls = globe.controls();
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.35;
      controls.addEventListener("start", () => (controls.autoRotate = false));

      globeRef.current = globe;

      resize = new ResizeObserver(() => globe.width(el.clientWidth).height(el.clientHeight));
      resize.observe(el);

      const tick = () => {
        raf = requestAnimationFrame(tick);
        const datums = datumsRef.current;
        if (!datums.length) return;
        const now = simTimeRef.current();
        for (const d of datums) {
          const s = stateAt(d.satrec, now);
          if (s) {
            d.lat = s.lat;
            d.lng = s.lng;
            d.alt = s.alt / EARTH_RADIUS_KM;
          }
        }
        globe.objectsData(datums);
        const shortest = Math.min(...datums.map((d) => d.periodMin));
        if (Math.abs(now.getTime() - pathsCentreRef.current) > shortest * 60_000 * PATH_REFRESH_FRACTION) rebuildPaths(now);
      };
      raf = requestAnimationFrame(tick);
      setReady(true);
    })().catch((err) => console.error("Globe failed to initialise", err));

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      resize?.disconnect();
      // _destructor stops globe.gl's own render loop and frees the WebGL context.
      globeRef.current?._destructor?.();
      globeRef.current = null;
      visualsRef.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fleet changes: rebuild the satellite objects when the TLE set changes; otherwise
  // only bands changed, so restyle in place.
  const tleKey = satellites.map((s) => `${s.satelliteId}:${s.tle.tleLine1}:${s.tle.tleLine2}`).join("|");
  useEffect(() => {
    if (!ready) return;
    bandsRef.current = new Map(satellites.map((s) => [s.satelliteId, s.band]));
    const current = datumsRef.current.map((d) => d.id).join("|");
    const wanted = satellites.map((s) => s.satelliteId).join("|");
    if (current !== wanted || datumsRef.current.length === 0) {
      const now = simTimeRef.current();
      const datums: SatDatum[] = [];
      for (const s of satellites) {
        const satrec = makeSatrec(s.tle);
        if (!satrec) continue;
        const pos = stateAt(satrec, now);
        if (!pos) continue;
        datums.push({
          id: s.satelliteId,
          name: s.name,
          satrec,
          periodMin: orbitInfo(satrec).periodMin,
          lat: pos.lat,
          lng: pos.lng,
          alt: pos.alt / EARTH_RADIUS_KM,
        });
      }
      visualsRef.current.clear();
      datumsRef.current = datums;
      globeRef.current.objectsData(datums);
      rebuildPaths(now);
    }
    applyStyles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, tleKey, satellites]);

  // Selection: highlight, and fly the camera over the selected satellite.
  useEffect(() => {
    selectedRef.current = selectedId;
    if (!ready) return;
    applyStyles();
    const globe = globeRef.current;
    const d = datumsRef.current.find((x) => x.id === selectedId);
    if (globe && d) {
      globe.controls().autoRotate = false;
      globe.pointOfView({ lat: d.lat, lng: d.lng, altitude: 1.5 }, 1200);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, ready]);

  return (
    <div className="absolute inset-0">
      <div ref={mountRef} className="absolute inset-0" id="globeCanvas" />
      {!ready && (
        <p className="absolute inset-0 flex items-center justify-center text-[13px] text-muted-foreground">Loading globe…</p>
      )}
    </div>
  );
}
