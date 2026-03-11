"""Failing contract tests for POST/GET /schemas — must fail before implementation (TDD).

Tests:
- POST /schemas with 3 valid element_ids → 200 + linkml_yaml
- POST /schemas with unknown id → 422 + unknown_ids in detail
- POST /schemas with 51 elements → 202 + job_id
- GET /schemas/{id} → stored schema
- GET /schemas/{id}/versions → list
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.main import app
from src.services.backend_client import get_backend_client


@pytest.mark.asyncio
async def test_post_schemas_sync_returns_linkml_yaml(client):
    """POST /schemas with ≤50 elements returns 200 with linkml_yaml."""
    element_ids = [str(uuid.uuid4()) for _ in range(3)]

    with patch("src.api.v1.schemas.SchemaBuilder") as MockBuilder:
        mock_result = AsyncMock()
        mock_result.linkml_yaml = "id: TestSchema\nname: TestSchema\n"
        mock_result.linkml_jsonld = "{}"
        mock_result.name = "TestSchema"
        mock_result.version = "2026.03.0"
        mock_result.schema_id = None

        instance = MockBuilder.return_value
        instance.build = AsyncMock(return_value=mock_result)

        with patch("src.api.v1.schemas.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/schemas",
                json={
                    "name": "TestSchema",
                    "version": "2026.03.0",
                    "classes": [{"name": "MyClass", "element_ids": element_ids}],
                    "save": False,
                },
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "linkml_yaml" in data
    assert data["linkml_yaml"]


@pytest.mark.asyncio
async def test_post_schemas_unknown_ids_returns_422(client):
    """POST /schemas with unknown element ID returns 422 with unknown_ids in detail."""

    with patch("src.api.v1.schemas.SchemaBuilder") as MockBuilder:
        instance = MockBuilder.return_value
        instance.build = AsyncMock(side_effect=ValueError("unknown_ids: ['nonexistent']"))
        with patch("src.api.v1.schemas.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/schemas",
                json={
                    "name": "BadSchema",
                    "version": "2026.03.0",
                    "classes": [{"name": "MyClass", "element_ids": ["nonexistent"]}],
                    "save": False,
                },
            )

    assert resp.status_code == 422, resp.text
    data = resp.json()
    assert "unknown_ids" in str(data).lower() or "detail" in data


@pytest.mark.asyncio
async def test_post_schemas_large_request_returns_202(client):
    """POST /schemas with >50 elements returns 202 + job_id."""
    element_ids = [str(uuid.uuid4()) for _ in range(51)]

    with patch("src.api.v1.schemas.build_schema_task") as mock_task:
        mock_task.delay.return_value.id = "test-job-id"
        with patch("src.api.v1.schemas.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/schemas",
                json={
                    "name": "LargeSchema",
                    "version": "2026.03.0",
                    "classes": [{"name": "BigClass", "element_ids": element_ids}],
                    "save": False,
                },
            )

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_get_schema_by_id(client):
    """GET /schemas/{id} returns the stored schema."""
    schema_id = str(uuid.uuid4())

    mock_client = AsyncMock()
    mock_client.get_schema.return_value = {
        "id": schema_id,
        "name": "TestSchema",
        "version": "2026.03.0",
        "linkml_yaml": "id: TestSchema\n",
        "status": "published",
    }
    app.dependency_overrides[get_backend_client] = lambda: mock_client
    try:
        resp = await client.get(f"/schemas/{schema_id}")
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == schema_id


@pytest.mark.asyncio
async def test_get_schema_versions(client):
    """GET /schemas/{id}/versions returns a list."""
    schema_id = str(uuid.uuid4())

    mock_client = AsyncMock()
    mock_client.get_schema.return_value = {
        "id": schema_id,
        "name": "TestSchema",
        "version": "2026.03.0",
        "linkml_yaml": "id: TestSchema\n",
        "status": "published",
    }
    app.dependency_overrides[get_backend_client] = lambda: mock_client
    try:
        resp = await client.get(f"/schemas/{schema_id}/versions")
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
