"""Contract tests for mapping function endpoints — T050.

Tests MUST FAIL before T060 (mappings router) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def two_elements(client, curator_token):
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"map-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    elements = []
    for i in range(4):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"map-el-{i}-{uuid4()}", "data_type": "integer", "source_id": source["id"]},
        )
        assert el_resp.status_code == 201
        elements.append(el_resp.json())

    return source, elements


class TestMappingsContract:
    async def test_post_mapping_returns_201_with_uri(self, client, curator_token, two_elements):
        """POST /mappings returns 201 MappingFunctionResponse with uri field."""
        _, elements = two_elements

        response = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "identity",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
                "sssom_predicate": "skos:exactMatch",
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "uri" in body
        assert body["uri"].startswith("http")
        assert "/mappings/" in body["uri"]

    async def test_circular_mapping_returns_409_with_cycle_path(self, client, curator_token, two_elements):
        """Circular registration returns 409 with cycle_path."""
        _, elements = two_elements

        # A→B
        resp1 = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "linear",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert resp1.status_code == 201

        # B→C
        resp2 = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "linear",
                "output_element_id": elements[2]["id"],
                "input_element_ids": [{"element_id": elements[1]["id"], "position": 0}],
            },
        )
        assert resp2.status_code == 201

        # C→A (creates cycle)
        resp3 = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "linear",
                "output_element_id": elements[0]["id"],
                "input_element_ids": [{"element_id": elements[2]["id"], "position": 0}],
            },
        )
        assert resp3.status_code == 409, f"Expected 409 for cycle, got {resp3.status_code}"
        body = resp3.json()
        assert "cycle_path" in str(body)

    async def test_unknown_element_ids_return_422(self, client, curator_token):
        """POST /mappings with unknown element IDs returns 422."""
        response = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "identity",
                "output_element_id": str(uuid4()),
                "input_element_ids": [{"element_id": str(uuid4()), "position": 0}],
            },
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    async def test_get_mappings_returns_filtered_list(self, client, curator_token, two_elements):
        """GET /mappings?source_element_id=X returns filtered list."""
        _, elements = two_elements

        await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "identity",
                "output_element_id": elements[3]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )

        list_resp = await client.get(
            "/api/v1/mappings",
            params={"source_element_id": elements[0]["id"]},
        )
        assert list_resp.status_code == 200

    async def test_unauthenticated_write_returns_401(self, client, two_elements):
        _, elements = two_elements
        response = await client.post(
            "/api/v1/mappings",
            json={
                "function_type": "identity",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert response.status_code == 401

    async def test_viewer_returns_403(self, client, viewer_token, two_elements):
        _, elements = two_elements
        response = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "function_type": "identity",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert response.status_code == 403

    async def test_put_mapping_bumps_version_num_uri_unchanged(self, client, curator_token, two_elements):
        """PUT /mappings/{id} bumps version_num; URI is unchanged."""
        _, elements = two_elements

        create_resp = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "identity",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert create_resp.status_code == 201
        mapping = create_resp.json()

        update_resp = await client.put(
            f"/api/v1/mappings/{mapping['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"description": "Updated description", "version_num": mapping["version_num"]},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["uri"] == mapping["uri"], "URI must be unchanged after update"
        assert updated["version_num"] == mapping["version_num"] + 1
