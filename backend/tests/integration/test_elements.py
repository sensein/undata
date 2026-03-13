"""Integration tests for data element lifecycle — T033.

Tests MUST FAIL before T034–T042 (element services + router) are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def curator_source(client, curator_token):
    resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"integration-src-{uuid4()}", "format": "bids"},
    )
    assert resp.status_code == 201
    return resp.json()


class TestElementLifecycle:
    async def test_full_element_lifecycle(self, client, curator_token, curator_source):
        """Full lifecycle: create, get, keyword search, update, history, delete."""
        source_id = curator_source["id"]

        # Create 3 elements
        created = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/elements",
                headers={"Authorization": f"Bearer {curator_token}"},
                json={
                    "name": f"participant_age_{i}",
                    "data_type": "integer",
                    "source_id": source_id,
                    "description": f"Age of participant group {i}",
                    "semantic_graph": {
                        "entities": [],
                        "unit": {"label": "year", "symbol": "yr", "external_uri": None},
                        "relations": [],
                    },
                },
            )
            assert resp.status_code == 201, f"Create {i} failed: {resp.text}"
            body = resp.json()
            assert "uri" in body
            created.append(body)

        # Get by ID
        get_resp = await client.get(f"/api/v1/elements/{created[0]['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["uri"] == created[0]["uri"]

        # Keyword search
        search_resp = await client.get("/api/v1/elements", params={"q": "participant_age"})
        assert search_resp.status_code == 200
        assert search_resp.json()["total"] >= 3

        # Update element (version bump)
        update_resp = await client.put(
            f"/api/v1/elements/{created[0]['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "participant_age_0_updated",
                "data_type": "integer",
                "version_num": created[0]["version_num"],
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["version_num"] == created[0]["version_num"] + 1

        # Version history has 2 entries
        history_resp = await client.get(f"/api/v1/elements/{created[0]['id']}/history")
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) == 2

        # Soft-delete one element
        del_resp = await client.request(
            "DELETE",
            f"/api/v1/elements/{created[2]['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"version_num": created[2]["version_num"]},
        )
        assert del_resp.status_code in (200, 204)

        # Deleted element absent from list
        list_resp = await client.get("/api/v1/elements", params={"source_id": source_id})
        ids = [e["id"] for e in list_resp.json()["items"]]
        assert created[2]["id"] not in ids

    async def test_viewer_cannot_create_element(self, client, viewer_token, curator_source):
        """Viewer gets 403 on element creation."""
        resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "viewer-test", "data_type": "string", "source_id": curator_source["id"]},
        )
        assert resp.status_code == 403

    async def test_nested_element_children(self, client, curator_token, curator_source):
        """Create parent (object type) + child; verify children in GET response."""
        source_id = curator_source["id"]

        parent_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "subject-record", "data_type": "object", "source_id": source_id},
        )
        assert parent_resp.status_code == 201
        parent = parent_resp.json()

        child_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "subject-age", "data_type": "integer", "source_id": source_id},
        )
        assert child_resp.status_code == 201
        child = child_resp.json()

        # Link child
        link_resp = await client.post(
            f"/api/v1/elements/{parent['id']}/children",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"children": [{"child_id": child["id"], "position": 0, "field_name": "age"}]},
        )
        assert link_resp.status_code in (200, 201), f"Link failed: {link_resp.text}"

        # Verify children appear in GET
        get_resp = await client.get(f"/api/v1/elements/{parent['id']}")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["children"]) == 1

    async def test_has_aliases_and_has_mappings_filters(self, client, curator_token, curator_source):
        """has_aliases=true and has_mappings=true filters return only qualifying elements (T089)."""
        source_id = curator_source["id"]

        # Create four elements: alias pair, mapping input/output, and a plain control
        el_alias_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"el-alias-{uuid4()}", "data_type": "string", "source_id": source_id},
        )
        el_target_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"el-target-{uuid4()}", "data_type": "string", "source_id": source_id},
        )
        el_mapped_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"el-mapped-{uuid4()}", "data_type": "string", "source_id": source_id},
        )
        el_plain_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"el-plain-{uuid4()}", "data_type": "string", "source_id": source_id},
        )
        assert all(
            r.status_code == 201
            for r in [el_alias_resp, el_target_resp, el_mapped_resp, el_plain_resp]
        )
        el_alias_id = el_alias_resp.json()["id"]
        el_target_id = el_target_resp.json()["id"]
        el_mapped_id = el_mapped_resp.json()["id"]
        el_plain_id = el_plain_resp.json()["id"]

        # Create alias group containing el_alias and el_target
        alias_resp = await client.post(
            "/api/v1/aliases",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"sssom_predicate": "skos:exactMatch", "element_ids": [el_alias_id, el_target_id]},
        )
        assert alias_resp.status_code == 201, f"Alias creation failed: {alias_resp.text}"

        # Create custom mapping: el_mapped → el_target (use separate output to avoid cycle with alias)
        map_out_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"el-mapout-{uuid4()}", "data_type": "string", "source_id": source_id},
        )
        assert map_out_resp.status_code == 201
        el_mapout_id = map_out_resp.json()["id"]

        map_resp = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "custom",
                "output_element_id": el_mapout_id,
                "expression_type": "custom",
                "input_element_ids": [{"element_id": el_mapped_id, "position": 0}],
            },
        )
        assert map_resp.status_code == 201, f"Mapping creation failed: {map_resp.text}"

        # has_aliases=true must include el_alias_id, exclude el_plain_id
        alias_filter = await client.get(
            "/api/v1/elements",
            params={"has_aliases": "true", "source_id": source_id},
        )
        assert alias_filter.status_code == 200
        alias_ids = [i["id"] for i in alias_filter.json()["items"]]
        assert el_alias_id in alias_ids, "el_alias should appear in has_aliases=true"
        assert el_plain_id not in alias_ids, "el_plain should be absent from has_aliases=true"

        # has_mappings=true must include el_mapped_id and el_mapout_id, exclude el_plain_id
        map_filter = await client.get(
            "/api/v1/elements",
            params={"has_mappings": "true", "source_id": source_id},
        )
        assert map_filter.status_code == 200
        mapped_ids = [i["id"] for i in map_filter.json()["items"]]
        assert el_mapped_id in mapped_ids, "el_mapped (input) should appear in has_mappings=true"
        assert el_mapout_id in mapped_ids, "el_mapout (output) should appear in has_mappings=true"
        assert el_plain_id not in mapped_ids, "el_plain should be absent from has_mappings=true"

    async def test_circular_nesting_rejected(self, client, curator_token, curator_source):
        """Circular parent-child reference returns 400."""
        source_id = curator_source["id"]

        a_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "circular-a", "data_type": "object", "source_id": source_id},
        )
        b_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "circular-b", "data_type": "object", "source_id": source_id},
        )
        assert a_resp.status_code == 201 and b_resp.status_code == 201
        a, b = a_resp.json(), b_resp.json()

        # A → B
        link1 = await client.post(
            f"/api/v1/elements/{a['id']}/children",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"children": [{"child_id": b["id"], "position": 0, "field_name": "b"}]},
        )
        assert link1.status_code in (200, 201)

        # B → A (creates cycle)
        link2 = await client.post(
            f"/api/v1/elements/{b['id']}/children",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"children": [{"child_id": a["id"], "position": 0, "field_name": "a"}]},
        )
        assert link2.status_code == 400, f"Expected 400 for circular nesting, got {link2.status_code}"
