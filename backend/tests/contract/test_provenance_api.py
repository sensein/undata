"""Contract tests for upgraded PROV-O provenance endpoints — T011/T015.

TDD:
- T011 tests MUST FAIL before T012 (schema_changelog.py @context URL fix)
- T015 tests MUST FAIL before T016 (schema provenance @context URL fix)

These tests validate:
- US1: GET /elements/{id}/provenance uses correct @context URL (FR-006)
- US2: GET /schemas/{id}/provenance uses correct @context URL + wasDerivedFrom (FR-006)
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def element_with_history(client, curator_token):
    """Create a source and element, producing AuditLog / DataElementVersion rows."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-upgrade-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-el-{uuid4()}", "data_type": "string", "source_id": source_id},
    )
    assert el_resp.status_code == 201
    return el_resp.json()["id"], source_id


@pytest.fixture()
async def schema_with_changelog(client, curator_token):
    """Create a source, element, and schema so SchemaChangeLog has entries."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-schema-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    el_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"prov-el-{uuid4()}", "data_type": "string", "source_id": source_id},
    )
    assert el_resp.status_code == 201
    element_id = el_resp.json()["id"]

    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"prov-schema-{uuid4()}",
            "elements": [{"element_id": element_id, "position": 0}],
        },
    )
    assert schema_resp.status_code == 201
    return schema_resp.json()["id"], element_id


class TestElementProvenanceUpgrade:
    """T011 — GET /elements/{id}/provenance must use correct PROV-O @context (FR-006)."""

    async def test_element_provenance_correct_context_url(
        self, client, curator_token, element_with_history
    ):
        """@context MUST be 'https://www.w3.org/ns/prov.jsonld' (not the old http:// URL)."""
        element_id, _ = element_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        body = resp.json()
        assert "@context" in body, "Response must include @context"
        assert body["@context"] == "https://www.w3.org/ns/prov.jsonld", (
            f"Wrong @context URL: got {body['@context']!r}, "
            f"expected 'https://www.w3.org/ns/prov.jsonld' (FR-006)"
        )

    async def test_element_provenance_graph_has_entity_and_activity(
        self, client, curator_token, element_with_history
    ):
        """@graph must contain prov:Entity and prov:Activity nodes."""
        element_id, _ = element_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        graph = resp.json().get("@graph", [])
        types = {node.get("@type") for node in graph}
        assert any("Entity" in str(t) for t in types), f"No Entity node in graph: {types}"
        assert any("Activity" in str(t) for t in types), f"No Activity node in graph: {types}"

    async def test_element_provenance_activity_has_started_at_time(
        self, client, curator_token, element_with_history
    ):
        """Each Activity node must have prov:startedAtTime."""
        element_id, _ = element_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        graph = resp.json().get("@graph", [])
        activities = [n for n in graph if "Activity" in str(n.get("@type", ""))]
        for act in activities:
            assert "prov:startedAtTime" in act, (
                f"Activity missing prov:startedAtTime: {act}"
            )

    async def test_element_provenance_returns_ld_json_content_type(
        self, client, curator_token, element_with_history
    ):
        """Response Content-Type must be application/ld+json."""
        element_id, _ = element_with_history

        resp = await client.get(
            f"/api/v1/elements/{element_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "ld+json" in ct, f"Expected application/ld+json, got: {ct!r}"

    async def test_element_provenance_invalid_id_returns_404(self, client, curator_token):
        """GET /elements/{unknown}/provenance → 404."""
        resp = await client.get(
            f"/api/v1/elements/{uuid4()}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 404


class TestSchemaProvenanceUpgrade:
    """T015 — GET /schemas/{id}/provenance must use correct PROV-O @context + wasDerivedFrom."""

    async def test_schema_provenance_correct_context_url(
        self, client, curator_token, schema_with_changelog
    ):
        """@context MUST be 'https://www.w3.org/ns/prov.jsonld'."""
        schema_id, _ = schema_with_changelog

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        body = resp.json()
        assert "@context" in body, "Response must include @context"
        assert body["@context"] == "https://www.w3.org/ns/prov.jsonld", (
            f"Wrong @context URL: got {body['@context']!r}, "
            f"expected 'https://www.w3.org/ns/prov.jsonld' (FR-006)"
        )

    async def test_schema_provenance_graph_has_entity(
        self, client, curator_token, schema_with_changelog
    ):
        """@graph must contain at least one prov:Entity for the schema."""
        schema_id, _ = schema_with_changelog

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        graph = resp.json().get("@graph", [])
        types = {node.get("@type") for node in graph}
        assert any("Entity" in str(t) for t in types), f"No Entity node in graph: {types}"

    async def test_schema_provenance_invalid_id_returns_404(self, client, curator_token):
        """GET /schemas/{unknown}/provenance → 404."""
        resp = await client.get(
            f"/api/v1/schemas/{uuid4()}/provenance",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 404
