"use client";

import { DatabaseIcon, PlayIcon, StopIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { PageHeader, Panel } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError, type DetectionModel, type MonitoringConfig, type Satellite, type SessionStatus } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import { useUser } from "@/lib/useUser";

const POLL_MS = 2000;

function SessionCell({ session }: { session: SessionStatus | undefined }) {
  if (!session) return <span className="text-muted-foreground">Stopped</span>;
  if (!session.running) {
    return <span className="text-[color:var(--risk-critical)]">Stopped with an error</span>;
  }
  const c = session.counters;
  return (
    <span className="inline-flex flex-col">
      <span className="inline-flex items-center gap-1.5 font-medium">
        <span className="size-2 animate-pulse rounded-full bg-[color:var(--risk-low)]" aria-hidden="true" />
        Running
      </span>
      {c && (
        <span className="num text-[12px] text-muted-foreground">
          {c.windows} windows · {c.detections} detections
        </span>
      )}
    </span>
  );
}

export default function AdminPage() {
  const { user, error: userError } = useUser(["Administrator"]);
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [models, setModels] = useState<DetectionModel[]>([]);
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [configs, setConfigs] = useState<Record<string, MonitoringConfig>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const report = (text: string, ok = true) => {
    setMessage(text);
    if (ok) toast.success(text);
    else toast.error(text);
  };

  const reload = useCallback(() => {
    if (!user) return;
    api.satellites().then(setSatellites).catch(() => {});
    api.listModels().then(setModels).catch(() => {});
    api.listSessions().then(setSessions).catch(() => {});
  }, [user]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Counters change every window while a session runs; poll only while one does.
  const anyRunning = sessions.some((s) => s.running);
  useEffect(() => {
    if (!user || !anyRunning) return;
    const id = setInterval(() => api.listSessions().then(setSessions).catch(() => {}), POLL_MS);
    return () => clearInterval(id);
  }, [user, anyRunning]);

  useEffect(() => {
    if (!user) return;
    Promise.all(satellites.map((s) => api.getConfig(s.satelliteId).catch(() => null))).then((rows) => {
      const map: Record<string, MonitoringConfig> = {};
      rows.forEach((c, i) => {
        if (c) map[satellites[i].satelliteId] = c;
      });
      setConfigs(map);
    });
  }, [user, satellites]);

  async function importDataset() {
    setBusy("import");
    try {
      const result = await api.importDataset(false);
      report(`Imported: ${result.channelsCreated} channel(s) created, ${result.channelsUpdated} updated.`);
      reload();
    } catch (err) {
      report(err instanceof ApiError ? err.message : "Import failed.", false);
    } finally {
      setBusy(null);
    }
  }

  async function saveConfig(satelliteId: string) {
    const persistence = Number((document.getElementById(`persistence-${satelliteId}`) as HTMLInputElement).value);
    const severity = Number((document.getElementById(`severity-${satelliteId}`) as HTMLInputElement).value);
    setBusy(`config-${satelliteId}`);
    try {
      const updated = await api.updateConfig(satelliteId, persistence, severity);
      setConfigs((prev) => ({ ...prev, [satelliteId]: updated }));
      report(`Saved monitoring config for ${satelliteId}.`);
    } catch (err) {
      report(err instanceof ApiError ? err.message : "Save failed.", false);
    } finally {
      setBusy(null);
    }
  }

  async function toggleSession(satelliteId: string, running: boolean, modelId: string) {
    setBusy(`session-${satelliteId}`);
    try {
      if (running) {
        await api.stopSession(satelliteId);
        report(`Stopped monitoring ${satelliteId}.`);
      } else {
        await api.startSession(satelliteId, modelId);
        report(`Started monitoring ${satelliteId}.`);
      }
      setTimeout(reload, 300); // let the session registry settle before refetching
    } catch (err) {
      report(err instanceof ApiError ? err.message : "Could not change the session.", false);
    } finally {
      setBusy(null);
    }
  }

  if (userError) {
    return (
      <p id="adminError" className="p-6">
        {userError}
      </p>
    );
  }
  if (!user) return <p id="loading" className="p-6 text-muted-foreground">Loading…</p>;

  const sessionById = new Map(sessions.map((s) => [s.satelliteId, s]));
  const defaultModel = models.find((m) => m.modelType !== "placeholder")?.modelId ?? models[0]?.modelId ?? "MDL-LSTM-100-80";

  return (
    <>
      <PageHeader
        title="Administration"
        titleId="adminTitle"
        description="Start and stop telemetry replay per satellite, tune its alerting thresholds, and manage the dataset and models."
      />
      <div className="flex flex-col gap-4 p-6">
        {message && (
          <p id="adminMessage" className="sr-only" aria-live="polite">
            {message}
          </p>
        )}

        <Panel
          title="Monitoring"
          actions={
            <span className="num text-[12px] text-muted-foreground">
              Model {defaultModel} · replay at 1 window/s
            </span>
          }
        >
          <div className="overflow-x-auto">
            <Table id="satellitesTable">
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">Satellite</TableHead>
                  <TableHead>Session</TableHead>
                  <TableHead>Persistence N</TableHead>
                  <TableHead>Severity threshold</TableHead>
                  <TableHead className="pr-4 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {satellites.map((s) => {
                  const config = configs[s.satelliteId];
                  const session = sessionById.get(s.satelliteId);
                  const running = !!session?.running;
                  return (
                    <TableRow key={s.satelliteId} id={`admin-sat-${s.satelliteId}`}>
                      <TableCell className="pl-4">
                        <span className="font-medium">{s.name}</span>
                        <span className="num ml-2 text-[12px] text-muted-foreground">{s.satelliteId}</span>
                      </TableCell>
                      <TableCell id={`session-status-${s.satelliteId}`}>
                        <SessionCell session={session} />
                      </TableCell>
                      <TableCell>
                        <Input
                          key={`p-${config?.configId}-${config?.persistenceThreshold}`}
                          id={`persistence-${s.satelliteId}`}
                          type="number"
                          min={1}
                          defaultValue={config?.persistenceThreshold ?? 3}
                          aria-label={`Persistence N for ${s.name}`}
                          className="num h-8 w-20"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          key={`s-${config?.configId}-${config?.severityThreshold}`}
                          id={`severity-${s.satelliteId}`}
                          type="number"
                          step={0.05}
                          min={0.01}
                          max={1}
                          defaultValue={config?.severityThreshold ?? 0.5}
                          aria-label={`Severity threshold for ${s.name}`}
                          className="num h-8 w-24"
                        />
                      </TableCell>
                      <TableCell className="pr-4">
                        <div className="flex justify-end gap-2">
                          <Button
                            id={`save-config-${s.satelliteId}`}
                            variant="ghost"
                            size="sm"
                            disabled={busy !== null}
                            onClick={() => saveConfig(s.satelliteId)}
                          >
                            Save
                          </Button>
                          <Button
                            id={`session-toggle-${s.satelliteId}`}
                            variant={running ? "outline" : "default"}
                            size="sm"
                            className="w-20"
                            disabled={busy !== null}
                            onClick={() => toggleSession(s.satelliteId, running, defaultModel)}
                          >
                            {running ? <StopIcon weight="fill" /> : <PlayIcon weight="fill" />}
                            {running ? "Stop" : "Start"}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          {sessions.some((s) => !s.running) && (
            <ul className="border-t px-4 py-3 text-[12px] text-[color:var(--risk-critical)]">
              {sessions
                .filter((s) => !s.running)
                .map((s) => (
                  <li key={s.satelliteId}>
                    {s.satelliteId}: {s.lastError ?? "stopped unexpectedly"}
                  </li>
                ))}
            </ul>
          )}
        </Panel>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <Panel title="Models">
            <div className="overflow-x-auto">
              <Table id="modelsTable">
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-4">Model</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Threshold</TableHead>
                    <TableHead>Trained (UTC)</TableHead>
                    <TableHead className="pr-4 text-right">Channels</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m) => (
                    <TableRow key={m.modelId}>
                      <TableCell className="num pl-4">{m.modelId}</TableCell>
                      <TableCell>{m.modelType}</TableCell>
                      <TableCell className="num text-right">{m.threshold}</TableCell>
                      <TableCell className="num text-muted-foreground">{formatUtc(m.trainedAt, false)}</TableCell>
                      <TableCell className="num pr-4 text-right">{m.channelsTrained}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Panel>

          <Panel title="Dataset" bodyClassName="flex flex-col gap-3 p-4">
            <p className="text-[13px] leading-relaxed text-muted-foreground">
              Registers the NASA SMAP/MSL channels from <code className="num">data/</code> in the database (REQ-1). Safe to
              re-run; existing channels are updated, not duplicated.
            </p>
            <Button id="importDatasetBtn" variant="outline" onClick={importDataset} disabled={busy !== null} className="self-start">
              <DatabaseIcon />
              {busy === "import" ? "Importing…" : "Import SMAP/MSL dataset"}
            </Button>
          </Panel>
        </div>
      </div>
    </>
  );
}
