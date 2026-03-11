"""TokenService — API key issuance, validation, and revocation."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import get_logger
from src.models.db import APIKey, UserProfile

logger = get_logger(__name__)

# Module-level TTL cache: key = token_hash, value = (user_id: UUID, revoked_at: datetime | None)
_token_cache: TTLCache = TTLCache(maxsize=1024, ttl=settings.token_cache_ttl_seconds)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class TokenService:
    @staticmethod
    async def issue(
        session: AsyncSession, user_id: UUID, label: str | None = None
    ) -> tuple[str, APIKey]:
        """Issue a new API key.

        Returns:
            (raw_token, APIKey ORM object) — raw_token is shown ONCE; hash stored.
        """
        raw_token = secrets.token_hex(32)  # 64-char hex
        token_hash = _hash_token(raw_token)

        key = APIKey(
            user_id=user_id,
            token_hash=token_hash,
            label=label,
        )
        session.add(key)
        await session.flush()

        logger.info("token.issued", extra={"user_id": str(user_id), "key_id": str(key.id)})
        return raw_token, key

    @staticmethod
    async def validate(session: AsyncSession, token_str: str) -> UserProfile | None:
        """Validate a Bearer token string.

        Uses a TTL cache to avoid repeated DB lookups. Returns the associated
        UserProfile if valid and not revoked, else None.

        Also updates `last_used_at` on cache miss (DB hit).
        """
        token_hash = _hash_token(token_str)

        # Check cache first
        if token_hash in _token_cache:
            cached_user_id, cached_revoked_at = _token_cache[token_hash]
            if cached_revoked_at is not None:
                return None
            # Fetch profile (lightweight — just for the object)
            result = await session.execute(
                select(UserProfile).where(UserProfile.id == cached_user_id)
            )
            user = result.scalar_one_or_none()
            return user if (user and user.is_active) else None

        # DB lookup
        result = await session.execute(select(APIKey).where(APIKey.token_hash == token_hash))
        key = result.scalar_one_or_none()
        if key is None:
            _token_cache[token_hash] = (None, datetime.now(timezone.utc))
            return None

        if key.revoked_at is not None:
            _token_cache[token_hash] = (key.user_id, key.revoked_at)
            return None

        # Update last_used_at
        key.last_used_at = datetime.now(timezone.utc)
        await session.flush()

        # Cache the result
        _token_cache[token_hash] = (key.user_id, None)

        # Fetch user profile
        user_result = await session.execute(
            select(UserProfile).where(UserProfile.id == key.user_id)
        )
        user = user_result.scalar_one_or_none()
        return user if (user and user.is_active) else None

    @staticmethod
    async def revoke(session: AsyncSession, key_id: UUID, revoked_by_id: UUID) -> APIKey:
        """Revoke an API key by ID.

        Sets revoked_at and evicts the cache entry.

        Raises:
            ValueError: if the key does not exist.
        """
        result = await session.execute(select(APIKey).where(APIKey.id == key_id))
        key = result.scalar_one_or_none()
        if key is None:
            raise ValueError(f"API key {key_id} not found")

        key.revoked_at = datetime.now(timezone.utc)
        key.revoked_by = revoked_by_id
        await session.flush()

        # Evict from cache
        _token_cache.pop(key.token_hash, None)

        logger.info(
            "token.revoked", extra={"key_id": str(key_id), "revoked_by": str(revoked_by_id)}
        )
        return key
