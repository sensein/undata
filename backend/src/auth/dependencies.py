"""FastAPI auth dependencies — user extraction and role enforcement."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.middleware import extract_token, is_jwt, validate_jwt
from src.db.models import UserProfile
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Role hierarchy — admin can do everything
ROLE_HIERARCHY = {
    "admin": 4,
    "curator": 3,
    "contributor": 2,
    "viewer": 1,
}


def check_role(claims: dict, required_role: str) -> bool:
    """Check if JWT claims contain the required role (or higher)."""
    roles = claims.get("realm_access", {}).get("roles", [])
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    for role in roles:
        if ROLE_HIERARCHY.get(role, 0) >= required_level:
            return True
    return False


async def get_current_user(request: Request) -> dict | None:
    """Extract and validate user from request.

    Checks Authorization header for JWT. Returns decoded claims or None.
    Expired tokens return None (client should re-login).
    """
    auth_header = request.headers.get("authorization")
    token = extract_token(auth_header)
    if not token:
        # Also check cookie
        token = request.cookies.get("access_token")
    if not token:
        return None

    if is_jwt(token):
        claims = validate_jwt(token)
        if claims is None:
            return None
        # Ensure/update user profile in DB
        await _ensure_user_profile(claims)
        return claims
    else:
        # API key — handled separately
        from src.auth.api_keys import validate_api_key

        return await validate_api_key(token)


async def _ensure_user_profile(claims: dict) -> None:
    """Create or update UserProfile from JWT claims."""
    sub = claims.get("sub", "")
    if not sub:
        return

    async with AsyncSessionLocal() as session:
        stmt = select(UserProfile).where(UserProfile.external_sub == sub)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile is None:
            # Create new user
            roles = claims.get("realm_access", {}).get("roles", [])
            role = "viewer"
            for r in ["admin", "curator", "contributor"]:
                if r in roles:
                    role = r
                    break

            profile = UserProfile(
                external_sub=sub,
                email=claims.get("email", ""),
                display_name=claims.get("name", claims.get("preferred_username", sub)),
                role=role,
            )
            session.add(profile)
            await session.commit()
        else:
            # Update name/email if changed
            changed = False
            if claims.get("email") and profile.email != claims["email"]:
                profile.email = claims["email"]
                changed = True
            if claims.get("name") and profile.display_name != claims["name"]:
                profile.display_name = claims["name"]
                changed = True
            if changed:
                await session.commit()


def require_auth(user: dict | None) -> dict:
    """Raise 401 if user is None."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(role: str):
    """Return a dependency that checks for a specific role."""

    def _check(user: dict | None) -> dict:
        user = require_auth(user)
        if not check_role(user, role):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' required. Your roles: {user.get('realm_access', {}).get('roles', [])}",
            )
        return user

    return _check
