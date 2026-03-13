"""Shared pytest fixtures for the Schema Backend test suite."""

from __future__ import annotations

import hashlib
import os
import secrets
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.session import Base
from src.models.db import APIKey, UserProfile, UserRole

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://undata:undata@localhost:5432/undata_test",
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Run Alembic migrations once for the entire test session.

    Runs alembic in a subprocess to avoid asyncio.run() conflicts with the
    pytest-asyncio event loop — each process has its own event loop state.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"url={TEST_DATABASE_URL}", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "SQLALCHEMY_URL": TEST_DATABASE_URL},
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed:\n{result.stdout}\n{result.stderr}"
        )


@pytest.fixture(scope="session", autouse=True)
def setup_app_state():
    """Initialize app.state for tests.

    ASGITransport does not trigger the FastAPI lifespan, so app.state.unit_service
    is never set automatically. This fixture ensures it is available for all tests.
    """
    from src.core.config import settings
    from src.main import app
    from src.services.units import UnitResolutionService

    if not hasattr(app.state, "unit_service") or app.state.unit_service is None:
        app.state.unit_service = UnitResolutionService(ttl_path=settings.qudt_ttl_path)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def seed_undata_source():
    """Seed the canonical undata SchemaSource row (idempotent).

    The lifespan is not triggered by ASGITransport so we replicate the seed
    logic here once per test session.
    """
    from src.main import _seed_undata_source

    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(eng, expire_on_commit=False)
    async with SessionLocal() as session:
        async with session.begin():
            await _seed_undata_source(session)
    await eng.dispose()


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession that rolls back after each test.

    Creates a fresh engine per test to avoid asyncpg event-loop conflicts:
    asyncpg connections are bound to the event loop they were created in,
    and pytest-asyncio creates a new event loop per function by default.
    """
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(eng, expire_on_commit=False)
    async with SessionLocal() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()
    await eng.dispose()


# ---------------------------------------------------------------------------
# App / HTTP client fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx.AsyncClient wired to the FastAPI test app."""
    from src.db.session import get_db
    from src.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def mock_admin_user(db_session: AsyncSession) -> UserProfile:
    """Create an admin UserProfile in the test DB."""
    user = UserProfile(
        external_sub="admin-sub",
        external_iss="https://test.issuer",
        email="admin@test.local",
        display_name="Test Admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(user_id=user.id, role="admin")
    db_session.add(role)
    await db_session.flush()

    return user


@pytest_asyncio.fixture()
async def mock_curator_user(db_session: AsyncSession) -> UserProfile:
    """Create a curator UserProfile in the test DB."""
    user = UserProfile(
        external_sub="curator-sub",
        external_iss="https://test.issuer",
        email="curator@test.local",
        display_name="Test Curator",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(user_id=user.id, role="curator")
    db_session.add(role)
    await db_session.flush()

    return user


@pytest_asyncio.fixture()
async def mock_viewer_user(db_session: AsyncSession) -> UserProfile:
    """Create a viewer UserProfile in the test DB."""
    user = UserProfile(
        external_sub="viewer-sub",
        external_iss="https://test.issuer",
        email="viewer@test.local",
        display_name="Test Viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    role = UserRole(user_id=user.id, role="viewer")
    db_session.add(role)
    await db_session.flush()

    return user


# ---------------------------------------------------------------------------
# Token fixtures
# ---------------------------------------------------------------------------


def _issue_token(user: UserProfile) -> tuple[str, APIKey]:
    """Create a raw token and APIKey ORM object (not persisted)."""
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    key = APIKey(
        user_id=user.id,
        token_hash=token_hash,
        label="test-token",
    )
    return raw_token, key


@pytest_asyncio.fixture()
async def curator_token(db_session: AsyncSession, mock_curator_user: UserProfile) -> str:
    """Return a valid Bearer token for the curator user."""
    raw_token, key = _issue_token(mock_curator_user)
    db_session.add(key)
    await db_session.flush()
    return raw_token


@pytest_asyncio.fixture()
async def viewer_token(db_session: AsyncSession, mock_viewer_user: UserProfile) -> str:
    """Return a valid Bearer token for the viewer user."""
    raw_token, key = _issue_token(mock_viewer_user)
    db_session.add(key)
    await db_session.flush()
    return raw_token
