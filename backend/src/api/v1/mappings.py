"""Mapping function management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.models.db import MappingFunction
from src.models.schemas import (
    MappingFunctionCreate,
    MappingFunctionResponse,
    MappingFunctionSummary,
    MappingFunctionUpdate,
    MappingFunctionVersionResponse,
    PaginatedList,
)
from src.services.authz import Role, require_role
from src.services.mappings import (
    CycleDetectedError,
    ElementNotFoundError,
    MappingService,
    VersionConflictError,
)

router = APIRouter(prefix="/mappings", tags=["mappings"])


def _build_mapping_response(mapping) -> MappingFunctionResponse:
    inputs = []
    if mapping.inputs:
        inputs = [
            {"element_id": str(inp.element_id), "position": inp.position} for inp in mapping.inputs
        ]

    current_version = None
    if mapping.current_version:
        cv = mapping.current_version
        current_version = MappingFunctionVersionResponse(
            id=cv.id,
            mapping_id=cv.mapping_id,
            version_num=cv.version_num,
            description=cv.description,
            expression=cv.expression,
            expression_type=cv.expression_type,
            parameter_schema=cv.parameter_schema,
            inverse_mapping_id=cv.inverse_mapping_id,
            sssom_predicate=cv.sssom_predicate,
            created_at=cv.created_at,
            created_by_display_name=None,
        )

    return MappingFunctionResponse(
        id=mapping.id,
        uri=mapping.uri,
        function_type=mapping.function_type,
        output_element_id=mapping.output_element_id,
        status=mapping.status,
        version_num=mapping.version_num,
        created_at=mapping.created_at,
        deleted_at=mapping.deleted_at,
        current_version=current_version,
        inputs=inputs,
    )


@router.get("/", response_model=PaginatedList[MappingFunctionSummary])
async def list_mappings(
    source_element_id: UUID | None = None,
    target_element_id: UUID | None = None,
    function_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    total, mappings = await MappingService.list(
        session,
        source_element_id=source_element_id,
        target_element_id=target_element_id,
        function_type=function_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [MappingFunctionSummary.model_validate(m) for m in mappings]
    return PaginatedList(total=total, limit=limit, offset=offset, items=items)


@router.post("/", response_model=MappingFunctionResponse, status_code=201)
async def create_mapping(
    data: MappingFunctionCreate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        mapping = await MappingService.create(session, data, current_user.id)
    except CycleDetectedError as e:
        raise HTTPException(
            status_code=409,
            detail={"error": "cycle_detected", "details": {"cycle_path": e.cycle_path}},
        )
    except ElementNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Reload with eager relationships to avoid lazy-load in sync context
    result = await session.execute(
        select(MappingFunction)
        .where(MappingFunction.id == mapping.id)
        .options(
            selectinload(MappingFunction.inputs),
            selectinload(MappingFunction.current_version),
        )
    )
    mapping = result.scalar_one()
    return _build_mapping_response(mapping)


@router.get("/{mapping_id}", response_model=MappingFunctionResponse)
async def get_mapping(
    mapping_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    mapping = await MappingService.get(session, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")
    result = await session.execute(
        select(MappingFunction)
        .where(MappingFunction.id == mapping_id)
        .options(
            selectinload(MappingFunction.inputs),
            selectinload(MappingFunction.current_version),
        )
    )
    mapping = result.scalar_one()
    return _build_mapping_response(mapping)


@router.put("/{mapping_id}", response_model=MappingFunctionResponse)
async def update_mapping(
    mapping_id: UUID,
    data: MappingFunctionUpdate,
    version_num: int = 1,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        mapping = await MappingService.update(
            session, mapping_id, data, current_user.id, version_num
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except VersionConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    result = await session.execute(
        select(MappingFunction)
        .where(MappingFunction.id == mapping.id)
        .options(
            selectinload(MappingFunction.inputs),
            selectinload(MappingFunction.current_version),
        )
    )
    mapping = result.scalar_one()
    return _build_mapping_response(mapping)


@router.delete("/{mapping_id}", response_model=MappingFunctionResponse)
async def delete_mapping(
    mapping_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.CURATOR)),
):
    try:
        mapping = await MappingService.delete(session, mapping_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = await session.execute(
        select(MappingFunction)
        .where(MappingFunction.id == mapping.id)
        .options(
            selectinload(MappingFunction.inputs),
            selectinload(MappingFunction.current_version),
        )
    )
    mapping = result.scalar_one()
    return _build_mapping_response(mapping)


@router.get("/{mapping_id}/history", response_model=list[MappingFunctionVersionResponse])
async def get_mapping_history(
    mapping_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    versions = await MappingService.get_history(session, mapping_id)
    return [
        MappingFunctionVersionResponse(
            id=v.id,
            mapping_id=v.mapping_id,
            version_num=v.version_num,
            description=v.description,
            expression=v.expression,
            expression_type=v.expression_type,
            parameter_schema=v.parameter_schema,
            inverse_mapping_id=v.inverse_mapping_id,
            sssom_predicate=v.sssom_predicate,
            created_at=v.created_at,
            created_by_display_name=None,
        )
        for v in versions
    ]



# ---------------------------------------------------------------------------
# PUT /mappings/{id}/accept (T028 — FR-014)
# ---------------------------------------------------------------------------


@router.put("/{mapping_id}/accept")
async def accept_mapping(
    mapping_id: UUID,
    confidence_threshold: float | None = None,
    session: AsyncSession = Depends(get_db),
):
    """Accept a pending_curation mapping, optionally gated by confidence score (FR-014).

    Raises 422 if the mapping is not in pending_curation status or confidence is below threshold.
    Raises 404 if the mapping does not exist.
    """
    from src.services.mappings import MappingService

    try:
        mapping = await MappingService.accept_mapping(
            session, mapping_id, confidence_threshold=confidence_threshold
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": msg})
        raise HTTPException(status_code=422, detail={"error": "accept_rejected", "message": msg})

    await session.commit()
    from src.models.schemas import MappingFunctionResponse

    return MappingFunctionResponse.model_validate(mapping)
