"""Strawberry GraphQL schema — database-backed resolvers.

All queries go through PostgreSQL via SQLAlchemy async session.
The frontend communicates exclusively through this GraphQL API.
"""

from __future__ import annotations

from typing import Optional

import strawberry
from sqlalchemy import func, select
from strawberry.fastapi import GraphQLRouter

from src.db.session import AsyncSessionLocal
from src.models.db import (
    CurationFlag as CurationFlagModel,
    Element as ElementModel,
    RunSummary as RunSummaryModel,
    Value as ValueModel,
)

from .types import (
    CurationFlag,
    Element,
    ElementConnection,
    ElementEdge,
    FlagStatus,
    FlagType,
    OntologyAnnotation,
    PageInfo,
    ProvenanceEntry,
    RunSummary,
    Value,
)


def _to_element(row: ElementModel) -> Element:
    anns = row.ontology_annotations or []
    prov_list = row.provenance or []
    return Element(
        sha256=row.sha256,
        data_type=row.data_type,
        unit=row.unit,
        pattern=row.pattern,
        value_domain=row.value_domain,
        description=row.description,
        min_value=row.min_value,
        max_value=row.max_value,
        type_ref=row.type_ref,
        ontology_annotations=[
            OntologyAnnotation(**a)
            for a in anns
            if isinstance(a, dict) and "term_uri" in a
        ],
        provenance=[
            ProvenanceEntry(
                source=p.get("source", ""),
                class_name=p.get("class", p.get("class_", "")),
                name=p.get("name", ""),
                description=p.get("description"),
            )
            for p in prov_list
            if isinstance(p, dict)
        ],
        file_name=row.file_name,
    )


def _to_value(row: ValueModel) -> Value:
    anns = row.ontology_annotations or []
    prov_list = row.provenance or []
    return Value(
        sha256=row.sha256,
        label=row.label,
        value_type=row.value_type,
        description=row.description,
        ontology_id=row.ontology_id,
        ontology_annotations=[
            OntologyAnnotation(**a)
            for a in anns
            if isinstance(a, dict) and "term_uri" in a
        ],
        provenance=[
            ProvenanceEntry(
                source=p.get("source", ""),
                class_name=p.get("class", p.get("class_", "")),
                name=p.get("name", ""),
                description=p.get("description"),
            )
            for p in prov_list
            if isinstance(p, dict)
        ],
        file_name=row.file_name,
    )


@strawberry.type
class Query:
    @strawberry.field
    async def element(self, sha256: str) -> Optional[Element]:
        """Look up a single element by sha256 hash prefix."""
        async with AsyncSessionLocal() as session:
            stmt = select(ElementModel).where(
                ElementModel.sha256.startswith(sha256)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return _to_element(row) if row else None

    @strawberry.field
    async def browse_elements(
        self,
        source: Optional[str] = None,
        data_type: Optional[str] = None,
        first: int = 20,
        offset: int = 0,
    ) -> ElementConnection:
        """Browse elements with filtering and pagination."""
        async with AsyncSessionLocal() as session:
            stmt = select(ElementModel)
            count_stmt = select(func.count()).select_from(ElementModel)

            if source:
                # Filter by source in provenance JSONB
                stmt = stmt.where(
                    ElementModel.provenance[0]["source"].astext == source
                )
                count_stmt = count_stmt.where(
                    ElementModel.provenance[0]["source"].astext == source
                )
            if data_type:
                stmt = stmt.where(ElementModel.data_type == data_type)
                count_stmt = count_stmt.where(ElementModel.data_type == data_type)

            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = stmt.order_by(ElementModel.file_name).offset(offset).limit(first)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            edges = [
                ElementEdge(
                    node=_to_element(row),
                    cursor=row.file_name,
                )
                for row in rows
            ]

            return ElementConnection(
                edges=edges,
                page_info=PageInfo(
                    has_next_page=offset + first < total,
                    has_previous_page=offset > 0,
                    start_cursor=edges[0].cursor if edges else None,
                    end_cursor=edges[-1].cursor if edges else None,
                ),
                total_count=total,
            )

    @strawberry.field
    async def browse_values(
        self,
        source: Optional[str] = None,
        first: int = 20,
        offset: int = 0,
    ) -> list[Value]:
        """Browse values with optional source filtering."""
        async with AsyncSessionLocal() as session:
            stmt = select(ValueModel)
            if source:
                stmt = stmt.where(
                    ValueModel.provenance[0]["source"].astext == source
                )
            stmt = stmt.order_by(ValueModel.label).offset(offset).limit(first)
            result = await session.execute(stmt)
            return [_to_value(row) for row in result.scalars().all()]

    @strawberry.field
    async def curation_queue(
        self,
        status: Optional[str] = "pending",
        flag_type: Optional[str] = None,
        first: int = 20,
        offset: int = 0,
    ) -> list[CurationFlag]:
        """List curation flags."""
        async with AsyncSessionLocal() as session:
            stmt = select(CurationFlagModel)
            if status:
                stmt = stmt.where(CurationFlagModel.status == status)
            if flag_type:
                stmt = stmt.where(CurationFlagModel.flag_type == flag_type)
            stmt = stmt.order_by(CurationFlagModel.created_at.desc()).offset(offset).limit(first)
            result = await session.execute(stmt)
            return [
                CurationFlag(
                    id=str(row.id),
                    entity_type=row.entity_type,
                    entity_ref=row.entity_ref,
                    flag_type=FlagType(row.flag_type),
                    context=row.context,
                    status=FlagStatus(row.status),
                    created_at=str(row.created_at),
                    resolved_at=str(row.resolved_at) if row.resolved_at else None,
                    resolved_by=row.resolved_by,
                    resolution_note=row.resolution_note,
                )
                for row in result.scalars().all()
            ]

    @strawberry.field
    async def run_summaries(self) -> list[RunSummary]:
        """List pipeline run summaries."""
        async with AsyncSessionLocal() as session:
            stmt = select(RunSummaryModel).order_by(RunSummaryModel.started_at.desc())
            result = await session.execute(stmt)
            return [
                RunSummary(
                    run_id=row.run_id,
                    source=row.source,
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                    entity_counts=row.entity_counts,
                    enrichment_rate=row.enrichment_rate,
                    curation_flags=row.curation_flags,
                    delta=row.delta,
                    timing=row.timing,
                )
                for row in result.scalars().all()
            ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def resolve_flag(
        self,
        flag_id: str,
        action: str,
        resolved_by: str,
        note: Optional[str] = None,
    ) -> Optional[CurationFlag]:
        """Resolve a curation flag."""
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(CurationFlagModel).where(
                    CurationFlagModel.id == flag_id
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if not row:
                    return None
                row.status = action
                row.resolved_by = resolved_by
                row.resolution_note = note
                row.resolved_at = datetime.now(timezone.utc)
                await session.flush()
                return CurationFlag(
                    id=str(row.id),
                    entity_type=row.entity_type,
                    entity_ref=row.entity_ref,
                    flag_type=FlagType(row.flag_type),
                    context=row.context,
                    status=FlagStatus(row.status),
                    created_at=str(row.created_at),
                    resolved_at=str(row.resolved_at),
                    resolved_by=row.resolved_by,
                    resolution_note=row.resolution_note,
                )

    @strawberry.mutation
    async def import_registry(self, registry_path: str) -> strawberry.scalars.JSON:
        """Import a flat-file registry into the database."""
        from pathlib import Path

        from src.services.import_service import import_registry

        async with AsyncSessionLocal() as session:
            async with session.begin():
                stats = await import_registry(session, Path(registry_path))
                await session.commit()
        return stats


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
