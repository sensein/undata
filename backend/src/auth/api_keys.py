"""API key validation — lookup hashed token, return user claims."""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select

from src.db.models import APIKey, UserProfile
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key for storage/lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def validate_api_key(token: str) -> dict | None:
    """Validate an API key and return user claims, or None if invalid.

    Looks up the key hash in the api_keys table, checks it's not revoked,
    and returns claims matching the JWT structure (sub, name, roles).
    """
    token_hash = hash_api_key(token)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(APIKey, UserProfile)
            .join(UserProfile, APIKey.user_id == UserProfile.id)
            .where(APIKey.token_hash == token_hash)
            .where(APIKey.revoked_at.is_(None))
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is None:
            return None

        api_key, user = row
        return {
            "sub": str(user.id),
            "email": user.email or "",
            "name": user.display_name or str(user.id),
            "realm_access": {"roles": [user.role]},
            "auth_method": "api_key",
        }
