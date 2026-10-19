"""MonitoringSession: wiring detect -> lifecycle -> DB writes (REQ-18), without needing
a real dataset or a trained model (ScriptedDetector + a fake replay source)."""

from datetime import datetime, timezone

import numpy as np
import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, make_engine
from app.models import Alert, AlertStatus, Attribution, Channel, Detection, DetectionOutcome
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


def test_paced_replay_spaces_windows_instead_of_running_flat_out(session_factory):
    """A full-speed replay pins every CPU core until it ends; live monitoring is paced."""
    import asyncio
    import time

    def run(windows_per_second):
        windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(5)]
        session = MonitoringSession(
            satellite_id="SAT-001",
            model_id=MODEL_ID,
            detector=ScriptedDetector([0.1] * 5, threshold=1.0),
            source=FakeSource(windows),
            db_factory=session_factory,
        )
        started = time.perf_counter()
        counters = asyncio.run(session.run_async(windows_per_second))
        return time.perf_counter() - started, counters.windows

    paced, paced_windows = run(20.0)  # 5 windows at 20/s: about 0.25s
    flat_out, flat_windows = run(None)
    assert paced_windows == flat_windows == 5
    assert paced >= 0.24
    assert flat_out < paced


# --- Phase 3: episode escalation, attribution ---------------------------------------------


def test_second_confirmed_window_in_same_episode_escalates_not_duplicates(session_factory):
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(2)]
    detector = ScriptedDetector([1.2, 2.0], threshold=1.0)  # both anomalous, persistence_n=1
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    session.run()
    with session_factory() as db:
        detections = db.query(Detection).filter_by(satellite_id="SAT-001").all()
        alerts = db.query(Alert).all()
        assert len(detections) == 2  # every confirmed window is logged (REQ-18)
        assert len(alerts) == 1  # but only one alert for the episode
        assert alerts[0].risk_level > 1  # escalated by the second, stronger window


def test_alert_risk_level_never_decreases_within_an_episode(session_factory):
    # Window 0: score=5.0, persistence=1 -> risk_level 5. Window 1: score=1.2, persistence=2
    # (weaker but more persistent) -> risk_level 2 on its own. The alert must stay at 5.
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(2)]
    detector = ScriptedDetector([5.0, 1.2], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    session.run()
    with session_factory() as db:
        alerts = db.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].risk_level == 5  # not downgraded to window 1's own (lower) risk_level of 2


def test_episode_ends_after_persistence_n_normal_windows_then_a_new_alert_starts(session_factory):
    # persistence_n=2: windows 0-1 anomalous confirm episode 1 (w0 suppressed, w1 confirmed);
    # windows 2-3 normal end it (streak reaches 2); windows 4-5 anomalous confirm episode 2.
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(6)]
    detector = ScriptedDetector([2.0, 2.0, 0.1, 0.1, 2.0, 2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
        persistence_n=2,
    )
    session.run()
    with session_factory() as db:
        alerts = db.query(Alert).order_by(Alert.created_at).all()
        assert len(alerts) == 2  # the episode ended and a new one started
        detections = db.query(Detection).filter_by(satellite_id="SAT-001").all()
        assert len(detections) == 4  # w0,w1,w4,w5 all logged (2 suppressed, 2 confirmed)


def test_episode_stays_open_through_a_single_normal_blip_below_persistence_n(session_factory):
    # persistence_n=3: w0-2 anomalous confirm episode 1 (consecutive reaches 3 at w2).
    # w3 is a single normal blip (streak=1, below persistence_n=3: episode NOT ended).
    # w4-6 anomalous re-confirm (consecutive resets at w3, reaches 3 again at w6) and,
    # because the episode never ended, escalate the SAME alert instead of opening a new one.
    windows = [fake_window("SAT-001", i, i * 70, i * 70 + 70) for i in range(7)]
    detector = ScriptedDetector([2.0, 2.0, 2.0, 0.1, 2.0, 2.0, 2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
        persistence_n=3,
    )
    session.run()
    with session_factory() as db:
        assert db.query(Alert).count() == 1  # still the same episode


def test_attribution_rows_written_when_the_channel_is_imported(session_factory):
    with session_factory() as db:
        db.add(
            Channel(
                channel_id="CHN-Z-1", satellite_id="SAT-001", channel_name="Z-1", dataset_chan_id="Z-1"
            )
        )
        db.commit()

    windows = [fake_window("SAT-001", 0, 100, 170)]
    detector = ScriptedDetector([2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    session.run()
    with session_factory() as db:
        detection = db.query(Detection).filter_by(satellite_id="SAT-001").one()
        attributions = db.query(Attribution).filter_by(detection_id=detection.detection_id).all()
        assert len(attributions) == 1
        assert attributions[0].channel_id == "CHN-Z-1"
        assert attributions[0].contribution_score == 1.0


def test_attribution_skipped_without_crashing_when_channel_not_imported(session_factory):
    """REQ-18/REQ-7: a detection is still logged even if dataset import hasn't happened yet;
    attribution is simply left empty (unknown) rather than failing the write."""
    windows = [fake_window("SAT-001", 0, 100, 170)]
    detector = ScriptedDetector([2.0], threshold=1.0)
    session = MonitoringSession(
        satellite_id="SAT-001",
        model_id=MODEL_ID,
        detector=detector,
        source=FakeSource(windows),
        db_factory=session_factory,
    )
    session.run()
    with session_factory() as db:
        assert db.query(Detection).filter_by(satellite_id="SAT-001").count() == 1
        assert db.query(Attribution).count() == 0
        assert db.query(Alert).count() == 1  # the alert is still raised (Exp 5 assumption 6)
