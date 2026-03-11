"""Contract tests for POST /diff.

Tests:
- POST /diff known source+target → 200 SchemaDiff with correct coverage field
- POST /diff identical schemas → 200 with all lists empty and coverage=FULL
- POST /diff unknown source schema → 404
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.main import app
from src.models import SchemaDiff
from src.services.backend_client import BackendClientError, get_backend_client

SOURCE_ID = str(uuid.uuid4())
TARGET_ID = str(uuid.uuid4())


@pytest.mark.asyncio
async def test_diff_known_schemas_returns_200(client):
    """POST /diff with valid schemas returns 200 with SchemaDiff."""
    diff_result = SchemaDiff(
        source_schema_id=SOURCE_ID,
        target_schema_id=TARGET_ID,
        coverage="PARTIAL",
        added=[{"element_id": str(uuid.uuid4()), "name": "new_field", "schema_id": TARGET_ID}],
        removed=[],
        renamed=[],
        type_changed=[],
        constraint_changed=[],
        description_changed=[],
        draft_pathway=None,
    )

    mock_client = AsyncMock()
    mock_client.get_schema.return_value = {"id": SOURCE_ID}
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.diff.SchemaDiffer") as MockDiffer:
            instance = MockDiffer.return_value
            instance.diff = AsyncMock(return_value=diff_result)

            resp = await client.post(
                "/diff",
                json={
                    "source_schema_id": SOURCE_ID,
                    "target_schema_id": TARGET_ID,
                },
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "coverage" in data
    assert "added" in data


@pytest.mark.asyncio
async def test_diff_identical_schemas_returns_full_coverage(client):
    """POST /diff on identical schemas returns 200 with empty diffs and coverage=FULL."""
    diff_result = SchemaDiff(
        source_schema_id=SOURCE_ID,
        target_schema_id=TARGET_ID,
        coverage="FULL",
        added=[],
        removed=[],
        renamed=[],
        type_changed=[],
        constraint_changed=[],
        description_changed=[],
        draft_pathway=None,
    )

    mock_client = AsyncMock()
    mock_client.get_schema.return_value = {"id": SOURCE_ID}
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.diff.SchemaDiffer") as MockDiffer:
            instance = MockDiffer.return_value
            instance.diff = AsyncMock(return_value=diff_result)

            resp = await client.post(
                "/diff",
                json={
                    "source_schema_id": SOURCE_ID,
                    "target_schema_id": SOURCE_ID,  # same schema
                },
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["coverage"] == "FULL"
    assert data["added"] == []
    assert data["removed"] == []


@pytest.mark.asyncio
async def test_diff_unknown_schema_returns_404(client):
    """POST /diff where source schema does not exist returns 404."""
    mock_client = AsyncMock()
    mock_client.get_schema.side_effect = BackendClientError(404, "Not found")
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        resp = await client.post(
            "/diff",
            json={
                "source_schema_id": str(uuid.uuid4()),
                "target_schema_id": str(uuid.uuid4()),
            },
        )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 404, resp.text
