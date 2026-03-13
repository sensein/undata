"""Contract tests for data element endpoints — T032.

Tests MUST FAIL before T041 (elements router) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestElementsContract:
    @pytest.fixture()
    async def bids_source(self, client, curator_token):
        resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"bids-{uuid4()}", "format": "bids"},
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_post_element_returns_201_with_uri(self, client, curator_token, bids_source):
        """POST /elements returns 201 DataElementResponse with uri field."""
        response = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "age",
                "data_type": "integer",
                "source_id": bids_source["id"],
                "source_local_id": "age_001",
                "semantic_graph": {
                    "entities": [{"label": "Participant", "type": "Person", "role": "subject", "external_uri": None}],
                    "property": {"label": "age", "type": "numeric", "external_uri": None},
                    "unit": {"label": "year", "symbol": "yr", "external_uri": None},
                    "relations": [],
                    "domain": "neuroscience",
                    "range_type": None,
                    "context": None,
                },
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "uri" in body, "Response must include 'uri' field"
        assert body["uri"].startswith("http"), f"URI should be an HTTP URL, got: {body['uri']}"
        assert "/elements/" in body["uri"], f"URI should contain /elements/, got: {body['uri']}"
        assert "created_by" not in body, "Response must NOT include 'created_by'"
        assert "semantic_graph" in body
        assert body["unit"] == "year", f"unit should be 'year' (from semantic_graph.unit.label), got: {body['unit']}"

    async def test_two_elements_same_name_different_source_have_distinct_uris(
        self, client, curator_token
    ):
        """Two elements with same name but different source_id have distinct URIs."""
        source1 = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"src1-{uuid4()}", "format": "bids"},
        )
        source2 = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"src2-{uuid4()}", "format": "dandi"},
        )

        el1_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "age", "data_type": "integer", "source_id": source1.json()["id"]},
        )
        el2_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "age", "data_type": "integer", "source_id": source2.json()["id"]},
        )

        assert el1_resp.status_code == 201
        assert el2_resp.status_code == 201
        assert el1_resp.json()["uri"] != el2_resp.json()["uri"], "Elements from different sources must have distinct URIs"

    async def test_bulk_create_returns_207_with_uris(self, client, curator_token, bids_source):
        """POST /elements/bulk returns 207 with succeeded list including uri per item."""
        response = await client.post(
            "/api/v1/elements/bulk",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "elements": [
                    {"name": f"el-bulk-{i}", "data_type": "string", "source_id": bids_source["id"]}
                    for i in range(3)
                ]
            },
        )
        assert response.status_code == 207, f"Expected 207, got {response.status_code}"
        body = response.json()
        assert "succeeded" in body
        for item in body["succeeded"]:
            assert "uri" in item, "Each succeeded item must have uri"

    async def test_get_elements_keyword_search(self, client, curator_token, bids_source):
        """GET /elements?q=age returns PaginatedList[DataElementSummary] with uri and unit."""
        # Create element first
        await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "age",
                "data_type": "integer",
                "source_id": bids_source["id"],
                "semantic_graph": {
                    "entities": [],
                    "unit": {"label": "year", "symbol": "yr", "external_uri": None},
                    "relations": [],
                },
            },
        )

        response = await client.get("/api/v1/elements", params={"q": "age"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        assert "items" in body
        for item in body["items"]:
            assert "uri" in item

    async def test_get_elements_unit_filter(self, client, curator_token, bids_source):
        """GET /elements?unit=year filters by unit field."""
        await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "age-unit-filter",
                "data_type": "integer",
                "source_id": bids_source["id"],
                "semantic_graph": {
                    "entities": [],
                    "unit": {"label": "year", "symbol": "yr", "external_uri": None},
                    "relations": [],
                },
            },
        )

        response = await client.get("/api/v1/elements", params={"unit": "year"})
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item.get("unit") == "year"

    async def test_put_element_increments_version_num(self, client, curator_token, bids_source):
        """PUT /elements/{id} increments version_num."""
        create_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "version-bump-test", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert create_resp.status_code == 201
        element = create_resp.json()
        original_version = element["version_num"]

        update_resp = await client.put(
            f"/api/v1/elements/{element['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "version-bump-updated", "data_type": "string", "version_num": original_version},
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        assert update_resp.json()["version_num"] == original_version + 1

    async def test_get_element_history_returns_ordered_versions(self, client, curator_token, bids_source):
        """GET /elements/{id}/history returns ordered version list."""
        create_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "history-test", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert create_resp.status_code == 201
        element = create_resp.json()

        await client.put(
            f"/api/v1/elements/{element['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "history-test-v2", "data_type": "string", "version_num": element["version_num"]},
        )

        history_resp = await client.get(f"/api/v1/elements/{element['id']}/history")
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) >= 2
        assert history[0]["version_num"] < history[-1]["version_num"]

    async def test_delete_element_sets_deleted_at(self, client, curator_token, bids_source):
        """DELETE /elements/{id} sets deleted_at and excludes element from list."""
        create_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "delete-test", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert create_resp.status_code == 201
        element = create_resp.json()

        delete_resp = await client.request(
            "DELETE",
            f"/api/v1/elements/{element['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"version_num": element["version_num"]},
        )
        assert delete_resp.status_code in (200, 204), f"Expected 200/204, got {delete_resp.status_code}"

        # Deleted element should not appear in list
        list_resp = await client.get("/api/v1/elements")
        ids_in_list = [item["id"] for item in list_resp.json()["items"]]
        assert element["id"] not in ids_in_list, "Deleted element should be excluded from list"

    async def test_unauthenticated_write_returns_401(self, client, bids_source):
        """POST /elements without auth returns 401."""
        response = await client.post(
            "/api/v1/elements",
            json={"name": "no-auth", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert response.status_code == 401

    async def test_element_response_includes_enriched_fields(self, client, curator_token, bids_source):
        """DataElementResponse includes alias_groups, mappings_as_input, mappings_as_output, supersedes (T084)."""
        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "enriched-field-test", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "alias_groups" in body, "alias_groups field must be present"
        assert "mappings_as_input" in body, "mappings_as_input field must be present"
        assert "mappings_as_output" in body, "mappings_as_output field must be present"
        assert "supersedes" in body, "supersedes field must be present"
        assert isinstance(body["alias_groups"], list)
        assert isinstance(body["mappings_as_input"], list)
        assert isinstance(body["mappings_as_output"], list)
        assert body["alias_groups"] == []
        assert body["mappings_as_input"] == []
        assert body["mappings_as_output"] == []
        assert body["supersedes"] is None

    async def test_semantic_duplicate_returns_409(self, client, curator_token):
        """POST /elements with undata source and duplicate semantic_graph fingerprint → 409 (T087)."""
        src_resp = await client.get("/api/v1/sources", params={"name": "undata"})
        assert src_resp.status_code == 200
        undata_id = src_resp.json()["items"][0]["id"]

        sg = {
            "entities": [{"label": "mouse", "type": "organism", "role": "subject"}],
            "property": {"label": "body_weight", "type": "physical"},
            "unit": {"label": "gram", "symbol": "g"},
            "relations": [],
        }

        r1 = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "body_weight_mouse",
                "data_type": "number",
                "source_id": undata_id,
                "semantic_graph": sg,
            },
        )
        assert r1.status_code == 201, f"First element creation failed: {r1.text}"

        # Identical fingerprint — must fail
        r2 = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "body_weight_mouse_dup",
                "data_type": "number",
                "source_id": undata_id,
                "semantic_graph": sg,
            },
        )
        assert r2.status_code == 409, f"Expected 409 for semantic duplicate, got {r2.status_code}: {r2.text}"
        detail = r2.json().get("detail", {})
        assert detail.get("error") == "semantic_duplicate"
        assert "existing_id" in detail
        assert "existing_uri" in detail

        # Different unit → distinct fingerprint → must succeed
        r3 = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "body_weight_mouse_oz",
                "data_type": "number",
                "source_id": undata_id,
                "semantic_graph": {**sg, "unit": {"label": "ounce", "symbol": "oz"}},
            },
        )
        assert r3.status_code == 201, f"Element with distinct unit should succeed, got {r3.status_code}: {r3.text}"

    async def test_object_type_element_includes_children(self, client, curator_token, bids_source):
        """GET /elements/{id} for object-type element includes children list."""
        # Create parent (object type)
        parent_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "subject-info", "data_type": "object", "source_id": bids_source["id"]},
        )
        assert parent_resp.status_code == 201
        parent = parent_resp.json()

        # Create child element
        child_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "child-field", "data_type": "string", "source_id": bids_source["id"]},
        )
        assert child_resp.status_code == 201
        child = child_resp.json()

        # Link child to parent
        link_resp = await client.post(
            f"/api/v1/elements/{parent['id']}/children",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"children": [{"child_id": child["id"], "position": 0, "field_name": "child_field"}]},
        )
        assert link_resp.status_code in (200, 201), f"Expected 200/201, got {link_resp.status_code}: {link_resp.text}"

        # GET parent should include children
        get_resp = await client.get(f"/api/v1/elements/{parent['id']}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "children" in body
        assert len(body["children"]) >= 1
