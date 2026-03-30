"""Tests for browse query filters and sorting.

Regression tests for:
- Source filter on elements (JSONB provenance @> filter)
- Total count must reflect applied filters
- Search text filter finds elements by provenance name
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.graphql import resolvers as r


@pytest.fixture
async def seeded_session(db_session: AsyncSession):
    """Seed a few elements with different sources."""
    from src.storage.database_backend import DatabaseBackend

    backend = DatabaseBackend(db_session)

    # BIDS element
    await backend.entities.write("elements", {
        "sha256": "aaa111",
        "semantic": {"data_type": "string", "unit": "years"},
        "provenance": [{"source": "bids", "class": "columns", "name": "age"}],
    }, identifier="age_aaa111")

    # NWB element
    await backend.entities.write("elements", {
        "sha256": "bbb222",
        "semantic": {"data_type": "string"},
        "provenance": [{"source": "nwb", "class": "nwb", "name": "age"}],
    }, identifier="age_bbb222")

    # DANDI element
    await backend.entities.write("elements", {
        "sha256": "ccc333",
        "semantic": {"data_type": "float"},
        "provenance": [{"source": "dandi", "class": "Participant", "name": "weight"}],
    }, identifier="weight_ccc333")

    await db_session.commit()
    return db_session


async def test_source_filter_returns_correct_count(seeded_session):
    """Source filter must return only matching elements and correct totalCount."""
    result = await r.resolve_browse_elements(
        seeded_session, source="bids", first=50,
    )
    assert result.total_count == 1
    assert len(result.edges) == 1
    assert result.edges[0].node.sha256 == "aaa111"


async def test_source_filter_nwb(seeded_session):
    """NWB filter returns only NWB elements."""
    result = await r.resolve_browse_elements(
        seeded_session, source="nwb", first=50,
    )
    assert result.total_count == 1
    assert result.edges[0].node.sha256 == "bbb222"


async def test_no_filter_returns_all(seeded_session):
    """No filter returns all elements."""
    result = await r.resolve_browse_elements(
        seeded_session, first=50,
    )
    assert result.total_count == 3
    assert len(result.edges) == 3


async def test_search_text_finds_by_name(seeded_session):
    """Search text must match provenance name via tsvector or ILIKE."""
    result = await r.resolve_browse_elements(
        seeded_session, search_text="weight", first=50,
    )
    # Should find the DANDI weight element
    assert result.total_count >= 1
    sha_list = [e.node.sha256 for e in result.edges]
    assert "ccc333" in sha_list


async def test_data_type_filter(seeded_session):
    """Data type filter returns only matching types."""
    from src.graphql.types import DataType

    result = await r.resolve_browse_elements(
        seeded_session, data_type=DataType.FLOAT, first=50,
    )
    assert result.total_count == 1
    assert result.edges[0].node.sha256 == "ccc333"


async def test_pagination_load_more(seeded_session):
    """Pagination: first page returns subset, second page returns remainder."""
    # Get first page
    result1 = await r.resolve_browse_elements(seeded_session, first=2)
    assert result1.total_count == 3
    assert len(result1.edges) == 2
    assert result1.page_info.has_next_page is True
    assert result1.page_info.end_cursor is not None

    # Get second page using cursor
    result2 = await r.resolve_browse_elements(
        seeded_session, first=2, after=result1.page_info.end_cursor
    )
    assert len(result2.edges) == 1
    assert result2.page_info.has_next_page is False

    # Ensure no duplicates
    page1_shas = {e.node.sha256 for e in result1.edges}
    page2_shas = {e.node.sha256 for e in result2.edges}
    assert page1_shas.isdisjoint(page2_shas)
