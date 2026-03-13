"""DynamicSchemaService — schema composition with persistent URIs and supersession."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.uri import mint_schema_uri
from src.models.db import DataElement, DynamicSchema, DynamicSchemaElement
from src.models.schemas import (
    DynamicSchemaCreate,
    DynamicSchemaUpdate,
    SupersedeSchemaRequest,
)
from src.services.audit import AuditService

logger = get_logger(__name__)


class VersionConflictError(Exception):
    pass


class SchemaNotFoundError(Exception):
    pass


class AlreadySupersededError(Exception):
    pass


class ElementNotFoundError(Exception):
    pass


class DynamicSchemaService:
    @staticmethod
    async def create(
        session: AsyncSession,
        data: DynamicSchemaCreate,
        actor_id: UUID,
    ) -> DynamicSchema:
        """Create a new DynamicSchema with URI minting."""
        schema_id = uuid.uuid4()
        uri = mint_schema_uri(str(schema_id))

        # Validate all element IDs exist
        for item in data.elements:
            result = await session.execute(
                select(DataElement.id).where(DataElement.id == UUID(str(item.element_id)))
            )
            if result.scalar_one_or_none() is None:
                raise ElementNotFoundError(f"Element {item.element_id} not found")

        schema = DynamicSchema(
            id=schema_id,
            uri=uri,
            name=data.name,
            description=data.description,
            version_num=1,
        )
        session.add(schema)
        await session.flush()

        for item in data.elements:
            link = DynamicSchemaElement(
                schema_id=schema.id,
                element_id=UUID(str(item.element_id)),
                position=item.position,
                field_alias=item.field_alias,
            )
            session.add(link)

        await session.flush()

        await AuditService.record(
            session,
            record_type="DynamicSchema",
            record_id=schema.id,
            operation="create",
            actor_id=actor_id,
            version_num=1,
        )
        logger.info("schema.created", extra={"schema_id": str(schema.id), "uri": uri})
        return schema

    @staticmethod
    async def get(session: AsyncSession, schema_id: UUID) -> DynamicSchema | None:
        result = await session.execute(select(DynamicSchema).where(DynamicSchema.id == schema_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        element_id: UUID | None = None,
        q: str | None = None,
        include_superseded: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[DynamicSchema]]:
        query = select(DynamicSchema).where(DynamicSchema.deleted_at.is_(None))

        if not include_superseded:
            query = query.where(DynamicSchema.superseded_by.is_(None))

        if element_id:
            query = query.join(
                DynamicSchemaElement,
                DynamicSchema.id == DynamicSchemaElement.schema_id,
            ).where(DynamicSchemaElement.element_id == element_id)

        count_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()

        result = await session.execute(
            query.order_by(DynamicSchema.created_at.desc()).limit(limit).offset(offset)
        )
        return total, list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        schema_id: UUID,
        data: DynamicSchemaUpdate,
        actor_id: UUID,
    ) -> DynamicSchema:
        schema = await DynamicSchemaService.get(session, schema_id)
        if schema is None:
            raise SchemaNotFoundError(f"Schema {schema_id} not found")

        if schema.version_num != data.version_num:
            raise VersionConflictError(
                f"Version conflict: current={schema.version_num}, provided={data.version_num}"
            )

        # Remove elements
        if data.remove:
            for el_id in data.remove:
                result = await session.execute(
                    select(DynamicSchemaElement).where(
                        DynamicSchemaElement.schema_id == schema_id,
                        DynamicSchemaElement.element_id == UUID(str(el_id)),
                    )
                )
                link = result.scalar_one_or_none()
                if link:
                    await session.delete(link)

        # Add elements
        if data.add:
            for item in data.add:
                link = DynamicSchemaElement(
                    schema_id=schema.id,
                    element_id=UUID(str(item.element_id)),
                    position=item.position,
                    field_alias=item.field_alias,
                )
                session.add(link)

        if data.name is not None:
            schema.name = data.name
        if data.description is not None:
            schema.description = data.description

        schema.version_num += 1
        schema.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await AuditService.record(
            session,
            record_type="DynamicSchema",
            record_id=schema.id,
            operation="update",
            actor_id=actor_id,
            version_num=schema.version_num,
        )
        return schema

    @staticmethod
    async def delete(session: AsyncSession, schema_id: UUID, actor_id: UUID) -> DynamicSchema:
        schema = await DynamicSchemaService.get(session, schema_id)
        if schema is None:
            raise SchemaNotFoundError(f"Schema {schema_id} not found")

        schema.deleted_at = datetime.now(timezone.utc)
        await session.flush()

        await AuditService.record(
            session,
            record_type="DynamicSchema",
            record_id=schema_id,
            operation="delete",
            actor_id=actor_id,
        )
        return schema

    @staticmethod
    async def supersede(
        session: AsyncSession,
        old_id: UUID,
        req: SupersedeSchemaRequest,
        actor_id: UUID,
    ) -> tuple[DynamicSchema, DynamicSchema]:
        """Replace a schema with a semantically distinct successor."""
        old = await DynamicSchemaService.get(session, old_id)
        if old is None:
            raise SchemaNotFoundError(f"Schema {old_id} not found")
        if old.superseded_by is not None:
            raise AlreadySupersededError(f"Schema {old_id} is already superseded")

        new = await DynamicSchemaService.create(session, req.new_schema_data, actor_id)

        old.superseded_by = new.id
        old.deleted_at = datetime.now(timezone.utc)
        await session.flush()

        await AuditService.record(
            session,
            record_type="DynamicSchema",
            record_id=old.id,
            operation="supersede",
            actor_id=actor_id,
            diff={"supersede_reason": req.supersede_reason, "superseded_by": new.uri},
        )

        return new, old
