"""Test fixtures for backend tests.

Each test gets a fresh engine + session to avoid event loop conflicts.
Tables are created at the start and cleaned between tests.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Override DATABASE_URL for tests BEFORE importing app modules
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://undata:undata@localhost:5432/undata_test",
)

from src.db.session import Base  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    """Per-test async session with fresh engine.

    Creates engine per test to avoid event-loop-binding issues with asyncpg.
    Creates tables, yields session, truncates tables, disposes engine.
    """
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)

    # Create tables
    async with engine.begin() as conn:
        from src.db import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)

    # Yield session
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    # Truncate all tables for isolation
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    await engine.dispose()
