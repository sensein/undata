"""Schema source management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import UserProfile
from src.models.schemas import (
    PaginatedList,
    SchemaClassCreate,
    SchemaClassElementLink,
    SchemaClassElementLinkResponse,
    SchemaClassesResponse,
    SchemaClassRead,
    SchemaSourceCreate,
    SchemaSourceResponse,
)
from src.services.authz import Role, require_role
from src.services.schema_class import (
    create_class_node,
    get_classes_for_source,
    link_element_to_class,
)
from src.services.sources import DuplicateSourceError, SourceService, VersionConflictError

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_response(source) -> SchemaSourceResponse:
    return SchemaSourceResponse(
        id=source.id,
        name=source.name,
        format=source.format,
        url=source.url,
        version_tag=source.version_tag,
        content_hash=source.content_hash,
        ingested_at=source.ingested_at,
        is_active=source.is_active,
        metadata=source.metadata_,
        version_num=source.version_num,
    )


@router.get("/", response_model=PaginatedList[SchemaSourceResponse])
async def list_sources(
    name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List schema sources (public). Optional exact-match ?name= filter."""
    total, sources = await SourceService.list(session, name=name, limit=limit, offset=offset)
    return PaginatedList(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_response(s) for s in sources],
    )


@router.post("/", response_model=SchemaSourceResponse, status_code=201)
async def create_source(
    body: SchemaSourceCreate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Create a new schema source (curator+)."""
    try:
        source = await SourceService.create(session, body, current_user.id)
    except DuplicateSourceError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate_source", "message": str(exc)},
        )
    return _to_response(source)


@router.get("/{source_id}", response_model=SchemaSourceResponse)
async def get_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a schema source by ID (public)."""
    source = await SourceService.get(session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return _to_response(source)


@router.put("/{source_id}", response_model=SchemaSourceResponse)
async def update_source(
    source_id: UUID,
    body: dict,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Update a schema source (curator+). Requires correct version_num."""
    version_num = body.get("version_num")
    if version_num is None:
        raise HTTPException(status_code=422, detail={"error": "version_num_required"})

    try:
        source = await SourceService.update(session, source_id, body, current_user.id, version_num)
    except ValueError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except VersionConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "version_conflict", "message": str(exc)}
        )

    return _to_response(source)


@router.post("/{source_id}/classes", response_model=SchemaClassRead, status_code=201)
async def create_class(
    source_id: UUID,
    body: SchemaClassCreate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Create a class node DataElement for a source (curator+)."""
    element = await create_class_node(
        source_id=source_id,
        class_name=body.class_name,
        description=body.description,
        parent_class_id=body.parent_class_id,
        actor_id=current_user.id,
        db=session,
    )
    return SchemaClassRead(
        id=element.id,
        class_name=element.source_local_id,
        description=body.description,
        parent_class_id=body.parent_class_id,
        elements=[],
    )


@router.get("/{source_id}/classes", response_model=SchemaClassesResponse)
async def list_source_classes(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """List all class nodes for a source (public)."""
    source = await SourceService.get(session, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.models.db import DataElement, DataElementChild, SchemaClassInheritance
    from src.models.schemas import SchemaClassElementRef

    classes = await get_classes_for_source(source_id=source_id, db=session)

    class_reads = []
    for cls_elem in classes:
        child_result = await session.execute(
            select(DataElementChild)
            .where(DataElementChild.parent_id == cls_elem.id)
            .order_by(DataElementChild.position)
            .options(
                selectinload(DataElementChild.child).selectinload(DataElement.current_version)
            )
        )
        children = list(child_result.scalars().all())

        parent_result = await session.execute(
            select(SchemaClassInheritance).where(
                SchemaClassInheritance.child_class_id == cls_elem.id,
                SchemaClassInheritance.relationship_type == "is_a",
            )
        )
        parent_row = parent_result.scalar_one_or_none()

        element_refs = []
        for child in children:
            cv = child.child.current_version if child.child else None
            element_refs.append(
                SchemaClassElementRef(
                    element_id=child.child_id,
                    name=cv.name if cv else "",
                    data_type=cv.data_type if cv else "string",
                    element_kind=child.child.element_kind if child.child else "scalar",
                    required=cv.required if cv else False,
                    allowed_values=cv.allowed_values if cv else None,
                    position=child.position,
                )
            )

        class_reads.append(
            SchemaClassRead(
                id=cls_elem.id,
                class_name=cls_elem.source_local_id,
                description=None,
                parent_class_id=parent_row.parent_class_id if parent_row else None,
                elements=element_refs,
            )
        )

    return SchemaClassesResponse(classes=class_reads)


@router.post(
    "/{source_id}/classes/{class_id}/elements",
    response_model=SchemaClassElementLinkResponse,
    status_code=201,
)
async def add_element_to_class(
    source_id: UUID,
    class_id: UUID,
    body: SchemaClassElementLink,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Link a DataElement to a class node (curator+)."""
    await link_element_to_class(
        class_element_id=class_id,
        member_element_id=body.element_id,
        position=body.position,
        db=session,
    )
    return SchemaClassElementLinkResponse(
        class_id=class_id,
        element_id=body.element_id,
        position=body.position,
    )
