"""Integration tests for OIDC + API key auth flow — T022.

Full mock OIDC flow using httpx against the test app.
Tests MUST FAIL before T023–T030 (auth services + routers) are implemented.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

MOCK_OPENID_CONFIG = {
    "authorization_endpoint": "http://keycloak:8080/realms/undata/protocol/openid-connect/auth",
    "token_endpoint": "http://keycloak:8080/realms/undata/protocol/openid-connect/token",
    "jwks_uri": "http://keycloak:8080/realms/undata/protocol/openid-connect/certs",
    "issuer": "http://keycloak:8080/realms/undata",
}


class TestAuthIntegration:
    """Full OIDC mock flow integration tests."""

    async def test_login_initiates_oidc_flow(self):
        """GET /auth/login redirects to Keycloak authorization URL."""
        from src.main import app

        with patch(
            "src.services.auth._fetch_openid_config", return_value=MOCK_OPENID_CONFIG
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/v1/auth/login", follow_redirects=False)

        assert response.status_code == 302, f"Expected 302, got {response.status_code}"

    async def test_token_issuance_and_validation(self, client, mock_curator_user, curator_token):
        """Issued token authenticates successfully on protected endpoint."""
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    async def test_token_revocation_causes_401(self, client, mock_curator_user, curator_token):
        """After revoking a token, subsequent calls return 401."""
        # Issue a second token to revoke
        issue_resp = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"label": "revoke-test"},
        )
        assert issue_resp.status_code == 201
        second_token = issue_resp.json()["token"]
        key_id = issue_resp.json()["id"]

        # Confirm it works
        ok_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {second_token}"},
        )
        assert ok_resp.status_code == 200

        # Revoke
        revoke_resp = await client.delete(
            f"/api/v1/tokens/{key_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert revoke_resp.status_code in (200, 204)

        # Now 401
        fail_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {second_token}"},
        )
        assert fail_resp.status_code == 401

    async def test_viewer_cannot_write_elements(self, client, viewer_token):
        """Viewer role receives 403 on element creation."""
        response = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "semantic": {"data_type": "integer"},
                "provenance": [{"source": "test", "class": "Test", "name": "test_var"}],
            },
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
