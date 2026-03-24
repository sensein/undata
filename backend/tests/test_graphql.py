"""Tests for the GraphQL API."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.db.session import Base, engine
from src.main import app
from src.models.db import Element, Value  # noqa: F401


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_browse_elements_empty(client):
    resp = await client.post(
        "/graphql",
        json={
            "query": "{ browseElements(first: 10) { totalCount edges { node { dataType } } } }"
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["browseElements"]["totalCount"] == 0
    assert data["browseElements"]["edges"] == []


@pytest.mark.asyncio
async def test_browse_elements_with_data(client):
    """Insert an element and query it."""
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                Element(
                    file_name="test_abc123.yaml",
                    data_type="string",
                    semantic={"data_type": "string"},
                    provenance=[{"source": "test", "class": "T", "name": "test_field"}],
                    ontology_annotations=[],
                )
            )

    resp = await client.post(
        "/graphql",
        json={
            "query": '{ browseElements(first: 10) { totalCount edges { node { dataType fileName provenance { source name } } } } }'
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["browseElements"]["totalCount"] == 1
    node = data["browseElements"]["edges"][0]["node"]
    assert node["dataType"] == "string"
    assert node["provenance"][0]["source"] == "test"


@pytest.mark.asyncio
async def test_run_summaries_empty(client):
    resp = await client.post(
        "/graphql",
        json={"query": "{ runSummaries { runId source } }"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["runSummaries"] == []
