"""In-process registry of running MonitoringSessions.

One asyncio task per monitored satellite (ARCHITECTURE.md 6.2). A single
FastAPI process is enough at this project's scale, so this is a plain
module-level dict rather than a broker.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.settings import settings
from app.models import DetectionModel, MonitoringConfig, Satellite
from app.pipeline.ingest import ReplaySource
from app.pipeline.session import MonitoringSession

logger = logging.getLogger(__name__)


@dataclass
class RunningSession:
    satellite_id: str
    model_id: str
    session: MonitoringSession
    task: asyncio.Task


_running: dict[str, RunningSession] = {}
# The most recent crash per satellite, kept after the task is removed from
# _running so GET /api/sessions can explain why a session is no longer there.
_last_error: dict[str, str] = {}


class SessionAlreadyRunning(Exception):
    pass


class NoTrainedChannels(Exception):
    pass


class ModelNotRegistered(Exception):
    """model_id has no DETECTION_MODEL row, e.g. training hasn't finished and
    registered it yet. Every DETECTION write is FK'd to this row, so failing
    fast here is much clearer than a mid-replay integrity error."""


def is_running(satellite_id: str) -> bool:
    return satellite_id in _running


def counters(satellite_id: str):
    entry = _running.get(satellite_id)
    return entry.session.counters if entry else None


def model_id(satellite_id: str) -> str | None:
    entry = _running.get(satellite_id)
    return entry.model_id if entry else None


def list_running() -> list[str]:
    return sorted(_running)


def last_error(satellite_id: str) -> str | None:
    return _last_error.get(satellite_id)


def list_errored() -> list[str]:
    return sorted(_last_error)


def _on_task_done(satellite_id: str, task: asyncio.Task) -> None:
    """Shared by every session's done-callback; a standalone function so it's testable
    on its own (closures captured inline aren't directly callable from a test)."""
    _running.pop(satellite_id, None)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception("MonitoringSession for %s stopped unexpectedly", satellite_id, exc_info=exc)
        _last_error[satellite_id] = f"{type(exc).__name__}: {exc}"


def _build_detector(model_id: str, chan_ids: list[str]):
    # Imported lazily: constructing an LstmDetector imports torch, which the
    # plain API tests should not need to have installed.
    import torch

    from app.pipeline.detect import LstmDetector

    torch.set_num_threads(settings.inference_threads)
    return LstmDetector(settings.models_dir / model_id, chan_ids)


async def start_session(satellite_id: str, model_id: str, speed: float | None = None) -> MonitoringSession:
    """speed: windows per second (defaults to settings.replay_windows_per_second); 0 replays flat out."""
    if satellite_id in _running:
        raise SessionAlreadyRunning(satellite_id)

    from app.pipeline.import_dataset import channel_ids_for_satellite

    with SessionLocal() as db:
        if db.get(Satellite, satellite_id) is None:
            raise ValueError(f"Unknown satellite {satellite_id}")
        if db.get(DetectionModel, model_id) is None:
            raise ModelNotRegistered(model_id)
        chan_ids = channel_ids_for_satellite(db, satellite_id)
        config = db.scalar(
            select(MonitoringConfig)
            .where(MonitoringConfig.satellite_id == satellite_id, MonitoringConfig.is_active)
            .order_by(MonitoringConfig.updated_at.desc())
        )
        persistence_n = config.persistence_threshold if config else 1
        severity_threshold = config.severity_threshold if config else 0.5
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
        persistence_n=persistence_n,
        severity_threshold=severity_threshold,
    )
    pace = settings.replay_windows_per_second if speed is None else speed
    task = asyncio.create_task(session.run_async(pace or None), name=f"monitor-{satellite_id}")
    _running[satellite_id] = RunningSession(satellite_id, model_id, session, task)
    _last_error.pop(satellite_id, None)
    task.add_done_callback(lambda t: _on_task_done(satellite_id, t))
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
