"""Integration tests for mapping registry lifecycle — T052.

Tests MUST FAIL before T053–T062 are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def four_elements(client, curator_token):
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"mapping-int-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    elements = []
    for i in range(4):
        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": f"mi-el-{i}-{uuid4()}",
                "data_type": "integer",
                "source_id": source["id"],
                "description": f"Mapping integration element {i}",
            },
        )
        assert el_resp.status_code == 201
        elements.append(el_resp.json())

    return source, elements


class TestMappingLifecycle:
    async def test_valid_dag_registration(self, client, curator_token, four_elements):
        """Register A→B, B→C as valid DAG — no error."""
        _, elements = four_elements

        resp1 = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "linear",
                "output_element_id": elements[1]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "linear",
                "output_element_id": elements[2]["id"],
                "input_element_ids": [{"element_id": elements[1]["id"], "position": 0}],
            },
        )
        assert resp2.status_code == 201

    async def test_cycle_rejection_with_cycle_path(self, client, curator_token, four_elements):
        """C→A attempt on existing A→B→C graph returns 409 with cycle_path."""
        _, elements = four_elements

        await client.post("/api/v1/mappings", headers={"Authorization": f"Bearer {curator_token}"},
                          json={"function_type": "linear", "output_element_id": elements[1]["id"],
                                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}]})
        await client.post("/api/v1/mappings", headers={"Authorization": f"Bearer {curator_token}"},
                          json={"function_type": "linear", "output_element_id": elements[2]["id"],
                                "input_element_ids": [{"element_id": elements[1]["id"], "position": 0}]})

        cycle_resp = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"function_type": "linear", "output_element_id": elements[0]["id"],
                  "input_element_ids": [{"element_id": elements[2]["id"], "position": 0}]},
        )
        assert cycle_resp.status_code == 409
        body = cycle_resp.json()
        assert "cycle_path" in str(body)

    async def test_mapping_version_history(self, client, curator_token, four_elements):
        """PUT /mappings/{id} creates version history; URI is unchanged."""
        _, elements = four_elements

        create_resp = await client.post(
            "/api/v1/mappings",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "function_type": "identity",
                "output_element_id": elements[3]["id"],
                "input_element_ids": [{"element_id": elements[0]["id"], "position": 0}],
            },
        )
        assert create_resp.status_code == 201
        mapping = create_resp.json()

        update_resp = await client.put(
            f"/api/v1/mappings/{mapping['id']}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"description": "v2 description", "version_num": mapping["version_num"]},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["uri"] == mapping["uri"]

        history_resp = await client.get(f"/api/v1/mappings/{mapping['id']}/history")
        assert history_resp.status_code == 200
        assert len(history_resp.json()) >= 2
        # History should be ascending by version_num
        versions = history_resp.json()
        assert versions[0]["version_num"] < versions[-1]["version_num"]
