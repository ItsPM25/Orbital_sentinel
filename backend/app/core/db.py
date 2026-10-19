from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.settings import settings


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores datetimes as UTC and always returns timezone-aware values.

    SQLite drops timezone info, so naive values read back are tagged as UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_engine(url: str, **kwargs) -> Engine:
    is_sqlite = url.startswith("sqlite")
    if is_sqlite:
        # timeout: how long a writer waits for SQLite's lock before failing with
        # "database is locked" (default 5s). Monitoring sessions and API requests
        # write concurrently, so give short overlapping writes room to queue.
        kwargs.setdefault("connect_args", {"check_same_thread": False, "timeout": 15})
    engine = create_engine(url, **kwargs)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # WAL lets the dashboard read while monitoring sessions write.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
