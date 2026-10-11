"""MonitoringSession orchestrator: wires 1.0 Ingest -> 2.0 Detect -> 3.0 Explain
-> lifecycle, and writes DETECTION/ATTRIBUTION/ALERT rows (REQ-7, REQ-8,
REQ-9, REQ-18). One instance per monitored satellite.

Episode handling (ARCHITECTURE.md 5.3): the first Confirmed window of a run
of consecutive anomalous windows raises a new Alert. Later Confirmed windows
in the same run are still logged as their own Detection (REQ-18 logs every
one), and attributed, but they escalate the existing open alert's risk_level
(only upward: an alert's displayed severity never drops mid-episode) instead
of creating a duplicate. The episode is "forgotten" (not force-resolved -
Acknowledged -> Resolved stays a human action, Exp 5 assumption 5) once
`persistence_n` consecutive Normal windows have passed, so the next anomaly
starts a fresh alert.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertStatus, Attribution, Channel, Detection, DetectionOutcome, new_id
from app.pipeline.explain.attribution import attribute
from app.pipeline.explain.severity import compute_severity
from app.pipeline.import_dataset import channel_pk
from app.pipeline.ingest import ReplaySource
from app.pipeline.lifecycle import DetectionLifecycle, OutcomeKind
from app.pipeline.types import ChannelScores, SessionCounters, TelemetryWindow

logger = logging.getLogger(__name__)


@dataclass
class MonitoringSession:
    """Replays one satellite's windows through a detector, explain stage and lifecycle.

    `db_factory` is called once per window write so each write happens on its
    own short-lived Session, since this runs inside an asyncio task rather
    than a request's scoped session.
    """

    satellite_id: str
    model_id: str
    detector: object  # app.pipeline.detect.Detector-shaped (duck-typed to avoid importing torch here)
    source: ReplaySource
    db_factory: Callable[[], Session]
    persistence_n: int = 1
    severity_threshold: float = 0.5
    counters: SessionCounters = field(default_factory=SessionCounters)
    lifecycle: DetectionLifecycle = field(init=False)
    _stop: bool = field(default=False, init=False)
    _open_alert_id: str | None = field(default=None, init=False)
    _normal_streak: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.lifecycle = DetectionLifecycle(persistence_n=self.persistence_n)

    def stop(self) -> None:
        self._stop = True

    def _write_attributions(self, db: Session, detection_id: str, scores: ChannelScores) -> None:
        ranked = attribute(scores)
        if not ranked:
            return  # no channel stood out: left as "unknown" (no ATTRIBUTION rows), Exp 5 assumption 6
        candidate_pks = {channel_pk(chan_id): chan_id for chan_id, _ in ranked}
        existing = set(db.scalars(select(Channel.channel_id).where(Channel.channel_id.in_(candidate_pks))))
        for chan_id, contribution in ranked:
            pk = channel_pk(chan_id)
            if pk not in existing:
                continue  # the channel hasn't been imported (REQ-1); skip rather than crash the session
            db.add(
                Attribution(
                    attribution_id=new_id("ATB"),
                    detection_id=detection_id,
                    channel_id=pk,
                    contribution_score=contribution,
                )
            )

    def _process_window(self, window: TelemetryWindow) -> None:
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

        if result.kind == OutcomeKind.SKIPPED:
            return
        if result.kind == OutcomeKind.NORMAL:
            self.counters.normal += 1
            self._normal_streak += 1
            if self._open_alert_id is not None and self._normal_streak >= self.persistence_n:
                self._open_alert_id = None  # episode forgotten; the alert itself is untouched
            return

        self._normal_streak = 0
        self.counters.detections += 1
        is_suppressed = result.kind == OutcomeKind.SUPPRESSED
        outcome = DetectionOutcome.SUPPRESSED if is_suppressed else DetectionOutcome.CONFIRMED
        severity_level, risk_level = compute_severity(
            scores.satellite_score, result.persistence_count, self.severity_threshold
        )

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
                self._write_attributions(db, detection_id, scores)
                if self._open_alert_id is None:
                    alert_id = new_id("ALT")
                    db.add(
                        Alert(
                            alert_id=alert_id,
                            detection_id=detection_id,
                            risk_level=risk_level,
                            created_at=window.timestamp,
                            status=AlertStatus.ALERT_RAISED,
                        )
                    )
                    self._open_alert_id = alert_id
                else:
                    open_alert = db.get(Alert, self._open_alert_id)
                    if open_alert is not None and risk_level > open_alert.risk_level:
                        open_alert.risk_level = risk_level
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
