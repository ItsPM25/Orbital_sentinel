"""MonitoringSession: wiring detect -> lifecycle -> DB writes (REQ-18), without needing
a real dataset or a trained model (ScriptedDetector + a fake replay source)."""

from datetime import datetime, timezone

import numpy as np
import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, make_engine
from app.models import Alert, AlertStatus, Detection, DetectionOutcome
from app.pipeline.detect import ScriptedDetector
from app.pipeline.session import MonitoringSession
from app.pipeline.types import TelemetryWindow
from app.seed import seed_reference

MODEL_ID = "MDL-DEMO-1"  # created by seed_reference()


@pytest.fixture()
def session_factory():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        seed_reference(db)
    yield factory
    engine.dispose()


def fake_window(satellite_id: str, i: int, start: int, end: int, malformed: bool = False) -> TelemetryWindow:
    return TelemetryWindow(
        satellite_id=satellite_id,
        start_index=start,
        end_index=end,
        history=100,
        arrays={"Z-1": np.zeros(end - start + 100, dtype=np.float32)},
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc).replace(microsecond=i),
        malformed=malformed,
    )


class FakeSource:
    def __init__(self, windows: list[TelemetryWindow]):
        self._windows = windows

    def windows(self):
        yield from self._windows


def test_normal_windows_produce_no_detection_rows(session_factory):
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(3)]
    detector = ScriptedDetector([0.1, 0.2, 0.3], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    counters = session.run()
    assert counters.windows == 3
    assert counters.normal == 3
    assert counters.detections == 0
    with session_factory() as db:
        assert db.query(Detection).count() == 0


def test_confirmed_window_writes_a_detection_and_an_alert(session_factory):
    windows = [fake_window("SAT-001", 0, 100, 170), fake_window("SAT-001", 1, 170, 240)]
    detector = ScriptedDetector([0.1, 2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
        persistence_n=1,
    )
    counters = session.run()
    assert counters.detections == 1
    with session_factory() as db:
        detections = db.query(Detection).filter_by(satellite_id="SAT-001").all()
        assert len(detections) == 1
        assert detections[0].outcome == DetectionOutcome.CONFIRMED
        assert detections[0].anomaly_score == 2.0
        alerts = db.query(Alert).filter_by(detection_id=detections[0].detection_id).all()
        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.ALERT_RAISED


def test_suppressed_window_writes_a_detection_but_no_alert(session_factory):
    """REQ-8 pass-through at N=1 never suppresses; this exercises persistence_n > 1 directly."""
    windows = [fake_window("SAT-001", 0, 100, 170)]
    detector = ScriptedDetector([2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
        persistence_n=3,  # needs 3 consecutive anomalous windows; this is only the 1st
    )
    session.run()
    with session_factory() as db:
        detections = db.query(Detection).all()
        assert len(detections) == 1
        assert detections[0].outcome == DetectionOutcome.SUPPRESSED
        assert db.query(Alert).count() == 0


def test_malformed_window_writes_no_detection_row(session_factory):
    windows = [fake_window("SAT-001", 0, 100, 170, malformed=True)]
    detector = ScriptedDetector([0.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    counters = session.run()
    assert counters.malformed == 1
    assert counters.detections == 0
    with session_factory() as db:
        assert db.query(Detection).count() == 0


def test_stop_halts_the_replay_before_it_finishes(session_factory):
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(10)]
    detector = ScriptedDetector([0.1] * 10, threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    session.stop()  # stop before any window is processed
    counters = session.run()
    assert counters.windows == 0


def test_window_scoring_is_well_under_one_second(session_factory):
    """Exit criterion: window scoring takes < 1s per satellite."""
    import time

    windows = [fake_window("SAT-001", 0, 100, 170)]
    detector = ScriptedDetector([0.1], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    started = time.perf_counter()
    session.run()
    assert time.perf_counter() - started < 1.0
    assert session.counters.last_score_ms < 1000
