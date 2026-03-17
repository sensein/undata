"""Tests for content-addressed element API endpoints."""

import pytest
from httpx import AsyncClient


class TestPostElement:
    async def test_create_returns_201(self, client: AsyncClient):
        body = {
            "semantic": {"data_type": "integer", "ontology_term": "http://example.org/age"},
            "provenance": [{"source": "bids", "class": "Participant", "name": "age"}],
        }
        resp = await client.post("/api/v1/elements", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert "uri" in data
        assert data["uri"].startswith("https://schema.undata.live/elements/age_")
        assert data["semantic"]["data_type"] == "integer"
        assert len(data["provenance"]) == 1

    async def test_same_semantic_returns_200_merges(self, client: AsyncClient):
        semantic = {"data_type": "string", "ontology_term": "http://example.org/test_merge"}
        body1 = {"semantic": semantic, "provenance": [{"source": "a", "class": "A", "name": "f"}]}
        body2 = {"semantic": semantic, "provenance": [{"source": "b", "class": "B", "name": "f"}]}

        resp1 = await client.post("/api/v1/elements", json=body1)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/elements", json=body2)
        assert resp2.status_code == 200
        assert resp1.json()["uri"] == resp2.json()["uri"]
        assert len(resp2.json()["provenance"]) == 2


class TestGetElements:
    async def test_list_elements(self, client: AsyncClient):
        # Create one first
        await client.post(
            "/api/v1/elements",
            json={
                "semantic": {"data_type": "boolean"},
                "provenance": [{"source": "test", "class": "T", "name": "flag"}],
            },
        )
        resp = await client.get("/api/v1/elements")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_filter_by_source(self, client: AsyncClient):
        await client.post(
            "/api/v1/elements",
            json={
                "semantic": {"data_type": "string", "ontology_term": "http://example.org/src_filter"},
                "provenance": [{"source": "only_this", "class": "X", "name": "z"}],
            },
        )
        resp = await client.get("/api/v1/elements", params={"source": "only_this"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert any(p["source"] == "only_this" for p in item["provenance"])

    async def test_get_by_uri(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/v1/elements",
            json={
                "semantic": {"data_type": "float", "unit": "meter"},
                "provenance": [{"source": "test", "class": "T", "name": "height"}],
            },
        )
        uri = create_resp.json()["uri"]
        resp = await client.get(f"/api/v1/elements/{uri}")
        assert resp.status_code == 200
        assert resp.json()["uri"] == uri

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/v1/elements/https://schema.undata.live/elements/nonexistent_000000")
        assert resp.status_code == 404
