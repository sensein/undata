"""Failing contract tests for /pathways endpoints — must fail before implementation (TDD).

Tests:
- POST /pathways valid → 201 + inverse_pathway_id auto-set
- POST /pathways unknown mapping_id → 422
- GET /pathways?source_schema_id=X → list
- GET /pathways/{id} → full steps resolved
- POST /pathways/compose valid → 200 composed pathway
- POST /pathways/compose schema mismatch → 422
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.main import app
from src.services.backend_client import get_backend_client

SOURCE_ID = str(uuid.uuid4())
TARGET_ID = str(uuid.uuid4())
MAPPING_ID = str(uuid.uuid4())
PATHWAY_ID = str(uuid.uuid4())


def _make_mapping(mapping_id: str, inverse_id: str | None = None) -> dict:
    return {
        "id": mapping_id,
        "function_type": "identity",
        "current_version": {
            "expression": "input_0",
            "expression_type": "identity",
            "inverse_mapping_id": inverse_id,
        },
    }


def _make_pathway(
    source: str = SOURCE_ID,
    target: str = TARGET_ID,
    steps: list | None = None,
    status: str = "active",
    inverse_id: str | None = None,
) -> dict:
    return {
        "id": PATHWAY_ID,
        "name": "BIDS-to-DANDI",
        "source_schema_id": source,
        "target_schema_id": target,
        "direction": "forward",
        "status": status,
        "steps": steps or [{"position": 0, "mapping_id": MAPPING_ID}],
        "inverse_pathway_id": inverse_id,
        "version_num": 0,
    }


@pytest.mark.asyncio
async def test_post_pathways_valid_returns_201(client):
    """POST /pathways with valid payload returns 201 with inverse_pathway_id set if derivable."""
    mock_client = AsyncMock()
    mock_client.create_pathway.return_value = _make_pathway()
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.pathways.PathwayService") as MockSvc:
            instance = MockSvc.return_value
            instance.validate_steps = AsyncMock(return_value=None)
            instance.can_derive_inverse = AsyncMock(return_value=False)

            resp = await client.post(
                "/pathways",
                json={
                    "name": "BIDS-to-DANDI",
                    "source_schema_id": SOURCE_ID,
                    "target_schema_id": TARGET_ID,
                    "direction": "forward",
                    "steps": [{"position": 0, "mapping_id": MAPPING_ID}],
                },
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_post_pathways_unknown_mapping_id_returns_422(client):
    """POST /pathways with unknown mapping_id returns 422."""
    with patch("src.api.v1.pathways.PathwayService") as MockSvc:
        instance = MockSvc.return_value
        instance.validate_steps = AsyncMock(side_effect=ValueError("mapping_id 'bad-id' not found"))

        with patch("src.api.v1.pathways.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/pathways",
                json={
                    "name": "Bad Pathway",
                    "source_schema_id": SOURCE_ID,
                    "target_schema_id": TARGET_ID,
                    "direction": "forward",
                    "steps": [{"position": 0, "mapping_id": "bad-id"}],
                },
            )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_list_pathways_filter_by_source(client):
    """GET /pathways?source_schema_id=X returns a list."""
    mock_client = AsyncMock()
    mock_client.list_pathways.return_value = {
        "total": 1,
        "limit": 50,
        "offset": 0,
        "items": [_make_pathway()],
    }
    app.dependency_overrides[get_backend_client] = lambda: mock_client
    try:
        resp = await client.get(f"/pathways?source_schema_id={SOURCE_ID}")
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data or isinstance(data, list)


@pytest.mark.asyncio
async def test_get_pathway_by_id(client):
    """GET /pathways/{id} returns full pathway."""
    mock_client = AsyncMock()
    mock_client.get_pathway.return_value = _make_pathway()
    app.dependency_overrides[get_backend_client] = lambda: mock_client
    try:
        resp = await client.get(f"/pathways/{PATHWAY_ID}")
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == PATHWAY_ID


@pytest.mark.asyncio
async def test_compose_pathways_valid_returns_200(client):
    """POST /pathways/compose with valid A→B + B→C returns 200 composed pathway."""
    schema_a = str(uuid.uuid4())
    schema_c = str(uuid.uuid4())

    pathway_a_id = str(uuid.uuid4())
    pathway_b_id = str(uuid.uuid4())

    composed = {
        "name": "composed",
        "source_schema_id": schema_a,
        "target_schema_id": schema_c,
        "direction": "forward",
        "status": "active",
        "steps": [
            {"position": 0, "mapping_id": str(uuid.uuid4())},
            {"position": 1, "mapping_id": str(uuid.uuid4())},
        ],
        "inverse_pathway_id": None,
        "version_num": 0,
    }

    with patch("src.api.v1.pathways.PathwayService") as MockSvc:
        instance = MockSvc.return_value
        instance.compose = AsyncMock(return_value=composed)

        with patch("src.api.v1.pathways.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/pathways/compose",
                json={"pathway_a_id": pathway_a_id, "pathway_b_id": pathway_b_id},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["steps"]) == 2


@pytest.mark.asyncio
async def test_compose_pathways_schema_mismatch_returns_422(client):
    """POST /pathways/compose where A.target != B.source returns 422."""
    from src.services.pathway_service import CompositionError

    pathway_a_id = str(uuid.uuid4())
    pathway_b_id = str(uuid.uuid4())

    with patch("src.api.v1.pathways.PathwayService") as MockSvc:
        instance = MockSvc.return_value
        instance.compose = AsyncMock(side_effect=CompositionError("Target/source schema mismatch"))

        with patch("src.api.v1.pathways.get_backend_client") as mock_get_client:
            mock_get_client.return_value = AsyncMock()

            resp = await client.post(
                "/pathways/compose",
                json={"pathway_a_id": pathway_a_id, "pathway_b_id": pathway_b_id},
            )

    assert resp.status_code == 422, resp.text
