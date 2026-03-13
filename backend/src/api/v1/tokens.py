"""API key management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import UserProfile
from src.models.schemas import APIKeyCreateResponse, APIKeySummary, TokenIssueRequest
from src.services.authz import get_current_user
from src.services.tokens import TokenService

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("/", response_model=list[APIKeySummary])
async def list_tokens(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all non-revoked API keys for the authenticated user."""
    from sqlalchemy import select

    from src.models.db import APIKey

    result = await session.execute(
        select(APIKey).where(
            APIKey.user_id == current_user.id,
            APIKey.revoked_at.is_(None),
        )
    )
    keys = result.scalars().all()
    return [
        APIKeySummary(
            id=k.id,
            label=k.label,
            issued_at=k.issued_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in keys
    ]


@router.post("/", response_model=APIKeyCreateResponse, status_code=201)
async def issue_token(
    body: TokenIssueRequest,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Issue a new API key. The token value is shown ONCE in the response."""
    raw_token, key = await TokenService.issue(session, current_user.id, body.label)
    return APIKeyCreateResponse(
        id=key.id,
        label=key.label,
        token=raw_token,
        issued_at=key.issued_at,
    )


@router.delete("/{key_id}", status_code=200)
async def revoke_token(
    key_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke an API key. User can revoke own keys; admin can revoke any."""
    from sqlalchemy import select

    from src.models.db import APIKey
    from src.services.authz import Role, _get_user_global_role

    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    # Ownership check: own key OR admin
    global_role = await _get_user_global_role(session, current_user.id)
    if key.user_id != current_user.id and global_role < Role.ADMIN:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    revoked_key = await TokenService.revoke(session, key_id, current_user.id)
    return {"id": str(revoked_key.id), "revoked_at": revoked_key.revoked_at.isoformat()}
