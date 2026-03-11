"""UserService — user profile management and role assignment."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.db import SourceMembership, UserProfile, UserRole

logger = get_logger(__name__)


class UserService:
    @staticmethod
    async def upsert_from_oidc(
        session: AsyncSession,
        sub: str,
        iss: str,
        email: str | None,
        display_name: str | None,
    ) -> UserProfile:
        """Upsert a UserProfile from OIDC claims.

        On conflict (external_sub, external_iss), updates last_login_at, email,
        and display_name. Creates a new profile on first login.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(UserProfile)
            .values(
                external_sub=sub,
                external_iss=iss,
                email=email,
                display_name=display_name,
                is_active=True,
            )
            .on_conflict_do_update(
                constraint="uq_user_profile_sub_iss",
                set_={
                    "email": email,
                    "display_name": display_name,
                    "last_login_at": func.now(),
                },
            )
            .returning(UserProfile)
        )
        result = await session.execute(stmt)
        user = result.scalar_one()
        logger.info("user.upserted", extra={"user_id": str(user.id), "iss": iss})
        return user

    @staticmethod
    async def get(session: AsyncSession, user_id: UUID) -> UserProfile | None:
        result = await session.execute(select(UserProfile).where(UserProfile.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[UserProfile]]:
        count_result = await session.execute(select(func.count()).select_from(UserProfile))
        total = count_result.scalar_one()

        result = await session.execute(
            select(UserProfile).order_by(UserProfile.created_at).limit(limit).offset(offset)
        )
        return total, list(result.scalars().all())

    @staticmethod
    async def assign_roles(
        session: AsyncSession,
        user_id: UUID,
        roles: list[str],
        granted_by_id: UUID,
    ) -> None:
        """Replace all roles for a user with the given set."""
        # Remove existing roles
        existing = await session.execute(select(UserRole).where(UserRole.user_id == user_id))
        for role in existing.scalars().all():
            await session.delete(role)
        await session.flush()

        # Insert new roles
        for role_name in roles:
            session.add(UserRole(user_id=user_id, role=role_name, granted_by=granted_by_id))
        await session.flush()
        logger.info("user.roles.assigned", extra={"user_id": str(user_id), "roles": roles})

    @staticmethod
    async def set_source_membership(
        session: AsyncSession,
        user_id: UUID,
        source_id: UUID,
        role: str,
        granted_by_id: UUID,
    ) -> SourceMembership:
        """Upsert source membership for a user."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(SourceMembership)
            .values(user_id=user_id, source_id=source_id, role=role, granted_by=granted_by_id)
            .on_conflict_do_update(
                constraint="pk_source_membership",
                set_={"role": role, "granted_by": granted_by_id},
            )
            .returning(SourceMembership)
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def remove_source_membership(
        session: AsyncSession,
        user_id: UUID,
        source_id: UUID,
    ) -> None:
        result = await session.execute(
            select(SourceMembership).where(
                SourceMembership.user_id == user_id,
                SourceMembership.source_id == source_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership:
            await session.delete(membership)
            await session.flush()

    @staticmethod
    async def get_roles(session: AsyncSession, user_id: UUID) -> list[str]:
        result = await session.execute(select(UserRole).where(UserRole.user_id == user_id))
        return [r.role for r in result.scalars().all()]
