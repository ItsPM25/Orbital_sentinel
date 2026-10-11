// Entity types traceable to the ER diagram (Experiment 4) and the
// detection-lifecycle state diagram (Experiment 5). ER attribute names are
// kept, converted from snake_case to camelCase.
//
// Phase 5 types (globe) are defined in lib/sgp4.ts and re-exported here for
// convenience.
export type { GeoPosition, TleEntry } from "./sgp4";

export type AlertStatus = "AlertRaised" | "Acknowledged" | "Resolved"; // states from the state diagram
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
  attributedChannel: string | null; // REQ-16/REQ-7: the top attributed channel, or null ("unknown")
}

// Detection joined with its Satellite, as served by GET /api/detections (REQ-18).
export interface DetectionView {
  detectionId: string;
  satelliteId: string;
  satelliteName: string;
  modelId: string;
  timestamp: string;
  anomalyScore: number;
  severityLevel: SeverityLevel | null;
  persistenceCount: number;
  outcome: "Suppressed" | "Confirmed" | null;
}
