"""Tests for content-addressed ElementService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.element import Element
from src.services.element_service import ElementService


@pytest.fixture
def element_service(db_session: AsyncSession) -> ElementService:
    return ElementService(db_session)


class TestCreateOrMerge:
    async def test_create_new_element_returns_uri(self, element_service: ElementService):
        semantic = {"data_type": "integer", "ontology_term": "http://example.org/age", "unit": "year"}
        provenance = [{"source": "bids", "class": "Participant", "name": "age", "description": "Age in years"}]

        elem, created = await element_service.create_or_merge(semantic, provenance)

        assert created is True
        assert elem.uri.startswith("https://schema.undata.live/elements/age_")
        assert elem.semantic_hash is not None
        assert len(elem.semantic_hash) == 64
        assert len(elem.provenance) == 1
        assert elem.provenance[0].source == "bids"

    async def test_same_semantic_returns_same_uri_merges_provenance(
        self, element_service: ElementService, db_session: AsyncSession
    ):
        semantic = {"data_type": "string", "ontology_term": "http://example.org/sex"}
        prov1 = [{"source": "bids", "class": "Participant", "name": "sex"}]
        prov2 = [{"source": "nwb", "class": "Subject", "name": "sex"}]

        elem1, created1 = await element_service.create_or_merge(semantic, prov1)
        await db_session.flush()

        elem2, created2 = await element_service.create_or_merge(semantic, prov2)

        assert created1 is True
        assert created2 is False
        assert elem1.uri == elem2.uri
        assert elem1.semantic_hash == elem2.semantic_hash
        assert len(elem2.provenance) == 2

    async def test_different_semantic_returns_different_uri(
        self, element_service: ElementService, db_session: AsyncSession
    ):
        sem_a = {"data_type": "integer", "ontology_term": "http://example.org/age", "unit": "year"}
        sem_b = {"data_type": "string", "ontology_term": "http://example.org/age", "unit": "iso8601_duration"}
        prov = [{"source": "test", "class": "Test", "name": "age"}]

        elem_a, _ = await element_service.create_or_merge(sem_a, prov)
        await db_session.flush()

        elem_b, _ = await element_service.create_or_merge(sem_b, prov)

        assert elem_a.uri != elem_b.uri
        assert elem_a.semantic_hash != elem_b.semantic_hash

    async def test_duplicate_provenance_skipped(
        self, element_service: ElementService, db_session: AsyncSession
    ):
        semantic = {"data_type": "float"}
        prov = [{"source": "bids", "class": "Participant", "name": "weight"}]

        elem1, _ = await element_service.create_or_merge(semantic, prov)
        await db_session.flush()

        elem2, _ = await element_service.create_or_merge(semantic, prov)

        assert len(elem2.provenance) == 1  # Not duplicated


class TestListElements:
    async def test_list_returns_created_elements(
        self, element_service: ElementService, db_session: AsyncSession
    ):
        semantic = {"data_type": "string"}
        prov = [{"source": "test", "class": "Test", "name": "field1"}]
        await element_service.create_or_merge(semantic, prov)
        await db_session.flush()

        elements, total = await element_service.list_elements()
        assert total >= 1
        assert any(e.provenance[0].name == "field1" for e in elements)

    async def test_filter_by_source(
        self, element_service: ElementService, db_session: AsyncSession
    ):
        await element_service.create_or_merge(
            {"data_type": "string"},
            [{"source": "bids", "class": "A", "name": "x"}],
        )
        await element_service.create_or_merge(
            {"data_type": "integer"},
            [{"source": "nwb", "class": "B", "name": "y"}],
        )
        await db_session.flush()

        bids_elems, bids_total = await element_service.list_elements(source="bids")
        assert bids_total >= 1
        for e in bids_elems:
            assert any(p.source == "bids" for p in e.provenance)
