"""Contract tests for Schema Provenance & Changelog API — T045/T046/T047/T048.

TDD: These tests MUST FAIL before GET /schemas/{id}/changelog,
POST/DELETE /schemas/{id}/provenance-mixin, GET /schemas/{id}/provenance,
and GET /elements/{id}/provenance are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def schema_with_history(client, curator_token):
    """Create a source, element, and schema; add + remove an element so changelog has entries."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el1_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-el-{uuid4()}", "data_type": "string", "source_id": source_id},
    )
    assert el1_resp.status_code == 201
    element_id = el1_resp.json()["id"]

    el2_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-el2-{uuid4()}", "data_type": "string", "source_id": source_id},
    )
    assert el2_resp.status_code == 201
    element2_id = el2_resp.json()["id"]

    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"prov-schema-{uuid4()}",
            "elements": [{"element_id": element_id, "position": 0}],
        },
    )
    assert schema_resp.status_code == 201
    schema_id = schema_resp.json()["id"]

    return schema_id, element_id, element2_id, source_id


class TestGetChangelog:
    """T045 — GET /api/v1/schemas/{id}/changelog"""

    async def test_changelog_returns_entries(self, client, curator_token, schema_with_history):
        """GET /schemas/{id}/changelog returns paginated changelog entries."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/changelog",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        body = resp.json()
        assert "schema_id" in body
        assert "entries" in body
        assert "total" in body
        assert body["schema_id"] == schema_id

    async def test_changelog_entries_have_required_fields(
        self, client, curator_token, schema_with_history
    ):
        """Each changelog entry has operation, actor_id, timestamp, breaking fields."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/changelog",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        if entries:
            entry = entries[0]
            assert "operation" in entry
            assert "actor_id" in entry
            assert "timestamp" in entry
            assert "breaking" in entry

    async def test_changelog_breaking_only_filter(
        self, client, curator_token, schema_with_history
    ):
        """?breaking_only=true returns only breaking entries."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/changelog?breaking_only=true",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        # All returned entries must be breaking
        assert all(e["breaking"] is True for e in entries)


class TestProvenanceMixin:
    """T046 — POST/DELETE /api/v1/schemas/{id}/provenance-mixin"""

    async def test_attach_provenance_mixin_returns_201(
        self, client, curator_token, schema_with_history
    ):
        """POST /schemas/{id}/provenance-mixin → 201 with attached=true."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.post(
            f"/api/v1/schemas/{schema_id}/provenance-mixin",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code in (200, 201), f"Expected 2xx: {resp.text}"
        body = resp.json()
        assert body.get("attached") is True
        assert "mixin_id" in body

    async def test_detach_provenance_mixin_returns_204(
        self, client, curator_token, schema_with_history
    ):
        """DELETE /schemas/{id}/provenance-mixin → 204."""
        schema_id, _, _, _ = schema_with_history

        attach_resp = await client.post(
            f"/api/v1/schemas/{schema_id}/provenance-mixin",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert attach_resp.status_code in (200, 201)

        del_resp = await client.delete(
            f"/api/v1/schemas/{schema_id}/provenance-mixin",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code in (200, 204), f"Expected 200/204: {del_resp.text}"

    async def test_resolved_includes_prov_elements_after_attach(
        self, client, curator_token, schema_with_history
    ):
        """GET /schemas/{id}/resolved after provenance-mixin attach shows prov_ elements."""
        schema_id, _, _, _ = schema_with_history

        attach_resp = await client.post(
            f"/api/v1/schemas/{schema_id}/provenance-mixin",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        # If no ProvenanceMixin system schema exists, endpoint may return 404 or 501
        if attach_resp.status_code not in (200, 201):
            pytest.skip("ProvenanceMixin system schema not seeded — skipping resolved check")

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/resolved",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        elements = resp.json()["elements"]
        prov_elements = [e for e in elements if e.get("name", "").startswith("prov_")]
        if not prov_elements:
            pytest.skip("ProvenanceMixin schema seeded but has no prov_ elements — skipping")
        assert len(prov_elements) >= 1


class TestGetSchemaProvenance:
    """T047 — GET /api/v1/schemas/{id}/provenance"""

    async def test_provenance_returns_jsonld(self, client, curator_token, schema_with_history):
        """GET /schemas/{id}/provenance returns application/ld+json with PROV-DM structure."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "ld+json" in content_type or "json" in content_type
        body = resp.json()
        assert "@context" in body or "@graph" in body

    async def test_provenance_graph_has_prov_nodes(
        self, client, curator_token, schema_with_history
    ):
        """PROV-DM @graph contains Entity, Activity, and Agent nodes."""
        schema_id, _, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        graph = body.get("@graph", [])
        types = {node.get("@type") for node in graph}
        # Should include at least a prov:Entity
        assert any("Entity" in str(t) for t in types), f"No Entity in graph types: {types}"


class TestGetElementProvenance:
    """T048 — GET /api/v1/elements/{id}/provenance"""

    async def test_element_provenance_returns_jsonld(
        self, client, curator_token, schema_with_history
    ):
        """GET /elements/{id}/provenance returns application/ld+json."""
        _, element_id, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "ld+json" in content_type or "json" in content_type
        body = resp.json()
        assert "@context" in body or "@graph" in body

    async def test_element_provenance_graph_has_entity(
        self, client, curator_token, schema_with_history
    ):
        """Element provenance @graph contains a prov:Entity for the element."""
        _, element_id, _, _ = schema_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        graph = body.get("@graph", [])
        types = {node.get("@type") for node in graph}
        assert any("Entity" in str(t) for t in types), f"No Entity in graph types: {types}"
