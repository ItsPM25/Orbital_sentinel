"use client";

import { ArrowLeftIcon, GlobeHemisphereWestIcon, InfoIcon } from "@phosphor-icons/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader, Panel, StatStrip } from "@/components/page-header";
import { RiskMeter, SeverityLabel } from "@/components/risk";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type Channel, type SatelliteHealth, type TelemetrySeries } from "@/lib/api";
import type { DetectionView } from "@/lib/entities";
import { fixed, formatUtc } from "@/lib/format";
import { bandVar } from "@/lib/risk";
import { useCoalesced } from "@/lib/useCoalesced";
import { useStream } from "@/lib/useStream";
import { cn } from "@/lib/utils";

// Recharts needs one row per point; anomaly ranges are rendered as a shaded Area
// using a band that is only non-zero inside a flagged range (REQ-17).
function buildChartRows(series: TelemetrySeries) {
  const bandMax = Math.max(...series.points, 0) * 1.05 || 1;
  const bandMin = Math.min(...series.points, 0) * 1.05;
  return series.pointIndices.map((index, i) => {
    const inRange = series.anomalyRanges.some((r) => index >= r.start && index <= r.end);
    return { index, value: series.points[i], anomalyBand: inRange ? [bandMin, bandMax] : null };
  });
}

const AXIS_TICK = { fill: "var(--muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono)" };

export default function SatelliteHealthPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const satelliteId = params.id;

  const [health, setHealth] = useState<SatelliteHealth | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [series, setSeries] = useState<TelemetrySeries | null>(null);
  const [detections, setDetections] = useState<DetectionView[] | null>(null);
  const [error, setError] = useState("");

  const loadHealth = useCallback(() => {
    api
      .satelliteHealth(satelliteId)
      .then(setHealth)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
        else if (err instanceof ApiError && err.status === 404) setError(`Satellite ${satelliteId} not found.`);
        else setError("Could not load satellite health.");
      });
    api.detections({ satelliteId, limit: 8 }).then(setDetections).catch(() => setDetections([]));
  }, [satelliteId, router]);

  useEffect(() => {
    loadHealth();
    api.satelliteChannels(satelliteId).then(setChannels).catch(() => {});
  }, [satelliteId, loadHealth]);

  // Default chart channel: the latest detection's top attributed channel; else the
  // channel behind this satellite's highest-risk attributed alert; else the first.
  useEffect(() => {
    if (selectedChannel || !health) return;
    if (health.attributedChannels.length) {
      setSelectedChannel(health.attributedChannels[0].channelId);
      return;
    }
    if (!channels.length) return;
    api
      .alerts()
      .then((alerts) => {
        const name = alerts.find((a) => a.satelliteId === satelliteId && a.attributedChannel)?.attributedChannel;
        const match = channels.find((c) => c.channelName === name || c.channelId === name);
        setSelectedChannel((current) => current || (match ?? channels[0]).channelId);
      })
      .catch(() => setSelectedChannel((current) => current || channels[0].channelId));
  }, [health, channels, selectedChannel, satelliteId]);

  useEffect(() => {
    if (!selectedChannel) return;
    api.satelliteTelemetry(satelliteId, selectedChannel).then(setSeries).catch(() => setSeries(null));
  }, [satelliteId, selectedChannel]);

  // Every detection for this satellite is an event; refresh at most every 2s.
  const scheduleRefresh = useCoalesced(() => {
    loadHealth();
    if (selectedChannel) api.satelliteTelemetry(satelliteId, selectedChannel).then(setSeries).catch(() => {});
  }, 2000);
  useStream((evt) => {
    if (evt.satelliteId === satelliteId) scheduleRefresh();
  });

  if (error) {
    return (
      <div className="p-6">
        <p id="healthError" className="text-[color:var(--risk-critical)]">
          {error}
        </p>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={health ? health.satelliteName : <span className="inline-block h-7 w-40 animate-pulse rounded-md bg-muted align-middle" />}
        titleId="healthTitle"
        description={
          <span className="num text-[13px]">
            {satelliteId} · health panel
          </span>
        }
        actions={
          <>
            <Button asChild variant="ghost" size="sm">
              <Link href="/satellites">
                <ArrowLeftIcon />
                All satellites
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/globe">
                <GlobeHemisphereWestIcon />
                Globe
              </Link>
            </Button>
          </>
        }
      />

      <div className="flex flex-col gap-4 p-6">
        {health?.isProxy && (
          <p id="proxyBadge" className="flex items-start gap-2 rounded-md border bg-card px-3 py-2 text-[13px] text-muted-foreground">
            <InfoIcon className="mt-0.5 size-4 shrink-0" />
            <span>
              Replayed telemetry. Proxy satellite: its health comes from{" "}
              {health.telemetrySource ?? "SMAP/MSL channels (docs/ARCHITECTURE.md section 4.3)"}, not from the real spacecraft.
            </span>
          </p>
        )}

        <StatStrip
          columns={5}
          items={[
            {
              label: "Verdict",
              id: "verdict",
              value: health ? (
                <span style={{ color: health.verdict === "Anomalous" ? bandVar("critical") : undefined }}>{health.verdict}</span>
              ) : (
                "–"
              ),
            },
            { label: "Risk level", id: "riskLevel", value: health ? <RiskMeter level={health.riskLevel} showLabel={false} /> : "–" },
            {
              label: "Severity",
              id: "severityLevel",
              value: health ? <span className="font-sans text-base"><SeverityLabel severity={health.severityLevel} /></span> : "–",
            },
            { label: "Anomaly score", id: "anomalyScore", value: health ? fixed(health.anomalyScore) : "–" },
            {
              label: "Last detection (UTC)",
              id: "detectedAt",
              value: <span className="text-base">{health ? formatUtc(health.detectedAt) : "–"}</span>,
            },
          ]}
        />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Panel
            title="Telemetry"
            actions={
              <Select value={selectedChannel} onValueChange={setSelectedChannel}>
                <SelectTrigger id="channelSelect" size="sm" className="num w-44" aria-label="Channel">
                  <SelectValue placeholder="Choose a channel" />
                </SelectTrigger>
                <SelectContent>
                  {channels.map((c) => (
                    <SelectItem key={c.channelId} value={c.channelId} className="num">
                      {c.channelName}
                      {c.unit ? ` (${c.unit})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            }
            bodyClassName="p-4"
          >
            {!series ? (
              <Skeleton className="h-80" />
            ) : (
              <div id="telemetryChart">
                <div className="h-80">
                  <ResponsiveContainer>
                    <ComposedChart data={buildChartRows(series)} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                      <CartesianGrid vertical={false} stroke="var(--border)" />
                      <XAxis dataKey="index" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--border)" }} minTickGap={40} />
                      <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} tickFormatter={(v: number) => v.toFixed(2)} />
                      <Tooltip
                        contentStyle={{
                          background: "var(--popover)",
                          border: "1px solid var(--border)",
                          borderRadius: 4,
                          fontSize: 12,
                          fontFamily: "var(--font-mono)",
                        }}
                        labelFormatter={(i) => `index ${i}`}
                        formatter={(v, name) => (name === "value" ? [Number(v).toFixed(4), "value"] : [null, null])}
                      />
                      {/* Shaded band over the ranges the model actually flagged (REQ-17) */}
                      <Area
                        dataKey="anomalyBand"
                        stroke="none"
                        fill="var(--risk-critical)"
                        fillOpacity={0.16}
                        isAnimationActive={false}
                        connectNulls={false}
                        activeDot={false}
                      />
                      <Line dataKey="value" dot={false} stroke="var(--foreground)" strokeWidth={1.25} isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
                  <span className="num">
                    {series.totalPoints.toLocaleString()} points ({series.points.length.toLocaleString()} shown, downsampled)
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-2.5 w-4 rounded-[2px]" style={{ background: "var(--risk-critical)", opacity: 0.35 }} />
                    {series.anomalyRanges.length} flagged range{series.anomalyRanges.length === 1 ? "" : "s"}
                  </span>
                </p>
              </div>
            )}
          </Panel>

          <div className="flex flex-col gap-4">
            <Panel title="Attributed channels" bodyClassName="p-4">
              {!health ? (
                <Skeleton className="h-24" />
              ) : health.attributedChannels.length === 0 ? (
                <p id="attributionUnknown" className="text-[13px] text-muted-foreground">
                  unknown (no channel stood out)
                </p>
              ) : (
                <ul id="attributedChannels" className="flex flex-col gap-1">
                  {health.attributedChannels.map((c) => {
                    const pct = Math.round(c.contributionScore * 100);
                    const active = c.channelId === selectedChannel;
                    return (
                      <li key={c.channelId}>
                        <button
                          onClick={() => setSelectedChannel(c.channelId)}
                          aria-pressed={active}
                          className={cn(
                            "grid w-full grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2 rounded-[3px] px-1.5 py-1 text-left text-[13px] hover:bg-accent",
                            active && "bg-accent",
                          )}
                        >
                          <span className="num truncate">{c.channelName}</span>
                          <span className="h-1.5 rounded-[1px] bg-muted">
                            <span className="block h-full rounded-[1px] bg-foreground" style={{ width: `${pct}%` }} />
                          </span>
                          <span className="num text-right text-muted-foreground">{pct}%</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>

            <Panel title="Recent detections" bodyClassName="py-1">
              {!detections ? (
                <Skeleton className="m-4 h-24" />
              ) : detections.length === 0 ? (
                <p className="px-4 py-3 text-[13px] text-muted-foreground">None logged for this satellite.</p>
              ) : (
                <ul className="divide-y text-[13px]">
                  {detections.map((d) => (
                    <li key={d.detectionId} className="flex items-center justify-between gap-3 px-4 py-2">
                      <span className="min-w-0">
                        <span className="num block truncate text-[12px] text-muted-foreground">{formatUtc(d.timestamp)}</span>
                        <SeverityLabel severity={d.severityLevel} />
                      </span>
                      <span className="text-right">
                        <span className="num block">{fixed(d.anomalyScore)}</span>
                        <span className="text-[12px] text-muted-foreground">{d.outcome ?? "–"}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      </div>
    </>
  );
}
