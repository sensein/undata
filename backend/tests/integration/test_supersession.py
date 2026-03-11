"""Full supersession lifecycle integration tests — T079 (Polish Phase 8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def source_id(client: AsyncClient, curator_token: str) -> str:
    headers = {"Authorization": f"Bearer {curator_token}"}
    resp = await client.post(
        "/api/v1/sources",
        json={"name": "supersede-test-src", "format": "bids", "content_hash": "sup-hash"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_element_supersession_lifecycle(client: AsyncClient, curator_token: str, source_id: str):
    """Element A superseded by A'; A has superseded_by set; A' has new distinct URI."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    # Create element A (temperature in Celsius)
    el_a_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "temperature_celsius",
            "data_type": "float",
            "source_id": source_id,
            "source_local_id": "temp_c",
            "semantic_graph": {
                "entities": [],
                "property": {"label": "temperature", "type": "physical"},
                "unit": {"label": "degree Celsius", "symbol": "°C"},
                "relations": [],
            },
        },
        headers=headers,
    )
    assert el_a_resp.status_code == 201
    el_a = el_a_resp.json()
    el_a_id = el_a["id"]
    el_a_uri = el_a["uri"]

    # Supersede A with A' (temperature in Fahrenheit)
    supersede_resp = await client.post(
        f"/api/v1/elements/{el_a_id}/supersede",
        json={
            "supersede_reason": "Switching to Fahrenheit for US compliance",
            "new_element_data": {
                "name": "temperature_fahrenheit",
                "data_type": "float",
                "source_id": source_id,
                "source_local_id": "temp_f",
                "semantic_graph": {
                    "entities": [],
                    "property": {"label": "temperature", "type": "physical"},
                    "unit": {"label": "degree Fahrenheit", "symbol": "°F"},
                    "relations": [],
                },
            },
        },
        headers=headers,
    )
    assert supersede_resp.status_code == 201
    result = supersede_resp.json()

    # A' has new distinct URI
    el_a_prime = result["new_element"]
    assert el_a_prime["uri"] != el_a_uri
    assert "/elements/" in el_a_prime["uri"]

    # A has superseded_by set
    superseded = result["superseded_element"]
    assert superseded["superseded_by"] is not None
    assert superseded["deleted_at"] is not None


@pytest.mark.asyncio
async def test_element_default_list_excludes_superseded(client: AsyncClient, curator_token: str, source_id: str):
    """GET /elements default excludes superseded elements."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    # Create and supersede an element
    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "old_weight", "data_type": "float", "source_id": source_id, "source_local_id": "old_wt"},
        headers=headers,
    )
    assert el_resp.status_code == 201
    old_id = el_resp.json()["id"]

    await client.post(
        f"/api/v1/elements/{old_id}/supersede",
        json={
            "supersede_reason": "Updated measurement",
            "new_element_data": {
                "name": "new_weight",
                "data_type": "float",
                "source_id": source_id,
                "source_local_id": "new_wt",
            },
        },
        headers=headers,
    )

    # Default list should not include old element
    list_resp = await client.get("/api/v1/elements", params={"source_id": source_id})
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert old_id not in ids


@pytest.mark.asyncio
async def test_element_list_include_superseded_flag(client: AsyncClient, curator_token: str, source_id: str):
    """GET /elements?include_superseded=true includes superseded elements with superseded_by."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "old_height", "data_type": "float", "source_id": source_id, "source_local_id": "old_ht"},
        headers=headers,
    )
    assert el_resp.status_code == 201
    old_id = el_resp.json()["id"]

    await client.post(
        f"/api/v1/elements/{old_id}/supersede",
        json={
            "supersede_reason": "Updated",
            "new_element_data": {
                "name": "new_height",
                "data_type": "float",
                "source_id": source_id,
                "source_local_id": "new_ht",
            },
        },
        headers=headers,
    )

    # With include_superseded=true, old element should appear
    list_resp = await client.get(
        "/api/v1/elements",
        params={"source_id": source_id, "include_superseded": "true"},
    )
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert old_id in ids


@pytest.mark.asyncio
async def test_double_supersession_returns_409(client: AsyncClient, curator_token: str, source_id: str):
    """Attempting to supersede an already-superseded element returns 409."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "dup_sup_el", "data_type": "string", "source_id": source_id, "source_local_id": "dup_s"},
        headers=headers,
    )
    assert el_resp.status_code == 201
    el_id = el_resp.json()["id"]

    payload = {
        "supersede_reason": "First supersession",
        "new_element_data": {
            "name": "dup_sup_el_v2",
            "data_type": "string",
            "source_id": source_id,
            "source_local_id": "dup_s2",
        },
    }

    resp1 = await client.post(f"/api/v1/elements/{el_id}/supersede", json=payload, headers=headers)
    assert resp1.status_code == 201

    # Second supersession of same element should fail
    payload2 = {
        "supersede_reason": "Second supersession",
        "new_element_data": {
            "name": "dup_sup_el_v3",
            "data_type": "string",
            "source_id": source_id,
            "source_local_id": "dup_s3",
        },
    }
    resp2 = await client.post(f"/api/v1/elements/{el_id}/supersede", json=payload2, headers=headers)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_schema_supersession_lifecycle(client: AsyncClient, curator_token: str, source_id: str):
    """Schema S superseded by S'; S has superseded_by; S' has new distinct URI."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    el_resp = await client.post(
        "/api/v1/elements",
        json={"name": "schema_sup_el", "data_type": "float", "source_id": source_id, "source_local_id": "sch_el"},
        headers=headers,
    )
    assert el_resp.status_code == 201
    el_id = el_resp.json()["id"]

    schema_resp = await client.post(
        "/api/v1/schemas",
        json={"name": "OldSchema", "elements": [{"element_id": el_id, "position": 0}]},
        headers=headers,
    )
    assert schema_resp.status_code == 201
    schema_id = schema_resp.json()["id"]
    schema_uri = schema_resp.json()["uri"]

    supersede_resp = await client.post(
        f"/api/v1/schemas/{schema_id}/supersede",
        json={
            "supersede_reason": "Schema updated",
            "new_schema_data": {
                "name": "NewSchema",
                "elements": [{"element_id": el_id, "position": 0}],
            },
        },
        headers=headers,
    )
    assert supersede_resp.status_code == 201
    result = supersede_resp.json()

    new_schema = result["new_schema"]
    assert new_schema["uri"] != schema_uri

    superseded = result["superseded_schema"]
    assert superseded["superseded_by"] is not None
    assert superseded["deleted_at"] is not None
