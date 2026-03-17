"""V2 schema shape API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from undata_library.hashing import (
    build_schema_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)

from ..models.db import get_session
from ..models.schema_v2 import SchemaProvenanceV2, SchemaShapeV2

router = APIRouter(prefix="/api/v2/schemas", tags=["schemas-v2"])


class SchemaCreateRequest(BaseModel):
    semantic: dict
    provenance: list[dict]


class SchemaResponse(BaseModel):
    uri: str
    semantic: dict
    provenance: list[dict]


class SchemaListResponse(BaseModel):
    items: list[SchemaResponse]
    total: int


def _schema_to_response(s: SchemaShapeV2) -> SchemaResponse:
    return SchemaResponse(
        uri=s.uri,
        semantic=s.semantic,
        provenance=[
            {"source": p.source, "name": p.name, "description": p.description}
            for p in s.provenance
        ],
    )


@router.post("", status_code=201)
async def create_schema(
    body: SchemaCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    sem_dict = dict(body.semantic)
    sha = compute_sha256(canonical_json(sem_dict))

    existing = (
        await session.execute(
            select(SchemaShapeV2).where(SchemaShapeV2.semantic_hash == sha)
        )
    ).scalar_one_or_none()

    if existing:
        existing_keys = {(p.source, p.name) for p in existing.provenance}
        for prov in body.provenance:
            if (prov["source"], prov["name"]) not in existing_keys:
                existing.provenance.append(
                    SchemaProvenanceV2(
                        source=prov["source"],
                        name=prov["name"],
                        description=prov.get("description"),
                    )
                )
        await session.commit()
        from fastapi.responses import JSONResponse

        return JSONResponse(
            content=_schema_to_response(existing).model_dump(), status_code=200
        )

    name = body.provenance[0]["name"] if body.provenance else "unknown"
    key = generate_short_key(sha)
    uri = build_schema_uri(name, key)

    schema = SchemaShapeV2(semantic_hash=sha, uri=uri, semantic=body.semantic)
    for prov in body.provenance:
        schema.provenance.append(
            SchemaProvenanceV2(
                source=prov["source"],
                name=prov["name"],
                description=prov.get("description"),
            )
        )
    session.add(schema)
    await session.commit()
    return _schema_to_response(schema)


@router.get("")
async def list_schemas(
    source: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SchemaListResponse:
    from sqlalchemy import func

    stmt = select(SchemaShapeV2)
    count_stmt = select(func.count(SchemaShapeV2.id))

    if source:
        stmt = stmt.join(SchemaProvenanceV2).where(SchemaProvenanceV2.source == source)
        count_stmt = count_stmt.join(SchemaProvenanceV2).where(
            SchemaProvenanceV2.source == source
        )

    total = (await session.execute(count_stmt)).scalar() or 0
    result = await session.execute(stmt.limit(limit).offset(offset))
    return SchemaListResponse(
        items=[_schema_to_response(s) for s in result.scalars().all()],
        total=total,
    )
