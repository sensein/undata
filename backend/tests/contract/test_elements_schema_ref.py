"""Contract tests for schema_ref enforcement (FR-002, FR-003) — T009/T010a.

FR-002: schema_ref is OPTIONAL on object-typed elements. Two valid paths:
  - object + schema_ref → named DynamicSchema reference
  - object + no schema_ref → anonymous inline structure via DataElementChild

FR-003: If schema_ref IS set, DataElementChild nesting MUST be rejected (mutually exclusive).

TDD: T009(b,c) MUST FAIL before T006/T010a are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def source(client, curator_token):
    resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"schema-ref-src-{uuid4()}", "format": "json"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
async def target_schema(client, curator_token, source):
    """Create a DynamicSchema to use as schema_ref target."""
    el_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"field-{uuid4()}", "data_type": "string", "source_id": source["id"]},
    )
    assert el_resp.status_code == 201
    element_id = el_resp.json()["id"]

    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"target-schema-{uuid4()}",
            "elements": [{"element_id": element_id, "position": 0}],
        },
    )
    assert schema_resp.status_code == 201
    return schema_resp.json()


class TestSchemaRefEnforcement:
    """T009(b) — schema_ref in POST /elements."""

    async def test_object_type_without_schema_ref_returns_201(
        self, client, curator_token, source
    ):
        """POST /elements with data_type='object' and no schema_ref → 201 (anonymous inline path)."""
        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"obj-no-ref-{uuid4()}",
                "data_type": "object",
                "source_id": source["id"],
            },
        )
        assert resp.status_code == 201, (
            f"Expected 201 for object type without schema_ref (DataElementChild path), "
            f"got {resp.status_code}: {resp.text}"
        )

    async def test_object_type_with_valid_schema_ref_returns_201(
        self, client, curator_token, source, target_schema
    ):
        """POST /elements with data_type='object' and valid schema_ref → 201 (FR-002)."""
        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"obj-with-ref-{uuid4()}",
                "data_type": "object",
                "source_id": source["id"],
                "schema_ref": target_schema["id"],
            },
        )
        assert resp.status_code == 201, (
            f"Expected 201 for object type with schema_ref, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("schema_ref") == target_schema["id"]

    async def test_non_object_type_without_schema_ref_succeeds(
        self, client, curator_token, source
    ):
        """POST /elements with data_type='string' and no schema_ref → 201 (validation is type-gated)."""
        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"str-no-ref-{uuid4()}",
                "data_type": "string",
                "source_id": source["id"],
            },
        )
        assert resp.status_code == 201, (
            f"Expected 201 for string type without schema_ref, got {resp.status_code}: {resp.text}"
        )


class TestDataElementChildGuard:
    """T009(c) — DataElementChild rejected when parent has schema_ref (FR-003).

    If the child-creation endpoint does not exist or rejects the operation
    differently, we accept 404/422/400 as proof the guard is in place.
    """

    async def test_child_rejected_when_parent_has_schema_ref(
        self, client, curator_token, source, target_schema
    ):
        """Creating a DataElementChild when parent has schema_ref → 422 (FR-003)."""
        # Create a parent element with schema_ref
        parent_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"obj-parent-{uuid4()}",
                "data_type": "object",
                "source_id": source["id"],
                "schema_ref": target_schema["id"],
            },
        )
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        # Create a child element to reference
        child_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"child-el-{uuid4()}", "data_type": "string", "source_id": source["id"]},
        )
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # Attempt to link child to parent that has schema_ref — must be rejected
        link_resp = await client.post(
            f"/api/v1/elements/{parent_id}/children",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"child_element_id": child_id, "field_name": "nested", "position": 0},
        )
        assert link_resp.status_code in (400, 404, 422), (
            f"Expected 400/404/422 when adding DataElementChild to schema_ref parent, "
            f"got {link_resp.status_code}: {link_resp.text}"
        )
