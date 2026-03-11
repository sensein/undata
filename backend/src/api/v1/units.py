"""Unit discovery endpoints — GET /units and GET /units/unresolvable."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.db import DataElement, DataElementVersion
from src.models.schemas import PaginatedList


class UnitSummary(BaseModel):
    label: str | None
    symbol: str | None
    cmixf_valid: bool | None
    qudt_uri: str | None
    qudt_unresolvable: bool
    element_count: int


class UnresolvableUnitItem(BaseModel):
    label: str | None
    symbol: str | None
    cmixf_valid: bool | None
    qudt_uri: str | None
    qudt_unresolvable: bool
    element_count: int
    element_ids: list[str]


router = APIRouter(prefix="/units", tags=["units"])


@router.get("/unresolvable", response_model=PaginatedList[UnresolvableUnitItem])
async def list_unresolvable_units(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> PaginatedList[UnresolvableUnitItem]:
    """Return units used in active elements where QUDT resolution failed.

    Each item includes element_ids for traceability.
    NOTE: This route must be declared before /  to avoid being shadowed.
    """
    # Query active (non-deleted, non-superseded) element versions with unit info
    stmt = (
        select(DataElementVersion)
        .join(DataElement, DataElement.current_version_id == DataElementVersion.id)
        .where(
            DataElement.deleted_at.is_(None),
            DataElementVersion.semantic_graph.isnot(None),
        )
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    # Aggregate unresolvable units from semantic_graph JSONB
    unresolvable: dict[tuple, dict] = {}
    for version in versions:
        sg = version.semantic_graph
        if not sg or not sg.get("unit"):
            continue
        unit_node = sg["unit"]
        if not unit_node.get("qudt_unresolvable", False):
            continue

        label = unit_node.get("label")
        symbol = unit_node.get("symbol")
        key = (label, symbol)

        if key not in unresolvable:
            unresolvable[key] = {
                "label": label,
                "symbol": symbol,
                "cmixf_valid": unit_node.get("cmixf_valid"),
                "qudt_uri": unit_node.get("external_uri"),
                "qudt_unresolvable": True,
                "element_count": 0,
                "element_ids": [],
            }
        unresolvable[key]["element_count"] += 1
        unresolvable[key]["element_ids"].append(str(version.element_id))

    items_all = list(unresolvable.values())
    total = len(items_all)
    page = items_all[offset : offset + limit]

    return PaginatedList(
        total=total,
        limit=limit,
        offset=offset,
        items=[UnresolvableUnitItem(**item) for item in page],
    )


@router.get("/", response_model=PaginatedList[UnitSummary])
async def list_units(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> PaginatedList[UnitSummary]:
    """Return paginated list of distinct unit symbols used across active elements.

    Aggregated from semantic_graph.unit nodes; includes resolution status.
    """
    # Query active element current versions with non-null semantic_graph
    stmt = (
        select(DataElementVersion)
        .join(DataElement, DataElement.current_version_id == DataElementVersion.id)
        .where(
            DataElement.deleted_at.is_(None),
            DataElementVersion.semantic_graph.isnot(None),
        )
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    # Aggregate distinct (label, symbol) unit pairs
    unit_agg: dict[tuple, dict] = {}
    for version in versions:
        sg = version.semantic_graph
        if not sg or not sg.get("unit"):
            continue
        unit_node = sg["unit"]
        label = unit_node.get("label")
        symbol = unit_node.get("symbol")
        key = (label, symbol)

        if key not in unit_agg:
            unit_agg[key] = {
                "label": label,
                "symbol": symbol,
                "cmixf_valid": unit_node.get("cmixf_valid"),
                "qudt_uri": unit_node.get("external_uri"),
                "qudt_unresolvable": unit_node.get("qudt_unresolvable", False),
                "element_count": 0,
            }
        unit_agg[key]["element_count"] += 1

    items_all = list(unit_agg.values())
    total = len(items_all)
    page = items_all[offset : offset + limit]

    return PaginatedList(
        total=total,
        limit=limit,
        offset=offset,
        items=[UnitSummary(**item) for item in page],
    )
