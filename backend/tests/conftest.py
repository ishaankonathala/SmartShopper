"""Shared pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Product, ShopperDNA, ShoppingHistory, UserProfile  # noqa: F401
from app.services.seed import seed_products


@pytest.fixture()
def engine():
    """In-memory SQLite engine with FK enforcement enabled."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _fk(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine):
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine) -> TestClient:
    """Provide a TestClient wired to an in-memory SQLite database."""
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_client(client: TestClient, engine) -> TestClient:
    """API client with the demo catalogue already seeded."""
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        seed_products(session)
    finally:
        session.close()
    return client


@pytest.fixture()
def sample_profile_payload() -> dict:
    return {
        "name": "Ishaan",
        "email": "ishaan@example.com",
        "max_budget": 6500,
        "min_budget": 1000,
        "preferred_categories": ["Headphones"],
        "preferred_brands": ["SonyDemo"],
        "disliked_attributes": ["bulky"],
    }
