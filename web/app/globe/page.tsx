"use client";
/**
 * /globe — 3D orbital-tracking globe (REQ-12 … REQ-15).
 *
 * 5a: Real satellite positions via SGP4 (satellite.js), orbit trails, hover ground track.
 * 5b: Risk colours from SSE ranking events; click → health-panel drawer.
 *
 * globe.gl requires a real DOM (no SSR), so the GlobeCanvas component is
 * dynamically imported with { ssr: false }.
 *
 * ARCHITECTURE.md §5.5, §5.6 (5.0 Visualise), AD-5.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { TleEntry } from "@/lib/sgp4";
import { riskColour } from "@/lib/sgp4";
import type { SatelliteRanking } from "@/lib/api";
import { useCoalesced } from "@/lib/useCoalesced";
import { useStream } from "@/lib/useStream";
import type { SatelliteHealth } from "@/lib/api";
import styles from "./globe.module.css";

// Dynamic import so globe.gl never runs during SSR (it needs window + WebGL).
const GlobeCanvas = dynamic(() => import("./GlobeCanvas"), { ssr: false, loading: () => <GlobeLoader /> });

// ---------------------------------------------------------------------------
// Health panel drawer (5b — same data as /satellites/[id], REQ-15)
// ---------------------------------------------------------------------------
function HealthDrawer({
  satelliteId,
  onClose,
}: {
  satelliteId: string;
  onClose: () => void;
}) {
  const [health, setHealth] = useState<SatelliteHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setHealth(null);
    setError(null);
    api
      .satelliteHealth(satelliteId)
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, [satelliteId]);

  return (
    <div className={styles.drawer} id={`healthDrawer-${satelliteId}`}>
      <div className={styles.drawerHeader}>
        <h2 className={styles.drawerTitle}>
          {health?.satelliteName ?? satelliteId}
          {health?.isProxy && <span className={styles.proxyBadge}>Replayed telemetry</span>}
        </h2>
        <button className={styles.drawerClose} onClick={onClose} id="drawerClose" aria-label="Close panel">
          ✕
        </button>
      </div>

      {error && <p className={styles.drawerError}>{error}</p>}
      {!health && !error && <p className={styles.drawerLoading}>Loading health data…</p>}

      {health && (
        <>
          <div className={styles.verdictRow}>
            <span
              className={styles.verdictBadge}
              data-verdict={health.verdict}
              style={{ background: riskColour(health.riskLevel, health.severityLevel) }}
            >
              {health.verdict}
            </span>
            {health.riskLevel != null && (
              <span className={styles.riskChip}>Risk {health.riskLevel}/10 · {health.severityLevel}</span>
            )}
          </div>

          {health.anomalyScore != null && (
            <p className={styles.scoreRow}>
              Score: <strong>{health.anomalyScore.toFixed(3)}</strong>
              {health.detectedAt && (
                <> · Detected {new Date(health.detectedAt).toLocaleTimeString()}</>
              )}
            </p>
          )}

          {health.attributedChannels.length > 0 && (
            <div className={styles.attrBlock}>
              <h3 className={styles.attrTitle}>Attributed channels</h3>
              <ul className={styles.attrList}>
                {health.attributedChannels.map((ch) => (
                  <li key={ch.channelId} className={styles.attrItem}>
                    <span className={styles.attrName}>{ch.channelName}</span>
                    <span className={styles.attrBar} style={{ width: `${(ch.contributionScore * 100).toFixed(0)}%` }} />
                    <span className={styles.attrScore}>{(ch.contributionScore * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {health.telemetrySource && (
            <p className={styles.sourceNote}>Source channels: {health.telemetrySource}</p>
          )}

          <Link href={`/satellites/${satelliteId}`} className={styles.drawerLink}>
            Open full health panel →
          </Link>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading state shown while GlobeCanvas hydrates
// ---------------------------------------------------------------------------
function GlobeLoader() {
  return (
    <div className={styles.loaderWrap}>
      <div className={styles.spinner} />
      <p className={styles.loaderText}>Initialising 3D globe…</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------
export default function GlobePage() {
  const [tles, setTles] = useState<TleEntry[]>([]);
  const [ranking, setRanking] = useState<SatelliteRanking[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tleFetching, setTleFetching] = useState(true);
  const [tleError, setTleError] = useState<string | null>(null);

  // Initial data load
  const loadAll = useCallback(async () => {
    setTleFetching(true);
    try {
      const [tleData, rankingData] = await Promise.all([api.tle(), api.ranking()]);
      setTles(tleData);
      setRanking(rankingData);
    } catch (e) {
      setTleError(String(e));
    } finally {
      setTleFetching(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // REQ-14: update risk colours live from SSE ranking events
  const scheduleRankingReload = useCoalesced(() => {
    api.ranking().then(setRanking).catch(() => {});
  });
  useStream((evt) => {
    if (evt.event === "ranking") scheduleRankingReload();
  });

  // Build a risk-map keyed by satelliteId for fast colour lookup
  // Memoised: GlobeCanvas rebuilds every orbit-trail mesh when this identity changes,
  // so a fresh Map on every render meant a full rebuild on every re-render.
  const riskMap = useMemo(() => new Map(ranking.map((r) => [r.satelliteId, r])), [ranking]);

  return (
    <div className={styles.page}>
      {/* Top nav */}
      <header className={styles.header}>
        <span className={styles.logo}>⬡ Orbital Sentinel</span>
        <nav className={styles.nav}>
          <Link href="/dashboard" className={styles.navLink}>Alerts</Link>
          <Link href="/evaluation" className={styles.navLink}>Evaluation</Link>
          <Link href="/admin" className={styles.navLink}>Admin</Link>
        </nav>
      </header>

      {/* Main area: globe + optional drawer */}
      <div className={styles.main}>
        {/* Globe */}
        <div className={styles.globeWrap} id="globeContainer">
          {tleError ? (
            <div className={styles.tleErrorWrap}>
              <p className={styles.tleError}>Could not load TLE data: {tleError}</p>
              <button className={styles.retryBtn} onClick={loadAll}>Retry</button>
            </div>
          ) : tleFetching ? (
            <GlobeLoader />
          ) : (
            <GlobeCanvas
              tles={tles}
              riskMap={riskMap}
              onSelectSatellite={setSelectedId}
              selectedId={selectedId}
            />
          )}
          {/* Satellite list overlay — gives Selenium a reliable click target (TC09);
               also useful as a fleet overview for the analyst. */}
          {!tleFetching && !tleError && (
            <SatelliteListPanel
              tles={tles}
              riskMap={riskMap}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </div>

        {/* Health panel drawer — REQ-15 */}
        {selectedId && (
          <HealthDrawer satelliteId={selectedId} onClose={() => setSelectedId(null)} />
        )}
      </div>

      {/* Legend */}
      <Legend />

      {/* Help note */}
      <footer className={styles.footer}>
        <em>
          Orbital positions are live (SGP4 propagation from real TLEs). Health colours reflect
          replayed SMAP/MSL telemetry — not the real satellite&apos;s current state. This is a
          proof-of-concept for anomaly detection, not an operational monitoring tool.
        </em>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Satellite list panel — fleet overview + Selenium click targets (TC09)
// ---------------------------------------------------------------------------
function SatelliteListPanel({
  tles,
  riskMap,
  selectedId,
  onSelect,
}: {
  tles: TleEntry[];
  riskMap: Map<string, SatelliteRanking>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <div className={styles.satList} id="satListPanel">
      <span className={styles.satListTitle}>Fleet</span>
      {tles.map((t) => {
        const r = riskMap.get(t.satelliteId);
        const colour = riskColour(r?.riskLevel ?? null, r?.severityLevel ?? null);
        const active = selectedId === t.satelliteId;
        return (
          <button
            key={t.satelliteId}
            id={`sat-list-${t.satelliteId}`}
            className={styles.satChip}
            data-active={active}
            onClick={() => onSelect(active ? null : t.satelliteId)}
            title={`${t.satelliteId} — NORAD ${t.noradId ?? "N/A"}`}
          >
            <span className={styles.satDot} style={{ background: colour }} />
            <span className={styles.satName}>{t.satelliteId}</span>
            {r?.severityLevel && (
              <span className={styles.satSeverity} style={{ color: colour }}>
                {r.severityLevel}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function Legend() {
  return (
    <div className={styles.legend} id="globeLegend">
      <span className={styles.legendTitle}>Risk</span>
      {[
        { colour: "#22c55e", label: "Nominal" },
        { colour: "#eab308", label: "Medium" },
        { colour: "#f97316", label: "High" },
        { colour: "#ef4444", label: "Critical" },
      ].map(({ colour, label }) => (
        <span key={label} className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: colour }} />
          {label}
        </span>
      ))}
    </div>
  );
}
