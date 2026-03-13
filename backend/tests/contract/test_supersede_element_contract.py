"""Contract tests for element supersession — T073.

Tests MUST FAIL before T075 (supersede endpoint) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestSupersedeElementContract:
    @pytest.fixture()
    async def source_and_element(self, client, curator_token):
        src_resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"supersede-src-{uuid4()}", "format": "bids"},
        )
        assert src_resp.status_code == 201
        source = src_resp.json()

        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "old-element", "data_type": "integer", "source_id": source["id"]},
        )
        assert el_resp.status_code == 201
        return source, el_resp.json()

    async def test_supersede_returns_201_with_two_objects(self, client, curator_token, source_and_element):
        """POST /elements/{id}/supersede returns 201 with new and old element."""
        source, old_element = source_and_element

        response = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Updated unit from year to month",
                "new_element_data": {
                    "name": "old-element-v2",
                    "data_type": "integer",
                    "source_id": source["id"],
                },
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "new_element" in body
        assert "superseded_element" in body
        new_el = body["new_element"]
        old_stub = body["superseded_element"]
        assert new_el["uri"] != old_element["uri"], "New element must have distinct URI"
        assert new_el.get("supersedes") == old_element["uri"], "New element must reference old URI via supersedes"
        assert old_stub["superseded_by"] == new_el["uri"], "Old element must have superseded_by = new URI"
        assert old_stub["deleted_at"] is not None, "Old element must have deleted_at set"

    async def test_supersede_missing_reason_returns_422(self, client, curator_token, source_and_element):
        """POST /elements/{id}/supersede with missing supersede_reason returns 422."""
        source, old_element = source_and_element

        response = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                # no supersede_reason
                "new_element_data": {"name": "new", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    async def test_supersede_nonexistent_element_returns_404(self, client, curator_token, source_and_element):
        """POST /elements/{id}/supersede with nonexistent element ID returns 404."""
        source, _ = source_and_element

        response = await client.post(
            f"/api/v1/elements/{uuid4()}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Test",
                "new_element_data": {"name": "new", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    async def test_supersede_already_superseded_returns_409(self, client, curator_token, source_and_element):
        """POST /elements/{id}/supersede on an already-superseded element returns 409."""
        source, old_element = source_and_element

        # First supersession
        resp1 = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "First supersession",
                "new_element_data": {"name": "new-v1", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert resp1.status_code == 201

        # Second supersession on already-superseded element
        resp2 = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Second attempt",
                "new_element_data": {"name": "new-v2", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert resp2.status_code == 409, f"Expected 409, got {resp2.status_code}"

    async def test_supersede_unauthenticated_returns_401(self, client, source_and_element):
        """POST /elements/{id}/supersede without auth returns 401."""
        source, old_element = source_and_element

        response = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            json={
                "supersede_reason": "test",
                "new_element_data": {"name": "new", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    async def test_get_new_element_has_supersedes_back_reference(self, client, curator_token, source_and_element):
        """GET /elements/{new_id} after supersession returns supersedes=old.uri (T085)."""
        source, old_element = source_and_element

        sup_resp = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "supersede_reason": "Changed unit",
                "new_element_data": {
                    "name": "new-supersedes-test",
                    "data_type": "integer",
                    "source_id": source["id"],
                },
            },
        )
        assert sup_resp.status_code == 201
        new_element_id = sup_resp.json()["new_element"]["id"]
        new_element_uri = sup_resp.json()["new_element"]["uri"]

        # GET the new element — supersedes must point to old URI
        get_new = await client.get(f"/api/v1/elements/{new_element_id}")
        assert get_new.status_code == 200
        body_new = get_new.json()
        assert body_new.get("supersedes") == old_element["uri"], (
            f"Expected supersedes={old_element['uri']}, got {body_new.get('supersedes')}"
        )
        assert body_new.get("superseded_by") is None

        # GET the old element — superseded_by must point to new URI
        get_old = await client.get(f"/api/v1/elements/{old_element['id']}")
        assert get_old.status_code == 200
        body_old = get_old.json()
        assert body_old.get("superseded_by") == new_element_uri, (
            f"Expected superseded_by={new_element_uri}, got {body_old.get('superseded_by')}"
        )
        assert body_old.get("supersedes") is None

    async def test_supersede_viewer_returns_403(self, client, viewer_token, source_and_element):
        """POST /elements/{id}/supersede with viewer role returns 403."""
        source, old_element = source_and_element

        response = await client.post(
            f"/api/v1/elements/{old_element['id']}/supersede",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "supersede_reason": "test",
                "new_element_data": {"name": "new", "data_type": "integer", "source_id": source["id"]},
            },
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
