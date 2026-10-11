"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type DetectionModel, type MonitoringConfig, type Satellite, type SessionStatus } from "@/lib/api";
import { useUser } from "@/lib/useUser";

export default function AdminPage() {
  const { user, error: userError } = useUser(["Administrator"]);
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [models, setModels] = useState<DetectionModel[]>([]);
  const [sessions, setSessions] = useState<SessionStatus[]>([]);
  const [configs, setConfigs] = useState<Record<string, MonitoringConfig>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    if (!user) return;
    api.satellites().then(setSatellites).catch(() => {});
    api.listModels().then(setModels).catch(() => {});
    api.listSessions().then(setSessions).catch(() => {});
  }, [user]);

  useEffect(() => {
    reload();
  }, [reload]);

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
    setBusy(true);
    setMessage("");
    try {
      const result = await api.importDataset(false);
      setMessage(`Imported: ${result.channelsCreated} channel(s) created, ${result.channelsUpdated} updated.`);
      reload();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveConfig(satelliteId: string, persistenceThreshold: number, severityThreshold: number) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.updateConfig(satelliteId, persistenceThreshold, severityThreshold);
      setConfigs((prev) => ({ ...prev, [satelliteId]: updated }));
      setMessage(`Saved monitoring config for ${satelliteId}.`);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleSession(satelliteId: string, running: boolean, modelId: string) {
    setBusy(true);
    setMessage("");
    try {
      if (running) {
        await api.stopSession(satelliteId);
        setMessage(`Stopped monitoring ${satelliteId}.`);
      } else {
        await api.startSession(satelliteId, modelId);
        setMessage(`Started monitoring ${satelliteId}.`);
      }
      setTimeout(reload, 300); // let the session registry settle before refetching
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Could not change the session.");
    } finally {
      setBusy(false);
    }
  }

  if (userError) return <p id="adminError">{userError}</p>;
  if (!user) return <p id="loading">Loading...</p>;

  const runningIds = new Set(sessions.map((s) => s.satelliteId));
  const defaultModel = models[0]?.modelId ?? "MDL-LSTM-100-80";

  return (
    <main>
      <h1 id="adminTitle">Orbital Sentinel - Admin</h1>
      {message && <p id="adminMessage">{message}</p>}
      {busy && <p id="busyIndicator">Working...</p>}

      <h2>Dataset</h2>
      <button id="importDatasetBtn" onClick={importDataset} disabled={busy}>
        Import SMAP/MSL dataset
      </button>

      <h2>Models</h2>
      <table id="modelsTable" border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr><th>Model ID</th><th>Type</th><th>Threshold</th><th>Trained At</th><th>Channels Trained</th></tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.modelId}>
              <td>{m.modelId}</td>
              <td>{m.modelType}</td>
              <td>{m.threshold}</td>
              <td>{m.trainedAt ?? "-"}</td>
              <td>{m.channelsTrained}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Satellites &amp; Monitoring</h2>
      <table id="satellitesTable" border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Satellite</th>
            <th>Persistence N</th>
            <th>Severity Threshold</th>
            <th>Session</th>
          </tr>
        </thead>
        <tbody>
          {satellites.map((s) => {
            const config = configs[s.satelliteId];
            const running = runningIds.has(s.satelliteId);
            return (
              <tr key={s.satelliteId} id={`admin-sat-${s.satelliteId}`}>
                <td>{s.name} ({s.satelliteId})</td>
                <td>
                  <input
                    id={`persistence-${s.satelliteId}`}
                    type="number"
                    min={1}
                    defaultValue={config?.persistenceThreshold ?? 3}
                    style={{ width: 60 }}
                    onBlur={(e) => {
                      const sev = Number(
                        (document.getElementById(`severity-${s.satelliteId}`) as HTMLInputElement)?.value ?? 0.5
                      );
                      saveConfig(s.satelliteId, Number(e.target.value), sev);
                    }}
                  />
                </td>
                <td>
                  <input
                    id={`severity-${s.satelliteId}`}
                    type="number"
                    step={0.05}
                    min={0.01}
                    max={1}
                    defaultValue={config?.severityThreshold ?? 0.5}
                    style={{ width: 70 }}
                    onBlur={(e) => {
                      const persistence = Number(
                        (document.getElementById(`persistence-${s.satelliteId}`) as HTMLInputElement)?.value ?? 3
                      );
                      saveConfig(s.satelliteId, persistence, Number(e.target.value));
                    }}
                  />
                </td>
                <td>
                  <button
                    id={`session-toggle-${s.satelliteId}`}
                    disabled={busy}
                    onClick={() => toggleSession(s.satelliteId, running, defaultModel)}
                  >
                    {running ? "Stop" : "Start"}
                  </button>
                  <span id={`session-status-${s.satelliteId}`}> {running ? "running" : "stopped"}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </main>
  );
}
