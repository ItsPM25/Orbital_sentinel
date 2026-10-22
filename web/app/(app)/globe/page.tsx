"use client";
/**
 * /globe: 3D orbital tracking (REQ-12 ... REQ-15). Positions are propagated from
 * real TLEs; the risk colours come from replayed SMAP/MSL telemetry. The clock
 * can run faster than real time so orbital motion is visible; the readout always
 * says which.
 *
 * globe.gl needs a real DOM and WebGL, so GlobeCanvas is loaded with ssr: false.
 */

import { ArrowRightIcon, XIcon } from "@phosphor-icons/react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BandSwatch, RiskMeter } from "@/components/risk";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, type SatelliteHealth, type SatelliteRanking } from "@/lib/api";
import { fixed, formatUtc, formatUtcTime } from "@/lib/format";
import { BAND_LABEL, bandVar, riskBand } from "@/lib/risk";
import { makeSatrec, orbitInfo, stateAt, type SatState, type TleEntry } from "@/lib/sgp4";
import { useCoalesced } from "@/lib/useCoalesced";
import { useStream } from "@/lib/useStream";
import { cn } from "@/lib/utils";
import type { GlobeSatellite } from "./GlobeCanvas";

const GlobeCanvas = dynamic(() => import("./GlobeCanvas"), {
  ssr: false,
  loading: () => <p className="absolute inset-0 flex items-center justify-center text-[13px] text-muted-foreground">Loading globe…</p>,
});

const SPEEDS = [1, 10, 60, 300] as const;
type Speed = (typeof SPEEDS)[number];

/** Simulation clock: real time scaled by `speed` from an anchor. */
function useSimClock(initialSpeed: Speed) {
  const clock = useRef({ anchorReal: Date.now(), anchorSim: Date.now(), speed: initialSpeed as number });
  const [speed, setSpeedState] = useState<Speed>(initialSpeed);
  const now = useCallback(() => {
    const c = clock.current;
    return new Date(c.anchorSim + (Date.now() - c.anchorReal) * c.speed);
  }, []);
  const setSpeed = useCallback(
    (next: Speed) => {
      const c = clock.current;
      // Going back to 1x means "live": jump to the real current time.
      c.anchorSim = next === 1 ? Date.now() : now().getTime();
      c.anchorReal = Date.now();
      c.speed = next;
      setSpeedState(next);
    },
    [now],
  );
  return { now, speed, setSpeed };
}

/** Re-renders every `ms` and returns the latest value of `read()`; null until mounted,
 * so the statically prerendered HTML never contains a time that won't match the client. */
function useTicker<T>(read: () => T, ms: number): T | null {
  const [value, setValue] = useState<T | null>(null);
  const readRef = useRef(read);
  readRef.current = read;
  useEffect(() => {
    setValue(readRef.current());
    const id = setInterval(() => setValue(readRef.current()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return value;
}

export default function GlobePage() {
  const [tles, setTles] = useState<TleEntry[] | null>(null);
  const [ranking, setRanking] = useState<SatelliteRanking[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clock = useSimClock(60);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [tleData, rankingData] = await Promise.all([api.tle(), api.ranking()]);
      setTles(tleData);
      setRanking(rankingData);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // REQ-14: risk colours follow SSE ranking events (coalesced to one refetch a second).
  const scheduleRankingReload = useCoalesced(() => {
    api.ranking().then(setRanking).catch(() => {});
  });
  useStream((evt) => {
    if (evt.event === "ranking") scheduleRankingReload();
  });

  const rankingById = useMemo(() => new Map(ranking.map((r) => [r.satelliteId, r])), [ranking]);
  const satellites: GlobeSatellite[] = useMemo(
    () =>
      (tles ?? []).map((tle) => {
        const r = rankingById.get(tle.satelliteId);
        return { satelliteId: tle.satelliteId, name: r?.satelliteName ?? tle.satelliteId, band: riskBand(r?.riskLevel), tle };
      }),
    [tles, rankingById],
  );
  const selected = satellites.find((s) => s.satelliteId === selectedId) ?? null;
  const anyStale = (tles ?? []).some((t) => t.stale);

  return (
    <div className="dark flex h-[calc(100dvh-3rem)] flex-col bg-background text-foreground md:h-dvh lg:flex-row">
      <div className="relative min-h-[55vh] flex-1 overflow-hidden" id="globeContainer">
        {error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <p className="text-[13px]">Could not load orbital data: {error}</p>
            <Button variant="outline" size="sm" onClick={loadAll}>
              Retry
            </Button>
          </div>
        ) : tles ? (
          <GlobeCanvas satellites={satellites} selectedId={selectedId} onSelect={setSelectedId} getSimTime={clock.now} />
        ) : (
          <p className="absolute inset-0 flex items-center justify-center text-[13px] text-muted-foreground">Loading orbital data…</p>
        )}

        <ClockBar now={clock.now} speed={clock.speed} onSpeed={clock.setSpeed} stale={anyStale} />
        <Legend />
      </div>

      <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-t bg-card lg:w-[22rem] lg:border-t-0 lg:border-l">
        <FleetList satellites={satellites} ranking={rankingById} selectedId={selectedId} onSelect={setSelectedId} loading={!tles && !error} />
        {selected && (
          <SatelliteDetail
            key={selected.satelliteId}
            satellite={selected}
            ranking={rankingById.get(selected.satelliteId) ?? null}
            now={clock.now}
            onClose={() => setSelectedId(null)}
          />
        )}
      </aside>
    </div>
  );
}

function ClockBar({ now, speed, onSpeed, stale }: { now: () => Date; speed: Speed; onSpeed: (s: Speed) => void; stale: boolean }) {
  const time = useTicker(now, 250);
  return (
    <div className="pointer-events-none absolute top-0 left-0 flex flex-wrap items-center gap-3 p-4">
      <div className="pointer-events-auto rounded-md border bg-card/90 px-3 py-2">
        <p className="text-[12px] text-muted-foreground" id="simMode">
          {speed === 1 ? "Live, UTC" : `Simulated at ${speed}×, UTC`}
        </p>
        <p className="num text-[15px] font-medium" id="simClock">
          {time ? `${formatUtc(time.toISOString()).slice(0, 10)} ${formatUtcTime(time)}` : " "}
        </p>
      </div>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={String(speed)}
        onValueChange={(v) => v && onSpeed(Number(v) as Speed)}
        aria-label="Simulation speed"
        className="pointer-events-auto bg-card/90"
      >
        {SPEEDS.map((s) => (
          <ToggleGroupItem key={s} value={String(s)} className="num px-2.5">
            {s === 1 ? "Live" : `${s}×`}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {stale && (
        <p className="pointer-events-auto rounded-md border bg-card/90 px-2.5 py-1.5 text-[12px] text-muted-foreground">
          CelesTrak unreachable: using cached TLEs
        </p>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-0 left-0 p-4" id="globeLegend">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border bg-card/90 px-3 py-2 text-[12px]">
        {(["critical", "high", "medium", "low", "none"] as const).map((band) => (
          <span key={band} className="inline-flex items-center gap-1.5">
            <BandSwatch band={band} />
            {BAND_LABEL[band]}
          </span>
        ))}
      </div>
    </div>
  );
}

function FleetList({
  satellites,
  ranking,
  selectedId,
  onSelect,
  loading,
}: {
  satellites: GlobeSatellite[];
  ranking: Map<string, SatelliteRanking>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  loading: boolean;
}) {
  // Highest risk first, like the dashboard.
  const ordered = [...satellites].sort(
    (a, b) => (ranking.get(b.satelliteId)?.riskLevel ?? 0) - (ranking.get(a.satelliteId)?.riskLevel ?? 0),
  );
  return (
    <section id="satListPanel" className="border-b">
      <div className="flex items-baseline justify-between px-4 pt-4 pb-2">
        <h2 className="text-[13px] font-semibold">Fleet</h2>
        <span className="text-[12px] text-muted-foreground">Select a satellite</span>
      </div>
      {loading && (
        <div className="flex flex-col gap-1.5 px-4 pb-4">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      )}
      <ul className="pb-2">
        {ordered.map((s) => {
          const r = ranking.get(s.satelliteId);
          const active = selectedId === s.satelliteId;
          return (
            <li key={s.satelliteId}>
              <button
                id={`sat-list-${s.satelliteId}`}
                onClick={() => onSelect(active ? null : s.satelliteId)}
                aria-pressed={active}
                className={cn(
                  "flex w-full items-center gap-3 border-l-2 border-transparent px-4 py-2 text-left hover:bg-accent",
                  active && "border-l-foreground bg-accent",
                )}
              >
                <BandSwatch band={s.band} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{s.name}</span>
                  <span className="num block text-[12px] text-muted-foreground">
                    {s.satelliteId} · NORAD {s.tle.noradId ?? "–"}
                  </span>
                </span>
                <span className="text-[12px]" style={{ color: bandVar(s.band) }}>
                  {r?.riskLevel != null ? `${r.riskLevel} ${BAND_LABEL[s.band]}` : BAND_LABEL.none}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="num text-right">{children}</dd>
    </div>
  );
}

function SatelliteDetail({
  satellite,
  ranking,
  now,
  onClose,
}: {
  satellite: GlobeSatellite;
  ranking: SatelliteRanking | null;
  now: () => Date;
  onClose: () => void;
}) {
  const id = satellite.satelliteId;
  const satrec = useMemo(() => makeSatrec(satellite.tle), [satellite.tle]);
  const orbit = useMemo(() => (satrec ? orbitInfo(satrec) : null), [satrec]);
  const live: SatState | null = useTicker(() => (satrec ? stateAt(satrec, now()) : null), 500) ?? null;
  const [health, setHealth] = useState<SatelliteHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = useCallback(() => {
    api
      .satelliteHealth(id)
      .then(setHealth)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);
  useEffect(() => {
    loadHealth();
  }, [loadHealth]);
  const scheduleHealth = useCoalesced(loadHealth, 2000);
  useStream((evt) => {
    if (evt.satelliteId === id) scheduleHealth();
  });

  return (
    <section id={`healthDrawer-${id}`} aria-label={`${satellite.name} details`} className="flex flex-col gap-5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{satellite.name}</h2>
          <p className="num text-[12px] text-muted-foreground">
            {id} · NORAD {satellite.tle.noradId ?? "–"}
          </p>
        </div>
        <Button id="drawerClose" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close details">
          <XIcon />
        </Button>
      </div>

      <div>
        <h3 className="mb-1 text-[13px] font-semibold">Health</h3>
        {error && <p className="text-[13px] text-[color:var(--risk-critical)]">{error}</p>}
        {!health && !error && <Skeleton className="h-20" />}
        {health && (
          <dl className="text-[13px]">
            <Row label="Verdict">
              <span style={{ color: health.verdict === "Anomalous" ? bandVar("critical") : undefined }}>{health.verdict}</span>
            </Row>
            <Row label="Risk">
              <RiskMeter level={ranking?.riskLevel ?? health.riskLevel} />
            </Row>
            <Row label="Anomaly score">{fixed(health.anomalyScore)}</Row>
            <Row label="Last detection">{formatUtc(health.detectedAt)}</Row>
            {ranking?.alertId && (
              <Row label="Open alert">
                <Link href="/dashboard" className="underline underline-offset-4">
                  {ranking.alertId}
                </Link>
              </Row>
            )}
          </dl>
        )}
      </div>

      {health && health.attributedChannels.length > 0 && (
        <div>
          <h3 className="mb-2 text-[13px] font-semibold">Attributed channels</h3>
          <ul className="flex flex-col gap-1.5">
            {health.attributedChannels.map((ch) => (
              <li key={ch.channelId} className="grid grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2 text-[13px]">
                <span className="num truncate">{ch.channelName}</span>
                <span className="h-1.5 rounded-[1px] bg-muted">
                  <span className="block h-full rounded-[1px] bg-foreground" style={{ width: `${Math.round(ch.contributionScore * 100)}%` }} />
                </span>
                <span className="num text-right text-muted-foreground">{Math.round(ch.contributionScore * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="mb-1 text-[13px] font-semibold">Position</h3>
        <dl className="text-[13px]" id="livePosition">
          <Row label="Latitude">{live ? `${live.lat.toFixed(2)}°` : "–"}</Row>
          <Row label="Longitude">{live ? `${live.lng.toFixed(2)}°` : "–"}</Row>
          <Row label="Altitude">{live ? `${live.alt.toFixed(0)} km` : "–"}</Row>
          <Row label="Speed">{live ? `${live.speed.toFixed(2)} km/s` : "–"}</Row>
        </dl>
      </div>

      {orbit && (
        <div>
          <h3 className="mb-1 text-[13px] font-semibold">Orbit</h3>
          <dl className="text-[13px]">
            <Row label="Period">{orbit.periodMin.toFixed(1)} min</Row>
            <Row label="Inclination">{orbit.inclinationDeg.toFixed(2)}°</Row>
            <Row label="Perigee / apogee">
              {orbit.perigeeKm.toFixed(0)} / {orbit.apogeeKm.toFixed(0)} km
            </Row>
            <Row label="TLE fetched">{satellite.tle.stale ? "cached snapshot" : formatUtc(satellite.tle.fetchedAt, false)}</Row>
          </dl>
        </div>
      )}

      {health?.isProxy && (
        <p className="rounded-md border px-3 py-2 text-[12px] leading-relaxed text-muted-foreground">
          Proxy satellite: its health comes from replayed {health.telemetrySource ?? "SMAP/MSL"} telemetry, not from the real
          spacecraft. The orbit is real.
        </p>
      )}

      <Button asChild variant="outline" className="justify-between">
        <Link href={`/satellites/${id}`}>
          Open health panel
          <ArrowRightIcon />
        </Link>
      </Button>
    </section>
  );
}
