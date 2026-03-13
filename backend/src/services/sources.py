"""SourceService — schema source CRUD with optimistic concurrency."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.db import SchemaSource
from src.models.schemas import SchemaSourceCreate
from src.services.audit import AuditService

logger = get_logger(__name__)


class VersionConflictError(Exception):
    """Raised when version_num does not match current row version."""


class DuplicateSourceError(Exception):
    """Raised when a source with the same name already exists."""


class SourceService:
    @staticmethod
    async def create(
        session: AsyncSession, data: SchemaSourceCreate, actor_id: UUID
    ) -> SchemaSource:
        source = SchemaSource(
            name=data.name,
            format=data.format,
            url=data.url,
            version_tag=data.version_tag,
            content_hash=data.content_hash,
            is_active=True,
            metadata_=data.metadata,
            version_num=1,
        )
        session.add(source)
        try:
            await session.flush()
        except IntegrityError as exc:
            if "uq_schema_source_name" in str(exc) or "unique" in str(exc).lower():
                raise DuplicateSourceError(
                    f"Source '{data.name}' already exists"
                ) from exc
            raise

        await AuditService.record(
            session,
            record_type="SchemaSource",
            record_id=source.id,
            operation="create",
            actor_id=actor_id,
            version_num=1,
        )
        logger.info(
            "source.created",
            extra={"source_id": str(source.id), "source_name": source.name},
        )
        return source

    @staticmethod
    async def get(session: AsyncSession, source_id: UUID) -> SchemaSource | None:
        result = await session.execute(select(SchemaSource).where(SchemaSource.id == source_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[SchemaSource]]:
        """List schema sources with optional exact-match name filter.

        The `name` param supports exact-match lookup (e.g., ?name=undata).
        """
        query = select(SchemaSource)
        count_query = select(func.count()).select_from(SchemaSource)

        if name is not None:
            query = query.where(SchemaSource.name == name)
            count_query = count_query.where(SchemaSource.name == name)

        count_result = await session.execute(count_query)
        total = count_result.scalar_one()

        result = await session.execute(
            query.order_by(SchemaSource.name).limit(limit).offset(offset)
        )
        return total, list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        source_id: UUID,
        data: dict,
        actor_id: UUID,
        version_num: int,
    ) -> SchemaSource:
        source = await SourceService.get(session, source_id)
        if source is None:
            raise ValueError(f"SchemaSource {source_id} not found")

        if source.version_num != version_num:
            raise VersionConflictError(
                f"Version conflict: current={source.version_num}, provided={version_num}"
            )

        old_data = {
            "name": source.name,
            "format": source.format,
            "url": source.url,
            "version_tag": source.version_tag,
        }

        for field, value in data.items():
            if field not in ("version_num",) and hasattr(source, field):
                setattr(source, field, value)

        source.version_num += 1
        await session.flush()

        await AuditService.record(
            session,
            record_type="SchemaSource",
            record_id=source.id,
            operation="update",
            actor_id=actor_id,
            version_num=source.version_num,
            diff={k: {"old": old_data[k], "new": getattr(source, k)} for k in old_data},
        )
        return source
