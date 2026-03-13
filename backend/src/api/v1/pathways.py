"""Migration pathway management endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.models.db import MigrationPathway
from src.models.schemas import (
    MigrationPathwayCreate,
    MigrationPathwayResponse,
    MigrationPathwayUpdate,
    PaginatedList,
)

router = APIRouter(prefix="/pathways", tags=["pathways"])


@router.post("", response_model=MigrationPathwayResponse, status_code=201)
async def create_pathway(
    payload: MigrationPathwayCreate,
    db: AsyncSession = Depends(get_db),
) -> MigrationPathwayResponse:
    """Create a migration pathway."""
    steps = [{"position": s.position, "mapping_id": str(s.mapping_id)} for s in payload.steps]
    pathway = MigrationPathway(
        id=uuid.uuid4(),
        name=payload.name,
        source_schema_id=payload.source_schema_id,
        target_schema_id=payload.target_schema_id,
        direction=payload.direction,
        status="active",
        steps=steps,
    )
    db.add(pathway)
    await db.commit()
    await db.refresh(pathway)
    return MigrationPathwayResponse.model_validate(pathway)


@router.get("", response_model=PaginatedList[MigrationPathwayResponse])
async def list_pathways(
    source_schema_id: Annotated[UUID | None, Query()] = None,
    target_schema_id: Annotated[UUID | None, Query()] = None,
    direction: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
) -> PaginatedList[MigrationPathwayResponse]:
    """List migration pathways with optional filters."""
    q = select(MigrationPathway)
    if source_schema_id is not None:
        q = q.where(MigrationPathway.source_schema_id == source_schema_id)
    if target_schema_id is not None:
        q = q.where(MigrationPathway.target_schema_id == target_schema_id)
    if direction is not None:
        q = q.where(MigrationPathway.direction == direction)
    if status is not None:
        q = q.where(MigrationPathway.status == status)

    total_q = q
    result_total = await db.execute(total_q)
    total = len(result_total.scalars().all())

    q = q.offset(offset).limit(limit).order_by(MigrationPathway.created_at.desc())
    result = await db.execute(q)
    pathways = result.scalars().all()

    return PaginatedList(
        total=total,
        limit=limit,
        offset=offset,
        items=[MigrationPathwayResponse.model_validate(p) for p in pathways],
    )


@router.get("/{pathway_id}", response_model=MigrationPathwayResponse)
async def get_pathway(
    pathway_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MigrationPathwayResponse:
    """Get a migration pathway by ID."""
    result = await db.execute(
        select(MigrationPathway).where(MigrationPathway.id == pathway_id)
    )
    pathway = result.scalar_one_or_none()
    if pathway is None:
        raise HTTPException(status_code=404, detail="Pathway not found")
    return MigrationPathwayResponse.model_validate(pathway)


@router.put("/{pathway_id}", response_model=MigrationPathwayResponse)
async def update_pathway(
    pathway_id: UUID,
    payload: MigrationPathwayUpdate,
    db: AsyncSession = Depends(get_db),
) -> MigrationPathwayResponse:
    """Update a migration pathway."""
    result = await db.execute(
        select(MigrationPathway).where(MigrationPathway.id == pathway_id)
    )
    pathway = result.scalar_one_or_none()
    if pathway is None:
        raise HTTPException(status_code=404, detail="Pathway not found")

    if payload.name is not None:
        pathway.name = payload.name
    if payload.status is not None:
        pathway.status = payload.status
    if payload.steps is not None:
        pathway.steps = [
            {"position": s.position, "mapping_id": str(s.mapping_id)} for s in payload.steps
        ]
        pathway.version_num = pathway.version_num + 1

    await db.commit()
    await db.refresh(pathway)
    return MigrationPathwayResponse.model_validate(pathway)


@router.delete("/{pathway_id}", status_code=204)
async def delete_pathway(
    pathway_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a migration pathway by setting status='deleted'."""
    result = await db.execute(
        select(MigrationPathway).where(MigrationPathway.id == pathway_id)
    )
    pathway = result.scalar_one_or_none()
    if pathway is None:
        raise HTTPException(status_code=404, detail="Pathway not found")
    pathway.status = "deleted"
    await db.commit()
