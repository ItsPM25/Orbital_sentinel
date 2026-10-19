// Risk bands, shared by every view that colours by risk (REQ-14, REQ-16).
// Bands mirror risk_label() in backend/app/pipeline/explain/severity.py:
// >=9 CRITICAL, >=6 HIGH, >=4 MEDIUM, else LOW; no open alert = nominal.

export type RiskBand = "critical" | "high" | "medium" | "low" | "none";

export function riskBand(riskLevel: number | null | undefined): RiskBand {
  if (riskLevel == null) return "none";
  if (riskLevel >= 9) return "critical";
  if (riskLevel >= 6) return "high";
  if (riskLevel >= 4) return "medium";
  return "low";
}

export const BAND_LABEL: Record<RiskBand, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "Nominal",
};

/** CSS colour for DOM elements; follows the light/dark theme tokens. */
export function bandVar(band: RiskBand): string {
  return `var(--risk-${band})`;
}

/** Fixed colours for WebGL (three.js can't read CSS variables). The globe is always
 * drawn on a dark background, so these are the dark-theme values. */
export const BAND_HEX: Record<RiskBand, string> = {
  critical: "#f0645a",
  high: "#f08c3c",
  medium: "#e2bd45",
  low: "#6fbf86",
  none: "#9aa3ad",
};
