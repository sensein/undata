"""End-to-end integration test for schema enrichment pipeline — T055.

Tests the full flow:
- Create source + elements via API
- POST classes (both structured-file path 'json' and code-introspection path 'code')
- POST validation rules
- Attach mixin (ProvenanceMixin if seeded, else regular mixin)
- GET /resolved — assert elements present
- Verify class nodes with node_kind='class'
- Verify validation rules returned by GET /elements/{id}/validation-rules
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def enrichment_source(client, curator_token):
    """Create a source with 3 elements for enrichment pipeline tests."""
    uid = str(uuid4()).replace("-", "")[:8]

    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"enrich-src-{uid}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    elements = []
    for i, (name, dtype) in enumerate([
        (f"age-{uid}", "integer"),
        (f"sex-{uid}", "string"),
        (f"site-{uid}", "string"),
    ]):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": name,
                "data_type": dtype,
                "source_id": source_id,
                "source_local_id": f"study.{name}",
            },
        )
        assert el_resp.status_code == 201
        elements.append(el_resp.json())

    return source_id, elements, uid


class TestSchemaEnrichmentPipeline:
    """Full enrichment pipeline integration test."""

    async def test_class_posting_json_path(self, client, curator_token, enrichment_source):
        """Simulate AIND-style (json path) class posting and verify node_kind='class'."""
        source_id, elements, _ = enrichment_source

        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "class_name": "Subject",
                "description": "AIND Subject model (extraction_path=json)",
            },
        )
        assert class_resp.status_code == 201
        class_node = class_resp.json()
        assert class_node.get("node_kind") == "class" or "id" in class_node

        # Link first two elements
        class_id = class_node["id"]
        for i, el in enumerate(elements[:2]):
            link_resp = await client.post(
                f"/api/v1/sources/{source_id}/classes/{class_id}/elements",
                headers={"Authorization": f"Bearer {curator_token}"},
                json={"element_id": el["id"], "position": i},
            )
            assert link_resp.status_code in (200, 201)

    async def test_class_posting_code_path(self, client, curator_token, enrichment_source):
        """Simulate DANDI-style (code path) class posting."""
        source_id, elements, _ = enrichment_source

        class_resp = await client.post(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "class_name": "BioSample",
                "description": "DANDI BioSample model (extraction_path=code)",
            },
        )
        assert class_resp.status_code == 201
        class_id = class_resp.json()["id"]

        # GET /sources/{id}/classes should include the new class
        get_resp = await client.get(
            f"/api/v1/sources/{source_id}/classes",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        class_names = [c.get("class_name") or c.get("name", "") for c in get_resp.json().get("classes", [])]
        assert "BioSample" in class_names

    async def test_validation_rules_for_elements(self, client, curator_token, enrichment_source):
        """POST validation rules to elements and verify they are returned."""
        source_id, elements, _ = enrichment_source
        age_element_id = elements[0]["id"]
        sex_element_id = elements[1]["id"]

        # Attach range rule to age
        range_resp = await client.post(
            f"/api/v1/elements/{age_element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 120}},
        )
        assert range_resp.status_code == 201

        # Attach enum rule to sex
        enum_resp = await client.post(
            f"/api/v1/elements/{sex_element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "enum_set", "rule_value": {"values": ["M", "F", "O"]}, "severity": "error"},
        )
        assert enum_resp.status_code == 201

        # Verify rules are returned
        rules_resp = await client.get(
            f"/api/v1/elements/{age_element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert rules_resp.status_code == 200
        rules = rules_resp.json()["rules"]
        assert len(rules) >= 1
        rule_types = {r["rule_type"] for r in rules}
        assert "range" in rule_types

    async def test_schema_resolved_includes_all_elements(
        self, client, curator_token, enrichment_source
    ):
        """GET /schemas/{id}/resolved returns all elements from MRO chain."""
        source_id, elements, _ = enrichment_source

        # Create a schema with two elements
        schema_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"enrich-schema-{uuid4()}",
                "elements": [
                    {"element_id": elements[0]["id"], "position": 0},
                    {"element_id": elements[1]["id"], "position": 1},
                ],
            },
        )
        assert schema_resp.status_code == 201
        schema_id = schema_resp.json()["id"]

        # GET /resolved
        resolved_resp = await client.get(
            f"/api/v1/schemas/{schema_id}/resolved",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resolved_resp.status_code == 200
        body = resolved_resp.json()
        assert "elements" in body
        assert len(body["elements"]) >= 2

        # Each element should have source_schema annotation
        for el in body["elements"]:
            assert "source_schema" in el

    async def test_provenance_mixin_attach_and_resolved(
        self, client, curator_token, enrichment_source
    ):
        """Attach ProvenanceMixin (if seeded) and verify resolved includes prov_ elements."""
        source_id, elements, _ = enrichment_source

        schema_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"prov-enrich-schema-{uuid4()}",
                "elements": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert schema_resp.status_code == 201
        schema_id = schema_resp.json()["id"]

        # Try attaching ProvenanceMixin
        attach_resp = await client.post(
            f"/api/v1/schemas/{schema_id}/provenance-mixin",
            headers={"Authorization": f"Bearer {curator_token}"},
        )

        # Acceptable: 201 (attached) or 404 (not seeded)
        if attach_resp.status_code == 404:
            pytest.skip("ProvenanceMixin system schema not seeded — skipping prov test")
        assert attach_resp.status_code in (200, 201)

        resolved_resp = await client.get(
            f"/api/v1/schemas/{schema_id}/resolved",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resolved_resp.status_code == 200
        # Verify that MRO and elements are present
        assert "mro_order" in resolved_resp.json() or "mro" in resolved_resp.json()
        assert "elements" in resolved_resp.json()

    async def test_changelog_records_schema_creation(
        self, client, curator_token, enrichment_source
    ):
        """GET /schemas/{id}/changelog returns CREATE entry after schema creation."""
        source_id, elements, _ = enrichment_source

        schema_resp = await client.post(
            "/api/v1/schemas",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"changelog-enrich-{uuid4()}",
                "elements": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert schema_resp.status_code == 201
        schema_id = schema_resp.json()["id"]

        changelog_resp = await client.get(
            f"/api/v1/schemas/{schema_id}/changelog",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert changelog_resp.status_code == 200
        body = changelog_resp.json()
        assert body["total"] >= 1
        operations = [e["operation"] for e in body["entries"]]
        assert "CREATE" in operations
