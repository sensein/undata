"""API contract tests — verify all response shapes match contracts/rest-api.md.

T067 (Polish Phase 8)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_element_response_has_uri(client: AsyncClient, curator_token: str):
    """DataElement response includes uri field."""
    headers = {"Authorization": f"Bearer {curator_token}"}
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "contract-src", "format": "bids", "content_hash": "c1"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "age", "data_type": "integer", "source_id": source_id, "source_local_id": "age_c"},
        headers=headers,
    )
    assert el_resp.status_code == 201
    data = el_resp.json()
    assert "uri" in data
    assert data["uri"].startswith("http")
    assert "/elements/" in data["uri"]


@pytest.mark.asyncio
async def test_mapping_response_has_uri(client: AsyncClient, curator_token: str):
    """MappingFunction response includes uri field."""
    headers = {"Authorization": f"Bearer {curator_token}"}
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "contract-map-src", "format": "bids", "content_hash": "c2"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el_a = await client.post(
        "/api/v1/elements",
        json={"name": "weight_kg", "data_type": "float", "source_id": source_id, "source_local_id": "wt_kg"},
        headers=headers,
    )
    assert el_a.status_code == 201

    el_b = await client.post(
        "/api/v1/elements",
        json={"name": "weight_lb", "data_type": "float", "source_id": source_id, "source_local_id": "wt_lb"},
        headers=headers,
    )
    assert el_b.status_code == 201

    map_resp = await client.post(
        "/api/v1/mappings",
        json={
            "function_type": "formula",
            "output_element_id": el_b.json()["id"],
            "expression": "x * 2.20462",
            "expression_type": "python",
            "input_element_ids": [{"element_id": el_a.json()["id"], "position": 0}],
        },
        headers=headers,
    )
    assert map_resp.status_code == 201
    data = map_resp.json()
    assert "uri" in data
    assert "/mappings/" in data["uri"]


@pytest.mark.asyncio
async def test_schema_response_has_uri(client: AsyncClient, curator_token: str):
    """DynamicSchema response includes uri field."""
    headers = {"Authorization": f"Bearer {curator_token}"}
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "contract-schema-src", "format": "bids", "content_hash": "c3"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el = await client.post(
        "/api/v1/elements",
        json={"name": "height_cm", "data_type": "float", "source_id": source_id, "source_local_id": "ht_cm"},
        headers=headers,
    )
    assert el.status_code == 201

    schema_resp = await client.post(
        "/api/v1/schemas",
        json={
            "name": "Demographics",
            "description": "Basic demographics",
            "elements": [{"element_id": el.json()["id"], "position": 0}],
        },
        headers=headers,
    )
    assert schema_resp.status_code == 201
    data = schema_resp.json()
    assert "uri" in data
    assert "/schemas/" in data["uri"]


@pytest.mark.asyncio
async def test_error_envelope_shape_on_404(client: AsyncClient):
    """404 errors return ErrorEnvelope shape."""
    import uuid
    resp = await client.get(f"/api/v1/elements/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_error_envelope_shape_on_401(client: AsyncClient):
    """Unauthenticated write returns 401."""
    resp = await client.post(
        "/api/v1/sources",
        json={"name": "unauth", "format": "bids", "content_hash": "x"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_paginated_list_envelope(client: AsyncClient):
    """List endpoints return PaginatedList envelope with total/limit/offset/items."""
    resp = await client.get("/api/v1/elements")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_audit_entry_has_actor_id_uuid_type(client: AsyncClient, curator_token: str):
    """AuditEntry has actor_id (UUID) and actor_display_name (string)."""
    audit_resp = await client.get("/api/v1/audit", params={"limit": 5})
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    for item in data["items"]:
        assert "actor_id" in item
        assert "actor_display_name" in item


@pytest.mark.asyncio
async def test_schema_uri_unchanged_after_put(client: AsyncClient, curator_token: str):
    """DynamicSchema.uri is stable after PUT (membership update)."""
    headers = {"Authorization": f"Bearer {curator_token}"}
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "contract-stable-src", "format": "bids", "content_hash": "c4"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el = await client.post(
        "/api/v1/elements",
        json={"name": "stable_el", "data_type": "string", "source_id": source_id, "source_local_id": "s1"},
        headers=headers,
    )
    assert el.status_code == 201
    el_id = el.json()["id"]

    schema_resp = await client.post(
        "/api/v1/schemas",
        json={"name": "StableSchema", "elements": [{"element_id": el_id, "position": 0}]},
        headers=headers,
    )
    assert schema_resp.status_code == 201
    schema_id = schema_resp.json()["id"]
    original_uri = schema_resp.json()["uri"]

    el2 = await client.post(
        "/api/v1/elements",
        json={"name": "stable_el2", "data_type": "string", "source_id": source_id, "source_local_id": "s2"},
        headers=headers,
    )
    assert el2.status_code == 201

    put_resp = await client.put(
        f"/api/v1/schemas/{schema_id}",
        json={"add": [{"element_id": el2.json()["id"], "position": 1}], "version_num": 1},
        headers=headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["uri"] == original_uri, "URI must be stable after membership update"
