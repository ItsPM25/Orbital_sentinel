"use client";

import { ArrowRightIcon } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { RiskMeter, StatusTag } from "@/components/risk";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type Satellite, type SatelliteRanking } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import { useCoalesced } from "@/lib/useCoalesced";
import { useStream } from "@/lib/useStream";

/** The fleet at a glance (REQ-10's ranking, with the satellites' identities). */
export default function SatellitesPage() {
  const [satellites, setSatellites] = useState<Satellite[] | null>(null);
  const [ranking, setRanking] = useState<SatelliteRanking[]>([]);

  useEffect(() => {
    api.satellites().then(setSatellites).catch(() => setSatellites([]));
    api.ranking().then(setRanking).catch(() => {});
  }, []);

  const scheduleRanking = useCoalesced(() => {
    api.ranking().then(setRanking).catch(() => {});
  });
  useStream((evt) => {
    if (evt.event === "ranking") scheduleRanking();
  });

  const rankingById = useMemo(() => new Map(ranking.map((r) => [r.satelliteId, r])), [ranking]);
  const ordered = useMemo(
    () =>
      [...(satellites ?? [])].sort(
        (a, b) => (rankingById.get(b.satelliteId)?.riskLevel ?? 0) - (rankingById.get(a.satelliteId)?.riskLevel ?? 0),
      ),
    [satellites, rankingById],
  );

  return (
    <>
      <PageHeader
        title="Satellites"
        description="The monitored fleet, highest current risk first. SMAP's telemetry is its own; the other four replay SMAP or MSL channels as proxies."
      />
      <div className="p-6">
        <div className="overflow-x-auto rounded-md border bg-card">
          {!satellites ? (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : (
            <Table id="satelliteTable">
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Satellite</TableHead>
                  <TableHead>NORAD</TableHead>
                  <TableHead>Telemetry</TableHead>
                  <TableHead>Current risk</TableHead>
                  <TableHead>Open alert</TableHead>
                  <TableHead>Last detection (UTC)</TableHead>
                  <TableHead className="pr-4" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {ordered.map((s) => {
                  const r = rankingById.get(s.satelliteId);
                  return (
                    <TableRow key={s.satelliteId} id={`satellite-${s.satelliteId}`}>
                      <TableCell className="pl-4">
                        <Link href={`/satellites/${s.satelliteId}`} className="font-medium underline-offset-4 hover:underline">
                          {s.name}
                        </Link>
                        <span className="num ml-2 text-[12px] text-muted-foreground">{s.satelliteId}</span>
                      </TableCell>
                      <TableCell className="num">{s.noradId ?? "–"}</TableCell>
                      <TableCell className="text-muted-foreground">{s.isProxy ? "Proxy (replayed)" : "Own (replayed)"}</TableCell>
                      <TableCell>
                        <RiskMeter level={r?.riskLevel ?? null} />
                      </TableCell>
                      <TableCell>
                        {r?.alertId ? (
                          <span className="inline-flex items-center gap-2">
                            <span className="num text-[13px]">{r.alertId}</span>
                            {r.status && <StatusTag status={r.status} />}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">None</span>
                        )}
                      </TableCell>
                      <TableCell className="num text-muted-foreground">{formatUtc(r?.lastDetectionAt)}</TableCell>
                      <TableCell className="pr-4 text-right">
                        <Link
                          href={`/satellites/${s.satelliteId}`}
                          aria-label={`Open ${s.name} health panel`}
                          className="inline-flex size-7 items-center justify-center rounded-md hover:bg-accent"
                        >
                          <ArrowRightIcon className="size-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </>
  );
}
