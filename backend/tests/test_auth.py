"""Tests for authentication middleware and role enforcement.

Uses mock JWTs — does NOT require running Keycloak.
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

# RSA key pair for test JWT signing
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Generate test RSA key pair
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

PRIVATE_PEM = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
PUBLIC_PEM = _public_key.public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)


def _make_token(
    sub: str = "test-user-123",
    email: str = "curator@test.local",
    name: str = "Test Curator",
    roles: list[str] | None = None,
    expired: bool = False,
) -> str:
    """Create a signed JWT for testing."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "preferred_username": name,
        "realm_access": {"roles": roles or ["curator"]},
        "iss": "http://keycloak:8080/realms/undata",
        "aud": "undata-backend",
        "iat": now - 60,
        "exp": (now - 3600) if expired else (now + 3600),
    }
    return jwt.encode(payload, PRIVATE_PEM, algorithm="RS256")


class TestAuthMiddleware:
    """Test JWT validation and role enforcement."""

    async def test_queries_work_without_auth(self, db_session):
        """Queries should remain public — no auth required."""
        from src.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200

    async def test_auth_me_returns_401_without_token(self, db_session):
        """GET /auth/me should return 401 without a token."""
        from src.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/me")
            assert resp.status_code == 401

    async def test_expired_token_rejected(self, db_session):
        """Expired JWT should be rejected."""
        from src.auth.middleware import validate_jwt

        token = _make_token(expired=True)
        result = validate_jwt(token, PUBLIC_PEM)
        assert result is None

    async def test_valid_token_extracts_user(self, db_session):
        """Valid JWT should return user info."""
        from src.auth.middleware import validate_jwt

        token = _make_token(name="Test User", roles=["curator"])
        result = validate_jwt(token, PUBLIC_PEM)
        assert result is not None
        assert result["name"] == "Test User"
        assert "curator" in result["realm_access"]["roles"]

    async def test_role_check_curator_allowed(self, db_session):
        """Curator role should pass curator check."""
        from src.auth.dependencies import check_role

        claims = {"realm_access": {"roles": ["curator"]}}
        assert check_role(claims, "curator") is True

    async def test_role_check_viewer_denied(self, db_session):
        """Viewer role should fail curator check."""
        from src.auth.dependencies import check_role

        claims = {"realm_access": {"roles": ["viewer"]}}
        assert check_role(claims, "curator") is False

    async def test_admin_has_all_roles(self, db_session):
        """Admin should pass any role check."""
        from src.auth.dependencies import check_role

        claims = {"realm_access": {"roles": ["admin"]}}
        assert check_role(claims, "curator") is True
        assert check_role(claims, "contributor") is True
        assert check_role(claims, "admin") is True
