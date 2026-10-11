"""services/sessions.py: the real start_session()/stop_session(), not the API-mocked
layer (tests/test_sessions_api.py). Found via manual testing: starting a session with
a model_id that has no DETECTION_MODEL row yet (e.g. training hasn't registered it)
used to crash the replay task mid-run with a FOREIGN KEY integrity error instead of
failing fast - this is the regression test for that fix.
"""

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, make_engine
from app.seed import seed_reference
from app.services import sessions as session_service


@pytest.fixture()
def isolated_db(monkeypatch):
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        seed_reference(db)  # satellites + users + MDL-DEMO-1, no MDL-LSTM-100-80
    monkeypatch.setattr(session_service, "SessionLocal", factory)
    yield factory
    engine.dispose()


async def test_start_session_rejects_an_unregistered_model_before_touching_the_detector(isolated_db):
    with pytest.raises(session_service.ModelNotRegistered):
        await session_service.start_session("SAT-001", "MDL-NOT-TRAINED-YET")
    assert not session_service.is_running("SAT-001")


async def test_start_session_rejects_an_unknown_satellite(isolated_db):
    with pytest.raises(ValueError):
        await session_service.start_session("SAT-999", "MDL-DEMO-1")


async def test_start_session_with_a_registered_model_but_no_channels_raises_no_trained_channels(isolated_db):
    # SAT-001 exists and MDL-DEMO-1 is registered, but no CHANNEL rows were imported.
    with pytest.raises(session_service.NoTrainedChannels):
        await session_service.start_session("SAT-001", "MDL-DEMO-1")


async def test_a_crashed_task_is_removed_from_running_and_recorded_as_an_error(isolated_db):
    """Regression test for the real bug: a DB integrity error (or any other exception)
    raised inside MonitoringSession.run_async() used to vanish the session from
    /api/sessions with no trace. _on_task_done is the exact callback start_session()
    attaches to every session's task."""
    import asyncio

    async def boom():
        raise RuntimeError("synthetic crash for this test")

    task = asyncio.create_task(boom(), name="monitor-SAT-001")
    entry = session_service.RunningSession("SAT-001", "MDL-DEMO-1", object(), task)
    session_service._running["SAT-001"] = entry
    task.add_done_callback(lambda t: session_service._on_task_done("SAT-001", t))

    with pytest.raises(RuntimeError):
        await task
    await asyncio.sleep(0)  # let the done-callback run

    assert not session_service.is_running("SAT-001")
    assert "RuntimeError" in session_service.last_error("SAT-001")
    assert "SAT-001" in session_service.list_errored()


async def test_a_cancelled_task_is_removed_but_not_recorded_as_an_error(isolated_db):
    """stop_session() cancels the task on timeout; that is a normal stop, not a crash."""
    import asyncio

    async def runs_forever():
        await asyncio.sleep(10)

    task = asyncio.create_task(runs_forever(), name="monitor-SAT-002")
    entry = session_service.RunningSession("SAT-002", "MDL-DEMO-1", object(), task)
    session_service._running["SAT-002"] = entry
    task.add_done_callback(lambda t: session_service._on_task_done("SAT-002", t))

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert not session_service.is_running("SAT-002")
    assert session_service.last_error("SAT-002") is None
