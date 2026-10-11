"""3.3 Severity scoring (REQ-9): severity_index = norm(score) x g(persistence),
mapped to a LOW/MEDIUM/HIGH/CRITICAL band and a 1-10 risk_level.

The risk_level bands (>=9 CRITICAL, >=6 HIGH, >=4 MEDIUM, else LOW) are the
canonical definition; app/schemas/alert.py imports risk_label() from here
rather than keeping its own copy, so the alert list and the detection log
always agree on what a given risk_level means.

ADR 003 records the chosen constants and why.
"""

from __future__ import annotations

from app.models import SeverityLevel

# A satellite score of SCORE_CAP or higher counts as maximally severe on its own.
SCORE_CAP = 3.0
# A detection confirmed by this many consecutive anomalous windows or more counts
# as maximally persistent on its own.
PERSISTENCE_SATURATE = 5


def risk_label(risk_level: int) -> SeverityLevel:
    if risk_level >= 9:
        return SeverityLevel.CRITICAL
    if risk_level >= 6:
        return SeverityLevel.HIGH
    if risk_level >= 4:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


def compute_severity(
    score: float,
    persistence_count: int,
    severity_threshold: float,
    score_cap: float = SCORE_CAP,
    persistence_saturate: int = PERSISTENCE_SATURATE,
) -> tuple[str, int]:
    """Returns (severity_level, risk_level) for a confirmed detection.

    `score` is the satellite score (smoothed error / dynamic threshold; > 1 is
    anomalous). `severity_threshold` is MONITORING_CONFIG's per-satellite
    sensitivity knob: a lower value makes the same raw severity reach a higher
    band sooner (the satellite escalates more readily).
    """
    norm_score = _clamp((score - 1.0) / max(score_cap - 1.0, 1e-9))
    norm_persistence = _clamp(persistence_count / max(persistence_saturate, 1))
    severity_index = norm_score * norm_persistence
    adjusted = _clamp(severity_index / max(severity_threshold, 1e-9))
    risk_level = max(1, min(10, round(1 + 9 * adjusted)))
    return risk_label(risk_level), risk_level


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
