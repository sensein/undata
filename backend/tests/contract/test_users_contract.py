"""Contract tests for user profile endpoints — T019.

Tests MUST FAIL before T028 (users router) is implemented.
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
async def unauthenticated_client():
    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestUsersContract:
    async def test_get_me_without_token_returns_401(self, unauthenticated_client):
        """GET /users/me without token returns 401."""
        response = await unauthenticated_client.get("/api/v1/users/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    async def test_get_me_with_valid_token_returns_user_profile(self, client, curator_token):
        """GET /users/me with valid curator token returns UserProfile shape."""
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        assert "id" in body
        assert "email" in body
        assert "roles" in body
        assert "source_memberships" in body

    async def test_put_roles_by_non_admin_returns_403(self, client, curator_token, mock_curator_user):
        """PUT /users/{id}/roles by non-admin returns 403."""
        response = await client.put(
            f"/api/v1/users/{mock_curator_user.id}/roles",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"roles": ["admin"]},
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    async def test_list_users_by_viewer_returns_403(self, client, viewer_token):
        """GET /users by viewer returns 403."""
        response = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
