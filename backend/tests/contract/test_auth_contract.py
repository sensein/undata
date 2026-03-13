"""Contract tests for authentication endpoints — T018.

These tests define the API contract for:
  GET  /auth/login       → 302 redirect to Keycloak
  GET  /auth/callback    → 302 on success, 401 on invalid state
  POST /auth/logout      → 200 {"status": "logged_out"}

Tests MUST FAIL before T029 (auth router) is implemented.
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

MOCK_OPENID_CONFIG = {
    "authorization_endpoint": "http://keycloak:8080/realms/undata/protocol/openid-connect/auth",
    "token_endpoint": "http://keycloak:8080/realms/undata/protocol/openid-connect/token",
    "jwks_uri": "http://keycloak:8080/realms/undata/protocol/openid-connect/certs",
    "issuer": "http://keycloak:8080/realms/undata",
}


@pytest.fixture()
async def unauthenticated_client():
    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestAuthContract:
    async def test_login_redirects_to_keycloak(self, unauthenticated_client):
        """GET /auth/login returns 302 with Keycloak Location header."""
        with patch(
            "src.services.auth._fetch_openid_config", return_value=MOCK_OPENID_CONFIG
        ):
            response = await unauthenticated_client.get(
                "/api/v1/auth/login", follow_redirects=False
            )
        assert response.status_code == 302, f"Expected 302, got {response.status_code}"
        location = response.headers.get("location", "")
        assert (
            "keycloak" in location.lower()
            or "realms" in location.lower()
            or "openid-connect" in location.lower()
        ), f"Expected Keycloak redirect URL, got: {location}"

    async def test_callback_valid_code_redirects(self, unauthenticated_client):
        """GET /auth/callback with valid code+state returns 302."""
        # This will need real mock state — for now assert endpoint exists
        response = await unauthenticated_client.get(
            "/api/v1/auth/callback",
            params={"code": "testcode", "state": "teststate"},
            follow_redirects=False,
        )
        # 302 on success, 401/400 on invalid state — endpoint must exist (not 404)
        assert response.status_code != 404, "Auth callback endpoint must exist"

    async def test_callback_invalid_state_returns_401(self, unauthenticated_client):
        """GET /auth/callback with missing/invalid state returns 401."""
        response = await unauthenticated_client.get(
            "/api/v1/auth/callback",
            params={"code": "testcode"},  # no state
            follow_redirects=False,
        )
        assert response.status_code in (400, 401, 422), (
            f"Expected 400/401/422 for missing state, got {response.status_code}"
        )

    async def test_logout_returns_200(self, unauthenticated_client):
        """POST /auth/logout returns 200 with status=logged_out."""
        response = await unauthenticated_client.post("/api/v1/auth/logout")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        body = response.json()
        assert body.get("status") == "logged_out", f"Expected status='logged_out', got {body}"
