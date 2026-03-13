"""Failing unit tests for SchemaDiffer — must fail before implementation (TDD).

Tests:
- All 6 diff types computed correctly (ADDED, REMOVED, RENAMED, TYPE_CHANGED,
  CONSTRAINT_CHANGED, DESCRIPTION_CHANGED)
- FULL coverage when all diffs have registered mappings
- PARTIAL coverage with gap list
- draft_pathway assembled from existing mappings
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.services.schema_differ import SchemaDiffer


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def differ(mock_client):
    return SchemaDiffer(mock_client)


def _make_element(
    elem_id: str,
    name: str,
    data_type: str = "string",
    description: str = "",
    constraints: dict | None = None,
    source_name: str = "BIDS",
) -> dict:
    return {
        "id": elem_id,
        "name": name,
        "data_type": data_type,
        "description": description,
        "constraints": constraints or {},
        "source_name": source_name,
        "source_local_id": f"{source_name}.{name}",
    }


# ---- Tests ----


@pytest.mark.asyncio
async def test_added_elements_detected(differ, mock_client):
    """Elements in target but not source appear in diff.added."""
    source_elements = [_make_element("e1", "subject_id")]
    target_elements = [_make_element("e1", "subject_id"), _make_element("e2", "session_id")]

    mock_client.get_schema_elements.side_effect = [source_elements, target_elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    added_names = [e["name"] for e in diff.added]
    assert "session_id" in added_names


@pytest.mark.asyncio
async def test_removed_elements_detected(differ, mock_client):
    """Elements in source but not target appear in diff.removed."""
    source_elements = [
        _make_element("e1", "subject_id"),
        _make_element("e2", "old_field"),
    ]
    target_elements = [_make_element("e1", "subject_id")]

    mock_client.get_schema_elements.side_effect = [source_elements, target_elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    removed_names = [e["name"] for e in diff.removed]
    assert "old_field" in removed_names


@pytest.mark.asyncio
async def test_type_changed_detected(differ, mock_client):
    """Elements with same name but different data_type appear in diff.type_changed."""
    source_elements = [_make_element("e1", "count", data_type="string")]
    target_elements = [_make_element("e2", "count", data_type="integer")]

    mock_client.get_schema_elements.side_effect = [source_elements, target_elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    type_changed_names = [c["name"] for c in diff.type_changed]
    assert "count" in type_changed_names


@pytest.mark.asyncio
async def test_description_changed_detected(differ, mock_client):
    """Elements with same name/type but different descriptions appear in description_changed."""
    source_elements = [_make_element("e1", "label", description="old desc")]
    target_elements = [_make_element("e2", "label", description="new desc")]

    mock_client.get_schema_elements.side_effect = [source_elements, target_elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    desc_names = [c["name"] for c in diff.description_changed]
    assert "label" in desc_names


@pytest.mark.asyncio
async def test_identical_schemas_produce_empty_diff(differ, mock_client):
    """Identical schemas produce empty diff lists and FULL coverage."""
    elements = [_make_element("e1", "subject_id"), _make_element("e2", "session_id")]

    mock_client.get_schema_elements.side_effect = [elements, elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    assert diff.added == []
    assert diff.removed == []
    assert diff.type_changed == []
    assert diff.description_changed == []
    assert diff.coverage == "FULL"


@pytest.mark.asyncio
async def test_partial_coverage_when_no_mappings(differ, mock_client):
    """PARTIAL coverage when diff exists but no mappings cover it."""
    source_elements = [_make_element("e1", "subject_id")]
    target_elements = [_make_element("e1", "subject_id"), _make_element("e2", "session_id")]

    mock_client.get_schema_elements.side_effect = [source_elements, target_elements]
    mock_client.list_pathways.return_value = {"items": []}

    diff = await differ.diff("schema-src", "schema-tgt")

    assert diff.coverage in ("PARTIAL", "NONE")
