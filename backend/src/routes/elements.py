"""V2 element API endpoints — content-addressed identity model."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.db import UserProfile
from ..services.authz import Role, require_role
from ..services.element_service import ElementService

router = APIRouter(prefix="/api/v1/elements", tags=["elements"])


class SemanticInput(BaseModel):
    ontology_term: str | None = None
    data_type: str
    unit: str | None = None
    constraints: dict | None = None
    # reproschema-aligned fields:
    response_options: list[dict] | None = None
    question_text: str | None = None
    value_domain: str | None = None
    min_value: float | None = None
    max_value: float | None = None


class ProvenanceInput(BaseModel):
    source: str
    class_: str | None = None

    model_config = {"populate_by_name": True}

    # Accept both "class" and "class_" from JSON
    def model_post_init(self, __context):
        pass


class ElementCreateRequest(BaseModel):
    semantic: SemanticInput
    provenance: list[dict]


class ProvenanceResponse(BaseModel):
    source: str
    class_: str
    name: str
    description: str | None = None
    required: bool | None = None
    multivalued: bool | None = None


class ElementResponse(BaseModel):
    uri: str
    semantic: dict
    provenance: list[dict]


class ElementListResponse(BaseModel):
    items: list[ElementResponse]
    total: int


def _element_to_response(elem) -> ElementResponse:
    provenance = [
        {
            "source": p.source,
            "class": p.class_,
            "name": p.name,
            "description": p.description,
            "required": p.required,
            "multivalued": p.multivalued,
        }
        for p in elem.provenance
    ]
    return ElementResponse(uri=elem.uri, semantic=elem.semantic, provenance=provenance)


@router.post("", status_code=201)
async def create_element(
    body: ElementCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_role(Role.CONTRIBUTOR)),
):
    """Create a new element or merge provenance into existing.

    Returns 201 if new, 200 if merged.
    """
    svc = ElementService(session)
    elem, created = await svc.create_or_merge(
        semantic=body.semantic.model_dump(exclude_none=True),
        provenance=body.provenance,
    )
    await session.commit()

    response = _element_to_response(elem)

    if created:
        return response  # 201

    # Override status to 200 for merge
    from fastapi.responses import JSONResponse

    return JSONResponse(content=response.model_dump(), status_code=200)


@router.get("")
async def list_elements(
    source: str | None = Query(None),
    data_type: str | None = Query(None),
    ontology_term: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> ElementListResponse:
    """List elements with optional filters."""
    svc = ElementService(session)
    elements, total = await svc.list_elements(
        source=source,
        data_type=data_type,
        ontology_term=ontology_term,
        limit=limit,
        offset=offset,
    )
    return ElementListResponse(
        items=[_element_to_response(e) for e in elements],
        total=total,
    )


@router.get("/{uri:path}")
async def get_element(
    uri: str,
    session: AsyncSession = Depends(get_db),
):
    """Get a single element by URI."""
    svc = ElementService(session)
    elem = await svc.get_by_uri(uri)
    if not elem:
        from fastapi import HTTPException

        raise HTTPException(404, detail=f"Element not found: {uri}")
    return _element_to_response(elem)
