"""Contract tests for schema supersession — T076.

Tests MUST FAIL before T078 (supersede schema endpoint) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def schema_with_elements(client, curator_token):
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"ss-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    el_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"ss-el-{uuid4()}", "data_type": "integer", "source_id": source["id"]},
    )
    assert el_resp.status_code == 201
    element = el_resp.json()

    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": "supersede-test-schema", "elements": [{"element_id": element["id"], "position": 0}]},
    )
    assert schema_resp.status_code == 201
    return source, element, schema_resp.json()


class TestSupersedeSchemaContract:
    async def test_supersede_schema_returns_201(self, client, curator_token, schema_with_elements):
        """POST /schemas/{id}/supersede returns 201 with distinct URIs."""
        source, element, old_schema = schema_with_elements

        response = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Updated schema structure",
                "new_schema_data": {
                    "name": "updated-schema",
                    "elements": [{"element_id": element["id"], "position": 0}],
                },
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "new_schema" in body
        assert "superseded_schema" in body
        new_schema = body["new_schema"]
        old_stub = body["superseded_schema"]
        assert new_schema["uri"] != old_schema["uri"], "New schema must have distinct URI"
        assert old_stub["superseded_by"] == new_schema["uri"]
        assert old_stub["deleted_at"] is not None

    async def test_supersede_missing_reason_returns_422(self, client, curator_token, schema_with_elements):
        """POST /schemas/{id}/supersede without supersede_reason returns 422."""
        _, element, old_schema = schema_with_elements

        response = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"new_schema_data": {"name": "new", "elements": []}},
        )
        assert response.status_code == 422

    async def test_supersede_nonexistent_schema_returns_404(self, client, curator_token):
        """POST /schemas/{id}/supersede with nonexistent ID returns 404."""
        response = await client.post(
            f"/api/v1/schemas/{uuid4()}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"supersede_reason": "test", "new_schema_data": {"name": "new", "elements": []}},
        )
        assert response.status_code == 404

    async def test_supersede_already_superseded_returns_409(self, client, curator_token, schema_with_elements):
        """POST /schemas/{id}/supersede on already-superseded schema returns 409."""
        source, element, old_schema = schema_with_elements

        # First supersession
        resp1 = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "First",
                "new_schema_data": {"name": "new-v1", "elements": [{"element_id": element["id"], "position": 0}]},
            },
        )
        assert resp1.status_code == 201

        # Second on already-superseded
        resp2 = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Second",
                "new_schema_data": {"name": "new-v2", "elements": [{"element_id": element["id"], "position": 0}]},
            },
        )
        assert resp2.status_code == 409

    async def test_supersede_unauthenticated_returns_401(self, client, schema_with_elements):
        """POST /schemas/{id}/supersede without auth returns 401."""
        _, element, old_schema = schema_with_elements

        response = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            json={"supersede_reason": "test", "new_schema_data": {"name": "new", "elements": []}},
        )
        assert response.status_code == 401

    async def test_supersede_viewer_returns_403(self, client, viewer_token, schema_with_elements):
        """POST /schemas/{id}/supersede with viewer role returns 403."""
        _, element, old_schema = schema_with_elements

        response = await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"supersede_reason": "test", "new_schema_data": {"name": "new", "elements": []}},
        )
        assert response.status_code == 403

    async def test_list_schemas_excludes_superseded_by_default(self, client, curator_token, schema_with_elements):
        """GET /schemas with include_superseded=false excludes old schema."""
        source, element, old_schema = schema_with_elements

        await client.post(
            f"/api/v1/schemas/{old_schema['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "test",
                "new_schema_data": {"name": "replacement", "elements": [{"element_id": element["id"], "position": 0}]},
            },
        )

        list_resp = await client.get("/api/v1/schemas", params={"include_superseded": False})
        schema_ids = [s["id"] for s in list_resp.json()["items"]]
        assert old_schema["id"] not in schema_ids, "Superseded schema must be excluded from default listing"
