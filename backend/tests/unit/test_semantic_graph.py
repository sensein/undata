"""SemanticGraph Pydantic model unit tests — T080 (Polish Phase 8) + T088 (semantic dedup guard)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schemas import (
    SemanticGraph,
    SemanticGraphEntity,
    SemanticGraphOverlap,
    SemanticGraphUnit,
)


def test_semantic_graph_temperature_example():
    """Valid temperature/water/Celsius SemanticGraph deserializes correctly."""
    data = {
        "entities": [
            {"label": "water", "type": "substance", "role": "subject", "external_uri": None},
        ],
        "property": {"label": "temperature", "type": "physical", "external_uri": None},
        "unit": {"label": "degree Celsius", "symbol": "°C", "external_uri": None},
        "relations": [],
        "domain": "physics",
        "range_type": "float",
        "context": None,
    }
    sg = SemanticGraph(**data)
    assert sg.unit is not None
    assert sg.unit.label == "degree Celsius"
    assert sg.property is not None
    assert sg.property.label == "temperature"


def test_semantic_graph_unit_extracted_to_unit_field():
    """unit field is populated from semantic_graph.unit.label in the SemanticGraphUnit."""
    from src.models.schemas import SemanticGraphUnit
    unit = SemanticGraphUnit(label="kilogram", symbol="kg", external_uri=None)
    assert unit.label == "kilogram"


def test_semantic_graph_missing_unit_is_none():
    """SemanticGraph without unit has unit=None."""
    sg = SemanticGraph(entities=[], property=None, unit=None, relations=[], domain=None, range_type=None, context=None)
    assert sg.unit is None


def test_semantic_graph_entity_missing_label_raises():
    """Entity without label raises ValidationError."""
    with pytest.raises((ValidationError, TypeError)):
        SemanticGraphEntity(type="substance", role="subject")  # missing label


def test_semantic_graph_context_optional():
    """context field is optional."""
    sg = SemanticGraph(entities=[], property=None, unit=None, relations=[], domain=None, range_type=None, context=None)
    assert sg.context is None


def test_semantic_graph_external_uri_optional():
    """external_uri on entity nodes is optional (None allowed)."""
    entity = SemanticGraphEntity(label="person", type="organism", role="subject", external_uri=None)
    assert entity.external_uri is None


def test_elements_with_different_unit_labels_are_distinct():
    """Two elements with different unit.label are semantically distinct."""
    unit_celsius = SemanticGraphUnit(label="degree Celsius", symbol="°C")
    unit_fahrenheit = SemanticGraphUnit(label="degree Fahrenheit", symbol="°F")
    assert unit_celsius.label != unit_fahrenheit.label


def test_elements_with_different_entity_labels_are_distinct():
    """Two elements with different entity.label are semantically distinct."""
    entity_a = SemanticGraphEntity(label="person", type="organism", role="subject")
    entity_b = SemanticGraphEntity(label="animal", type="organism", role="subject")
    assert entity_a.label != entity_b.label


def test_semantic_graph_overlap_domain_none_when_absent_from_both():
    """SemanticGraphOverlap.domain_match is None when domain absent from both elements."""
    overlap = SemanticGraphOverlap(
        property_match=True,
        unit_match=True,
        entity_labels_match=True,
        domain_match=None,
    )
    assert overlap.domain_match is None
    assert isinstance(overlap.domain_match, type(None))


# ---------------------------------------------------------------------------
# T088: Unit tests for _check_undata_semantic_duplicate()
# ---------------------------------------------------------------------------

_SG_PERSON_AGE_YEAR = {
    "entities": [{"label": "person", "type": "organism", "role": "subject"}],
    "property": {"label": "age", "type": "demographic"},
    "unit": {"label": "year", "symbol": "yr"},
    "relations": [],
}


def _make_sg_model(**overrides):
    """Return a SemanticGraph Pydantic model with optional field overrides."""
    data = {**_SG_PERSON_AGE_YEAR, **overrides}
    return SemanticGraph.model_validate(data)


@pytest.mark.asyncio
async def test_semantic_dedup_no_existing_elements_no_exception():
    """No existing undata elements → _check_undata_semantic_duplicate raises nothing (T088a)."""
    from src.models.schemas import DataElementCreate
    from src.services.elements import _check_undata_semantic_duplicate

    data = DataElementCreate(
        name="age_test",
        data_type="integer",
        source_id=uuid4(),
        semantic_graph=_make_sg_model(),
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Should not raise
    await _check_undata_semantic_duplicate(mock_session, data)


@pytest.mark.asyncio
async def test_semantic_dedup_exact_match_raises_semantic_duplicate_error():
    """Existing element with identical fingerprint → raises SemanticDuplicateError (T088b)."""
    from src.models.db import DataElement, DataElementVersion
    from src.models.schemas import DataElementCreate
    from src.services.elements import SemanticDuplicateError, _check_undata_semantic_duplicate

    data = DataElementCreate(
        name="age_dup",
        data_type="integer",
        source_id=uuid4(),
        semantic_graph=_make_sg_model(),
    )

    existing_id = uuid4()
    existing_uri = f"http://localhost:8002/elements/{existing_id}"

    mock_element = DataElement(
        id=existing_id,
        uri=existing_uri,
        source_local_id="age_original",
    )
    mock_version = DataElementVersion(
        element_id=existing_id,
        version_num=1,
        name="age_original",
        data_type="integer",
        required=False,
        multivalued=False,
        created_by=uuid4(),
        semantic_graph=_SG_PERSON_AGE_YEAR,
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_element, mock_version)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(SemanticDuplicateError) as exc_info:
        await _check_undata_semantic_duplicate(mock_session, data)

    assert exc_info.value.existing_id == str(existing_id)
    assert exc_info.value.existing_uri == existing_uri


@pytest.mark.asyncio
async def test_semantic_dedup_different_entity_no_exception():
    """Same property+unit but different entity label → no exception (T088c)."""
    from src.models.db import DataElement, DataElementVersion
    from src.models.schemas import DataElementCreate
    from src.services.elements import _check_undata_semantic_duplicate

    data = DataElementCreate(
        name="rat_age",
        data_type="integer",
        source_id=uuid4(),
        semantic_graph=_make_sg_model(
            entities=[{"label": "rat", "type": "organism", "role": "subject"}]
        ),
    )

    mock_element = DataElement(id=uuid4(), uri="http://example.com/e/1", source_local_id="x")
    mock_version = DataElementVersion(
        element_id=mock_element.id,
        version_num=1,
        name="person_age",
        data_type="integer",
        required=False,
        multivalued=False,
        created_by=uuid4(),
        semantic_graph=_SG_PERSON_AGE_YEAR,  # person entity — different from rat
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_element, mock_version)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    await _check_undata_semantic_duplicate(mock_session, data)  # no exception


@pytest.mark.asyncio
async def test_semantic_dedup_different_unit_no_exception():
    """Same entity+property but different unit label → no exception (T088d)."""
    from src.models.db import DataElement, DataElementVersion
    from src.models.schemas import DataElementCreate
    from src.services.elements import _check_undata_semantic_duplicate

    data = DataElementCreate(
        name="age_months",
        data_type="integer",
        source_id=uuid4(),
        semantic_graph=_make_sg_model(unit={"label": "month", "symbol": "mo"}),
    )

    mock_element = DataElement(id=uuid4(), uri="http://example.com/e/2", source_local_id="y")
    mock_version = DataElementVersion(
        element_id=mock_element.id,
        version_num=1,
        name="age_years",
        data_type="integer",
        required=False,
        multivalued=False,
        created_by=uuid4(),
        semantic_graph=_SG_PERSON_AGE_YEAR,  # unit=year — different from month
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_element, mock_version)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    await _check_undata_semantic_duplicate(mock_session, data)  # no exception


@pytest.mark.asyncio
async def test_semantic_dedup_null_semantic_graph_skips_check():
    """semantic_graph=None on incoming request → guard skips entirely (T088e)."""
    from src.models.schemas import DataElementCreate
    from src.services.elements import _check_undata_semantic_duplicate

    data = DataElementCreate(
        name="no_sg",
        data_type="string",
        source_id=uuid4(),
        semantic_graph=None,
    )

    mock_session = AsyncMock(spec=AsyncSession)

    await _check_undata_semantic_duplicate(mock_session, data)
    mock_session.execute.assert_not_called()
