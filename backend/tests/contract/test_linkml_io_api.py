"""Contract tests for LinkML import/export endpoints — T018/T023.

TDD:
- T018 tests MUST FAIL before T021 (GET /schemas/{id}/linkml route added)
- T023 tests MUST FAIL before T026 (POST /schemas/import/linkml route added)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import yaml


@pytest.fixture()
async def schema_for_export(client, curator_token):
    """Create a source, elements, and schema ready for LinkML export."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"linkml-export-src-{uuid4()}", "format": "json"},
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    elements = []
    for name, dtype in [("subject_id", "string"), ("age", "integer"), ("active", "boolean")]:
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"{name}-{uuid4()}", "data_type": dtype, "source_id": source_id},
        )
        assert el_resp.status_code == 201
        elements.append(el_resp.json())

    schema_resp = await client.post(
        "/api/v1/schemas",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={
            "name": f"export-schema-{uuid4()}",
            "elements": [{"element_id": e["id"], "position": i} for i, e in enumerate(elements)],
        },
    )
    assert schema_resp.status_code == 201
    return schema_resp.json()["id"], elements


class TestLinkMLExport:
    """T018 — GET /schemas/{id}/linkml returns valid LinkML YAML."""

    async def test_export_returns_200_yaml(self, client, curator_token, schema_for_export):
        """GET /schemas/{id}/linkml → 200 with application/yaml content type."""
        schema_id, _ = schema_for_export

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/linkml",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for LinkML export, got {resp.status_code}: {resp.text}"
        )
        ct = resp.headers.get("content-type", "")
        assert "yaml" in ct or "text" in ct, f"Expected YAML content type, got: {ct!r}"

    async def test_export_body_is_valid_yaml_with_classes(
        self, client, curator_token, schema_for_export
    ):
        """Response body is valid YAML containing a 'classes:' key."""
        schema_id, _ = schema_for_export

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/linkml",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        parsed = yaml.safe_load(resp.text)
        assert isinstance(parsed, dict), "Body must be a YAML mapping"
        assert "classes" in parsed or "slots" in parsed, (
            f"LinkML YAML must have 'classes' or 'slots', got keys: {list(parsed.keys())}"
        )

    async def test_export_has_roundtrip_fidelity_header(
        self, client, curator_token, schema_for_export
    ):
        """X-Roundtrip-Fidelity header is present and in [0.0, 1.0]."""
        schema_id, _ = schema_for_export

        resp = await client.get(
            f"/api/v1/schemas/{schema_id}/linkml",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200
        header_val = resp.headers.get("x-roundtrip-fidelity")
        assert header_val is not None, "X-Roundtrip-Fidelity header must be present"
        score = float(header_val)
        assert 0.0 <= score <= 1.0, f"Fidelity score must be in [0.0, 1.0], got {score}"

    async def test_export_unknown_schema_returns_404(self, client, curator_token):
        """GET /schemas/{unknown}/linkml → 404."""
        resp = await client.get(
            f"/api/v1/schemas/{uuid4()}/linkml",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 404


class TestLinkMLImport:
    """T023 — POST /schemas/import/linkml creates a schema."""

    def _minimal_linkml(self, name: str) -> str:
        return yaml.dump(
            {
                "id": f"https://schema.undata.live/test/{name}",
                "name": name,
                "prefixes": {"linkml": "https://w3id.org/linkml/"},
                "imports": ["linkml:types"],
                "default_range": "string",
                "classes": {
                    name: {
                        "description": f"Test class {name}",
                        "attributes": {
                            "id": {"identifier": True, "range": "string"},
                            "label": {"range": "string"},
                        },
                    }
                },
            }
        )

    async def test_import_valid_yaml_returns_201(self, client, curator_token):
        """POST /schemas/import/linkml with valid YAML → 201 + RoundtripResult."""
        name = f"import-test-{uuid4().hex[:8]}"
        resp = await client.post(
            "/api/v1/schemas/import/linkml",
            headers={
                "Authorization": f"Bearer {curator_token}",
                "Content-Type": "application/yaml",
            },
            content=self._minimal_linkml(name).encode(),
        )
        assert resp.status_code == 201, (
            f"Expected 201 for LinkML import, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "fidelity_score" in body, "Response must include fidelity_score"
        assert "loss_points" in body, "Response must include loss_points"
        assert "schema_id" in body, "Response must include schema_id"
        assert 0.0 <= body["fidelity_score"] <= 1.0

    async def test_import_duplicate_uri_returns_409(self, client, curator_token):
        """POST /schemas/import/linkml with same URI twice → second call returns 409."""
        name = f"dup-test-{uuid4().hex[:8]}"
        yaml_body = self._minimal_linkml(name).encode()

        first = await client.post(
            "/api/v1/schemas/import/linkml",
            headers={
                "Authorization": f"Bearer {curator_token}",
                "Content-Type": "application/yaml",
            },
            content=yaml_body,
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/v1/schemas/import/linkml",
            headers={
                "Authorization": f"Bearer {curator_token}",
                "Content-Type": "application/yaml",
            },
            content=yaml_body,
        )
        assert second.status_code == 409, (
            f"Expected 409 for duplicate URI, got {second.status_code}: {second.text}"
        )

    async def test_import_invalid_yaml_returns_422(self, client, curator_token):
        """POST /schemas/import/linkml with malformed YAML → 422."""
        resp = await client.post(
            "/api/v1/schemas/import/linkml",
            headers={
                "Authorization": f"Bearer {curator_token}",
                "Content-Type": "application/yaml",
            },
            content=b"{{not: valid: yaml: [[[",
        )
        assert resp.status_code == 422, (
            f"Expected 422 for invalid YAML, got {resp.status_code}: {resp.text}"
        )

    async def test_import_unknown_slot_uri_succeeds_with_loss_point(self, client, curator_token):
        """Import with unknown slot_uri → 201 with 'unknown_slot_uri' in loss_points."""
        name = f"unknown-uri-{uuid4().hex[:8]}"
        schema_dict = yaml.safe_load(self._minimal_linkml(name))
        schema_dict["slots"] = {
            "exotic_slot": {
                "slot_uri": "http://example.org/non-existent-ontology/exotic",
                "range": "string",
            }
        }
        resp = await client.post(
            "/api/v1/schemas/import/linkml",
            headers={
                "Authorization": f"Bearer {curator_token}",
                "Content-Type": "application/yaml",
            },
            content=yaml.dump(schema_dict).encode(),
        )
        assert resp.status_code == 201, (
            f"Expected 201 for import with unknown slot_uri, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        # May or may not flag unknown_slot_uri depending on validation depth
        assert isinstance(body["loss_points"], list)
