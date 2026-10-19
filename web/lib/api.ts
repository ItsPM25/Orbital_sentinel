// Typed client for the backend API (ARCHITECTURE.md section 7). Every call goes
// through the same-origin /api/* Next.js rewrite, so no base URL is needed.
import type { AlertView, DetectionView } from "./entities";
import type { TleEntry } from "./sgp4";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export interface User {
  userId: string;
  firstName: string;
  lastName: string;
  role: "Analyst" | "Administrator" | "Evaluator";
  email: string;
}

export interface Satellite {
  satelliteId: string;
  name: string;
  noradId: number | null;
  currentStatus: string;
  isProxy: boolean;
  riskLevel: number | null;
  verdict: "Anomalous" | "Nominal";
  severityLevel: string | null;
}

export interface AttributedChannel {
  channelId: string;
  channelName: string;
  contributionScore: number;
}

export interface Channel {
  channelId: string;
  channelName: string;
  unit: string | null;
}

export interface SatelliteHealth {
  satelliteId: string;
  satelliteName: string;
  verdict: "Anomalous" | "Nominal";
  riskLevel: number | null;
  severityLevel: string | null;
  anomalyScore: number | null;
  detectionId: string | null;
  detectedAt: string | null;
  attributedChannels: AttributedChannel[];
  isProxy: boolean;
  telemetrySource: string | null;
}

export interface AnomalyRange {
  start: number;
  end: number;
  detectionId: string;
}

export interface TelemetrySeries {
  satelliteId: string;
  channelId: string;
  channelName: string;
  unit: string | null;
  totalPoints: number;
  points: number[];
  pointIndices: number[];
  anomalyRanges: AnomalyRange[];
  isProxy: boolean;
}

export interface SatelliteRanking {
  satelliteId: string;
  satelliteName: string;
  riskLevel: number | null;
  severityLevel: string | null;
  status: string | null;
  alertId: string | null;
  lastDetectionAt: string | null;
}

export interface MonitoringConfig {
  configId: string;
  satelliteId: string;
  setByUserId: string;
  persistenceThreshold: number;
  severityThreshold: number;
  updatedAt: string;
  isActive: boolean;
}

export interface DetectionModel {
  modelId: string;
  modelName: string;
  modelType: string;
  threshold: number;
  trainedAt: string | null;
  channelsTrained: number;
}

export interface SessionStatus {
  satelliteId: string;
  modelId: string;
  running: boolean;
  counters: Record<string, number> | null;
  lastError?: string | null;
}

export interface EvaluationMetrics {
  available: boolean;
  modelId: string | null;
  persistence: "on" | "off" | null;
  channelsEvaluated: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  pointFpr: number | null;
  message: string | null;
}

export const api = {
  me: () => request<User>("/api/me"),
  logout: () => request<{ ok: boolean }>("/api/logout", { method: "POST" }),

  satellites: () => request<Satellite[]>("/api/satellites"),
  satelliteHealth: (id: string) => request<SatelliteHealth>(`/api/satellites/${id}/health`),
  satelliteChannels: (id: string) => request<Channel[]>(`/api/satellites/${id}/channels`),
  satelliteTelemetry: (id: string, channel: string, from?: number, to?: number) => {
    const params = new URLSearchParams({ channel });
    if (from !== undefined) params.set("from", String(from));
    if (to !== undefined) params.set("to", String(to));
    return request<TelemetrySeries>(`/api/satellites/${id}/telemetry?${params}`);
  },

  alerts: () => request<AlertView[]>("/api/alerts"),
  acknowledgeAlert: (id: string) => request<AlertView>(`/api/alerts/${id}/acknowledge`, { method: "POST" }),

  detections: (params?: { satelliteId?: string; outcome?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.satelliteId) qs.set("satelliteId", params.satelliteId);
    if (params?.outcome) qs.set("outcome", params.outcome);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<DetectionView[]>(`/api/detections${suffix}`);
  },

  ranking: () => request<SatelliteRanking[]>("/api/ranking"),

  evaluationMetrics: (modelId?: string, persistence?: "on" | "off") => {
    const qs = new URLSearchParams();
    if (modelId) qs.set("modelId", modelId);
    if (persistence) qs.set("persistence", persistence);
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<EvaluationMetrics>(`/api/evaluation/metrics${suffix}`);
  },

  // Admin
  startSession: (satelliteId: string, modelId?: string) =>
    request<SessionStatus>("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ satelliteId, ...(modelId ? { modelId } : {}) }),
    }),
  stopSession: (satelliteId: string) => request<{ ok: boolean }>(`/api/sessions/${satelliteId}`, { method: "DELETE" }),
  listSessions: () => request<SessionStatus[]>("/api/sessions"),

  getConfig: (satelliteId: string) => request<MonitoringConfig>(`/api/admin/config/${satelliteId}`),
  updateConfig: (satelliteId: string, persistenceThreshold: number, severityThreshold: number) =>
    request<MonitoringConfig>(`/api/admin/config/${satelliteId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persistenceThreshold, severityThreshold }),
    }),
  importDataset: (includeReadings = false) =>
    request<{ channelsCreated: number; channelsUpdated: number; channels: number }>("/api/admin/datasets/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ includeReadings }),
    }),
  listModels: () => request<DetectionModel[]>("/api/admin/models"),

  // Phase 5 — TLE feed (REQ-12)
  tle: () => request<TleEntry[]>("/api/tle"),
};
