"""Failing unit tests for SchemaBuilder — must fail before implementation (TDD).

Tests:
- build() produces a valid SchemaDefinition YAML with correct slots and classes
- Unknown element IDs raise ValueError with the unknown IDs listed
- Name collision detection raises ConflictError with details
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.services.schema_builder import ConflictError, SchemaBuilder


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


@pytest.fixture
def builder(mock_client):
    return SchemaBuilder(mock_client)


# ---- Helper element dicts ----


def _make_element(name: str, data_type: str, source_name: str = "BIDS") -> dict:
    return {
        "id": f"elem-{name}",
        "name": name,
        "data_type": data_type,
        "description": f"Test element {name}",
        "source_local_id": f"{source_name}.{name}",
        "source_name": source_name,
        "required": False,
        "multivalued": False,
        "allowed_values": None,
        "constraints": {},
    }


# ---- Tests ----


@pytest.mark.asyncio
async def test_build_produces_valid_schema_yaml(builder, mock_client):
    """build() should produce a YAML string that parses as a LinkML SchemaDefinition."""
    mock_client.get_element.side_effect = lambda eid: _make_element(
        eid.replace("elem-", ""), "string"
    )

    result = await builder.build(
        name="TestSchema",
        version="2026.03.0",
        classes=[{"name": "SubjectClass", "element_ids": ["elem-subject_id", "elem-session_id"]}],
    )

    assert result.linkml_yaml is not None
    assert "TestSchema" in result.linkml_yaml
    assert "subject_id" in result.linkml_yaml or "session_id" in result.linkml_yaml
    assert "SubjectClass" in result.linkml_yaml


@pytest.mark.asyncio
async def test_build_unknown_ids_raise_value_error(builder, mock_client):
    """build() with an unknown element ID should raise ValueError listing the bad IDs."""
    from src.services.backend_client import BackendClientError

    mock_client.get_element.side_effect = BackendClientError(404, "Not found")

    with pytest.raises(ValueError, match="unknown_ids"):
        await builder.build(
            name="TestSchema",
            version="2026.03.0",
            classes=[{"name": "MyClass", "element_ids": ["nonexistent-id"]}],
        )


@pytest.mark.asyncio
async def test_build_name_collision_raises_conflict_error(builder, mock_client):
    """build() with elements that have the same name from different sources raises ConflictError."""
    # Two elements with the same name from different sources
    elem_a = _make_element("subject_id", "string", source_name="BIDS")
    elem_b = _make_element("subject_id", "integer", source_name="DANDI")

    # Returns elem_a for first call, elem_b for second
    mock_client.get_element.side_effect = [elem_a, elem_b]

    with pytest.raises(ConflictError) as exc_info:
        await builder.build(
            name="CollidingSchema",
            version="2026.03.0",
            classes=[
                {
                    "name": "MyClass",
                    "element_ids": ["elem-subject_id_bids", "elem-subject_id_dandi"],
                }
            ],
        )
    assert "subject_id" in str(exc_info.value).lower() or exc_info.value.conflicting_names


@pytest.mark.asyncio
async def test_build_produces_linkml_jsonld(builder, mock_client):
    """build() should include a JSON-LD serialization."""
    mock_client.get_element.side_effect = lambda eid: _make_element(
        eid.replace("elem-", ""), "string"
    )

    result = await builder.build(
        name="JsonLdSchema",
        version="2026.03.0",
        classes=[{"name": "MyClass", "element_ids": ["elem-field_a"]}],
    )

    assert result.linkml_jsonld is not None
    assert len(result.linkml_jsonld) > 0
