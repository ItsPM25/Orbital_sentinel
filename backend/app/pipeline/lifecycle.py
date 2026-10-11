"""Exp 5 detection lifecycle: 14 states and 19 transitions (ARCHITECTURE.md §5.4).

Per-window processing runs Idle → … → AlertRaised, then hands off back to Idle
so the pipeline never waits for a human acknowledge. AlertRaised → Acknowledged
→ Resolved is driven on the ALERT row (and can be exercised here with wait_for_ack).

Phase 2 uses persistence N = 1 (pass-through). Phase 3 makes the filter real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    IDLE = "Idle"
    INGESTING = "Ingesting"
    DATA_ERROR = "DataError"
    SCORING = "Scoring"
    NORMAL = "Normal"
    ANOMALOUS = "Anomalous"
    FILTERING = "Filtering"
    SUPPRESSED = "Suppressed"
    CONFIRMED = "Confirmed"
    ATTRIBUTING = "Attributing"
    SCORING_SEVERITY = "ScoringSeverity"
    ALERT_RAISED = "AlertRaised"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"
    STOPPED = "Stopped"  # terminal [*] after monitoringStopped


class OutcomeKind(StrEnum):
    SKIPPED = "skipped"
    NORMAL = "normal"
    SUPPRESSED = "Suppressed"
    CONFIRMED = "Confirmed"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"
    STOPPED = "Stopped"


@dataclass(frozen=True)
class Transition:
    source: State
    dest: State
    event: str
    guard: str | None = None


@dataclass
class WindowResult:
    kind: OutcomeKind
    persistence_count: int
    transitions: list[Transition]
    state: State


@dataclass
class DetectionLifecycle:
    persistence_n: int = 1  # Phase 2: pass-through
    state: State = State.IDLE
    consecutive: int = 0
    log: list[Transition] = field(default_factory=list)

    def _go(self, dest: State, event: str, guard: str | None = None) -> Transition:
        transition = Transition(self.state, dest, event, guard)
        self.log.append(transition)
        self.state = dest
        return transition

    def process_window(
        self, *, malformed: bool, score: float, threshold: float, wait_for_ack: bool = False
    ) -> WindowResult:
        if self.state != State.IDLE:
            raise RuntimeError(f"process_window requires Idle, not {self.state}")
        start = len(self.log)
        self._go(State.INGESTING, "newWindowArrives")
        if malformed:
            self._go(State.DATA_ERROR, "validated", "dataMalformed")
            self._go(State.IDLE, "recovered")
            return WindowResult(OutcomeKind.SKIPPED, self.consecutive, self.log[start:], self.state)

        self._go(State.SCORING, "validated", "!dataMalformed")
        if score <= threshold:
            self.consecutive = 0
            self._go(State.NORMAL, "scored", "score ≤ threshold")
            self._go(State.IDLE, "windowComplete")
            return WindowResult(OutcomeKind.NORMAL, self.consecutive, self.log[start:], self.state)

        self._go(State.ANOMALOUS, "scored", "score > threshold")
        self.consecutive += 1
        self._go(State.FILTERING, "checkPersistence")
        if self.consecutive < self.persistence_n:
            self._go(State.SUPPRESSED, "evaluated", "count < N")
            self._go(State.IDLE, "logged")
            return WindowResult(OutcomeKind.SUPPRESSED, self.consecutive, self.log[start:], self.state)

        self._go(State.CONFIRMED, "evaluated", "count ≥ N")
        self._go(State.ATTRIBUTING, "confirmed")
        self._go(State.SCORING_SEVERITY, "channelsAttributed")
        self._go(State.ALERT_RAISED, "severityComputed")
        if wait_for_ack:
            return WindowResult(OutcomeKind.CONFIRMED, self.consecutive, self.log[start:], self.state)
        # Transition 19: hand the alert off; the window machine returns to Idle.
        self._go(State.IDLE, "handedOff")
        return WindowResult(OutcomeKind.CONFIRMED, self.consecutive, self.log[start:], self.state)

    def user_ack(self) -> WindowResult:
        if self.state != State.ALERT_RAISED:
            raise RuntimeError(f"userAck requires AlertRaised, not {self.state}")
        start = len(self.log)
        self._go(State.ACKNOWLEDGED, "userAck")
        return WindowResult(OutcomeKind.ACKNOWLEDGED, self.consecutive, self.log[start:], self.state)

    def resolve(self, monitoring_active: bool = True) -> WindowResult:
        if self.state != State.ACKNOWLEDGED:
            raise RuntimeError(f"resolve requires Acknowledged, not {self.state}")
        start = len(self.log)
        self._go(State.RESOLVED, "logDetection")
        if monitoring_active:
            self._go(State.IDLE, "monitoringActive", "monitoringActive")
            kind = OutcomeKind.RESOLVED
        else:
            self._go(State.STOPPED, "monitoringStopped", "satelliteDeactivated")
            kind = OutcomeKind.STOPPED
        return WindowResult(kind, self.consecutive, self.log[start:], self.state)
