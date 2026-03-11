"""Downstream contract tests — T082 (Polish Phase 8).

Tests that downstream consumers can rely on stable API contracts.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_elements_filtered_by_source_id(client: AsyncClient, curator_token: str):
    """GET /elements?source_id=<id> returns only elements belonging to that source."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    # Create a dedicated source
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "downstream-src-a", "format": "bids", "content_hash": "down-a"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    # Create element in that source
    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "ds_element", "data_type": "float", "source_id": source_id, "source_local_id": "ds_el"},
        headers=headers,
    )
    assert el_resp.status_code == 201

    # Create a different source and element
    src2_resp = await client.post(
        "/api/v1/sources",
        json={"name": "downstream-src-b", "format": "dandi", "content_hash": "down-b"},
        headers=headers,
    )
    assert src2_resp.status_code == 201
    source_id_b = src2_resp.json()["id"]

    await client.post(
        "/api/v1/elements",
        json={"name": "ds_other", "data_type": "string", "source_id": source_id_b, "source_local_id": "ds_other"},
        headers=headers,
    )

    # Filter by source A
    list_resp = await client.get("/api/v1/elements", params={"source_id": source_id})
    assert list_resp.status_code == 200
    data = list_resp.json()
    for item in data["items"]:
        assert item["source"]["id"] == source_id


@pytest.mark.asyncio
async def test_get_mappings_filtered_by_target_element_id(client: AsyncClient, curator_token: str):
    """GET /mappings?target_element_id=<id> returns MappingFunctionResponse items with output_element_id matching."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "downstream-map-src", "format": "bids", "content_hash": "down-map"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el_a = await client.post(
        "/api/v1/elements",
        json={"name": "ds_input", "data_type": "float", "source_id": source_id, "source_local_id": "ds_in"},
        headers=headers,
    )
    assert el_a.status_code == 201

    el_b = await client.post(
        "/api/v1/elements",
        json={"name": "ds_output", "data_type": "float", "source_id": source_id, "source_local_id": "ds_out"},
        headers=headers,
    )
    assert el_b.status_code == 201
    target_id = el_b.json()["id"]

    map_resp = await client.post(
        "/api/v1/mappings",
        json={
            "function_type": "identity",
            "output_element_id": target_id,
            "expression_type": "identity",
            "input_element_ids": [{"element_id": el_a.json()["id"], "position": 0}],
        },
        headers=headers,
    )
    assert map_resp.status_code == 201

    list_resp = await client.get("/api/v1/mappings", params={"target_element_id": target_id})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["output_element_id"] == target_id
        assert "uri" in item
        assert "function_type" in item


@pytest.mark.asyncio
async def test_get_sources_name_filter_returns_undata(client: AsyncClient):
    """GET /sources?name=undata returns exactly one source with format=canonical."""
    resp = await client.get("/api/v1/sources", params={"name": "undata"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "undata"
    assert data["items"][0]["format"] == "canonical"
