"""In-process registry of running MonitoringSessions.

One asyncio task per monitored satellite (ARCHITECTURE.md 6.2). A single
FastAPI process is enough at this project's scale, so this is a plain
module-level dict rather than a broker.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.db import SessionLocal
from app.core.settings import settings
from app.models import Satellite
from app.pipeline.ingest import ReplaySource
from app.pipeline.session import MonitoringSession


@dataclass
class RunningSession:
    satellite_id: str
    model_id: str
    session: MonitoringSession
    task: asyncio.Task


_running: dict[str, RunningSession] = {}


class SessionAlreadyRunning(Exception):
    pass


class NoTrainedChannels(Exception):
    pass


def is_running(satellite_id: str) -> bool:
    return satellite_id in _running


def counters(satellite_id: str):
    entry = _running.get(satellite_id)
    return entry.session.counters if entry else None


def list_running() -> list[str]:
    return sorted(_running)


def _build_detector(model_id: str, chan_ids: list[str]):
    # Imported lazily: constructing an LstmDetector imports torch, which the
    # plain API tests should not need to have installed.
    from app.pipeline.detect import LstmDetector

    return LstmDetector(settings.models_dir / model_id, chan_ids)


async def start_session(satellite_id: str, model_id: str, speed: float | None = None) -> MonitoringSession:
    """speed: windows per second to simulate real-time pacing; None replays as fast as possible."""
    if satellite_id in _running:
        raise SessionAlreadyRunning(satellite_id)

    from app.pipeline.import_dataset import channel_ids_for_satellite

    with SessionLocal() as db:
        if db.get(Satellite, satellite_id) is None:
            raise ValueError(f"Unknown satellite {satellite_id}")
        chan_ids = channel_ids_for_satellite(db, satellite_id)
    if not chan_ids:
        raise NoTrainedChannels(satellite_id)

    loop = asyncio.get_running_loop()
    detector = await loop.run_in_executor(None, _build_detector, model_id, chan_ids)
    if not detector.chan_ids:
        raise NoTrainedChannels(satellite_id)

    source = ReplaySource(satellite_id, detector.chan_ids, settings.data_dir)
    session = MonitoringSession(
        satellite_id=satellite_id,
        model_id=model_id,
        detector=detector,
        source=source,
        db_factory=SessionLocal,
    )
    task = asyncio.create_task(session.run_async(), name=f"monitor-{satellite_id}")
    _running[satellite_id] = RunningSession(satellite_id, model_id, session, task)

    def _cleanup(_task: asyncio.Task) -> None:
        _running.pop(satellite_id, None)

    task.add_done_callback(_cleanup)
    return session


async def stop_session(satellite_id: str) -> bool:
    entry = _running.get(satellite_id)
    if entry is None:
        return False
    entry.session.stop()
    try:
        await asyncio.wait_for(entry.task, timeout=5)
    except (TimeoutError, asyncio.CancelledError):
        entry.task.cancel()
    _running.pop(satellite_id, None)
    return True
