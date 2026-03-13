"""Contract tests for /units endpoints — T095.

Tests MUST FAIL before T097-T100 (UnitResolutionService + /units router) are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def source_with_units(client, curator_token):
    """Create a source and elements with unit information."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"unit-test-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    # Create element with resolvable unit
    el1_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"weight_{uuid4().hex[:6]}",
            "data_type": "number",
            "source_id": source["id"],
            "semantic_graph": {
                "entities": [],
                "unit": {"label": "kilogram", "symbol": "kg"},
                "relations": [],
            },
        },
    )
    assert el1_resp.status_code == 201

    # Create element with unresolvable unit
    el2_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"mystery_{uuid4().hex[:6]}",
            "data_type": "number",
            "source_id": source["id"],
            "semantic_graph": {
                "entities": [],
                "unit": {"label": "foobarunit_xyz", "symbol": "fbz"},
                "relations": [],
            },
        },
    )
    assert el2_resp.status_code == 201

    return {"source": source, "el1": el1_resp.json(), "el2": el2_resp.json()}


class TestUnitsContract:
    async def test_get_units_returns_paginated_list(self, client, source_with_units):
        """GET /units returns 200 with PaginatedList envelope."""
        resp = await client.get("/api/v1/units")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    async def test_get_units_item_shape(self, client, source_with_units):
        """Each unit item has required fields."""
        resp = await client.get("/api/v1/units", params={"limit": 100})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) >= 1, "Should have at least one unit from seeded elements"

        for item in body["items"]:
            assert "qudt_unresolvable" in item, f"Missing qudt_unresolvable: {item}"
            assert "element_count" in item, f"Missing element_count: {item}"
            assert isinstance(item["element_count"], int)
            assert item["element_count"] >= 1
            # cmixf_valid is bool or null
            assert item.get("cmixf_valid") is None or isinstance(item["cmixf_valid"], bool)
            # qudt_uri is str or null
            assert item.get("qudt_uri") is None or isinstance(item["qudt_uri"], str)

    async def test_get_units_pagination(self, client, source_with_units):
        """GET /units?limit=1 respects pagination."""
        resp = await client.get("/api/v1/units", params={"limit": 1})
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 1
        assert len(body["items"]) <= 1

    async def test_get_units_unauthenticated(self, client):
        """GET /units is a read-only endpoint — no auth required."""
        resp = await client.get("/api/v1/units")
        assert resp.status_code == 200

    async def test_get_units_unresolvable_returns_paginated_list(self, client, source_with_units):
        """GET /units/unresolvable returns 200 with PaginatedList."""
        resp = await client.get("/api/v1/units/unresolvable")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "total" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    async def test_get_units_unresolvable_only_unresolvable(self, client, source_with_units):
        """GET /units/unresolvable returns only items with qudt_unresolvable=true."""
        resp = await client.get("/api/v1/units/unresolvable")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["qudt_unresolvable"] is True, (
                f"All items in /units/unresolvable must have qudt_unresolvable=true, got: {item}"
            )

    async def test_get_units_unresolvable_unauthenticated(self, client):
        """GET /units/unresolvable is a read-only endpoint — no auth required."""
        resp = await client.get("/api/v1/units/unresolvable")
        assert resp.status_code == 200

    async def test_element_create_enriches_unit(self, client, curator_token):
        """POST /elements enriches semantic_graph.unit with cmixf_valid and qudt_unresolvable."""
        src_resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"enrich-src-{uuid4()}", "format": "bids"},
        )
        assert src_resp.status_code == 201

        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"weight_{uuid4().hex[:6]}",
                "data_type": "number",
                "source_id": src_resp.json()["id"],
                "semantic_graph": {
                    "entities": [],
                    "unit": {"label": "kilogram", "symbol": "kg"},
                    "relations": [],
                },
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        unit = body["semantic_graph"]["unit"]
        assert "cmixf_valid" in unit, f"cmixf_valid missing from unit: {unit}"
        assert "qudt_unresolvable" in unit, f"qudt_unresolvable missing from unit: {unit}"
        assert isinstance(unit["cmixf_valid"], bool)
        assert isinstance(unit["qudt_unresolvable"], bool)
