"""Audit log query endpoint."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import UserProfile
from src.models.schemas import AuditLogResponse, PaginatedList
from src.services.audit import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/", response_model=PaginatedList[AuditLogResponse])
async def list_audit_entries(
    record_type: str | None = None,
    record_id: UUID | None = None,
    operation: str | None = None,
    actor_id: UUID | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    total, entries = await AuditService.query(
        session,
        record_type=record_type,
        record_id=record_id,
        operation=operation,
        actor_id=actor_id,
        from_ts=from_,
        to_ts=to,
        limit=limit,
        offset=offset,
    )

    items = []
    for entry in entries:
        # Resolve actor display name
        actor_display_name = None
        if entry.actor_id:
            user_result = await session.execute(
                select(UserProfile).where(UserProfile.id == entry.actor_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                actor_display_name = user.display_name

        items.append(
            AuditLogResponse(
                id=entry.id,
                record_type=entry.record_type,
                record_id=entry.record_id,
                operation=entry.operation,
                actor_id=entry.actor_id,
                actor_display_name=actor_display_name,
                timestamp=entry.timestamp,
                version_num=entry.version_num,
                diff=entry.diff,
            )
        )

    return PaginatedList(total=total, limit=limit, offset=offset, items=items)
