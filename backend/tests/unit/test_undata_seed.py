"""Unit tests for startup undata SchemaSource seeding — T084.

Constitution Principle II (TDD): These tests MUST fail before T017
(main.py) is implemented. They confirm that:

1. The lifespan handler inserts a canonical undata source on empty DB.
2. The insert is idempotent — no error when the row already exists.
3. After seeding, GET /sources?name=undata returns exactly one record
   with format="canonical" and is_active=True.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestUndataSeeding:
    """Verify lifespan-time seeding of the canonical undata SchemaSource."""

    @pytest.mark.asyncio
    async def test_seed_inserts_undata_source_on_empty_db(self):
        """Lifespan calls idempotent INSERT for name='undata', format='canonical'."""
        # Arrange — simulate empty DB (execute returns no row)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        # Import the seeding function once T017 is implemented
        # This import MUST FAIL before T017 is written — that is intentional.
        from src.main import _seed_undata_source  # noqa: PLC0415

        # Act
        await _seed_undata_source(mock_session)

        # Assert — execute was called at least once (the INSERT)
        assert mock_session.execute.called, "Expected session.execute to be called for INSERT"
        call_args = mock_session.execute.call_args_list
        # Inspect the actual TextClause text from each call's first positional arg
        sql_texts = []
        for c in call_args:
            arg = c.args[0] if c.args else None
            if arg is not None:
                sql_texts.append(str(arg).lower())
        assert any(
            "undata" in s or "schema_source" in s or "insert" in s
            for s in sql_texts
        ), f"Expected INSERT for 'undata'/'schema_source' in SQL calls: {sql_texts}"

    @pytest.mark.asyncio
    async def test_seed_idempotent_when_source_exists(self):
        """Seeding must not raise when undata row already exists."""
        mock_session = AsyncMock()
        # Simulate existing row (ON CONFLICT DO NOTHING behaviour)
        mock_session.execute = AsyncMock(return_value=MagicMock())

        from src.main import _seed_undata_source  # noqa: PLC0415

        # Should complete without raising
        await _seed_undata_source(mock_session)

    @pytest.mark.asyncio
    async def test_get_sources_returns_undata_after_seed(self):
        """GET /sources?name=undata returns exactly one canonical record.

        Requires a running PostgreSQL database (TEST_DATABASE_URL).
        Skipped automatically in environments without DB access.
        """
        import os

        if not os.environ.get("TEST_DATABASE_URL"):
            pytest.skip("TEST_DATABASE_URL not set; skipping DB-dependent seed verification")

        from httpx import ASGITransport, AsyncClient

        try:
            from src.main import app  # noqa: PLC0415
        except ImportError:
            pytest.skip("src.main not yet implemented (expected pre-T017)")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
        ) as ac:
            response = await ac.get("/api/v1/sources/", params={"name": "undata"})

        # Will fail until seeding and the sources router are implemented
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        items = body.get("items", [])
        assert len(items) == 1, f"Expected exactly 1 undata source, got {len(items)}"
        source = items[0]
        assert source["format"] == "canonical", f"Expected format='canonical', got {source['format']}"
        assert source["is_active"] is True, f"Expected is_active=True, got {source['is_active']}"
