"""Authorization dependencies — RBAC and ReBAC via FastAPI Depends."""

from __future__ import annotations

from enum import IntEnum
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.models.db import SourceMembership, UserProfile, UserRole

logger = get_logger(__name__)


class Role(IntEnum):
    VIEWER = 0
    CONTRIBUTOR = 1
    CURATOR = 2
    ADMIN = 3

    @classmethod
    def from_str(cls, role_name: str) -> "Role":
        mapping = {
            "viewer": cls.VIEWER,
            "contributor": cls.CONTRIBUTOR,
            "curator": cls.CURATOR,
            "admin": cls.ADMIN,
            "owner": cls.CURATOR,  # source owner ≥ curator
        }
        return mapping.get(role_name.lower(), cls.VIEWER)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserProfile:
    """Extract and validate Bearer token; return associated UserProfile.

    Raises HTTP 401 if token is missing or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "missing_token"})

    token_str = auth_header[len("Bearer ") :]

    from src.services.tokens import TokenService  # avoid circular import

    user = await TokenService.validate(session, token_str)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_or_revoked_token"})

    return user


async def _get_user_global_role(session: AsyncSession, user_id: UUID) -> Role:
    result = await session.execute(select(UserRole).where(UserRole.user_id == user_id))
    roles = [Role.from_str(r.role) for r in result.scalars().all()]
    return max(roles, default=Role.VIEWER)


async def check_role(
    session: AsyncSession,
    user: UserProfile,
    min_role: Role,
) -> UserProfile:
    """Core role check — raises HTTP 403 if user's global role is below min_role."""
    effective_role = await _get_user_global_role(session, user.id)
    if effective_role < min_role:
        raise HTTPException(
            status_code=403,
            detail={"error": "insufficient_role", "required": min_role.name},
        )
    return user


async def check_source_access(
    session: AsyncSession,
    user: UserProfile,
    source_id: UUID,
    min_role: Role,
) -> UserProfile:
    """Core source access check — global role first, then source membership."""
    global_role = await _get_user_global_role(session, user.id)
    if global_role >= min_role:
        return user

    result = await session.execute(
        select(SourceMembership).where(
            SourceMembership.user_id == user.id,
            SourceMembership.source_id == source_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "not_source_member"},
        )

    membership_role = Role.from_str(membership.role)
    effective = max(global_role, membership_role)
    if effective < min_role:
        raise HTTPException(
            status_code=403,
            detail={"error": "insufficient_source_role"},
        )

    return user


def require_role(min_role: Role) -> Callable:
    """Return a FastAPI Depends callable that enforces a minimum global role."""

    async def dependency(
        current_user: UserProfile = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> UserProfile:
        return await check_role(session, current_user, min_role)

    return dependency


def require_source_access(source_id_param: str, min_role: Role) -> Callable:
    """Return a FastAPI Depends callable that enforces source-level access."""

    async def dependency(
        current_user: UserProfile = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> UserProfile:
        try:
            source_uuid = UUID(source_id_param)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_source_id"})
        return await check_source_access(session, current_user, source_uuid, min_role)

    return dependency
