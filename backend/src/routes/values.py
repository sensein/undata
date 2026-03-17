"""V2 value concept API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from undata_library.hashing import (
    build_value_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)

from ..db.session import get_db
from ..models.value import ValueConcept, ValueProvenance

router = APIRouter(prefix="/api/v1/values", tags=["values-v2"])


class ValueCreateRequest(BaseModel):
    semantic: dict
    provenance: list[dict]


class ValueResponse(BaseModel):
    uri: str
    semantic: dict
    provenance: list[dict]


class ValueListResponse(BaseModel):
    items: list[ValueResponse]
    total: int


def _value_to_response(v: ValueConcept) -> ValueResponse:
    return ValueResponse(
        uri=v.uri,
        semantic=v.semantic,
        provenance=[{"source": p.source, "raw_value": p.raw_value} for p in v.provenance],
    )


@router.post("", status_code=201)
async def create_value(
    body: ValueCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    sem_dict = dict(body.semantic)
    sha = compute_sha256(canonical_json(sem_dict))

    existing = (
        await session.execute(
            select(ValueConcept).where(ValueConcept.semantic_hash == sha)
        )
    ).scalar_one_or_none()

    if existing:
        existing_keys = {(p.source, p.raw_value) for p in existing.provenance}
        for prov in body.provenance:
            if (prov["source"], prov["raw_value"]) not in existing_keys:
                existing.provenance.append(
                    ValueProvenance(source=prov["source"], raw_value=prov["raw_value"])
                )
        await session.commit()
        from fastapi.responses import JSONResponse

        return JSONResponse(content=_value_to_response(existing).model_dump(), status_code=200)

    label = sem_dict.get("label", "unknown")
    key = generate_short_key(sha)
    uri = build_value_uri(label, key)

    value = ValueConcept(semantic_hash=sha, uri=uri, semantic=body.semantic)
    for prov in body.provenance:
        value.provenance.append(
            ValueProvenance(source=prov["source"], raw_value=prov["raw_value"])
        )
    session.add(value)
    await session.commit()
    return _value_to_response(value)


@router.get("")
async def list_values(
    source: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> ValueListResponse:
    from sqlalchemy import func

    stmt = select(ValueConcept)
    count_stmt = select(func.count(ValueConcept.id))

    if source:
        stmt = stmt.join(ValueProvenance).where(ValueProvenance.source == source)
        count_stmt = count_stmt.join(ValueProvenance).where(
            ValueProvenance.source == source
        )

    total = (await session.execute(count_stmt)).scalar() or 0
    result = await session.execute(stmt.limit(limit).offset(offset))
    return ValueListResponse(
        items=[_value_to_response(v) for v in result.scalars().all()],
        total=total,
    )
