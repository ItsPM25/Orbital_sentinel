// Entity types traceable to the ER diagram (Experiment 4) and the
// detection-lifecycle state diagram (Experiment 5). ER attribute names are
// kept, converted from snake_case to camelCase.

export type AlertStatus = "AlertRaised" | "Acknowledged"; // states from the state diagram
export type SeverityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface Satellite {
  satelliteId: string; // satellite_id (PK)
  name: string;
  noradId: number;
  currentStatus: string;
}

export interface Detection {
  detectionId: string; // detection_id (PK)
  satelliteId: string; // FK -> SATELLITE
  modelId: string; // FK -> DETECTION_MODEL
  timestamp: string;
  anomalyScore: number;
  isAnomaly: boolean; // derived: score >= threshold
  severityLevel: SeverityLevel; // derived: score & persistence
  persistenceCount: number;
}

export interface Alert {
  alertId: string; // alert_id (PK)
  detectionId: string; // FK -> DETECTION
  riskLevel: number; // risk_level, 1-10 (higher = worse)
  createdAt: string; // created_at
  acknowledgedBy: string | null; // FK -> USER (optional)
  acknowledgedAt: string | null;
  status: AlertStatus;
}

export interface User {
  userId: string; // user_id (PK)
  firstName: string;
  lastName: string;
  role: "Analyst" | "Administrator" | "Evaluator";
  email: string;
  password: string; // mock only, no real auth provider
}

// Alert joined with its Detection and Satellite, as served by GET /api/alerts.
export interface AlertView extends Alert {
  satelliteId: string;
  satelliteName: string;
  riskLabel: SeverityLevel;
  severityLevel: SeverityLevel;
  anomalyScore: number;
}
