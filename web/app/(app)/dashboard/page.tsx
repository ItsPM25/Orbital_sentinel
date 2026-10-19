"use client";

import { CheckIcon } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { PageHeader, StatStrip } from "@/components/page-header";
import { RiskMeter, SeverityLabel, StatusTag } from "@/components/risk";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AlertStatus, AlertView } from "@/lib/entities";
import { formatUtc } from "@/lib/format";
import { bandVar, riskBand } from "@/lib/risk";
import { useCoalesced } from "@/lib/useCoalesced";
import { useStream } from "@/lib/useStream";

type Filter = "all" | AlertStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "AlertRaised", label: "Raised" },
  { value: "Acknowledged", label: "Acknowledged" },
  { value: "Resolved", label: "Resolved" },
];

export default function DashboardPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<AlertView[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const reload = useCallback(() => {
    fetch("/api/alerts", { cache: "no-store" }).then(async (res) => {
      // 401 means there is no valid session.
      if (!res.ok) {
        router.replace("/login");
        return;
      }
      setAlerts(await res.json());
    });
  }, [router]);

  useEffect(() => {
    reload();
  }, [reload]);

  // REQ-16 live updates: a new or escalated alert refreshes the list (coalesced).
  const scheduleReload = useCoalesced(reload);
  useStream((evt) => {
    if (evt.event === "alert.created" || evt.event === "alert.updated" || evt.event === "ranking") {
      scheduleReload();
    }
  });

  async function acknowledge(alertId: string) {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (!res.ok) {
      toast.error(`Could not acknowledge ${alertId}`);
      return;
    }
    const updated: AlertView = await res.json();
    setAlerts((prev) => prev && prev.map((a) => (a.alertId === alertId ? updated : a)));
    toast.success(`${alertId} acknowledged`);
  }

  const summary = useMemo(() => {
    const list = alerts ?? [];
    const open = list.filter((a) => a.status !== "Resolved");
    return {
      open: open.length,
      critical: open.filter((a) => riskBand(a.riskLevel) === "critical").length,
      raised: list.filter((a) => a.status === "AlertRaised").length,
      satellites: new Set(open.map((a) => a.satelliteId)).size,
    };
  }, [alerts]);

  const shown = (alerts ?? []).filter((a) => filter === "all" || a.status === filter);

  return (
    <>
      <PageHeader
        title="Alerts"
        titleId="dashboardTitle"
        description="Ranked by risk level, highest first. The list updates live while monitoring sessions replay telemetry."
      />
      <div className="flex flex-col gap-4 p-6">
        <StatStrip
          items={[
            { label: "Open alerts", value: alerts ? summary.open : "–" },
            {
              label: "Critical",
              value: alerts ? <span style={{ color: summary.critical ? bandVar("critical") : undefined }}>{summary.critical}</span> : "–",
            },
            { label: "Awaiting acknowledgement", value: alerts ? summary.raised : "–" },
            { label: "Satellites affected", value: alerts ? summary.satellites : "–" },
          ]}
        />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={filter}
            onValueChange={(v) => v && setFilter(v as Filter)}
            aria-label="Filter by status"
          >
            {FILTERS.map((f) => (
              <ToggleGroupItem key={f.value} value={f.value} className="px-3">
                {f.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p id="alertCount" className="num text-[13px] text-muted-foreground">
            {shown.length} alerts
          </p>
        </div>

        <div className="overflow-x-auto rounded-md border bg-card">
          {!alerts ? (
            <div className="flex flex-col gap-2 p-4" id="loading">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <Table id="alertTable">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10 pl-4">#</TableHead>
                  <TableHead>Alert</TableHead>
                  <TableHead>Satellite</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Raised (UTC)</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="pr-4 text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((a, i) => {
                  const open = a.status === "AlertRaised";
                  return (
                    <TableRow
                      key={a.alertId}
                      id={`alert-${a.alertId}`}
                      className="border-l-2"
                      style={{ borderLeftColor: open ? bandVar(riskBand(a.riskLevel)) : "transparent" }}
                    >
                      <TableCell className="rank num pl-4 text-muted-foreground">{i + 1}</TableCell>
                      <TableCell className="alertId num">{a.alertId}</TableCell>
                      <TableCell className="satelliteName">
                        <Link href={`/satellites/${a.satelliteId}`} className="font-medium underline-offset-4 hover:underline">
                          {a.satelliteName}
                        </Link>
                        <span className="num ml-2 text-[12px] text-muted-foreground">{a.satelliteId}</span>
                      </TableCell>
                      <TableCell className="riskLevel">
                        <RiskMeter level={a.riskLevel} />
                      </TableCell>
                      <TableCell className="severityLevel">
                        <SeverityLabel severity={a.severityLevel} />
                      </TableCell>
                      <TableCell className="attributedChannel num">
                        {a.attributedChannel ?? <span className="text-muted-foreground">unknown</span>}
                      </TableCell>
                      <TableCell className="createdAt num text-muted-foreground">{formatUtc(a.createdAt)}</TableCell>
                      <TableCell className="status" id={`status-${a.alertId}`}>
                        <StatusTag status={a.status} />
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        <Button
                          id={`ack-${a.alertId}`}
                          variant="outline"
                          size="sm"
                          disabled={!open}
                          onClick={() => acknowledge(a.alertId)}
                        >
                          {!open && <CheckIcon />}
                          {open ? "Acknowledge" : a.status === "Resolved" ? "Resolved" : "Acknowledged"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {shown.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="py-10 text-center text-muted-foreground">
                      {alerts.length === 0
                        ? "No alerts yet. Start a monitoring session under Administration to replay telemetry."
                        : "No alerts with this status."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </>
  );
}
