"use client";

import { CaretLeftIcon, CaretRightIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { PageHeader, Panel } from "@/components/page-header";
import { SeverityLabel } from "@/components/risk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, ApiError, type EvaluationMetrics } from "@/lib/api";
import type { DetectionView } from "@/lib/entities";
import { fixed, formatUtc } from "@/lib/format";
import { useUser } from "@/lib/useUser";

const PAGE_SIZE = 25;

/** A score in [0, 1] as a number with a thin bar under it. */
function Score({ value, digits = 3 }: { value: number | null; digits?: number }) {
  return (
    <span className="inline-flex w-20 flex-col gap-1">
      <span className="num">{fixed(value, digits)}</span>
      <span className="h-1 rounded-[1px] bg-muted">
        <span className="block h-full rounded-[1px] bg-foreground" style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
      </span>
    </span>
  );
}

function MetricsRow({ label, metrics }: { label: string; metrics: EvaluationMetrics | null }) {
  if (!metrics) {
    return (
      <TableRow>
        <TableCell className="pl-4">{label}</TableCell>
        <TableCell colSpan={5}>
          <Skeleton className="h-5" />
        </TableCell>
      </TableRow>
    );
  }
  if (!metrics.available) {
    return (
      <TableRow>
        <TableCell className="pl-4">{label}</TableCell>
        <TableCell colSpan={5} className="text-muted-foreground">
          {metrics.message}
        </TableCell>
      </TableRow>
    );
  }
  return (
    <TableRow>
      <TableCell className="pl-4">{label}</TableCell>
      <TableCell className="num">{metrics.channelsEvaluated}</TableCell>
      <TableCell>
        <Score value={metrics.precision} />
      </TableCell>
      <TableCell>
        <Score value={metrics.recall} />
      </TableCell>
      <TableCell>
        <Score value={metrics.f1} />
      </TableCell>
      <TableCell className="num">{fixed(metrics.pointFpr, 4)}</TableCell>
    </TableRow>
  );
}

export default function EvaluationPage() {
  const { user, error: userError } = useUser(["Evaluator", "Administrator"]);
  const [baseline, setBaseline] = useState<EvaluationMetrics | null>(null);
  const [without, setWithout] = useState<EvaluationMetrics | null>(null);
  const [withFilter, setWithFilter] = useState<EvaluationMetrics | null>(null);

  const [detections, setDetections] = useState<DetectionView[] | null>(null);
  const [satelliteFilter, setSatelliteFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    api.evaluationMetrics().then(setBaseline).catch(() => {});
    api.evaluationMetrics(undefined, "off").then(setWithout).catch(() => {});
    api.evaluationMetrics(undefined, "on").then(setWithFilter).catch(() => {});
  }, [user]);

  useEffect(() => {
    if (!user) return;
    api
      .detections({
        satelliteId: satelliteFilter || undefined,
        outcome: outcomeFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .then(setDetections)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the detection log."));
  }, [user, satelliteFilter, outcomeFilter, page]);

  if (userError) {
    return (
      <p id="evalError" className="p-6">
        {userError}
      </p>
    );
  }

  return (
    <>
      <PageHeader
        title="Evaluation"
        titleId="evaluationTitle"
        description="Detector accuracy on the labelled SMAP/MSL test splits, and the log of every detection the system has made."
      />
      <div className="flex flex-col gap-4 p-6">
        <Panel
          title="Accuracy (REQ-5, REQ-11)"
          actions={<span className="text-[12px] text-muted-foreground">Event-level precision and recall; point-level FPR</span>}
        >
          <div className="overflow-x-auto">
            <Table id="metricsTable">
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Run</TableHead>
                  <TableHead>Channels</TableHead>
                  <TableHead>Precision</TableHead>
                  <TableHead>Recall</TableHead>
                  <TableHead>F1</TableHead>
                  <TableHead>Point FPR</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <MetricsRow label="Baseline (no persistence filter)" metrics={baseline} />
                <MetricsRow label="Without persistence filter" metrics={without} />
                <MetricsRow label="With persistence filter" metrics={withFilter} />
              </TableBody>
            </Table>
          </div>
          <p className="border-t px-4 py-3 text-[12px] leading-relaxed text-muted-foreground">
            Computed offline by <code className="num">python -m app.evaluation.baseline</code> and{" "}
            <code className="num">python -m app.evaluation.reports</code>, not live: scoring the whole labelled dataset on every
            page load would break the one-second response budget (SRS 5.1).
          </p>
        </Panel>

        <Panel title="Detection log (REQ-18)">
          <div className="flex flex-wrap items-end gap-4 border-b px-4 py-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="satelliteFilter" className="text-[12px] text-muted-foreground">
                Satellite ID
              </Label>
              <Input
                id="satelliteFilter"
                value={satelliteFilter}
                placeholder="e.g. SAT-001"
                className="num h-8 w-40"
                onChange={(e) => {
                  setPage(0);
                  setSatelliteFilter(e.target.value.trim());
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] text-muted-foreground">Outcome</span>
              <ToggleGroup
                id="outcomeFilter"
                type="single"
                variant="outline"
                size="sm"
                value={outcomeFilter || "all"}
                onValueChange={(v) => {
                  if (!v) return;
                  setPage(0);
                  setOutcomeFilter(v === "all" ? "" : v);
                }}
              >
                <ToggleGroupItem value="all" className="px-3">All</ToggleGroupItem>
                <ToggleGroupItem value="Confirmed" className="px-3">Confirmed</ToggleGroupItem>
                <ToggleGroupItem value="Suppressed" className="px-3">Suppressed</ToggleGroupItem>
              </ToggleGroup>
            </div>
            <p id="detectionCount" className="num ml-auto text-[13px] text-muted-foreground">
              {detections ? `${detections.length} detections (page ${page + 1})` : ""}
            </p>
          </div>

          {error && (
            <p id="detectionError" className="px-4 py-3 text-[color:var(--risk-critical)]">
              {error}
            </p>
          )}
          {!detections ? (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-8" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table id="detectionTable">
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-4">Detection</TableHead>
                    <TableHead>Satellite</TableHead>
                    <TableHead>Time (UTC)</TableHead>
                    <TableHead className="text-right">Anomaly score</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead className="text-right">Persistence</TableHead>
                    <TableHead className="pr-4">Outcome</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detections.map((d) => (
                    <TableRow key={d.detectionId} id={`detection-${d.detectionId}`}>
                      <TableCell className="num pl-4">{d.detectionId}</TableCell>
                      <TableCell>{d.satelliteName}</TableCell>
                      <TableCell className="num text-muted-foreground">{formatUtc(d.timestamp)}</TableCell>
                      <TableCell className="num text-right">{fixed(d.anomalyScore)}</TableCell>
                      <TableCell>
                        <SeverityLabel severity={d.severityLevel} />
                      </TableCell>
                      <TableCell className="num text-right">{d.persistenceCount}</TableCell>
                      <TableCell className="pr-4">{d.outcome ?? "–"}</TableCell>
                    </TableRow>
                  ))}
                  {detections.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                        No detections match these filters.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="flex items-center justify-end gap-2 border-t px-4 py-2">
            <Button id="prevPage" variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
              <CaretLeftIcon />
              Previous
            </Button>
            <Button
              id="nextPage"
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!detections || detections.length < PAGE_SIZE}
            >
              Next
              <CaretRightIcon />
            </Button>
          </div>
        </Panel>
      </div>
    </>
  );
}
