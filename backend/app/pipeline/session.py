"""MonitoringSession orchestrator: wires 1.0 Ingest -> 2.0 Detect -> lifecycle
and writes DETECTIONs (REQ-18). One instance per monitored satellite.

Phase 2 uses persistence_n = 1 (pass-through: every above-threshold window is
Confirmed and raises an Alert immediately). Phase 3 raises this to a real
persistence filter and merges confirmed windows in the same episode into one
escalating alert instead of one alert per window (ARCHITECTURE.md 5.3).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Alert, AlertStatus, Detection, DetectionOutcome, new_id
from app.pipeline.ingest import ReplaySource
from app.pipeline.lifecycle import DetectionLifecycle, OutcomeKind
from app.pipeline.types import SessionCounters, TelemetryWindow

logger = logging.getLogger(__name__)


# Placeholder severity bands (anomaly score -> label/risk) until Phase 3's real
# severity-scoring (REQ-9) replaces them with score x persistence.
def placeholder_severity(score: float) -> tuple[str, int]:
    if score >= 2.0:
        return "CRITICAL", 10
    if score >= 1.5:
        return "HIGH", 7
    if score >= 1.2:
        return "MEDIUM", 5
    return "LOW", 3


@dataclass
class MonitoringSession:
    """Replays one satellite's windows through a detector and the lifecycle.

    `db_factory` is called once per window batch so each write happens on its
    own short-lived Session, since this runs inside an asyncio task rather
    than a request's scoped session.
    """

    satellite_id: str
    model_id: str
    detector: object  # app.pipeline.detect.Detector-shaped (duck-typed to avoid importing torch here)
    source: ReplaySource
    db_factory: Callable[[], Session]
    persistence_n: int = 1
    counters: SessionCounters = field(default_factory=SessionCounters)
    lifecycle: DetectionLifecycle = field(init=False)
    _stop: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.lifecycle = DetectionLifecycle(persistence_n=self.persistence_n)

    def stop(self) -> None:
        self._stop = True

    def _process_window(self, window: TelemetryWindow) -> None:
        import time

        started = time.perf_counter()
        scores = self.detector.score(window)
        score_ms = (time.perf_counter() - started) * 1000
        self.counters.last_score_ms = score_ms
        self.counters.max_score_ms = max(self.counters.max_score_ms, score_ms)
        self.counters.windows += 1

        if window.malformed:
            self.counters.malformed += 1
            self.counters.interpolated = window.interpolated

        result = self.lifecycle.process_window(
            malformed=window.malformed, score=scores.satellite_score, threshold=scores.threshold
        )

        if result.kind == OutcomeKind.NORMAL:
            self.counters.normal += 1
            return
        if result.kind == OutcomeKind.SKIPPED:
            return

        # Anomalous (Suppressed or Confirmed, REQ-8 in Phase 3; here N=1 so always Confirmed).
        self.counters.detections += 1
        is_suppressed = result.kind == OutcomeKind.SUPPRESSED
        outcome = DetectionOutcome.SUPPRESSED if is_suppressed else DetectionOutcome.CONFIRMED
        severity_level, risk_level = placeholder_severity(scores.satellite_score)

        db = self.db_factory()
        try:
            detection_id = new_id("DET")
            db.add(
                Detection(
                    detection_id=detection_id,
                    satellite_id=self.satellite_id,
                    model_id=self.model_id,
                    timestamp=window.timestamp,
                    anomaly_score=scores.satellite_score,
                    severity_level=severity_level,
                    persistence_count=result.persistence_count,
                    window_start=window.start_index,
                    window_end=window.end_index,
                    outcome=outcome,
                )
            )
            if outcome == DetectionOutcome.CONFIRMED:
                db.add(
                    Alert(
                        alert_id=new_id("ALT"),
                        detection_id=detection_id,
                        risk_level=risk_level,
                        created_at=window.timestamp,
                        status=AlertStatus.ALERT_RAISED,
                    )
                )
            db.commit()
        finally:
            db.close()

    def run(self) -> SessionCounters:
        """Synchronous replay to completion (used directly by tests and the CLI)."""
        for window in self.source.windows():
            if self._stop:
                break
            self._process_window(window)
        return self.counters

    async def run_async(self, yield_every: int = 1) -> SessionCounters:
        """Same replay, yielding control to the event loop between windows."""
        for i, window in enumerate(self.source.windows()):
            if self._stop:
                break
            await asyncio.get_running_loop().run_in_executor(None, self._process_window, window)
            if i % yield_every == 0:
                await asyncio.sleep(0)
        return self.counters


def iter_detection_ids(db: Session, satellite_id: str) -> Iterator[str]:
    """Convenience for tests: detection ids written for a satellite, in order."""
    rows = (
        db.query(Detection.detection_id)
        .filter(Detection.satellite_id == satellite_id)
        .order_by(Detection.timestamp)
    )
    return (row[0] for row in rows)
