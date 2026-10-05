import type { Alert, AlertView, SeverityLevel, User } from "./entities";
import { detections, initialAlerts, satellites, users } from "./mockData";

export const SESSION_COOKIE = "os_session";

// In-memory state, kept on globalThis so it survives dev-server hot reloads.
const g = globalThis as unknown as { __osAlerts?: Alert[] };

function fresh(): Alert[] {
  return initialAlerts.map((a) => ({ ...a }));
}

function alerts(): Alert[] {
  if (!g.__osAlerts) g.__osAlerts = fresh();
  return g.__osAlerts;
}

export function reset(): void {
  g.__osAlerts = fresh();
}

function riskLabel(riskLevel: number): SeverityLevel {
  if (riskLevel >= 9) return "CRITICAL";
  if (riskLevel >= 6) return "HIGH";
  if (riskLevel >= 4) return "MEDIUM";
  return "LOW";
}

function toView(alert: Alert): AlertView {
  const detection = detections.find((d) => d.detectionId === alert.detectionId)!;
  const satellite = satellites.find((s) => s.satelliteId === detection.satelliteId)!;
  return {
    ...alert,
    satelliteId: satellite.satelliteId,
    satelliteName: satellite.name,
    riskLabel: riskLabel(alert.riskLevel),
    severityLevel: detection.severityLevel,
    anomalyScore: detection.anomalyScore,
  };
}

// Risk-ordered alert list (SRS REQ-16): highest risk first, then oldest first.
export function getRankedAlerts(): AlertView[] {
  return [...alerts()]
    .sort((a, b) => b.riskLevel - a.riskLevel || a.createdAt.localeCompare(b.createdAt))
    .map(toView);
}

// AlertRaised -> Acknowledged transition from the state diagram.
export function acknowledgeAlert(alertId: string, userId: string): AlertView | null {
  const alert = alerts().find((a) => a.alertId === alertId);
  if (!alert) return null;
  if (alert.status !== "Acknowledged") {
    alert.status = "Acknowledged";
    alert.acknowledgedBy = userId;
    alert.acknowledgedAt = new Date().toISOString();
  }
  return toView(alert);
}

export function authenticate(email: string, password: string): Omit<User, "password"> | null {
  const user = users.find((u) => u.email === email && u.password === password);
  if (!user) return null;
  const { password: _pw, ...safe } = user;
  return safe;
}
