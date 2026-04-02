"""GraphQL resolver functions using DatabaseBackend."""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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
        source_elements=row.source_elements or [] if hasattr(row, "source_elements") else [],
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


async def _paginated_query(session, model, stmt, first, after, sort_column=None):
    """Apply cursor pagination to a query and return edges + page_info + total.

    If sort_column is provided, sorts by that column instead of created_at.
    Cursor pagination uses (sort_column, id) for ordering.
    """
    # Total count WITH filters (use the filtered stmt, not unfiltered model)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar()

    order_col = sort_column if sort_column is not None else model.created_at

    # Apply cursor
    if after:
        from datetime import datetime as dt

        cursor_val, cursor_id = _decode_cursor(after)
        if sort_column is not None:
            # String-based cursor for non-timestamp sort columns
            stmt = stmt.where(
                (order_col > cursor_val)
                | ((order_col == cursor_val) & (model.id > uuid.UUID(cursor_id)))
            )
        else:
            ts_val = dt.fromisoformat(cursor_val)
            stmt = stmt.where(
                (order_col > ts_val)
                | ((order_col == ts_val) & (model.id > uuid.UUID(cursor_id)))
            )

    stmt = stmt.order_by(order_col, model.id).limit(first + 1)
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


# --- Cross-Entity Search ---


async def resolve_search(
    session: AsyncSession, query: str, first: int = 50, mode: str = "both"
) -> list[t.SearchResultType]:
    """Search across all entity types.

    Modes: lexical (tsvector/ILIKE), semantic (embedding similarity), both (combined).
    """
    from src.db.models import Element, Schema, Value, ValueSet

    results: list[t.SearchResultType] = []
    do_lexical = mode in ("lexical", "both")
    do_semantic = mode in ("semantic", "both")

    # --- Lexical search ---
    if do_lexical:
        elem_stmt = select(Element)
        if hasattr(Element, "search_tsv") and Element.search_tsv is not None:
            from sqlalchemy import func as sa_func
            elem_stmt = elem_stmt.where(
                Element.search_tsv.op("@@")(sa_func.plainto_tsquery("english", query))
            )
        else:
            elem_stmt = elem_stmt.where(
                Element.file_name.ilike(f"%{query}%") | Element.description.ilike(f"%{query}%")
            )
        elem_stmt = elem_stmt.limit(first)
        for row in (await session.execute(elem_stmt)).scalars():
            prov = row.provenance[0] if row.provenance else {}
            results.append(t.SearchResultType(
                entity_type="element", sha256=row.sha256,
                name=prov.get("name", row.file_name or row.sha256[:12]),
                source=prov.get("source"), data_type=row.data_type, unit=row.unit,
                description=row.description or prov.get("description", ""), score=1.0,
            ))

        for model_cls, etype, score_base in [
            (Schema, "schema", 0.9), (Value, "value", 0.8), (ValueSet, "valueset", 0.7),
        ]:
            name_col = getattr(model_cls, "label", None) or getattr(model_cls, "name", None) or model_cls.file_name
            stmt = select(model_cls).where(
                name_col.ilike(f"%{query}%") | model_cls.description.ilike(f"%{query}%")
            ).limit(first)
            for row in (await session.execute(stmt)).scalars():
                prov = row.provenance[0] if row.provenance else {}
                nm = getattr(row, "label", None) or getattr(row, "name", None) or row.file_name or row.sha256[:12]
                results.append(t.SearchResultType(
                    entity_type=etype, sha256=row.sha256,
                    name=prov.get("name", nm), source=prov.get("source"),
                    description=row.description or prov.get("description", ""), score=score_base,
                ))

    # --- Semantic search (pgvector nearest-neighbor) ---
    if do_semantic:
        try:
            from src.services.embedding_service import compute_embedding
            query_vec = compute_embedding(query)
            if query_vec is not None:
                from sqlalchemy import text as sa_text
                # Use pgvector cosine distance for element search
                sem_stmt = sa_text(
                    "SELECT sha256, file_name, data_type, unit, description, provenance, "
                    "1 - (embedding <=> :qvec::vector) AS similarity "
                    "FROM elements WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> :qvec::vector LIMIT :lim"
                )
                sem_result = await session.execute(
                    sem_stmt, {"qvec": str(query_vec.tolist()), "lim": first}
                )
                seen_sha = {r.sha256 for r in results}
                for row in sem_result:
                    if row.sha256 in seen_sha:
                        continue
                    prov = (row.provenance or [{}])[0] if row.provenance else {}
                    results.append(t.SearchResultType(
                        entity_type="element", sha256=row.sha256,
                        name=prov.get("name", row.file_name or row.sha256[:12]),
                        source=prov.get("source"), data_type=row.data_type, unit=row.unit,
                        description=row.description or prov.get("description", ""),
                        score=round(float(row.similarity), 4),
                    ))
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)

    results.sort(key=lambda r: (-r.score, r.name.lower()))
    return results[:first]


# --- Browse Queries ---


async def resolve_browse_elements(
    session: AsyncSession,
    source: str | None = None,
    data_type: t.DataType | None = None,
    has_annotations: bool | None = None,
    search_text: str | None = None,
    first: int = 20,
    after: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
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

    # Determine sort column
    sort_col_map = {
        "name": Element.file_name,
        "dataType": Element.data_type,
        "unit": Element.unit,
        "valueDomain": Element.value_domain,
        "description": Element.description,
    }
    sort_col = sort_col_map.get(sort_by or "", Element.file_name)
    if sort_order == "desc":
        sort_col = sort_col.desc().nulls_last()
    elif sort_col != Element.file_name:
        sort_col = sort_col.asc().nulls_last()

    rows, has_next, total = await _paginated_query(
        session, Element, stmt, first, after, sort_column=sort_col
    )
    edges = [
        t.ElementEdge(
            cursor=_encode_cursor(str(getattr(r, "file_name", "") or ""), str(r.id)),
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
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> t.SchemaConnection:
    from src.db.models import Schema

    stmt = select(Schema)
    if source:
        from sqlalchemy import text as sa_text
        stmt = stmt.where(sa_text("provenance @> :src ::jsonb").bindparams(
            src=f'[{{"source": "{source}"}}]'
        ))
    if search_text:
        stmt = stmt.where(
            Schema.file_name.ilike(f"%{search_text}%") | Schema.description.ilike(f"%{search_text}%")
        )

    sort_col_map = {"name": Schema.file_name, "description": Schema.description}
    sort_col = sort_col_map.get(sort_by or "", None)
    if sort_col is not None:
        if sort_order == "desc":
            sort_col = sort_col.desc().nulls_last()
        else:
            sort_col = sort_col.asc().nulls_last()

    rows, has_next, total = await _paginated_query(session, Schema, stmt, first, after, sort_column=sort_col)
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
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> t.ValueConnection:
    from src.db.models import Value

    stmt = select(Value)
    if source:
        from sqlalchemy import text as sa_text
        stmt = stmt.where(sa_text("provenance @> :src ::jsonb").bindparams(
            src=f'[{{"source": "{source}"}}]'
        ))
    if search_text:
        stmt = stmt.where(
            Value.label.ilike(f"%{search_text}%") | Value.description.ilike(f"%{search_text}%")
        )

    sort_col_map = {"name": Value.label, "label": Value.label, "description": Value.description}
    sort_col = sort_col_map.get(sort_by or "", None)
    if sort_col is not None:
        if sort_order == "desc":
            sort_col = sort_col.desc().nulls_last()
        else:
            sort_col = sort_col.asc().nulls_last()

    rows, has_next, total = await _paginated_query(session, Value, stmt, first, after, sort_column=sort_col)
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
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> t.ValueSetConnection:
    from src.db.models import ValueSet

    stmt = select(ValueSet)
    if source:
        from sqlalchemy import text as sa_text
        stmt = stmt.where(sa_text("provenance @> :src ::jsonb").bindparams(
            src=f'[{{"source": "{source}"}}]'
        ))
    if search_text:
        stmt = stmt.where(
            ValueSet.name.ilike(f"%{search_text}%") | ValueSet.description.ilike(f"%{search_text}%")
        )

    sort_col_map = {"name": ValueSet.name, "description": ValueSet.description}
    sort_col = sort_col_map.get(sort_by or "", None)
    if sort_col is not None:
        if sort_order == "desc":
            sort_col = sort_col.desc().nulls_last()
        else:
            sort_col = sort_col.asc().nulls_last()

    rows, has_next, total = await _paginated_query(session, ValueSet, stmt, first, after, sort_column=sort_col)
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


async def resolve_ontology_sources(
    session: AsyncSession, active: bool | None = None
) -> list[t.OntologySourceType]:
    from src.db.models import OntologySource

    stmt = select(OntologySource)
    if active is not None:
        stmt = stmt.where(OntologySource.active == active)
    stmt = stmt.order_by(OntologySource.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        t.OntologySourceType(
            id=str(r.id),
            name=r.name,
            display_name=r.display_name,
            url=r.url,
            format=r.format,
            term_count=r.term_count,
            active=r.active,
            last_refreshed_at=str(r.last_refreshed_at) if r.last_refreshed_at else None,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


async def resolve_ingestion_queue(
    session: AsyncSession, status: str | None = None, first: int = 50
) -> list[t.IngestionJobType]:
    from src.db.models import IngestionJob

    stmt = select(IngestionJob)
    if status:
        stmt = stmt.where(IngestionJob.status == status)
    stmt = stmt.order_by(IngestionJob.created_at.desc()).limit(first)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        t.IngestionJobType(
            id=str(r.id),
            repository_url=r.repository_url,
            adapter_type=r.adapter_type,
            status=r.status,
            auto_approved=r.auto_approved,
            entity_counts=r.entity_counts,
            error_message=r.error_message,
            approved_by=r.approved_by,
            started_at=str(r.started_at) if r.started_at else None,
            completed_at=str(r.completed_at) if r.completed_at else None,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


async def resolve_enrichment_proposals(
    session: AsyncSession,
    entity_type: str | None = None,
    entity_ref: str | None = None,
    status: str | None = None,
    first: int = 50,
) -> list[t.LLMEnrichmentProposalType]:
    from src.db.models import LLMEnrichmentProposal

    stmt = select(LLMEnrichmentProposal)
    if entity_type:
        stmt = stmt.where(LLMEnrichmentProposal.entity_type == entity_type)
    if entity_ref:
        stmt = stmt.where(LLMEnrichmentProposal.entity_ref.startswith(entity_ref))
    if status:
        stmt = stmt.where(LLMEnrichmentProposal.status == status)
    stmt = stmt.order_by(LLMEnrichmentProposal.created_at.desc()).limit(first)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        t.LLMEnrichmentProposalType(
            id=str(r.id),
            entity_type=r.entity_type,
            entity_ref=r.entity_ref,
            proposal_type=r.proposal_type,
            proposed_value=r.proposed_value or {},
            reasoning=r.reasoning,
            confidence=r.confidence,
            status=r.status,
            reviewed_by=r.reviewed_by,
            reviewed_at=str(r.reviewed_at) if r.reviewed_at else None,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


async def resolve_releases(
    session: AsyncSession, release_type: str | None = None
) -> list[t.ReleaseType]:
    from src.db.models import Release

    stmt = select(Release)
    if release_type:
        stmt = stmt.where(Release.release_type == release_type)
    stmt = stmt.order_by(Release.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return [
        t.ReleaseType(
            id=str(r.id),
            version=r.version,
            release_type=r.release_type,
            file_path=r.file_path,
            file_size=r.file_size,
            entity_counts=r.entity_counts,
            download_count=r.download_count,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


async def resolve_tag_release(session: AsyncSession, version: str) -> t.ReleaseType:
    from src.db.models import Release
    import uuid as _uuid

    latest = (
        await session.execute(
            select(Release)
            .where(Release.release_type == "nightly")
            .order_by(Release.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not latest:
        raise ValueError("No nightly release found to tag")

    versioned = Release(
        id=_uuid.uuid4(),
        version=version,
        release_type="versioned",
        file_path=latest.file_path,
        file_size=latest.file_size,
        entity_counts=latest.entity_counts,
    )
    session.add(versioned)
    await session.flush()
    return t.ReleaseType(
        id=str(versioned.id),
        version=versioned.version,
        release_type=versioned.release_type,
        file_path=versioned.file_path,
        file_size=versioned.file_size,
        entity_counts=versioned.entity_counts,
        download_count=0,
        created_at=str(versioned.created_at) if versioned.created_at else "",
    )


async def resolve_approve_annotation(
    session: AsyncSession, entity_sha256: str, annotation_index: int, curator: str
) -> t.Element:
    """Move an ontology annotation to curated_annotations (protected from re-enrichment)."""
    from src.db.models import Element

    stmt = select(Element).where(Element.sha256.startswith(entity_sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Element not found: {entity_sha256}")

    annotations = list(row.ontology_annotations or [])
    if annotation_index < 0 or annotation_index >= len(annotations):
        raise ValueError(f"Invalid annotation index: {annotation_index}")

    approved = annotations[annotation_index]
    approved["approved_by"] = curator
    approved["approved_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    curated = list(row.curated_annotations or [])
    curated.append(approved)
    row.curated_annotations = curated

    await session.flush()
    return _element_from_row(row)


async def resolve_reject_annotation(
    session: AsyncSession, entity_sha256: str, annotation_index: int, curator: str, reason: str | None = None
) -> t.Element:
    """Remove an ontology annotation and record the rejection."""
    from src.db.models import Element

    stmt = select(Element).where(Element.sha256.startswith(entity_sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Element not found: {entity_sha256}")

    annotations = list(row.ontology_annotations or [])
    if annotation_index < 0 or annotation_index >= len(annotations):
        raise ValueError(f"Invalid annotation index: {annotation_index}")

    removed = annotations.pop(annotation_index)
    row.ontology_annotations = annotations

    # Record rejection in provenance
    prov = list(row.provenance or [])
    prov.append({
        "source": "curation",
        "class": "",
        "name": f"rejected_annotation:{removed.get('term_uri', '')}",
        "description": reason or "Annotation rejected by curator",
        "attributed_to": curator,
        "activity": "curation",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    })
    row.provenance = prov

    await session.flush()
    return _element_from_row(row)


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


# --- T022: Element Versioning ---


async def resolve_version_element(
    session: AsyncSession,
    sha256: str,
    changes: dict,
    curator_name: str,
) -> t.Element:
    """Create a new version of an element with changed semantic fields.

    - Recomputes sha256 from the updated semantic content
    - Marks old element's superseded_by with the new sha256
    - Creates a Transform with function_type="curation_update" linking old->new
    - Returns the new element
    """
    from undata_library.hashing import canonical_json, compute_sha256

    from src.db.models import Element, Transform

    # Load old element
    stmt = select(Element).where(Element.sha256.startswith(sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Element not found: {sha256}")

    old_sha256 = row.sha256

    # Build new semantic dict with changes applied
    new_semantic = dict(row.semantic or {})
    for field, value in changes.items():
        if value is not None:
            new_semantic[field] = value

    # Recompute sha256 from new semantic content
    canonical = canonical_json(new_semantic)
    new_sha256 = compute_sha256(canonical)

    if new_sha256 == old_sha256:
        raise ValueError("No semantic change detected — new hash is identical to old hash")

    # Check that new sha256 doesn't already exist
    existing = (
        await session.execute(select(Element).where(Element.sha256 == new_sha256).limit(1))
    ).scalar_one_or_none()
    if existing:
        raise ValueError(f"Element with sha256 {new_sha256[:12]} already exists")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Build provenance for new element — carry forward old provenance + add curation entry
    new_provenance = list(row.provenance or [])
    new_provenance.append({
        "source": "curation",
        "class": "",
        "name": curator_name,
        "description": f"Versioned from {old_sha256[:12]}: {', '.join(changes.keys())}",
        "activity": "curation_update",
        "attributed_to": curator_name,
        "generated_at": now_iso,
    })

    # Create new element row with changed fields
    new_row = Element(
        sha256=new_sha256,
        file_name=row.file_name,
        data_type=changes.get("data_type", row.data_type),
        unit=changes.get("unit", row.unit),
        unit_uri=changes.get("unit_uri", row.unit_uri),
        pattern=changes.get("pattern", row.pattern),
        value_domain=changes.get("value_domain", row.value_domain),
        description=changes.get("description", row.description),
        min_value=changes.get("min_value", row.min_value),
        max_value=changes.get("max_value", row.max_value),
        type_ref=changes.get("type_ref", row.type_ref),
        semantic=new_semantic,
        provenance=new_provenance,
        ontology_annotations=list(row.ontology_annotations or []),
        curated_annotations=list(row.curated_annotations or []) if row.curated_annotations else None,
    )
    session.add(new_row)

    # Mark old element as superseded
    row.superseded_by = new_sha256

    # Create a Transform linking old -> new
    transform_semantic = {
        "source_element": old_sha256,
        "target_element": new_sha256,
        "function_type": "curation_update",
        "changes": changes,
    }
    transform_canonical = canonical_json(transform_semantic)
    transform_sha256 = compute_sha256(transform_canonical)

    transform = Transform(
        sha256=transform_sha256,
        source_element=old_sha256,
        target_element=new_sha256,
        function_type="curation_update",
        description=f"Curation update by {curator_name}: {', '.join(changes.keys())}",
        semantic=transform_semantic,
        provenance=[{
            "source": "curation",
            "class": "",
            "name": curator_name,
            "description": f"Versioned element {old_sha256[:12]} -> {new_sha256[:12]}",
            "activity": "curation_update",
            "attributed_to": curator_name,
            "generated_at": now_iso,
        }],
    )
    session.add(transform)

    await session.flush()
    return _element_from_row(new_row)


# --- T034: Ingestion Approval/Rejection ---


def _ingestion_job_to_type(row) -> t.IngestionJobType:
    return t.IngestionJobType(
        id=str(row.id),
        repository_url=row.repository_url,
        adapter_type=row.adapter_type,
        status=row.status,
        auto_approved=row.auto_approved,
        entity_counts=row.entity_counts,
        error_message=row.error_message,
        approved_by=row.approved_by,
        started_at=str(row.started_at) if row.started_at else None,
        completed_at=str(row.completed_at) if row.completed_at else None,
        created_at=str(row.created_at),
    )


async def resolve_approve_ingestion(
    session: AsyncSession,
    job_id: str,
    approver: str,
) -> t.IngestionJobType:
    """Approve an ingestion job — set status to 'approved' and record approver."""
    from src.db.models import IngestionJob

    stmt = select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id))
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Ingestion job not found: {job_id}")

    if row.status not in ("pending", "completed"):
        raise ValueError(f"Cannot approve job in status '{row.status}' — must be 'pending' or 'completed'")

    row.status = "approved"
    row.approved_by = approver
    await session.flush()
    return _ingestion_job_to_type(row)


async def resolve_reject_ingestion(
    session: AsyncSession,
    job_id: str,
    rejector: str,
    reason: str | None = None,
) -> t.IngestionJobType:
    """Reject an ingestion job — set status to 'rejected' and record reason."""
    from src.db.models import IngestionJob

    stmt = select(IngestionJob).where(IngestionJob.id == uuid.UUID(job_id))
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Ingestion job not found: {job_id}")

    if row.status not in ("pending", "completed"):
        raise ValueError(f"Cannot reject job in status '{row.status}' — must be 'pending' or 'completed'")

    row.status = "rejected"
    row.error_message = reason or "Rejected by curator"
    await session.flush()
    return _ingestion_job_to_type(row)


# --- T039-T040: Enrichment Request & Proposal Review ---


async def resolve_request_enrichment(
    session: AsyncSession,
    entity_type: str,
    entity_ref: str,
) -> t.LLMEnrichmentProposalType:
    """Request enrichment for an entity — calls enrichment_service.suggest_ontology_annotation."""
    from src.services.enrichment_service import suggest_ontology_annotation

    if entity_type != "element":
        raise ValueError(f"Enrichment currently only supports entity_type='element', got '{entity_type}'")

    result = await suggest_ontology_annotation(session, entity_ref)

    if "error" in result:
        raise ValueError(f"Enrichment failed: {result['error']}")

    # Load the created proposal to return it
    from src.db.models import LLMEnrichmentProposal

    proposal_id = result["proposal_id"]
    stmt = select(LLMEnrichmentProposal).where(
        LLMEnrichmentProposal.id == uuid.UUID(proposal_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError("Enrichment proposal was created but could not be loaded")

    return _proposal_to_type(row)


async def resolve_review_proposal(
    session: AsyncSession,
    proposal_id: str,
    decision: str,
    reviewer: str,
    reason: str | None = None,
) -> t.LLMEnrichmentProposalType:
    """Approve or reject an LLM enrichment proposal."""
    from src.db.models import LLMEnrichmentProposal

    stmt = select(LLMEnrichmentProposal).where(
        LLMEnrichmentProposal.id == uuid.UUID(proposal_id)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise ValueError(f"Enrichment proposal not found: {proposal_id}")

    if row.status != "pending":
        raise ValueError(f"Proposal already resolved with status '{row.status}'")

    if decision not in ("approved", "rejected"):
        raise ValueError(f"Decision must be 'approved' or 'rejected', got '{decision}'")

    now = datetime.now(timezone.utc)
    row.status = decision
    row.reviewed_by = reviewer
    row.reviewed_at = now

    # If approved, apply the proposed annotation to the entity
    if decision == "approved" and row.proposal_type == "ontology_annotation":
        from src.db.models import Element

        elem_stmt = select(Element).where(Element.sha256.startswith(row.entity_ref)).limit(1)
        elem_row = (await session.execute(elem_stmt)).scalar_one_or_none()
        if elem_row:
            annotations = list(elem_row.ontology_annotations or [])
            proposed = row.proposed_value or {}
            annotation = {
                "term_uri": proposed.get("term_uri", ""),
                "term_label": proposed.get("term_label", ""),
                "ontology": proposed.get("ontology", ""),
                "mapping_relation": proposed.get("mapping_relation", ""),
                "match_level": "llm_enrichment",
                "score": row.confidence or 0.0,
                "model": "llm",
                "primary": False,
            }
            annotations.append(annotation)
            elem_row.ontology_annotations = annotations

    await session.flush()
    return _proposal_to_type(row)


async def resolve_ontology_store_info(session: AsyncSession) -> list[dict]:
    """Read ontology info from pyoxigraph store, falling back to DB ontology_sources."""
    # Try pyoxigraph store first
    try:
        from pathlib import Path
        store_path = Path.home() / ".cache" / "undata" / "ontology-store"
        if store_path.exists():
            from undata_library.ontology_store import OntologyStore
            store = OntologyStore(store_path)
            loaded = store.list_loaded()
            if loaded:
                return [
                    {
                        "name": entry.get("name", "") or "",
                        "display_name": entry.get("display_name") or entry.get("name", "") or "",
                        "term_count": entry.get("term_count", 0) or 0,
                        "format": entry.get("format", "") or "",
                        "checksum": entry.get("checksum", "") or "",
                        "last_refreshed": entry.get("last_refreshed", "") or "",
                    }
                    for entry in loaded
                ]
    except Exception as e:
        logger.debug("Pyoxigraph store not available: %s", e)

    # Fallback: read from DB ontology_sources table
    from src.db.models import OntologySource
    stmt = select(OntologySource).where(OntologySource.active == True).order_by(OntologySource.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "name": r.name,
            "display_name": r.display_name,
            "term_count": r.term_count,
            "format": r.format,
            "checksum": r.checksum or "",
            "last_refreshed": str(r.last_refreshed_at) if r.last_refreshed_at else "",
        }
        for r in rows
    ]


async def resolve_audit_log(
    session: AsyncSession,
    entity_type: str | None = None,
    entity_ref: str | None = None,
    agent: str | None = None,
    activity: str | None = None,
    first: int = 50,
) -> list[t.AuditLogEntry]:
    """Query audit log entries with optional filters."""
    from src.db.models import AuditLog

    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_ref:
        stmt = stmt.where(AuditLog.entity_ref.startswith(entity_ref))
    if agent:
        stmt = stmt.where(AuditLog.agent == agent)
    if activity:
        stmt = stmt.where(AuditLog.activity == activity)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(first)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        t.AuditLogEntry(
            id=str(r.id),
            activity=r.activity,
            agent=r.agent,
            agent_type=r.agent_type,
            entity_type=r.entity_type,
            entity_ref=r.entity_ref,
            generated_entity_ref=r.generated_entity_ref,
            details=r.details,
            created_at=str(r.created_at) if r.created_at else "",
        )
        for r in rows
    ]


def _proposal_to_type(row) -> t.LLMEnrichmentProposalType:
    return t.LLMEnrichmentProposalType(
        id=str(row.id),
        entity_type=row.entity_type,
        entity_ref=row.entity_ref,
        proposal_type=row.proposal_type,
        proposed_value=row.proposed_value or {},
        reasoning=row.reasoning,
        confidence=row.confidence,
        evidence=getattr(row, "evidence", None),
        status=row.status,
        reviewed_by=row.reviewed_by,
        reviewed_at=str(row.reviewed_at) if row.reviewed_at else None,
        created_at=str(row.created_at),
    )
