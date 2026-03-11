"""Contract tests for API token endpoints — T020.

Tests MUST FAIL before T027 (tokens router) is implemented.
"""

import pytest
from httpx import ASGITransport, AsyncClient


class TestTokensContract:
    async def test_post_tokens_returns_201_with_token(self, client, curator_token):
        """POST /tokens with valid session returns 201 with 64-char hex token."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"label": "my-key"},
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        body = response.json()
        assert "token" in body, "Response must include 'token' field"
        assert len(body["token"]) == 64, f"Token must be 64-char hex, got length {len(body['token'])}"

    async def test_list_tokens_does_not_include_token_field(self, client, curator_token):
        """GET /tokens response items do NOT include 'token' field."""
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        for item in items:
            assert "token" not in item, "Token field must not appear in listing response"

    async def test_delete_token_sets_revoked_at(self, client, curator_token, mock_curator_user):
        """DELETE /tokens/{id} sets revoked_at; subsequent write returns 401."""
        # Issue a new key to revoke
        issue_resp = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"label": "to-revoke"},
        )
        assert issue_resp.status_code == 201
        key_id = issue_resp.json()["id"]
        new_token = issue_resp.json()["token"]

        # Revoke it
        revoke_resp = await client.delete(
            f"/api/v1/tokens/{key_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert revoke_resp.status_code in (200, 204), f"Expected 200/204, got {revoke_resp.status_code}"

        # Attempt to use revoked token
        retry_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert retry_resp.status_code == 401, (
            f"Revoked token must return 401, got {retry_resp.status_code}"
        )
