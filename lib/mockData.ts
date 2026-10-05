import type { Alert, Detection, Satellite, User } from "./entities";

export const satellites: Satellite[] = [
  { satelliteId: "SAT-001", name: "SMAP", noradId: 40376, currentStatus: "Monitored" },
  { satelliteId: "SAT-002", name: "Aqua", noradId: 27424, currentStatus: "Monitored" },
  { satelliteId: "SAT-003", name: "Terra", noradId: 25994, currentStatus: "Monitored" },
  { satelliteId: "SAT-004", name: "Landsat 9", noradId: 49260, currentStatus: "Monitored" },
  { satelliteId: "SAT-005", name: "Sentinel-2A", noradId: 40697, currentStatus: "Monitored" },
];

export const detections: Detection[] = [
  { detectionId: "DET-101", satelliteId: "SAT-001", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T08:12:00Z", anomalyScore: 0.97, isAnomaly: true, severityLevel: "CRITICAL", persistenceCount: 9 },
  { detectionId: "DET-102", satelliteId: "SAT-002", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T08:30:00Z", anomalyScore: 0.81, isAnomaly: true, severityLevel: "HIGH", persistenceCount: 6 },
  { detectionId: "DET-103", satelliteId: "SAT-003", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T09:05:00Z", anomalyScore: 0.55, isAnomaly: true, severityLevel: "MEDIUM", persistenceCount: 4 },
  { detectionId: "DET-104", satelliteId: "SAT-004", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T09:40:00Z", anomalyScore: 0.91, isAnomaly: true, severityLevel: "CRITICAL", persistenceCount: 8 },
  { detectionId: "DET-105", satelliteId: "SAT-005", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T10:02:00Z", anomalyScore: 0.38, isAnomaly: true, severityLevel: "LOW", persistenceCount: 3 },
  { detectionId: "DET-106", satelliteId: "SAT-001", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T10:20:00Z", anomalyScore: 0.72, isAnomaly: true, severityLevel: "HIGH", persistenceCount: 5 },
  { detectionId: "DET-107", satelliteId: "SAT-003", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T11:15:00Z", anomalyScore: 0.47, isAnomaly: true, severityLevel: "MEDIUM", persistenceCount: 3 },
  { detectionId: "DET-108", satelliteId: "SAT-002", modelId: "MDL-LSTM-1", timestamp: "2026-09-23T11:48:00Z", anomalyScore: 0.33, isAnomaly: true, severityLevel: "LOW", persistenceCount: 3 },
];

export const initialAlerts: Alert[] = [
  { alertId: "ALT-001", detectionId: "DET-101", riskLevel: 10, createdAt: "2026-09-23T08:12:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-002", detectionId: "DET-102", riskLevel: 7, createdAt: "2026-09-23T08:30:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-003", detectionId: "DET-103", riskLevel: 5, createdAt: "2026-09-23T09:05:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-004", detectionId: "DET-104", riskLevel: 9, createdAt: "2026-09-23T09:40:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-005", detectionId: "DET-105", riskLevel: 2, createdAt: "2026-09-23T10:02:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-006", detectionId: "DET-106", riskLevel: 7, createdAt: "2026-09-23T10:20:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-007", detectionId: "DET-107", riskLevel: 4, createdAt: "2026-09-23T11:15:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
  { alertId: "ALT-008", detectionId: "DET-108", riskLevel: 3, createdAt: "2026-09-23T11:48:30Z", acknowledgedBy: null, acknowledgedAt: null, status: "AlertRaised" },
];

export const users: User[] = [
  { userId: "USR-001", firstName: "Test", lastName: "Analyst", role: "Analyst", email: "analyst@orbitalsentinel.test", password: "sentinel123" },
];
