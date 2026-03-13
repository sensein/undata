"""AuthService — OIDC login, callback handling, session signing."""

from __future__ import annotations

from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import get_logger
from src.models.db import UserProfile
from src.services.users import UserService

logger = get_logger(__name__)

# Module-level JWKS cache: keycloak_realm → {kid: public_key}
_jwks_cache: dict[str, Any] = {}


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="session")


def _openid_config_url() -> str:
    return (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/.well-known/openid-configuration"
    )


async def _fetch_openid_config() -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(_openid_config_url(), timeout=10)
        resp.raise_for_status()
        return resp.json()


async def _fetch_jwks(jwks_uri: str) -> dict[str, Any]:
    cache_key = f"jwks:{jwks_uri}"
    if cache_key in _jwks_cache:
        return _jwks_cache[cache_key]

    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_uri, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()

    _jwks_cache[cache_key] = jwks
    return jwks


class AuthService:
    @staticmethod
    async def get_authorization_url(provider_hint: str | None = None) -> tuple[str, str]:
        """Construct the Keycloak OIDC authorization URL.

        Returns:
            (authorization_url, state) — state must be stored in session cookie.
        """
        config = await _fetch_openid_config()
        authorization_endpoint = config["authorization_endpoint"]

        client = AsyncOAuth2Client(
            client_id=settings.keycloak_client_id,
            redirect_uri=f"{settings.undata_base_url}/api/v1/auth/callback",
        )
        url, state = client.create_authorization_url(
            authorization_endpoint,
            scope="openid email profile",
        )
        return url, state

    @staticmethod
    async def handle_callback(
        session: AsyncSession,
        code: str,
        state: str,
        stored_state: str,
    ) -> UserProfile:
        """Exchange authorization code for tokens and upsert UserProfile.

        Args:
            session: Active DB session.
            code: Authorization code from Keycloak.
            state: State from callback query params.
            stored_state: State stored in session cookie (CSRF check).

        Returns:
            Upserted UserProfile.

        Raises:
            ValueError: On state mismatch or invalid token.
        """
        if state != stored_state:
            raise ValueError("State mismatch — possible CSRF attack")

        config = await _fetch_openid_config()
        token_endpoint = config["token_endpoint"]
        jwks_uri = config["jwks_uri"]

        client = AsyncOAuth2Client(
            client_id=settings.keycloak_client_id,
            client_secret=settings.keycloak_client_secret,
            redirect_uri=f"{settings.undata_base_url}/api/v1/auth/callback",
        )
        token_response = await client.fetch_token(
            token_endpoint,
            code=code,
            grant_type="authorization_code",
        )

        # Validate JWT (RS256) against JWKS
        jwks = await _fetch_jwks(jwks_uri)
        from authlib.jose import JsonWebKey
        from authlib.jose import jwt as authlib_jwt

        key_set = JsonWebKey.import_key_set(jwks)
        claims = authlib_jwt.decode(token_response["id_token"], key_set)
        claims.validate()

        sub = claims["sub"]
        iss = claims["iss"]
        email = claims.get("email")
        display_name = claims.get("name") or claims.get("preferred_username")

        user = await UserService.upsert_from_oidc(session, sub, iss, email, display_name)
        logger.info("auth.callback.success", extra={"user_id": str(user.id)})
        return user

    @staticmethod
    def sign_session(user_id: str) -> str:
        """Sign a user ID into a tamper-proof session token."""
        s = _get_serializer()
        return s.dumps(user_id)

    @staticmethod
    def verify_session(signed: str, max_age: int = 86400) -> str:
        """Verify and decode a signed session token.

        Returns:
            The original user_id string.

        Raises:
            itsdangerous exceptions on invalid/expired signature.
        """
        s = _get_serializer()
        return s.loads(signed, max_age=max_age)
