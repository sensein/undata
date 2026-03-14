"""Unit tests for LinkML generator Pass 2 — DynamicSchema inheritance (TDD).

Tests T023–T026: must FAIL before implementation, PASS after.
"""

from __future__ import annotations

import httpx
import pytest
import respx

BASE_URL = "http://localhost:8002/api/v1"


def _make_generator():
    from undata.linkml_gen import LinkMLSchemaGenerator

    return LinkMLSchemaGenerator(backend_url=BASE_URL)


# ── T023: is_mixin=True → mixin: true ────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_linkml_gen_emits_mixin_class():
    """Mock GET /schemas returns a schema with is_mixin=True → output has mixin: true (FR-009)."""
    mixin_id = "aaaa-bbbb-cccc-dddd"
    respx.get(f"{BASE_URL}/elements").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0, "page": 1, "pages": 1})
    )
    respx.get(f"{BASE_URL}/schemas").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"id": mixin_id, "name": "ProvenanceMixin", "is_mixin": True}],
                "total": 1,
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": mixin_id,
                "nodes": [{"id": mixin_id, "name": "ProvenanceMixin", "is_mixin": True}],
                "edges": [],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    gen = _make_generator()
    schema = await gen.generate()

    assert "ProvenanceMixin" in schema.classes, (
        "Expected 'ProvenanceMixin' class in output. "
        "Generator Pass 2 must emit DynamicSchema classes (FR-008)."
    )
    cls = schema.classes["ProvenanceMixin"]
    assert cls.mixin is True, (
        f"Expected mixin=True for ProvenanceMixin, got mixin={cls.mixin}. "
        "is_mixin=True must set mixin: true in LinkML class (FR-009)."
    )


# ── T024: parent_id → is_a: ParentName ───────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_linkml_gen_emits_is_a():
    """Mock DynamicSchema with parent_id → output class has is_a: ParentName (FR-011)."""
    parent_id = "pppp-0000-0000-0000"
    child_id = "cccc-0000-0000-0000"
    respx.get(f"{BASE_URL}/elements").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0, "page": 1, "pages": 1})
    )
    respx.get(f"{BASE_URL}/schemas").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": parent_id, "name": "ParentSchema", "is_mixin": False},
                    {"id": child_id, "name": "ChildSchema", "is_mixin": False},
                ],
                "total": 2,
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{parent_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": parent_id,
                "nodes": [{"id": parent_id, "name": "ParentSchema", "is_mixin": False}],
                "edges": [],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{child_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": child_id,
                "nodes": [
                    {"id": child_id, "name": "ChildSchema", "is_mixin": False},
                    {"id": parent_id, "name": "ParentSchema", "is_mixin": False},
                ],
                "edges": [
                    {
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "type": "inherits",
                        "position": 0,
                    }
                ],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{parent_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )
    respx.get(f"{BASE_URL}/schemas/{child_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    gen = _make_generator()
    schema = await gen.generate()

    assert "ChildSchema" in schema.classes, "Expected 'ChildSchema' in output classes."
    cls = schema.classes["ChildSchema"]
    assert cls.is_a == "ParentSchema", (
        f"Expected is_a='ParentSchema', got is_a={cls.is_a!r}. "
        "parent edge (type='inherits') must set is_a (FR-011)."
    )


# ── T025: mixin edges → mixins: [MixinName] ──────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_linkml_gen_emits_mixins():
    """Mock DynamicSchema with mixin edges → output class has mixins: [MixinName] (FR-010)."""
    mixin_id = "mmmm-0000-0000-0000"
    schema_id = "ssss-0000-0000-0000"
    respx.get(f"{BASE_URL}/elements").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0, "page": 1, "pages": 1})
    )
    respx.get(f"{BASE_URL}/schemas").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": mixin_id, "name": "TrackableMixin", "is_mixin": True},
                    {"id": schema_id, "name": "DataSchema", "is_mixin": False},
                ],
                "total": 2,
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": mixin_id,
                "nodes": [{"id": mixin_id, "name": "TrackableMixin", "is_mixin": True}],
                "edges": [],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{schema_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": schema_id,
                "nodes": [
                    {"id": schema_id, "name": "DataSchema", "is_mixin": False},
                    {"id": mixin_id, "name": "TrackableMixin", "is_mixin": True},
                ],
                "edges": [
                    {
                        "child_id": schema_id,
                        "parent_id": mixin_id,
                        "type": "mixin",
                        "position": 0,
                    }
                ],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )
    respx.get(f"{BASE_URL}/schemas/{schema_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    gen = _make_generator()
    schema = await gen.generate()

    assert "DataSchema" in schema.classes, "Expected 'DataSchema' in output classes."
    cls = schema.classes["DataSchema"]
    assert "TrackableMixin" in (cls.mixins or []), (
        f"Expected mixins=['TrackableMixin'], got mixins={cls.mixins!r}. "
        "mixin edges must set mixins list (FR-010)."
    )


# ── T026: mixin slot deduplication ───────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_linkml_gen_deduplicates_mixin_slots():
    """Mixin-contributed slots must NOT be duplicated on classes that use the mixin (FR-013)."""
    mixin_id = "mmmm-1111-1111-1111"
    schema_id = "ssss-1111-1111-1111"
    elem_id = "eeee-1111-1111-1111"

    # One element that belongs to both the mixin schema and the child schema
    shared_element = {
        "id": elem_id,
        "name": "created_at",
        "data_type": "string",
        "description": "Creation timestamp",
        "source": {"name": "BIDS"},
        "multivalued": False,
        "required": False,
        "allowed_values": None,
    }

    respx.get(f"{BASE_URL}/elements").mock(
        return_value=httpx.Response(
            200,
            json={"items": [shared_element], "total": 1, "page": 1, "pages": 1},
        )
    )
    respx.get(f"{BASE_URL}/schemas").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": mixin_id, "name": "TimestampMixin", "is_mixin": True},
                    {"id": schema_id, "name": "AnnotatedSchema", "is_mixin": False},
                ],
                "total": 2,
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": mixin_id,
                "nodes": [{"id": mixin_id, "name": "TimestampMixin", "is_mixin": True}],
                "edges": [],
            },
        )
    )
    respx.get(f"{BASE_URL}/schemas/{schema_id}/inheritance-tree").mock(
        return_value=httpx.Response(
            200,
            json={
                "schema_id": schema_id,
                "nodes": [
                    {"id": schema_id, "name": "AnnotatedSchema", "is_mixin": False},
                    {"id": mixin_id, "name": "TimestampMixin", "is_mixin": True},
                ],
                "edges": [
                    {
                        "child_id": schema_id,
                        "parent_id": mixin_id,
                        "type": "mixin",
                        "position": 0,
                    }
                ],
            },
        )
    )
    # Mixin resolved elements include "created_at"
    respx.get(f"{BASE_URL}/schemas/{mixin_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": [{"name": "created_at"}]})
    )
    respx.get(f"{BASE_URL}/schemas/{schema_id}/resolved").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    gen = _make_generator()
    schema = await gen.generate()

    assert "AnnotatedSchema" in schema.classes, "Expected 'AnnotatedSchema' in output."
    child_cls = schema.classes["AnnotatedSchema"]

    # "created_at" is contributed by TimestampMixin — must NOT appear in AnnotatedSchema slots
    assert "created_at" not in (child_cls.slots or []), (
        f"Slot 'created_at' must not be duplicated on AnnotatedSchema "
        f"(it is contributed by TimestampMixin). Got slots: {child_cls.slots}"
    )
