"""Contract tests for dynamic schema endpoints — T043.

Tests MUST FAIL before T047 (schemas router) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def curator_source_and_elements(client, curator_token):
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"schema-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    element_ids = []
    for i in range(3):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"schema-el-{i}-{uuid4()}", "data_type": "integer", "source_id": source["id"]},
        )
        assert el_resp.status_code == 201
        element_ids.append(el_resp.json()["id"])

    return source, element_ids


class TestSchemasContract:
    async def test_post_schema_returns_201_with_uri(self, client, curator_token, curator_source_and_elements):
        """POST /schemas returns 201 with uri field."""
        _, element_ids = curator_source_and_elements

        response = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "test-schema",
                "description": "Test schema",
                "elements": [{"element_id": eid, "position": i} for i, eid in enumerate(element_ids)],
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "uri" in body
        assert body["uri"].startswith("http")
        assert "/schemas/" in body["uri"]

    async def test_get_schemas_returns_paginated_list(self, client):
        """GET /schemas returns PaginatedList[DynamicSchemaSummary]."""
        response = await client.get("/api/v1/schemas")
        assert response.status_code == 200
        body = response.json()
        assert "total" in body
        assert "items" in body

    async def test_get_schema_by_id_returns_full_response(self, client, curator_token, curator_source_and_elements):
        """GET /schemas/{id} returns full DynamicSchemaResponse with elements[]."""
        _, element_ids = curator_source_and_elements

        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "full-response-test",
                "elements": [{"element_id": eid, "position": i} for i, eid in enumerate(element_ids[:2])],
            },
        )
        assert create_resp.status_code == 201
        schema_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/schemas/{schema_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "elements" in body
        assert len(body["elements"]) >= 1
        for el in body["elements"]:
            assert "element_uri" in el

    async def test_put_schema_updates_membership_but_uri_unchanged(self, client, curator_token, curator_source_and_elements):
        """PUT /schemas/{id} updates membership but URI is UNCHANGED."""
        _, element_ids = curator_source_and_elements

        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "uri-stable-test",
                "elements": [{"element_id": element_ids[0], "position": 0}],
            },
        )
        assert create_resp.status_code == 201
        schema = create_resp.json()
        original_uri = schema["uri"]

        update_resp = await client.put(
            f"/api/v1/schemas/{schema['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "add": [{"element_id": element_ids[1], "position": 1}],
                "remove": [],
                "version_num": schema["version_num"],
            },
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        assert update_resp.json()["uri"] == original_uri, "URI must remain stable after membership update"

    async def test_delete_schema_returns_200(self, client, curator_token, curator_source_and_elements):
        """DELETE /schemas/{id} returns 200."""
        _, element_ids = curator_source_and_elements

        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "delete-test-schema", "elements": [{"element_id": element_ids[0], "position": 0}]},
        )
        assert create_resp.status_code == 201
        schema_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/schemas/{schema_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code in (200, 204)

    async def test_post_schema_unauthenticated_returns_401(self, client):
        """POST /schemas without auth returns 401."""
        response = await client.post("/api/v1/schemas", json={"name": "no-auth", "elements": []})
        assert response.status_code == 401

    async def test_post_schema_viewer_returns_403(self, client, viewer_token):
        """POST /schemas with viewer role returns 403."""
        response = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "viewer-test", "elements": []},
        )
        assert response.status_code == 403

    async def test_put_schema_wrong_version_returns_409(self, client, curator_token, curator_source_and_elements):
        """PUT /schemas/{id} with wrong version_num returns 409."""
        _, element_ids = curator_source_and_elements

        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "conflict-schema", "elements": [{"element_id": element_ids[0], "position": 0}]},
        )
        assert create_resp.status_code == 201
        schema = create_resp.json()

        update_resp = await client.put(
            f"/api/v1/schemas/{schema['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"add": [], "remove": [], "version_num": 999},  # wrong
        )
        assert update_resp.status_code == 409
