"""Integration tests for dynamic schema lifecycle — T044.

Tests MUST FAIL before T045–T048 (schema service + router) are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def elements_for_schema(client, curator_token):
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"ds-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    element_ids = []
    for i in range(4):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"ds-el-{i}-{uuid4()}", "data_type": "integer", "source_id": source["id"]},
        )
        assert el_resp.status_code == 201
        element_ids.append(el_resp.json()["id"])

    return source, element_ids


class TestDynamicSchemaLifecycle:
    async def test_full_schema_lifecycle(self, client, curator_token, elements_for_schema):
        """Create, GET, PUT, verify URI stable, DELETE, verify exclusion."""
        source, element_ids = elements_for_schema

        # Create schema with 3 elements
        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "lifecycle-schema",
                "description": "Full lifecycle test",
                "elements": [
                    {"element_id": element_ids[0], "position": 0},
                    {"element_id": element_ids[1], "position": 1},
                    {"element_id": element_ids[2], "position": 2},
                ],
            },
        )
        assert create_resp.status_code == 201
        schema = create_resp.json()
        original_uri = schema["uri"]

        # GET by ID
        get_resp = await client.get(f"/api/v1/schemas/{schema['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["uri"] == original_uri

        # PUT: swap element 2 for element 3, verify URI unchanged + version bumped
        update_resp = await client.put(
            f"/api/v1/schemas/{schema['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "add": [{"element_id": element_ids[3], "position": 3}],
                "remove": [element_ids[2]],
                "version_num": schema["version_num"],
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["uri"] == original_uri, "URI must be stable after membership update"
        assert updated["version_num"] == schema["version_num"] + 1

        # GET filtered by element_id
        filter_resp = await client.get("/api/v1/schemas", params={"element_id": element_ids[3]})
        assert filter_resp.status_code == 200
        schema_ids = [s["id"] for s in filter_resp.json()["items"]]
        assert schema["id"] in schema_ids

        # DELETE
        del_resp = await client.delete(
            f"/api/v1/schemas/{schema['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code in (200, 204)

        # Not in list after delete
        list_resp = await client.get("/api/v1/schemas")
        ids = [s["id"] for s in list_resp.json()["items"]]
        assert schema["id"] not in ids

    async def test_audit_log_contains_schema_operations(self, client, curator_token, elements_for_schema):
        """Audit log shows CREATE, UPDATE, DELETE entries with actor_id UUID."""
        source, element_ids = elements_for_schema

        create_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "audit-schema", "elements": [{"element_id": element_ids[0], "position": 0}]},
        )
        assert create_resp.status_code == 201
        schema = create_resp.json()

        # Get audit log for this schema
        audit_resp = await client.get(
            "/api/v1/audit",
            headers={"Authorization": f"Bearer {curator_token}"},
            params={"record_type": "DynamicSchema", "record_id": schema["id"]},
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json().get("items", [])
        assert len(entries) >= 1
        for entry in entries:
            assert "actor_id" in entry, "Audit entry must include actor_id UUID"
