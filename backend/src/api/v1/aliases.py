"""Alias group management and detection endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import AliasGroupMember, DataElement, DataElementVersion, SchemaSource
from src.models.schemas import (
    AliasCandidatePair,
    AliasDetectRequest,
    AliasGroupCreate,
    AliasGroupResponse,
    AliasGroupSummary,
    AliasGroupUpdate,
    DataElementSummary,
    PaginatedList,
    SchemaSourceResponse,
)
from src.services.aliases import AliasGroupNotFoundError, AliasGroupService
from src.services.authz import Role, require_role
from src.services.mappings import CycleDetectedError

router = APIRouter(prefix="/aliases", tags=["aliases"])


async def _build_element_summary(session: AsyncSession, element: DataElement) -> DataElementSummary:
    from sqlalchemy import select

    version_result = await session.execute(
        select(DataElementVersion).where(DataElementVersion.id == element.current_version_id)
    )
    version = version_result.scalar_one_or_none()

    source_result = await session.execute(
        select(SchemaSource).where(SchemaSource.id == element.source_id)
    )
    source = source_result.scalar_one_or_none()

    source_resp = None
    if source:
        source_resp = SchemaSourceResponse(
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

    return DataElementSummary(
        id=element.id,
        uri=element.uri,
        name=version.name if version else "",
        data_type=version.data_type if version else "",
        description=version.description if version else None,
        required=version.required if version else False,
        multivalued=version.multivalued if version else False,
        source=source_resp,
        unit=version.unit if version else None,
        superseded_by=None,
        version_num=element.version_num,
    )


async def _build_group_response(session: AsyncSession, group) -> AliasGroupResponse:
    from sqlalchemy import select

    members_result = await session.execute(
        select(DataElement)
        .join(AliasGroupMember, DataElement.id == AliasGroupMember.element_id)
        .where(AliasGroupMember.alias_group_id == group.id)
    )
    elements = list(members_result.scalars().all())

    member_summaries = []
    for el in elements:
        summary = await _build_element_summary(session, el)
        member_summaries.append(summary)

    return AliasGroupResponse(
        id=group.id,
        name=group.name,
        sssom_predicate=group.sssom_predicate,
        confidence=group.confidence,
        detection_method=group.detection_method,
        members=member_summaries,
        created_at=group.created_at,
    )


@router.get("/", response_model=PaginatedList[AliasGroupSummary])
async def list_alias_groups(
    element_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select

    total, groups = await AliasGroupService.list(
        session, element_id=element_id, limit=limit, offset=offset
    )

    items = []
    for group in groups:
        member_count_result = await session.execute(
            select(func.count()).where(AliasGroupMember.alias_group_id == group.id)
        )
        member_count = member_count_result.scalar_one()
        items.append(
            AliasGroupSummary(
                id=group.id,
                name=group.name,
                sssom_predicate=group.sssom_predicate,
                confidence=group.confidence,
                detection_method=group.detection_method,
                member_count=member_count,
                created_at=group.created_at,
            )
        )
    return PaginatedList(total=total, limit=limit, offset=offset, items=items)


@router.post("/", response_model=AliasGroupResponse, status_code=201)
async def create_alias_group(
    data: AliasGroupCreate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        group = await AliasGroupService.create(session, data, current_user.id)
    except CycleDetectedError as e:
        raise HTTPException(
            status_code=409,
            detail={"error": "cycle_detected", "details": {"cycle_path": e.cycle_path}},
        )
    return await _build_group_response(session, group)


@router.post("/detect", response_model=PaginatedList[AliasCandidatePair])
async def detect_alias_candidates(
    data: AliasDetectRequest,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    total, pairs = await AliasGroupService.detect(
        session,
        source_id=data.source_id,
        threshold=data.threshold,
        cross_source_only=data.cross_source_only,
        limit=data.limit,
        offset=data.offset,
    )
    return PaginatedList(total=total, limit=data.limit, offset=data.offset, items=pairs)


@router.get("/{alias_group_id}", response_model=AliasGroupResponse)
async def get_alias_group(
    alias_group_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    group = await AliasGroupService.get(session, alias_group_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"AliasGroup {alias_group_id} not found")
    return await _build_group_response(session, group)


@router.put("/{alias_group_id}", response_model=AliasGroupResponse)
async def update_alias_group(
    alias_group_id: UUID,
    data: AliasGroupUpdate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        group = await AliasGroupService.update(session, alias_group_id, data, current_user.id)
    except AliasGroupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return await _build_group_response(session, group)


@router.delete("/{alias_group_id}", status_code=204)
async def delete_alias_group(
    alias_group_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        await AliasGroupService.delete(session, alias_group_id, current_user.id)
    except AliasGroupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
