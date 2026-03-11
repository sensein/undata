"""User profile management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import SourceMembership, UserProfile
from src.models.schemas import (
    PaginatedList,
    RoleAssignRequest,
    SourceMembershipRequest,
    SourceMembershipResponse,
    UserProfileResponse,
    UserProfileSummary,
)
from src.services.authz import Role, get_current_user, require_role
from src.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _build_user_response(
    user: UserProfile, roles: list[str], memberships: list
) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=roles,
        source_memberships=[{"source_id": str(m.source_id), "role": m.role} for m in memberships],
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated user."""
    from sqlalchemy import select

    roles = await UserService.get_roles(session, current_user.id)
    membership_result = await session.execute(
        select(SourceMembership).where(SourceMembership.user_id == current_user.id)
    )
    memberships = membership_result.scalars().all()
    return _build_user_response(current_user, roles, memberships)


@router.get("/", response_model=PaginatedList[UserProfileSummary])
async def list_users(
    limit: int = 50,
    offset: int = 0,
    current_user: UserProfile = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    total, users = await UserService.list(session, limit=limit, offset=offset)
    items = [
        UserProfileSummary(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            is_active=u.is_active,
        )
        for u in users
    ]
    return PaginatedList(total=total, limit=limit, offset=offset, items=items)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user(
    user_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific user profile (admin only)."""
    from sqlalchemy import select

    user = await UserService.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    roles = await UserService.get_roles(session, user_id)
    membership_result = await session.execute(
        select(SourceMembership).where(SourceMembership.user_id == user_id)
    )
    memberships = membership_result.scalars().all()
    return _build_user_response(user, roles, memberships)


@router.put("/{user_id}/roles", response_model=UserProfileResponse)
async def assign_roles(
    user_id: UUID,
    body: RoleAssignRequest,
    current_user: UserProfile = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """Replace all roles for a user (admin only)."""
    from sqlalchemy import select

    user = await UserService.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    await UserService.assign_roles(session, user_id, body.roles, current_user.id)
    roles = body.roles
    membership_result = await session.execute(
        select(SourceMembership).where(SourceMembership.user_id == user_id)
    )
    memberships = membership_result.scalars().all()
    return _build_user_response(user, roles, memberships)


@router.put("/{user_id}/sources/{source_id}", response_model=SourceMembershipResponse)
async def set_source_membership(
    user_id: UUID,
    source_id: UUID,
    body: SourceMembershipRequest,
    current_user: UserProfile = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """Set source membership for a user (admin only)."""
    membership = await UserService.set_source_membership(
        session, user_id, source_id, body.role, current_user.id
    )
    return SourceMembershipResponse(
        user_id=membership.user_id,
        source_id=membership.source_id,
        role=membership.role,
        granted_at=membership.granted_at,
    )


@router.delete("/{user_id}/sources/{source_id}", status_code=204)
async def remove_source_membership(
    user_id: UUID,
    source_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """Remove source membership for a user (admin only)."""
    await UserService.remove_source_membership(session, user_id, source_id)
