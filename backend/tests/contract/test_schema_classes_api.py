"""Contract tests for Schema Classes API — T016/T017/T018.

TDD: These tests MUST FAIL before the /schemas/{id}/classes and
/sources/{id}/classes endpoints are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def source_with_elements(client, curator_token):
    """Create a source with one enumeration element and two scalar elements."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"cls-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    # enumeration element
    enum_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"sex-{uuid4()}",
            "data_type": "string",
            "source_id": source["id"],
            "allowed_values": ["M", "F", "O"],
        },
    )
    assert enum_resp.status_code == 201
    enum_element = enum_resp.json()

    # scalar elements
    scalar_ids = []
    for i in range(2):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"field-{i}-{uuid4()}",
                "data_type": "string",
                "source_id": source["id"],
            },
        )
        assert el_resp.status_code == 201
        scalar_ids.append(el_resp.json()["id"])

    return source, enum_element["id"], scalar_ids


@pytest.fixture()
async def schema_with_class_element(client, curator_token, source_with_elements):
    """Create a schema that owns a class DataElement with 3 child elements."""
    source, enum_id, scalar_ids = source_with_elements
    all_element_ids = [enum_id] + scalar_ids

    # Create a schema with those elements
    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"cls-schema-{uuid4()}",
            "elements": [{"element_id": eid, "position": i} for i, eid in enumerate(all_element_ids)],
        },
    )
    assert schema_resp.status_code == 201
    return schema_resp.json(), source, all_element_ids


class TestGetSchemaClasses:
    """T016 — GET /api/v1/schemas/{id}/classes"""

    async def test_get_classes_for_schema_returns_list(
        self, client, curator_token, schema_with_class_element
    ):
        """GET /schemas/{id}/classes returns a classes list (may be empty)."""
        schema, source, element_ids = schema_with_class_element

        resp = await client.get(
            f"/api/v1/schemas/{schema['id']}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "classes" in body
        assert isinstance(body["classes"], list)

    async def test_get_classes_after_post_class_returns_class(
        self, client, curator_token, source_with_elements
    ):
        """After posting a class, GET /schemas/{id}/classes includes the class."""
        source, enum_id, scalar_ids = source_with_elements
        all_element_ids = [enum_id] + scalar_ids

        # Create a schema
        schema_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"cls-check-{uuid4()}",
                "elements": [{"element_id": eid, "position": i} for i, eid in enumerate(all_element_ids)],
            },
        )
        assert schema_resp.status_code == 201
        schema_id = schema_resp.json()["id"]
        source_id = source["id"]

        # POST class to source
        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": "SubjectClass", "description": "Test subject class"},
        )
        assert class_resp.status_code == 201, f"Expected 201: {class_resp.text}"
        class_id = class_resp.json()["id"]

        # Link one element to the class
        link_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"element_id": enum_id, "position": 0},
        )
        assert link_resp.status_code == 201, f"Expected 201: {link_resp.text}"

        # GET classes for schema
        get_resp = await client.get(
            f"/api/v1/schemas/{schema_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        classes = get_resp.json()["classes"]
        assert any(c["class_name"] == "SubjectClass" for c in classes)

    async def test_get_classes_has_enumeration_element(
        self, client, curator_token, source_with_elements
    ):
        """After posting a class with enumeration element, GET returns element_kind='enumeration'."""
        source, enum_id, scalar_ids = source_with_elements
        source_id = source["id"]

        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": f"EnumClass-{uuid4()}"},
        )
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        link_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"element_id": enum_id, "position": 0},
        )
        assert link_resp.status_code == 201

        # Create schema and get classes
        schema_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"enum-class-schema-{uuid4()}",
                "elements": [{"element_id": enum_id, "position": 0}],
            },
        )
        assert schema_resp.status_code == 201
        schema_id = schema_resp.json()["id"]

        get_resp = await client.get(
            f"/api/v1/schemas/{schema_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        classes = get_resp.json()["classes"]
        # At least one class should have an enumeration element
        all_elements = [el for cls in classes for el in cls.get("elements", [])]
        assert any(el.get("element_kind") == "enumeration" for el in all_elements)


class TestPostSourceClasses:
    """T017 — POST /api/v1/sources/{id}/classes and GET /api/v1/sources/{id}/classes"""

    async def test_post_class_returns_201_with_id(self, client, curator_token, source_with_elements):
        """POST /sources/{id}/classes returns 201 with stable id."""
        source, _, _ = source_with_elements

        resp = await client.post(
            f"/api/v1/sources/{source['id']}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": "BiologicalSex", "description": "Sex at birth"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "id" in body
        assert body["class_name"] == "BiologicalSex"

    async def test_get_source_classes_returns_created_class(self, client, curator_token, source_with_elements):
        """GET /sources/{id}/classes includes previously created class."""
        source, _, _ = source_with_elements
        source_id = source["id"]

        class_name = f"TestClass-{uuid4()}"
        post_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": class_name},
        )
        assert post_resp.status_code == 201

        get_resp = await client.get(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200, f"Expected 200: {get_resp.text}"
        body = get_resp.json()
        assert "classes" in body
        names = [c["class_name"] for c in body["classes"]]
        assert class_name in names

    async def test_post_class_with_parent_class(self, client, curator_token, source_with_elements):
        """POST /sources/{id}/classes with parent_class_id links inheritance."""
        source, _, _ = source_with_elements
        source_id = source["id"]

        parent_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": "ParentClass"},
        )
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        child_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": "ChildClass", "parent_class_id": parent_id},
        )
        assert child_resp.status_code == 201, f"Expected 201: {child_resp.text}"
        body = child_resp.json()
        assert body.get("parent_class_id") == parent_id


class TestLinkElementToClass:
    """T018 — POST /api/v1/sources/{id}/classes/{class_id}/elements"""

    async def test_link_element_returns_201(self, client, curator_token, source_with_elements):
        """POST .../classes/{class_id}/elements returns 201."""
        source, enum_id, scalar_ids = source_with_elements
        source_id = source["id"]

        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": f"LinkClass-{uuid4()}"},
        )
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        link_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"element_id": enum_id, "position": 0},
        )
        assert link_resp.status_code == 201, f"Expected 201: {link_resp.text}"

    async def test_linked_elements_preserve_position_order(self, client, curator_token, source_with_elements):
        """Elements linked to a class are returned in position order."""
        source, enum_id, scalar_ids = source_with_elements
        source_id = source["id"]

        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"class_name": f"OrderClass-{uuid4()}"},
        )
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        # Link enum at pos 1, scalar at pos 0
        await client.post(
            f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"element_id": enum_id, "position": 1},
        )
        await client.post(
            f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"element_id": scalar_ids[0], "position": 0},
        )

        # Get source classes and find our class
        get_resp = await client.get(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        classes = get_resp.json()["classes"]
        our_class = next(c for c in classes if c["id"] == class_id)
        positions = [el["position"] for el in our_class.get("elements", [])]
        assert positions == sorted(positions), "Elements not in position order"
