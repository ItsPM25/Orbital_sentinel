import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db, make_engine
from app.main import app
from app.seed import seed_all
from app.services import events

ANALYST = ("analyst@orbitalsentinel.test", "sentinel123")
ADMIN = ("admin@orbitalsentinel.test", "admin123")
EVALUATOR = ("evaluator@orbitalsentinel.test", "evaluator123")


@pytest.fixture(autouse=True)
def _clean_event_bus():
    # events._loop and ._subscribers are module-level globals (app/services/events.py);
    # without this, a loop bound or a subscriber left by one test (or the `client`
    # fixture's own lifespan startup) can leak into an unrelated later test.
    events._subscribers.clear()
    events._loop = None
    yield
    events._subscribers.clear()
    events._loop = None


@pytest.fixture()
def db_session():
    # One shared in-memory database per test.
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        seed_all(session)
        yield session
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, credentials: tuple[str, str]):
    email, password = credentials
    return client.post("/api/login", json={"email": email, "password": password})
