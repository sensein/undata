"""SchemaChangeLogService — record, list, and render PROV-DM provenance for DynamicSchema.

Implements:
- record(): Insert a SchemaChangeLog row after any schema mutation
- list(): Paginated query with optional breaking_only filter
- to_prov_jsonld(): Assemble W3C PROV-DM JSON-LD from SchemaChangeLog rows
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import SchemaChangeLog, UserProfile


async def record(
    *,
    schema_id: uuid.UUID,
    operation: str,
    actor_id: uuid.UUID,
    diff: dict[str, Any] | None = None,
    breaking: bool = False,
    reason: str | None = None,
    activity_type: str = "schema_edit",
    semantic_boundary_crossed: bool = False,
    db: AsyncSession,
) -> SchemaChangeLog:
    """Insert a SchemaChangeLog row. Returns the new row (not yet committed)."""
    from src.models.db import DynamicSchema

    version_result = await db.execute(
        select(DynamicSchema.version_num).where(DynamicSchema.id == schema_id)
    )
    version_row = version_result.first()
    version_num = version_row[0] if version_row else 1

    entry = SchemaChangeLog(
        id=uuid.uuid4(),
        schema_id=schema_id,
        version_num=version_num,
        operation=operation,
        actor_id=actor_id,
        timestamp=datetime.now(timezone.utc),
        activity_type=activity_type,
        diff=diff,
        breaking=breaking,
        semantic_boundary_crossed=semantic_boundary_crossed,
        reason=reason,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_changelog(
    *,
    schema_id: uuid.UUID,
    breaking_only: bool = False,
    page: int = 1,
    size: int = 20,
    db: AsyncSession,
) -> dict[str, Any]:
    """Return paginated changelog for a schema."""
    base_query = select(SchemaChangeLog).where(SchemaChangeLog.schema_id == schema_id)
    if breaking_only:
        base_query = base_query.where(SchemaChangeLog.breaking.is_(True))

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    rows_result = await db.execute(
        base_query.order_by(SchemaChangeLog.timestamp.desc()).offset(offset).limit(size)
    )
    entries = list(rows_result.scalars().all())

    # Fetch actor display names
    actor_ids = list({e.actor_id for e in entries})
    actor_map: dict[uuid.UUID, str] = {}
    if actor_ids:
        actor_result = await db.execute(
            select(UserProfile).where(UserProfile.id.in_(actor_ids))
        )
        for profile in actor_result.scalars().all():
            actor_map[profile.id] = profile.display_name

    entry_dicts = []
    for e in entries:
        entry_dicts.append(
            {
                "id": str(e.id),
                "schema_id": str(e.schema_id),
                "version_num": e.version_num,
                "operation": e.operation,
                "actor_id": str(e.actor_id),
                "actor_name": actor_map.get(e.actor_id),
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "activity_type": e.activity_type,
                "diff": e.diff,
                "breaking": e.breaking,
                "semantic_boundary_crossed": e.semantic_boundary_crossed,
                "reason": e.reason,
            }
        )

    return {
        "schema_id": str(schema_id),
        "total": total,
        "page": page,
        "size": size,
        "entries": entry_dicts,
    }


async def to_prov_jsonld(
    *,
    schema_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """Assemble W3C PROV-DM JSON-LD for a schema from its SchemaChangeLog rows."""
    from src.models.db import DynamicSchema

    schema_result = await db.execute(
        select(DynamicSchema).where(DynamicSchema.id == schema_id)
    )
    schema = schema_result.scalar_one_or_none()

    rows_result = await db.execute(
        select(SchemaChangeLog)
        .where(SchemaChangeLog.schema_id == schema_id)
        .order_by(SchemaChangeLog.timestamp.desc())
    )
    logs = list(rows_result.scalars().all())

    # Collect unique actors
    actor_ids = list({log.actor_id for log in logs})
    actor_map: dict[uuid.UUID, str] = {}
    if actor_ids:
        actor_result = await db.execute(
            select(UserProfile).where(UserProfile.id.in_(actor_ids))
        )
        for profile in actor_result.scalars().all():
            actor_map[profile.id] = profile.display_name

    schema_uri = f"https://schema.undata.live/schemas/{schema_id}"
    graph: list[dict[str, Any]] = []

    # prov:Entity for the schema
    entity: dict[str, Any] = {
        "@type": "prov:Entity",
        "@id": schema_uri,
    }
    if schema and schema.parent_id:
        entity["prov:wasDerivedFrom"] = {"@id": f"https://schema.undata.live/schemas/{schema.parent_id}"}

    if logs:
        latest = logs[0]
        entity["prov:wasGeneratedBy"] = {"@id": f"urn:activity:{latest.id}"}
        entity["prov:wasAttributedTo"] = {"@id": f"urn:agent:{latest.actor_id}"}

    graph.append(entity)

    # prov:Activity + prov:Agent for each log entry
    for log in logs:
        ts = log.timestamp.isoformat() if log.timestamp else None
        graph.append(
            {
                "@type": "prov:Activity",
                "@id": f"urn:activity:{log.id}",
                "prov:startedAtTime": ts,
                "prov:endedAtTime": ts,
                "prov:wasAssociatedWith": {"@id": f"urn:agent:{log.actor_id}"},
            }
        )
        agent_name = actor_map.get(log.actor_id)
        graph.append(
            {
                "@type": "prov:Agent",
                "@id": f"urn:agent:{log.actor_id}",
                "foaf:name": agent_name or str(log.actor_id),
            }
        )

    return {
        "@context": "http://www.w3.org/ns/prov",
        "@graph": graph,
    }


async def to_element_prov_jsonld(
    *,
    element_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """Assemble W3C PROV-DM JSON-LD for an element from its DataElementVersion history."""
    from src.models.db import DataElementVersion

    versions_result = await db.execute(
        select(DataElementVersion)
        .where(DataElementVersion.element_id == element_id)
        .order_by(DataElementVersion.version_num.desc())
    )
    versions = list(versions_result.scalars().all())

    # Collect unique actors
    actor_ids = list({v.created_by for v in versions})
    actor_map: dict[uuid.UUID, str] = {}
    if actor_ids:
        actor_result = await db.execute(
            select(UserProfile).where(UserProfile.id.in_(actor_ids))
        )
        for profile in actor_result.scalars().all():
            actor_map[profile.id] = profile.display_name

    element_uri = f"https://schema.undata.live/elements/{element_id}"
    graph: list[dict[str, Any]] = []

    # prov:Entity for the element
    entity: dict[str, Any] = {
        "@type": "prov:Entity",
        "@id": element_uri,
    }
    if versions:
        latest = versions[0]
        entity["prov:wasGeneratedBy"] = {"@id": f"urn:activity:el-{latest.id}"}
        entity["prov:wasAttributedTo"] = {"@id": f"urn:agent:{latest.created_by}"}
    graph.append(entity)

    # prov:Activity + prov:Agent for each version
    for version in versions:
        ts = version.created_at.isoformat() if version.created_at else None
        graph.append(
            {
                "@type": "prov:Activity",
                "@id": f"urn:activity:el-{version.id}",
                "prov:startedAtTime": ts,
                "prov:endedAtTime": ts,
                "prov:wasAssociatedWith": {"@id": f"urn:agent:{version.created_by}"},
            }
        )
        agent_name = actor_map.get(version.created_by)
        graph.append(
            {
                "@type": "prov:Agent",
                "@id": f"urn:agent:{version.created_by}",
                "foaf:name": agent_name or str(version.created_by),
            }
        )

    return {
        "@context": "http://www.w3.org/ns/prov",
        "@graph": graph,
    }
