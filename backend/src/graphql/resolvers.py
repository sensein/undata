"""GraphQL resolver functions using DatabaseBackend."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    ENTITY_MODEL_MAP,
    Contribution as ContributionModel,
    CurationFlag as CurationFlagModel,
    RunSummary as RunSummaryModel,
)
from src.storage.database_backend import DatabaseBackend

from . import types as t


def _encode_cursor(created_at, row_id) -> str:
    return base64.b64encode(f"{created_at}|{row_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    decoded = base64.b64decode(cursor.encode()).decode()
    parts = decoded.split("|", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _row_to_provenance(prov_list: list) -> list[t.ProvenanceEntry]:
    return [
        t.ProvenanceEntry(
            source=p.get("source", ""),
            class_name=p.get("class", ""),
            name=p.get("name", ""),
            description=p.get("description", ""),
        )
        for p in (prov_list or [])
        if isinstance(p, dict)
    ]


def _row_to_annotations(ann_list: list) -> list[t.OntologyAnnotation]:
    return [
        t.OntologyAnnotation(
            term_uri=a.get("term_uri", ""),
            term_label=a.get("term_label", ""),
            ontology=a.get("ontology", ""),
            mapping_relation=a.get("mapping_relation", ""),
            match_level=a.get("match_level", ""),
            score=float(a.get("score", 0)),
            model=a.get("model", ""),
            primary=bool(a.get("primary", False)),
        )
        for a in (ann_list or [])
        if isinstance(a, dict)
    ]


def _element_from_row(row) -> t.Element:
    return t.Element(
        sha256=row.sha256 or "",
        file_name=row.file_name,
        data_type=row.data_type,
        unit=row.unit,
        unit_uri=getattr(row, "unit_uri", None),
        pattern=row.pattern,
        value_domain=row.value_domain,
        description=row.description,
        min_value=row.min_value,
        max_value=row.max_value,
        type_ref=row.type_ref,
        semantic=row.semantic or {},
        provenance=_row_to_provenance(row.provenance),
        ontology_annotations=_row_to_annotations(row.ontology_annotations),
    )


def _schema_from_row(row) -> t.Schema:
    return t.Schema(
        sha256=row.sha256 or "",
        file_name=row.file_name,
        subclass_of=row.subclass_of,
        is_mixin=row.is_mixin,
        properties=row.properties or [],
        description=row.description,
        semantic=row.semantic or {},
        provenance=_row_to_provenance(row.provenance),
        ontology_annotations=_row_to_annotations(row.ontology_annotations),
    )


def _value_from_row(row) -> t.Value:
    return t.Value(
        sha256=row.sha256 or "",
        file_name=row.file_name,
        label=row.label,
        value_type=row.value_type,
        ontology_id=row.ontology_id,
        description=row.description,
        semantic=row.semantic or {},
        provenance=_row_to_provenance(row.provenance),
        ontology_annotations=_row_to_annotations(row.ontology_annotations),
    )


def _valueset_from_row(row) -> t.ValueSet:
    return t.ValueSet(
        sha256=row.sha256 or "",
        file_name=row.file_name,
        name=row.name,
        members=row.members or [],
        description=row.description,
        semantic=row.semantic or {},
        provenance=_row_to_provenance(row.provenance),
        ontology_annotations=_row_to_annotations(row.ontology_annotations),
    )


def _transform_from_row(row) -> t.Transform:
    return t.Transform(
        sha256=row.sha256 or "",
        file_name=row.file_name,
        source_element=row.source_element or "",
        target_element=row.target_element or "",
        function_type=row.function_type,
        input_type=row.input_type,
        output_type=row.output_type,
        expression=row.expression,
        expression_type=row.expression_type,
        confidence=row.confidence,
        description=row.description,
        semantic=row.semantic or {},
        provenance=_row_to_provenance(row.provenance),
    )


def _flag_from_row(row) -> t.CurationFlag:
    return t.CurationFlag(
        id=strawberry_id(row.id),
        entity_type=row.entity_type or "",
        entity_ref=row.entity_ref or "",
        flag_type=t.FlagType(row.flag_type) if row.flag_type else t.FlagType.NEEDS_REVIEW,
        context=row.context or {},
        llm_verification=row.llm_verification,
        status=t.FlagStatus(row.status) if row.status else t.FlagStatus.PENDING,
        created_at=str(row.created_at) if row.created_at else "",
        resolved_at=str(row.resolved_at) if row.resolved_at else None,
        resolved_by=row.resolved_by,
        resolution_note=row.resolution_note,
    )


def _contribution_from_row(row) -> t.Contribution:
    return t.Contribution(
        id=strawberry_id(row.id),
        entity_type=row.entity_type or "",
        entity_ref=row.entity_ref or "",
        contribution_type=t.ContributionType(row.contribution_type)
        if row.contribution_type
        else t.ContributionType.COMMENT,
        content=row.content or {},
        status=t.ContributionStatus(row.status) if row.status else t.ContributionStatus.PENDING,
        contributor=row.contributor,
        reviewed_by=row.reviewed_by,
        reviewed_at=str(row.reviewed_at) if row.reviewed_at else None,
        review_note=row.review_note,
        created_at=str(row.created_at) if row.created_at else "",
    )


def _run_from_row(row) -> t.RunSummary:
    return t.RunSummary(
        run_id=row.run_id or "",
        source=row.source or "",
        started_at=row.started_at,
        completed_at=row.completed_at,
        entity_counts=row.entity_counts or {},
        enrichment_rate=row.enrichment_rate,
        curation_flags=row.curation_flags,
        delta=row.delta,
        timing=row.timing,
    )


def strawberry_id(val) -> str:
    return str(val)


# --- Query Helpers ---


async def _paginated_query(session, model, stmt, first, after):
    """Apply cursor pagination to a query and return edges + page_info + total."""
    # Total count WITH filters (use the filtered stmt, not unfiltered model)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar()

    # Apply cursor
    if after:
        from datetime import datetime as dt

        cursor_ts, cursor_id = _decode_cursor(after)
        ts_val = dt.fromisoformat(cursor_ts)
        stmt = stmt.where(
            (model.created_at > ts_val)
            | ((model.created_at == ts_val) & (model.id > uuid.UUID(cursor_id)))
        )

    stmt = stmt.order_by(model.created_at, model.id).limit(first + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars())

    has_next = len(rows) > first
    if has_next:
        rows = rows[:first]

    return rows, has_next, total


# --- Single Entity Lookups ---


async def resolve_element(session: AsyncSession, sha256: str) -> t.Element | None:
    from src.db.models import Element

    stmt = select(Element).where(Element.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _element_from_row(row) if row else None


async def resolve_schema(session: AsyncSession, sha256: str) -> t.Schema | None:
    from src.db.models import Schema

    stmt = select(Schema).where(Schema.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _schema_from_row(row) if row else None


async def resolve_value(session: AsyncSession, sha256: str) -> t.Value | None:
    from src.db.models import Value

    stmt = select(Value).where(Value.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _value_from_row(row) if row else None


async def resolve_valueset(session: AsyncSession, sha256: str) -> t.ValueSet | None:
    from src.db.models import ValueSet

    stmt = select(ValueSet).where(ValueSet.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _valueset_from_row(row) if row else None


async def resolve_transform(session: AsyncSession, sha256: str) -> t.Transform | None:
    from src.db.models import Transform

    stmt = select(Transform).where(Transform.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _transform_from_row(row) if row else None


# --- Browse Queries ---


async def resolve_browse_elements(
    session: AsyncSession,
    source: str | None = None,
    data_type: t.DataType | None = None,
    has_annotations: bool | None = None,
    search_text: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.ElementConnection:
    from src.db.models import Element

    stmt = select(Element)
    if source:
        from sqlalchemy import text as sa_text

        stmt = stmt.where(sa_text("provenance @> :src_filter ::jsonb").bindparams(
            src_filter=f'[{{"source": "{source}"}}]'
        ))
    if data_type:
        stmt = stmt.where(Element.data_type == data_type.value)
    if has_annotations is True:
        stmt = stmt.where(func.jsonb_array_length(Element.ontology_annotations) > 0)
    if search_text:
        # Use tsvector full-text search if available, otherwise fall back to ILIKE
        if hasattr(Element, "search_tsv") and Element.search_tsv is not None:
            from sqlalchemy import func as sa_func

            stmt = stmt.where(
                Element.search_tsv.op("@@")(sa_func.plainto_tsquery("english", search_text))
            )
        else:
            pattern = f"%{search_text}%"
            stmt = stmt.where(
                Element.description.ilike(pattern)
                | Element.file_name.ilike(pattern)
            )

    rows, has_next, total = await _paginated_query(session, Element, stmt, first, after)
    edges = [
        t.ElementEdge(
            cursor=_encode_cursor(str(r.created_at), str(r.id)),
            node=_element_from_row(r),
        )
        for r in rows
    ]
    return t.ElementConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_browse_schemas(
    session: AsyncSession,
    source: str | None = None,
    search_text: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.SchemaConnection:
    from src.db.models import Schema

    stmt = select(Schema)
    if search_text:
        stmt = stmt.where(Schema.description.ilike(f"%{search_text}%"))

    rows, has_next, total = await _paginated_query(session, Schema, stmt, first, after)
    edges = [
        t.SchemaEdge(cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_schema_from_row(r))
        for r in rows
    ]
    return t.SchemaConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_browse_values(
    session: AsyncSession,
    source: str | None = None,
    search_text: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.ValueConnection:
    from src.db.models import Value

    stmt = select(Value)
    if search_text:
        stmt = stmt.where(Value.label.ilike(f"%{search_text}%"))

    rows, has_next, total = await _paginated_query(session, Value, stmt, first, after)
    edges = [
        t.ValueEdge(cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_value_from_row(r))
        for r in rows
    ]
    return t.ValueConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_browse_valuesets(
    session: AsyncSession,
    source: str | None = None,
    search_text: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.ValueSetConnection:
    from src.db.models import ValueSet

    stmt = select(ValueSet)
    if search_text:
        stmt = stmt.where(ValueSet.name.ilike(f"%{search_text}%"))

    rows, has_next, total = await _paginated_query(session, ValueSet, stmt, first, after)
    edges = [
        t.ValueSetEdge(cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_valueset_from_row(r))
        for r in rows
    ]
    return t.ValueSetConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_browse_transforms(
    session: AsyncSession,
    source_element: str | None = None,
    target_element: str | None = None,
    function_type: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.TransformConnection:
    from src.db.models import Transform

    stmt = select(Transform)
    if source_element:
        stmt = stmt.where(Transform.source_element.ilike(f"%{source_element}%"))
    if target_element:
        stmt = stmt.where(Transform.target_element.ilike(f"%{target_element}%"))
    if function_type:
        stmt = stmt.where(Transform.function_type == function_type)

    rows, has_next, total = await _paginated_query(session, Transform, stmt, first, after)
    edges = [
        t.TransformEdge(cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_transform_from_row(r))
        for r in rows
    ]
    return t.TransformConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_schemas_using_element(
    session: AsyncSession, element_sha256: str, first: int = 50
) -> t.SchemaConnection:
    """Find schemas whose properties[] JSONB array contains the element sha256."""
    from src.db.models import Element, Schema
    from sqlalchemy import text as sa_text

    # Resolve prefix to full sha256 if needed
    full_sha = element_sha256
    if len(element_sha256) < 64:
        row = (await session.execute(
            select(Element.sha256).where(Element.sha256.startswith(element_sha256)).limit(1)
        )).scalar_one_or_none()
        if row:
            full_sha = row

    stmt = select(Schema).where(
        sa_text("properties::jsonb @> :ref ::jsonb").bindparams(ref=f'["{full_sha}"]')
    )
    rows, has_next, total = await _paginated_query(session, Schema, stmt, first, None)
    edges = [
        t.SchemaEdge(cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_schema_from_row(r))
        for r in rows
    ]
    return t.SchemaConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_transforms_for_element(
    session: AsyncSession, element_sha256: str, first: int = 50
) -> t.TransformConnection:
    """Find transforms where source or target matches the element sha256 or contains it."""
    from src.db.models import Element, Transform

    # Resolve prefix to full sha256
    full_sha = element_sha256
    if len(element_sha256) < 64:
        row = (await session.execute(
            select(Element.sha256).where(Element.sha256.startswith(element_sha256)).limit(1)
        )).scalar_one_or_none()
        if row:
            full_sha = row

    stmt = select(Transform).where(
        Transform.source_element.ilike(f"%{full_sha}%")
        | Transform.target_element.ilike(f"%{full_sha}%")
    )
    rows, has_next, total = await _paginated_query(session, Transform, stmt, first, None)
    edges = [
        t.TransformEdge(
            cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_transform_from_row(r)
        )
        for r in rows
    ]
    return t.TransformConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_flags_for_entity(
    session: AsyncSession, entity_type: str, entity_ref: str, first: int = 50
) -> t.CurationFlagConnection:
    """Find curation flags for a specific entity (supports sha256 prefix matching)."""
    stmt = select(CurationFlagModel).where(
        CurationFlagModel.entity_type == entity_type,
        CurationFlagModel.entity_ref.startswith(entity_ref),
    )
    rows, has_next, total = await _paginated_query(session, CurationFlagModel, stmt, first, None)
    edges = [
        t.CurationFlagEdge(
            cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_flag_from_row(r)
        )
        for r in rows
    ]
    return t.CurationFlagConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_curation_queue(
    session: AsyncSession,
    flag_type: t.FlagType | None = None,
    status: t.FlagStatus | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.CurationFlagConnection:
    stmt = select(CurationFlagModel)
    if status:
        stmt = stmt.where(CurationFlagModel.status == status.value)
    if flag_type:
        stmt = stmt.where(CurationFlagModel.flag_type == flag_type.value)

    rows, has_next, total = await _paginated_query(session, CurationFlagModel, stmt, first, after)
    edges = [
        t.CurationFlagEdge(
            cursor=_encode_cursor(str(r.created_at), str(r.id)), node=_flag_from_row(r)
        )
        for r in rows
    ]
    return t.CurationFlagConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=has_next, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_run_summaries(
    session: AsyncSession,
    source: str | None = None,
    first: int = 20,
    after: str | None = None,
) -> t.RunSummaryConnection:
    stmt = select(RunSummaryModel)
    if source:
        stmt = stmt.where(RunSummaryModel.source == source)

    # Run summaries order by started_at desc
    stmt = stmt.order_by(RunSummaryModel.started_at.desc()).limit(first)
    result = await session.execute(stmt)
    rows = list(result.scalars())

    count_stmt = select(func.count()).select_from(RunSummaryModel)
    total = (await session.execute(count_stmt)).scalar()

    edges = [
        t.RunSummaryEdge(cursor=_encode_cursor(str(r.started_at), str(r.id)), node=_run_from_row(r))
        for r in rows
    ]
    return t.RunSummaryConnection(
        edges=edges,
        page_info=t.PageInfo(has_next_page=False, end_cursor=edges[-1].cursor if edges else None),
        total_count=total,
    )


async def resolve_latest_run(session: AsyncSession, source: str | None = None) -> t.RunSummary | None:
    stmt = select(RunSummaryModel).order_by(RunSummaryModel.started_at.desc()).limit(1)
    if source:
        stmt = stmt.where(RunSummaryModel.source == source)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return _run_from_row(row) if row else None


# --- Mutations ---


async def resolve_resolve_flag(session: AsyncSession, input: t.ResolveFlagInput) -> t.CurationFlag:
    backend = DatabaseBackend(session)
    from undata_library.models import FlagStatus

    result = await backend.flags.resolve_flag(
        str(input.flag_id), FlagStatus(input.action.value), input.resolved_by, input.note
    )
    if result is None:
        raise ValueError(f"Flag {input.flag_id} not found")

    # Re-read from DB for GraphQL type
    stmt = select(CurationFlagModel).where(CurationFlagModel.id == uuid.UUID(str(input.flag_id)))
    db_result = await session.execute(stmt)
    row = db_result.scalar_one()
    return _flag_from_row(row)


async def resolve_batch_resolve_flags(
    session: AsyncSession, input: t.BatchResolveFlagInput
) -> list[t.CurationFlag]:
    results = []
    for flag_id in input.flag_ids:
        single = t.ResolveFlagInput(
            flag_id=flag_id, action=input.action, resolved_by=input.resolved_by, note=input.note
        )
        results.append(await resolve_resolve_flag(session, single))
    return results


async def resolve_submit_contribution(
    session: AsyncSession, input: t.SubmitContributionInput
) -> t.Contribution:
    record = ContributionModel(
        entity_type=input.entity_type,
        entity_ref=input.entity_ref,
        contribution_type=input.contribution_type.value,
        content=input.content,
        contributor=input.contributor,
    )
    session.add(record)
    await session.flush()

    return _contribution_from_row(record)


async def resolve_update_entity(
    session: AsyncSession,
    entity_type: str,
    sha256: str,
    updates: dict,
    reason: str,
    curator_name: str,
) -> dict | None:
    """Update an entity's fields and record the change in provenance."""
    from datetime import datetime, timezone

    from src.db.models import ENTITY_MODEL_MAP

    model = ENTITY_MODEL_MAP.get(entity_type)
    if not model:
        raise ValueError(f"Invalid entity type: {entity_type}")

    stmt = select(model).where(model.sha256.startswith(sha256)).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        return None

    # Apply updates to columns and semantic JSONB
    semantic = dict(row.semantic or {})
    for field, value in updates.items():
        if value is None:
            continue
        if hasattr(row, field):
            setattr(row, field, value)
        semantic[field] = value
    row.semantic = semantic

    # Handle ontology_annotations specially
    if "ontology_annotations" in updates and updates["ontology_annotations"] is not None:
        row.ontology_annotations = updates["ontology_annotations"]
        semantic["ontology_annotations"] = updates["ontology_annotations"]
        row.semantic = semantic

    # Record change in provenance
    provenance = list(row.provenance or [])
    provenance.append({
        "source": "curation",
        "class": "",
        "name": curator_name,
        "description": reason,
        "activity": "curation",
        "attributed_to": curator_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    row.provenance = provenance

    await session.flush()
    return row


async def resolve_import_registry(session: AsyncSession, registry_path: str) -> t.ImportResult:
    from src.services.import_service import import_registry

    stats = await import_registry(session, registry_path)
    return t.ImportResult(
        elements=stats.get("elements", 0),
        schemas=stats.get("schemas", 0),
        values=stats.get("values", 0),
        valuesets=stats.get("valuesets", 0),
        flags=stats.get("flags", 0),
        runs=stats.get("runs", 0),
    )
