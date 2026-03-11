"""Failing unit tests for pathway validation logic — must fail before implementation (TDD).

Tests:
- Unknown mapping_id → rejected
- Auto-inverse derivation when all steps have inverses
- Pathway composition intermediate schema mismatch → error
- BROKEN detection logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.services.backend_client import BackendClientError
from src.services.pathway_service import (
    CompositionError,
    PathwayService,
)


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def service(mock_client):
    return PathwayService(mock_client)


def _make_pathway(
    source_schema_id: str,
    target_schema_id: str,
    steps: list[dict],
    status: str = "active",
    inverse_id: str | None = None,
) -> dict:
    return {
        "id": "pathway-id",
        "name": "Test Pathway",
        "source_schema_id": source_schema_id,
        "target_schema_id": target_schema_id,
        "direction": "forward",
        "status": status,
        "steps": steps,
        "inverse_pathway_id": inverse_id,
        "version_num": 0,
    }


def _make_mapping(mapping_id: str, inverse_id: str | None = None) -> dict:
    return {
        "id": mapping_id,
        "function_type": "identity",
        "current_version": {
            "expression": "input_0",
            "expression_type": "identity",
            "inverse_mapping_id": inverse_id,
        },
    }


# ---- Tests ----


@pytest.mark.asyncio
async def test_validate_steps_unknown_mapping_id_rejected(service, mock_client):
    """Steps referencing a non-existent mapping_id should raise ValueError."""
    mock_client.get_mapping.side_effect = BackendClientError(404, "Not found")

    with pytest.raises(ValueError, match="mapping_id"):
        await service.validate_steps([{"position": 0, "mapping_id": "nonexistent-id"}])


@pytest.mark.asyncio
async def test_auto_inverse_derived_when_all_steps_have_inverse(service, mock_client):
    """When all steps have inverse_mapping_id, auto-inverse pathway should be derivable."""
    mapping_a = _make_mapping("mapping-a", inverse_id="mapping-a-inv")
    mock_client.get_mapping.return_value = mapping_a

    steps = [{"position": 0, "mapping_id": "mapping-a"}]
    can_derive = await service.can_derive_inverse(steps)

    assert can_derive is True


@pytest.mark.asyncio
async def test_no_inverse_when_steps_lack_inverse_mapping(service, mock_client):
    """When any step lacks inverse_mapping_id, inverse cannot be auto-derived."""
    mapping_no_inv = _make_mapping("mapping-b", inverse_id=None)
    mock_client.get_mapping.return_value = mapping_no_inv

    steps = [{"position": 0, "mapping_id": "mapping-b"}]
    can_derive = await service.can_derive_inverse(steps)

    assert can_derive is False


@pytest.mark.asyncio
async def test_composition_schema_mismatch_raises_error(service, mock_client):
    """Composing pathways where A.target != B.source raises CompositionError."""
    pathway_a = _make_pathway("schema-1", "schema-2", [])
    pathway_b = _make_pathway("schema-99", "schema-3", [])  # mismatch

    mock_client.get_pathway.side_effect = [pathway_a, pathway_b]

    with pytest.raises(CompositionError, match="mismatch"):
        await service.compose("pathway-a-id", "pathway-b-id")


@pytest.mark.asyncio
async def test_composition_valid_concatenates_steps(service, mock_client):
    """Composing A→B and B→C pathways concatenates their steps."""
    pathway_a = _make_pathway(
        "schema-1",
        "schema-2",
        [{"position": 0, "mapping_id": "map-a"}],
    )
    pathway_b = _make_pathway(
        "schema-2",
        "schema-3",
        [{"position": 0, "mapping_id": "map-b"}],
    )

    mock_client.get_pathway.side_effect = [pathway_a, pathway_b]

    composed = await service.compose("pathway-a-id", "pathway-b-id")

    assert composed["source_schema_id"] == "schema-1"
    assert composed["target_schema_id"] == "schema-3"
    assert len(composed["steps"]) == 2
    # Steps should be re-indexed
    positions = [s["position"] for s in composed["steps"]]
    assert positions == sorted(positions)
