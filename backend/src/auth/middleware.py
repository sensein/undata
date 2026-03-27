"""JWT validation middleware for Keycloak OIDC tokens."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from src.core.config import settings

logger = logging.getLogger(__name__)

# Cached JWKS client (lazily initialized)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def validate_jwt(token: str, public_key: Any = None) -> dict | None:
    """Validate a JWT token and return decoded claims, or None if invalid.

    If public_key is provided (for testing), use it directly.
    Otherwise fetch the signing key from Keycloak's JWKS endpoint.
    """
    try:
        if public_key is not None:
            # Test mode — use provided key
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        else:
            # Production mode — fetch key from JWKS
            client = _get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.keycloak_client_id,
                issuer=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}",
            )
        return decoded
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("JWT invalid: %s", e)
        return None
    except Exception as e:
        logger.warning("JWT validation error: %s", e)
        return None


def extract_token(authorization: str | None) -> str | None:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def is_jwt(token: str) -> bool:
    """Check if a token looks like a JWT (has 3 dot-separated parts)."""
    return token.count(".") == 2
