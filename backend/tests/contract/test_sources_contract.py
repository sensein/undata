"""Contract tests for schema source endpoints — T031.

Tests MUST FAIL before T040 (sources router) is implemented.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


class TestSourcesContract:
    async def test_post_sources_returns_201_with_uuid(self, client, curator_token):
        """POST /sources returns 201 with id (UUID)."""
        response = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "test-source-001", "format": "bids", "url": "https://bids.org"},
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        body = response.json()
        assert "id" in body
        assert "name" in body
        assert body["name"] == "test-source-001"

    async def test_get_sources_returns_paginated_list(self, client):
        """GET /sources returns PaginatedList envelope."""
        response = await client.get("/api/v1/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        assert "total" in body
        assert "items" in body
        assert "limit" in body
        assert "offset" in body

    async def test_get_sources_by_name_undata_returns_one(self, client):
        """GET /sources?name=undata returns exactly one pre-seeded canonical source."""
        response = await client.get("/api/v1/sources", params={"name": "undata"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        items = body.get("items", [])
        assert len(items) == 1, f"Expected exactly 1 undata source, got {len(items)}: {items}"
        assert items[0]["format"] == "canonical"
        assert items[0]["is_active"] is True

    async def test_put_source_with_wrong_version_returns_409(self, client, curator_token):
        """PUT /sources/{id} with wrong version_num returns 409."""
        # Create a source first
        create_resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "version-conflict-test", "format": "nwb"},
        )
        assert create_resp.status_code == 201
        source_id = create_resp.json()["id"]

        # Update with wrong version_num (using 999 instead of 1)
        update_resp = await client.put(
            f"/api/v1/sources/{source_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": "version-conflict-test", "format": "nwb", "version_num": 999},
        )
        assert update_resp.status_code == 409, f"Expected 409, got {update_resp.status_code}"

    async def test_get_source_unknown_returns_404(self, client):
        """GET /sources/{id} unknown returns 404."""
        from uuid import uuid4
        response = await client.get(f"/api/v1/sources/{uuid4()}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    async def test_post_source_unauthenticated_returns_401(self, client):
        """POST /sources without auth returns 401."""
        response = await client.post("/api/v1/sources", json={"name": "no-auth-test", "format": "bids"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    async def test_post_source_viewer_returns_403(self, client, viewer_token):
        """POST /sources with viewer role returns 403."""
        response = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "viewer-test", "format": "bids"},
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
