"""FastAPI auth dependencies — user extraction and role enforcement."""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request
from sqlalchemy import select

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
        # Ensure/update user profile in DB and inject local role
        await _ensure_user_profile(claims)
        # Override realm_access roles with local role determination
        email = claims.get("email", "")
        keycloak_roles = claims.get("realm_access", {}).get("roles", [])
        local_role = _determine_role(email, keycloak_roles)
        claims.setdefault("realm_access", {})["roles"] = [local_role]
        return claims
    else:
        # API key — handled separately
        from src.auth.api_keys import validate_api_key

        return await validate_api_key(token)


# Emails with elevated roles (configurable via CURATOR_EMAILS / ADMIN_EMAILS env vars)
_CURATOR_EMAILS = set(
    e.strip().lower()
    for e in os.environ.get("CURATOR_EMAILS", "satra@mit.edu").split(",")
    if e.strip()
)
_ADMIN_EMAILS = set(
    e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
)


def _determine_role(email: str, keycloak_roles: list[str]) -> str:
    """Determine user role from email overrides and Keycloak roles."""
    email_lower = email.lower() if email else ""
    if email_lower in _ADMIN_EMAILS:
        return "admin"
    if email_lower in _CURATOR_EMAILS:
        return "curator"
    for r in ["admin", "curator", "contributor"]:
        if r in keycloak_roles:
            return r
    return "viewer"


async def _ensure_user_profile(claims: dict) -> None:
    """Create or update UserProfile from JWT claims."""
    sub = claims.get("sub", "")
    if not sub:
        return

    email = claims.get("email", "")
    keycloak_roles = claims.get("realm_access", {}).get("roles", [])
    role = _determine_role(email, keycloak_roles)

    async with AsyncSessionLocal() as session:
        stmt = select(UserProfile).where(UserProfile.external_sub == sub)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = UserProfile(
                external_sub=sub,
                email=email,
                display_name=claims.get("name", claims.get("preferred_username", sub)),
                role=role,
            )
            session.add(profile)
            await session.commit()
        else:
            # Update name/email/role if changed
            changed = False
            if claims.get("email") and profile.email != claims["email"]:
                profile.email = claims["email"]
                changed = True
            if claims.get("name") and profile.display_name != claims["name"]:
                profile.display_name = claims["name"]
                changed = True
            # Upgrade role if email is in curator/admin list
            if profile.role != role and role in ("curator", "admin"):
                profile.role = role
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
                detail=(
                    f"Role '{role}' required. "
                    f"Your roles: {user.get('realm_access', {}).get('roles', [])}"
                ),
            )
        return user

    return _check
