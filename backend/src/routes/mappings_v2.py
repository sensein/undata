"""V2 element mapping API endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.db import get_session
from ..models.mapping_v2 import ElementMappingV2

router = APIRouter(prefix="/api/v2/mappings", tags=["mappings-v2"])


class MappingCreateRequest(BaseModel):
    source_element_uri: str
    target_element_uri: str
    function_type: str
    expression: str | None = None
    expression_type: str | None = None
    sssom_predicate: str | None = None
    confidence: float | None = None
    attributed_to: str | None = None


class MappingResponse(BaseModel):
    id: int
    source_element_uri: str
    target_element_uri: str
    function_type: str
    expression: str | None
    expression_type: str | None
    sssom_predicate: str | None
    confidence: float | None
    attributed_to: str | None


class MappingListResponse(BaseModel):
    items: list[MappingResponse]
    total: int


def _mapping_to_response(m: ElementMappingV2) -> MappingResponse:
    return MappingResponse(
        id=m.id,
        source_element_uri=m.source_element_uri,
        target_element_uri=m.target_element_uri,
        function_type=m.function_type,
        expression=m.expression,
        expression_type=m.expression_type,
        sssom_predicate=m.sssom_predicate,
        confidence=m.confidence,
        attributed_to=m.attributed_to,
    )


@router.post("", status_code=201)
async def create_mapping(
    body: MappingCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    mapping = ElementMappingV2(
        source_element_uri=body.source_element_uri,
        target_element_uri=body.target_element_uri,
        function_type=body.function_type,
        expression=body.expression,
        expression_type=body.expression_type,
        sssom_predicate=body.sssom_predicate,
        confidence=body.confidence,
        attributed_to=body.attributed_to,
    )
    session.add(mapping)
    await session.commit()
    await session.refresh(mapping)
    return _mapping_to_response(mapping)


@router.get("")
async def list_mappings(
    element_uri: str | None = Query(None, description="Filter by source or target URI"),
    function_type: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> MappingListResponse:
    stmt = select(ElementMappingV2)
    count_stmt = select(func.count(ElementMappingV2.id))

    if element_uri:
        uri_filter = or_(
            ElementMappingV2.source_element_uri == element_uri,
            ElementMappingV2.target_element_uri == element_uri,
        )
        stmt = stmt.where(uri_filter)
        count_stmt = count_stmt.where(uri_filter)

    if function_type:
        stmt = stmt.where(ElementMappingV2.function_type == function_type)
        count_stmt = count_stmt.where(ElementMappingV2.function_type == function_type)

    total = (await session.execute(count_stmt)).scalar() or 0
    result = await session.execute(stmt.limit(limit).offset(offset))
    return MappingListResponse(
        items=[_mapping_to_response(m) for m in result.scalars().all()],
        total=total,
    )
