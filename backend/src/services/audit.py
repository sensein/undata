"""AuditService — records immutable audit trail entries in the same transaction."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.db import AuditLog

logger = get_logger(__name__)


class AuditService:
    @staticmethod
    async def record(
        session: AsyncSession,
        record_type: str,
        record_id: UUID,
        operation: str,
        actor_id: UUID,
        version_num: int | None = None,
        diff: dict[str, Any] | None = None,
    ) -> None:
        """Insert an AuditLog row in the same transaction as the caller.

        Args:
            session: The active async session (must already be in a transaction).
            record_type: Entity type being audited (e.g. "data_element").
            record_id: UUID of the entity being audited.
            operation: Operation performed (e.g. "create", "update", "delete", "supersede").
            actor_id: UUID FK → UserProfile of the user performing the action.
            version_num: Optional version number of the entity after the operation.
            diff: Optional dict of ``{"field": {"old": v1, "new": v2}}`` pairs.
        """
        log_entry = AuditLog(
            record_type=record_type,
            record_id=record_id,
            operation=operation,
            actor_id=actor_id,
            version_num=version_num,
            diff=diff,
        )
        session.add(log_entry)
        logger.debug(
            "audit.record",
            extra={
                "record_type": record_type,
                "record_id": str(record_id),
                "operation": operation,
                "actor_id": str(actor_id),
            },
        )

    @staticmethod
    async def query(
        session: AsyncSession,
        record_type: str | None = None,
        record_id: UUID | None = None,
        operation: str | None = None,
        actor_id: UUID | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AuditLog]]:
        """Query audit log with optional filters. Returns (total, items) ordered by timestamp DESC."""
        filters = []
        if record_type is not None:
            filters.append(AuditLog.record_type == record_type)
        if record_id is not None:
            filters.append(AuditLog.record_id == record_id)
        if operation is not None:
            filters.append(AuditLog.operation == operation)
        if actor_id is not None:
            filters.append(AuditLog.actor_id == actor_id)
        if from_ts is not None:
            filters.append(AuditLog.timestamp >= from_ts)
        if to_ts is not None:
            filters.append(AuditLog.timestamp <= to_ts)

        where_clause = and_(*filters) if filters else True

        count_result = await session.execute(
            select(func.count()).select_from(AuditLog).where(where_clause)
        )
        total = count_result.scalar_one()

        result = await session.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return total, list(result.scalars().all())
