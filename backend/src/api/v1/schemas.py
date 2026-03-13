"""Dynamic schema management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import src.services.schema_changelog as schema_changelog_svc
from src.db.session import get_db
from src.models.db import (
    DataElement,
    DataElementVersion,
    DynamicSchema,
    DynamicSchemaElement,
    SchemaMixin,
    UserProfile,
)
from src.models.schemas import (
    AddMixinRequest,
    DynamicSchemaCreate,
    DynamicSchemaElementRef,
    DynamicSchemaResponse,
    DynamicSchemaSummary,
    DynamicSchemaUpdate,
    InheritanceTreeEdge,
    InheritanceTreeNode,
    InheritanceTreeResponse,
    PaginatedList,
    ResolvedElementRef,
    ResolvedSchemaResponse,
    SchemaClassesResponse,
    SetParentRequest,
    SupersedeSchemaRequest,
)
from src.services.authz import Role, require_role
from src.services.dynamic_schemas import (
    AlreadySupersededError,
    DynamicSchemaService,
    ElementNotFoundError,
    SchemaNotFoundError,
    VersionConflictError,
)
from src.services.schema_class import get_classes_for_schema
from src.services.schema_mro import (
    CycleError,
    compute_depth,
    detect_cycle_in_adjacency,
    get_resolved_elements,
    invalidate_mro_cache,
    resolve_mro,
)

router = APIRouter(prefix="/schemas", tags=["schemas"])


async def _build_schema_response(
    session: AsyncSession, schema: DynamicSchema
) -> DynamicSchemaResponse:
    # Load elements
    elements_result = await session.execute(
        select(DynamicSchemaElement)
        .where(DynamicSchemaElement.schema_id == schema.id)
        .order_by(DynamicSchemaElement.position)
    )
    element_links = elements_result.scalars().all()

    element_refs = []
    for link in element_links:
        el_result = await session.execute(
            select(DataElement).where(DataElement.id == link.element_id)
        )
        el = el_result.scalar_one_or_none()
        if el:
            ver_result = await session.execute(
                select(DataElementVersion).where(DataElementVersion.id == el.current_version_id)
            )
            ver = ver_result.scalar_one_or_none()

            superseded_by_uri = None
            if el.superseded_by:
                sup_result = await session.execute(
                    select(DataElement.uri).where(DataElement.id == el.superseded_by)
                )
                superseded_by_uri = sup_result.scalar_one_or_none()

            element_refs.append(
                DynamicSchemaElementRef(
                    element_id=el.id,
                    element_uri=el.uri,
                    element_name=ver.name if ver else "",
                    position=link.position,
                    field_alias=link.field_alias,
                    element_unit=ver.unit if ver else None,
                    element_superseded_by=superseded_by_uri,
                )
            )

    # Resolve superseded_by URI
    superseded_by_uri = None
    if schema.superseded_by:
        sup_result = await session.execute(
            select(DynamicSchema.uri).where(DynamicSchema.id == schema.superseded_by)
        )
        superseded_by_uri = sup_result.scalar_one_or_none()

    return DynamicSchemaResponse(
        id=schema.id,
        uri=schema.uri,
        name=schema.name,
        description=schema.description,
        elements=element_refs,
        version_num=schema.version_num,
        superseded_by=superseded_by_uri,
        supersedes=None,  # Computed from audit log if needed
        created_at=schema.created_at,
        updated_at=schema.updated_at,
        deleted_at=schema.deleted_at,
    )


@router.get("/", response_model=PaginatedList[DynamicSchemaSummary])
async def list_schemas(
    element_id: UUID | None = None,
    q: str | None = None,
    include_superseded: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List dynamic schemas (public)."""
    total, schemas = await DynamicSchemaService.list(
        session,
        element_id=element_id,
        q=q,
        include_superseded=include_superseded,
        limit=limit,
        offset=offset,
    )

    # Count elements for each schema
    items = []
    for schema in schemas:
        count_result = await session.execute(
            select(DynamicSchemaElement).where(DynamicSchemaElement.schema_id == schema.id)
        )
        element_count = len(count_result.scalars().all())
        items.append(
            DynamicSchemaSummary(
                id=schema.id,
                uri=schema.uri,
                name=schema.name,
                element_count=element_count,
                version_num=schema.version_num,
                created_at=schema.created_at,
            )
        )

    return PaginatedList(total=total, limit=limit, offset=offset, items=items)


@router.post("/", response_model=DynamicSchemaResponse, status_code=201)
async def create_schema(
    body: DynamicSchemaCreate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Create a new dynamic schema (curator+)."""
    try:
        schema = await DynamicSchemaService.create(session, body, current_user.id)
    except ElementNotFoundError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "element_not_found", "message": str(exc)}
        )

    await schema_changelog_svc.record(
        schema_id=schema.id,
        operation="CREATE",
        actor_id=current_user.id,
        diff={"name": schema.name},
        activity_type="schema_create",
        db=session,
    )

    return await _build_schema_response(session, schema)


@router.get("/{schema_id}", response_model=DynamicSchemaResponse)
async def get_schema(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a dynamic schema by ID (public)."""
    schema = await DynamicSchemaService.get(session, schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return await _build_schema_response(session, schema)


@router.put("/{schema_id}", response_model=DynamicSchemaResponse)
async def update_schema(
    schema_id: UUID,
    body: DynamicSchemaUpdate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Update dynamic schema membership (curator+). URI is immutable."""
    try:
        schema = await DynamicSchemaService.update(session, schema_id, body, current_user.id)
    except SchemaNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except VersionConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "version_conflict", "message": str(exc)}
        )

    return await _build_schema_response(session, schema)


@router.delete("/{schema_id}")
async def delete_schema(
    schema_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a dynamic schema (curator+)."""
    try:
        schema = await DynamicSchemaService.delete(session, schema_id, current_user.id)
    except SchemaNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    return {"id": str(schema.id), "deleted_at": schema.deleted_at.isoformat()}


@router.get("/{schema_id}/classes", response_model=SchemaClassesResponse)
async def get_schema_classes(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return all class nodes for a schema (public)."""
    classes = await get_classes_for_schema(schema_id=schema_id, db=session)
    return SchemaClassesResponse(schema_id=schema_id, classes=classes)


@router.post("/{schema_id}/supersede", status_code=201)
async def supersede_schema(
    schema_id: UUID,
    body: SupersedeSchemaRequest,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Supersede a schema with a semantically distinct replacement (curator+)."""
    try:
        new_schema, old_schema = await DynamicSchemaService.supersede(
            session, schema_id, body, current_user.id
        )
    except SchemaNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except AlreadySupersededError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "already_superseded", "message": str(exc)}
        )

    new_response = await _build_schema_response(session, new_schema)
    return {
        "new_schema": new_response,
        "superseded_schema": {
            "id": str(old_schema.id),
            "uri": old_schema.uri,
            "superseded_by": new_schema.uri,
            "deleted_at": old_schema.deleted_at.isoformat() if old_schema.deleted_at else None,
        },
    }


# ---------------------------------------------------------------------------
# Inheritance & MRO endpoints — T041/T042/T043/T044
# ---------------------------------------------------------------------------


@router.put("/{schema_id}/parent")
async def set_schema_parent(
    schema_id: UUID,
    body: SetParentRequest,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Set (or clear) the parent schema for single inheritance (curator+)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.id == schema_id,
            DynamicSchema.deleted_at.is_(None),
        )
    )
    schema = schema_result.scalar_one_or_none()
    if schema is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    if body.parent_id is not None:
        # Verify parent exists
        parent_result = await session.execute(
            select(DynamicSchema).where(
                DynamicSchema.id == body.parent_id,
                DynamicSchema.deleted_at.is_(None),
            )
        )
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail={"error": "parent_not_found"})

        # Build adjacency graph for cycle detection
        all_schemas = await session.execute(
            select(DynamicSchema.id, DynamicSchema.parent_id).where(DynamicSchema.deleted_at.is_(None))
        )
        graph = {str(r[0]): str(r[1]) if r[1] else None for r in all_schemas.all()}

        if detect_cycle_in_adjacency(graph, str(schema_id), str(body.parent_id)):
            raise HTTPException(
                status_code=409,
                detail={"error": "cycle_detected", "message": "Setting this parent would create a circular inheritance chain"},
            )

        # Check depth
        depth = await compute_depth(body.parent_id, session)
        from src.services.schema_mro import MAX_DEPTH, check_depth_limit
        try:
            check_depth_limit(depth + 1)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail={"error": "depth_exceeded", "message": f"Inheritance depth would exceed {MAX_DEPTH}"},
            )

    old_parent_id = schema.parent_id
    schema.parent_id = body.parent_id
    await session.flush()
    invalidate_mro_cache(schema_id)

    await schema_changelog_svc.record(
        schema_id=schema_id,
        operation="SET_PARENT",
        actor_id=current_user.id,
        diff={"old_parent_id": str(old_parent_id) if old_parent_id else None, "new_parent_id": str(body.parent_id) if body.parent_id else None},
        activity_type="parent_change",
        db=session,
    )

    return {
        "id": str(schema.id),
        "parent_id": str(body.parent_id) if body.parent_id else None,
    }


@router.post("/{schema_id}/mixins", status_code=201)
async def add_mixin(
    schema_id: UUID,
    body: AddMixinRequest,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Attach a mixin schema to a schema (curator+)."""
    # Check duplicate
    existing = await session.execute(
        select(SchemaMixin).where(
            SchemaMixin.schema_id == schema_id,
            SchemaMixin.mixin_id == body.mixin_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail={"error": "duplicate_mixin"})

    mixin_row = SchemaMixin(
        schema_id=schema_id,
        mixin_id=body.mixin_id,
        position=body.position,
    )
    session.add(mixin_row)
    await session.flush()
    invalidate_mro_cache(schema_id)

    return {"schema_id": str(schema_id), "mixin_id": str(body.mixin_id), "position": body.position}


@router.delete("/{schema_id}/mixins/{mixin_id}", status_code=200)
async def remove_mixin(
    schema_id: UUID,
    mixin_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Detach a mixin schema from a schema (curator+)."""
    result = await session.execute(
        select(SchemaMixin).where(
            SchemaMixin.schema_id == schema_id,
            SchemaMixin.mixin_id == mixin_id,
        )
    )
    mixin_row = result.scalar_one_or_none()
    if mixin_row is None:
        raise HTTPException(status_code=404, detail={"error": "mixin_not_found"})

    await session.delete(mixin_row)
    invalidate_mro_cache(schema_id)
    return {"deleted": True}


@router.get("/{schema_id}/resolved", response_model=ResolvedSchemaResponse)
async def get_resolved_schema(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return fully resolved elements for a schema in C3 MRO order (public)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.id == schema_id,
            DynamicSchema.deleted_at.is_(None),
        )
    )
    schema = schema_result.scalar_one_or_none()
    if schema is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    try:
        mro = await resolve_mro(schema_id, session)
    except CycleError as exc:
        raise HTTPException(status_code=409, detail={"error": "cycle_detected", "message": str(exc)})

    elements_raw = await get_resolved_elements(schema_id, session)

    # Build schema name lookup
    schema_names: dict[str, str] = {}
    for s_id in mro:
        s_result = await session.execute(
            select(DynamicSchema.name).where(DynamicSchema.id == s_id)
        )
        row = s_result.first()
        if row:
            schema_names[str(s_id)] = row[0]

    element_refs = [
        ResolvedElementRef(
            element_id=e["element_id"],
            name=e["name"],
            data_type=e["data_type"],
            element_kind=e["element_kind"],
            required=e["required"],
            source_schema=e["source_schema"],
            source_schema_id=e["source_schema_id"],
            override=e["override"],
        )
        for e in elements_raw
    ]

    return ResolvedSchemaResponse(
        schema_id=schema_id,
        name=schema.name,
        mro_order=[schema_names.get(str(s), str(s)) for s in mro],
        elements=element_refs,
    )


@router.get("/{schema_id}/inheritance-tree", response_model=InheritanceTreeResponse)
async def get_inheritance_tree(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return the inheritance tree (nodes + edges) for a schema (public)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(DynamicSchema.id == schema_id)
    )
    root = schema_result.scalar_one_or_none()
    if root is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    # BFS/DFS traversal via parent_id and SchemaMixin links
    visited: set[str] = set()
    nodes: list[InheritanceTreeNode] = []
    edges: list[InheritanceTreeEdge] = []
    queue: list[UUID] = [schema_id]

    while queue:
        current_id = queue.pop(0)
        current_str = str(current_id)
        if current_str in visited:
            continue
        visited.add(current_str)

        s_result = await session.execute(
            select(DynamicSchema).where(DynamicSchema.id == current_id)
        )
        s = s_result.scalar_one_or_none()
        if s is None:
            continue

        nodes.append(InheritanceTreeNode(id=s.id, name=s.name, is_mixin=s.is_mixin))

        # Parent edge
        if s.parent_id is not None:
            edges.append(InheritanceTreeEdge(
                child_id=current_id,
                parent_id=s.parent_id,
                type="inherits",
            ))
            if str(s.parent_id) not in visited:
                queue.append(s.parent_id)

        # Mixin edges
        mixin_result = await session.execute(
            select(SchemaMixin)
            .where(SchemaMixin.schema_id == current_id)
            .order_by(SchemaMixin.position)
        )
        for mixin_row in mixin_result.scalars().all():
            edges.append(InheritanceTreeEdge(
                child_id=current_id,
                parent_id=mixin_row.mixin_id,
                type="mixin",
                position=mixin_row.position,
            ))
            if str(mixin_row.mixin_id) not in visited:
                queue.append(mixin_row.mixin_id)

    return InheritanceTreeResponse(schema_id=schema_id, nodes=nodes, edges=edges)


@router.get("/{schema_id}/changelog")
async def get_changelog(
    schema_id: UUID,
    breaking_only: bool = False,
    page: int = 1,
    size: int = 20,
    session: AsyncSession = Depends(get_db),
):
    """Return paginated changelog for a schema (public)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.id == schema_id,
            DynamicSchema.deleted_at.is_(None),
        )
    )
    if schema_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    return await schema_changelog_svc.list_changelog(
        schema_id=schema_id,
        breaking_only=breaking_only,
        page=page,
        size=size,
        db=session,
    )


from fastapi.responses import JSONResponse  # noqa: E402


@router.get("/{schema_id}/provenance")
async def get_schema_provenance(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return W3C PROV-DM JSON-LD provenance for a schema (public)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.id == schema_id,
            DynamicSchema.deleted_at.is_(None),
        )
    )
    if schema_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    prov = await schema_changelog_svc.to_prov_jsonld(schema_id=schema_id, db=session)
    return JSONResponse(content=prov, media_type="application/ld+json")


@router.post("/{schema_id}/provenance-mixin", status_code=201)
async def attach_provenance_mixin(
    schema_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Attach the system ProvenanceMixin to a schema (curator+)."""
    schema_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.id == schema_id,
            DynamicSchema.deleted_at.is_(None),
        )
    )
    if schema_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    # Look up ProvenanceMixin system schema by name
    prov_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.name == "ProvenanceMixin",
            DynamicSchema.is_mixin.is_(True),
            DynamicSchema.deleted_at.is_(None),
        )
    )
    prov_schema = prov_result.scalar_one_or_none()
    if prov_schema is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "provenance_mixin_not_found", "message": "ProvenanceMixin system schema not seeded"},
        )

    # Check duplicate
    existing = await session.execute(
        select(SchemaMixin).where(
            SchemaMixin.schema_id == schema_id,
            SchemaMixin.mixin_id == prov_schema.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail={"error": "duplicate_mixin"})

    mixin_row = SchemaMixin(
        schema_id=schema_id,
        mixin_id=prov_schema.id,
        position=0,
    )
    session.add(mixin_row)
    await session.flush()
    invalidate_mro_cache(schema_id)

    await schema_changelog_svc.record(
        schema_id=schema_id,
        operation="ATTACH_PROVENANCE_MIXIN",
        actor_id=current_user.id,
        diff={"mixin_id": str(prov_schema.id)},
        activity_type="mixin_attach",
        db=session,
    )

    return {"attached": True, "mixin_id": str(prov_schema.id)}


@router.delete("/{schema_id}/provenance-mixin", status_code=204)
async def detach_provenance_mixin(
    schema_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Detach the system ProvenanceMixin from a schema (curator+)."""
    # Look up ProvenanceMixin system schema by name
    prov_result = await session.execute(
        select(DynamicSchema).where(
            DynamicSchema.name == "ProvenanceMixin",
            DynamicSchema.is_mixin.is_(True),
            DynamicSchema.deleted_at.is_(None),
        )
    )
    prov_schema = prov_result.scalar_one_or_none()
    if prov_schema is None:
        raise HTTPException(status_code=404, detail={"error": "provenance_mixin_not_found"})

    result = await session.execute(
        select(SchemaMixin).where(
            SchemaMixin.schema_id == schema_id,
            SchemaMixin.mixin_id == prov_schema.id,
        )
    )
    mixin_row = result.scalar_one_or_none()
    if mixin_row is None:
        raise HTTPException(status_code=404, detail={"error": "mixin_not_found"})

    await session.delete(mixin_row)

    await schema_changelog_svc.record(
        schema_id=schema_id,
        operation="DETACH_PROVENANCE_MIXIN",
        actor_id=current_user.id,
        diff={"mixin_id": str(prov_schema.id)},
        activity_type="mixin_detach",
        db=session,
    )


# ---------------------------------------------------------------------------
# LinkML export (T021 — FR-008)
# ---------------------------------------------------------------------------


@router.get("/{schema_id}/linkml")
async def export_schema_linkml(
    schema_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Export a DynamicSchema as LinkML YAML (FR-008).

    Returns application/yaml with X-Roundtrip-Fidelity header.
    """
    from fastapi.responses import Response

    from src.services.linkml_io import export_schema

    try:
        yaml_str, result = await export_schema(schema_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})

    return Response(
        content=yaml_str,
        media_type="application/yaml",
        headers={"X-Roundtrip-Fidelity": str(result.fidelity_score)},
    )


# ---------------------------------------------------------------------------
# LinkML import (T026 — FR-009)
# ---------------------------------------------------------------------------


@router.post("/import/linkml", status_code=201)
async def import_schema_linkml(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CONTRIBUTOR)),
):
    """Import a LinkML YAML and create a DynamicSchema (FR-009).

    Accepts application/yaml body. Returns RoundtripResult JSON.
    """
    from src.services.linkml_io import DuplicateSchemaURIError, import_schema

    body_bytes = await request.body()
    try:
        yaml_str = body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "invalid_encoding", "message": str(exc)}
        )

    try:
        result = await import_schema(yaml_str, session, current_user.id)
    except DuplicateSchemaURIError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "schema_uri_conflict", "message": str(exc)}
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "invalid_yaml", "message": str(exc)}
        )

    return result
