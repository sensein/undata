"""Data element management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

import src.services.schema_changelog as schema_changelog_svc  # noqa: E402
from src.db.session import get_db
from src.models.db import (
    AliasGroup,
    AliasGroupMember,
    DataElement,
    DataElementVersion,
    MappingFunction,
    MappingInput,
    SchemaSource,
    UserProfile,
    ValidationRule,
)
from src.models.schemas import (
    BulkCreateRequest,
    BulkCreateResponse,
    DataElementChildRef,
    DataElementCreate,
    DataElementResponse,
    DataElementSummary,
    DataElementUpdate,
    DataElementVersionResponse,
    PaginatedList,
    SchemaSourceResponse,
    SemanticGraph,
    SupersedeElementRequest,
    ValidationRuleChangeRead,
    ValidationRuleCreate,
    ValidationRuleDeleteResponse,
    ValidationRuleRead,
    ValidationRulesResponse,
    ValidationRuleUpdate,
    ValidationRuleUpdateResponse,
)
from src.services.authz import Role, require_role
from src.services.elements import (
    AlreadySupersededError,
    CircularNestingError,
    DuplicateElementError,
    ElementNotFoundError,
    ElementService,
    InvalidNestingError,
    SemanticDuplicateError,
    VersionConflictError,
)
from src.services.validation_rule import (
    DuplicateRuleError,
    RuleNotFoundError,
    create_rule,
    delete_rule,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/elements", tags=["elements"])


async def _build_element_response(
    session: AsyncSession, element: DataElement
) -> DataElementResponse:
    """Construct a full DataElementResponse from ORM objects."""
    from sqlalchemy import select

    # Load current version
    version_result = await session.execute(
        select(DataElementVersion).where(DataElementVersion.id == element.current_version_id)
    )
    version = version_result.scalar_one_or_none()

    # Load source
    source_result = await session.execute(
        select(SchemaSource).where(SchemaSource.id == element.source_id)
    )
    source = source_result.scalar_one_or_none()

    # Load children
    from src.models.db import DataElementChild

    children_result = await session.execute(
        select(DataElementChild, DataElement)
        .join(DataElement, DataElementChild.child_id == DataElement.id)
        .where(DataElementChild.parent_id == element.id)
        .order_by(DataElementChild.position)
    )
    children = []
    for child_link, child_el in children_result.all():
        children.append(
            DataElementChildRef(
                id=child_el.id,
                uri=child_el.uri,
                field_name=child_link.field_name,
                position=child_link.position,
            )
        )

    # Resolve superseded_by URI
    superseded_by_uri = None
    if element.superseded_by:
        sup_result = await session.execute(
            select(DataElement.uri).where(DataElement.id == element.superseded_by)
        )
        superseded_by_uri = sup_result.scalar_one_or_none()

    # Resolve supersedes URI (find the element this one superseded)
    supersedes_uri = None
    superseded_el_result = await session.execute(
        select(DataElement.uri).where(DataElement.superseded_by == element.id)
    )
    supersedes_uri = superseded_el_result.scalar_one_or_none()

    # Resolve alias groups this element belongs to
    alias_groups_result = await session.execute(
        select(AliasGroup)
        .join(AliasGroupMember, AliasGroup.id == AliasGroupMember.alias_group_id)
        .where(AliasGroupMember.element_id == element.id)
    )
    alias_groups = [
        {
            "id": str(ag.id),
            "sssom_predicate": ag.sssom_predicate,
            "confidence": ag.confidence,
            "detection_method": ag.detection_method,
        }
        for ag in alias_groups_result.scalars().all()
    ]

    # Resolve mappings where this element is an input
    mappings_as_input_result = await session.execute(
        select(MappingFunction)
        .join(MappingInput, MappingFunction.id == MappingInput.mapping_id)
        .where(MappingInput.element_id == element.id, MappingFunction.deleted_at.is_(None))
    )
    mappings_as_input = [
        {"id": str(m.id), "uri": m.uri, "function_type": m.function_type}
        for m in mappings_as_input_result.scalars().all()
    ]

    # Resolve mappings where this element is the output
    mappings_as_output_result = await session.execute(
        select(MappingFunction).where(
            MappingFunction.output_element_id == element.id,
            MappingFunction.deleted_at.is_(None),
        )
    )
    mappings_as_output = [
        {"id": str(m.id), "uri": m.uri, "function_type": m.function_type}
        for m in mappings_as_output_result.scalars().all()
    ]

    semantic_graph = None
    unit = None
    if version:
        unit = version.unit
        if version.semantic_graph:
            try:
                semantic_graph = SemanticGraph.model_validate(version.semantic_graph)
            except Exception:
                pass

    source_response = None
    if source:
        source_response = SchemaSourceResponse(
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

    return DataElementResponse(
        id=element.id,
        uri=element.uri,
        name=version.name if version else "",
        data_type=version.data_type if version else "",
        description=version.description if version else None,
        required=version.required if version else False,
        multivalued=version.multivalued if version else False,
        allowed_values=version.allowed_values if version else None,
        constraints=version.constraints if version else None,
        semantic_graph=semantic_graph,
        unit=unit,
        superseded_by=superseded_by_uri,
        supersedes=supersedes_uri,
        source=source_response,
        source_local_id=element.source_local_id,
        children=children,
        alias_groups=alias_groups,
        mappings_as_input=mappings_as_input,
        mappings_as_output=mappings_as_output,
        schema_ref=element.schema_ref,
        version_num=element.version_num,
        created_at=element.created_at,
        deleted_at=element.deleted_at,
    )


def _build_summary(element: DataElement, version: DataElementVersion | None) -> DataElementSummary:
    unit = version.unit if version else None
    superseded_by = None  # resolved separately if needed
    return DataElementSummary(
        id=element.id,
        uri=element.uri,
        name=version.name if version else "",
        data_type=version.data_type if version else "",
        description=version.description if version else None,
        required=version.required if version else False,
        multivalued=version.multivalued if version else False,
        unit=unit,
        superseded_by=superseded_by,
        version_num=element.version_num,
    )


@router.get("/", response_model=PaginatedList[DataElementSummary])
async def list_elements(
    q: str | None = None,
    source_id: UUID | None = None,
    data_type: str | None = None,
    unit: str | None = None,
    subject: str | None = None,
    property: str | None = None,
    has_aliases: bool | None = None,
    has_mappings: bool | None = None,
    include_superseded: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List data elements (public). Supports keyword search, unit filter, etc."""
    from sqlalchemy import select

    total, elements = await ElementService.list(
        session,
        source_id=source_id,
        data_type=data_type,
        q=q,
        unit=unit,
        subject=subject,
        property_label=property,
        has_aliases=has_aliases,
        has_mappings=has_mappings,
        include_superseded=include_superseded,
        limit=limit,
        offset=offset,
    )

    # Load versions and sources for summary
    items = []
    for element in elements:
        version_result = await session.execute(
            select(DataElementVersion).where(DataElementVersion.id == element.current_version_id)
        )
        version = version_result.scalar_one_or_none()
        source_result = await session.execute(
            select(SchemaSource).where(SchemaSource.id == element.source_id)
        )
        source_obj = source_result.scalar_one_or_none()
        source_resp = (
            SchemaSourceResponse.model_validate(source_obj) if source_obj else None
        )
        summary = _build_summary(element, version)
        summary.source = source_resp
        items.append(summary)

    return PaginatedList(total=total, limit=limit, offset=offset, items=items)


@router.get("/{element_id}", response_model=DataElementResponse)
async def get_element(
    element_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get element by ID regardless of lifecycle state (public)."""
    element = await ElementService.get(session, element_id)
    if element is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return await _build_element_response(session, element)


@router.get("/{element_id}/history", response_model=list[DataElementVersionResponse])
async def get_element_history(
    element_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get version history for an element (public)."""
    from sqlalchemy import select

    element = await ElementService.get(session, element_id)
    if element is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    versions = await ElementService.get_history(session, element_id)

    result = []
    for v in versions:
        # Load creator display name
        creator_name = None
        if v.created_by:
            from src.models.db import UserProfile as UP

            user_result = await session.execute(
                select(UP.display_name).where(UP.id == v.created_by)
            )
            creator_name = user_result.scalar_one_or_none()

        semantic_graph = None
        if v.semantic_graph:
            try:
                semantic_graph = SemanticGraph.model_validate(v.semantic_graph)
            except Exception:
                pass

        result.append(
            DataElementVersionResponse(
                id=v.id,
                element_id=v.element_id,
                version_num=v.version_num,
                name=v.name,
                data_type=v.data_type,
                description=v.description,
                required=v.required,
                multivalued=v.multivalued,
                allowed_values=v.allowed_values,
                constraints=v.constraints,
                semantic_graph=semantic_graph,
                unit=v.unit,
                created_at=v.created_at,
                created_by_display_name=creator_name,
            )
        )

    return result


@router.post("/", response_model=DataElementResponse, status_code=201)
async def create_element(
    body: DataElementCreate,
    request: Request,
    current_user: UserProfile = Depends(require_role(Role.CONTRIBUTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Create a new data element (contributor+)."""
    unit_service = getattr(request.app.state, "unit_service", None)
    try:
        element = await ElementService.create(
            session, body, current_user.id, unit_service=unit_service
        )
    except SemanticDuplicateError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "semantic_duplicate",
                "existing_id": exc.existing_id,
                "existing_uri": exc.existing_uri,
            },
        )
    except DuplicateElementError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "duplicate_element", "message": str(exc)}
        )

    return await _build_element_response(session, element)


@router.post("/bulk", response_model=BulkCreateResponse, status_code=207)
async def bulk_create_elements(
    body: BulkCreateRequest,
    current_user: UserProfile = Depends(require_role(Role.CONTRIBUTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Bulk create data elements (contributor+). Partial success allowed."""
    result = await ElementService.bulk_create(session, body.elements, current_user.id)
    return result


@router.put("/{element_id}", response_model=DataElementResponse)
async def update_element(
    element_id: UUID,
    body: DataElementUpdate,
    request: Request,
    current_user: UserProfile = Depends(require_role(Role.CONTRIBUTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Update a data element (contributor+). Requires correct version_num."""
    unit_service = getattr(request.app.state, "unit_service", None)
    try:
        element = await ElementService.update(
            session, element_id, body, current_user.id, body.version_num,
            unit_service=unit_service,
        )
    except ElementNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except VersionConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "version_conflict", "message": str(exc)}
        )

    return await _build_element_response(session, element)


@router.delete("/{element_id}")
async def delete_element(
    element_id: UUID,
    version_num: int | None = None,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a data element (curator+). Optionally pass version_num for optimistic locking."""
    if version_num is None:
        # Auto-resolve current version
        element = await ElementService.get(session, element_id)
        if element is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        version_num = element.version_num

    try:
        element = await ElementService.delete(session, element_id, current_user.id, version_num)
    except ElementNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except VersionConflictError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "version_conflict", "message": str(exc)}
        )

    # Cascade soft-delete all active ValidationRules for this element (T066)
    from datetime import datetime, timezone

    from sqlalchemy import update as _update

    await session.execute(
        _update(ValidationRule)
        .where(
            ValidationRule.element_id == element_id,
            ValidationRule.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )

    return {"id": str(element.id), "deleted_at": element.deleted_at.isoformat()}


@router.post("/{element_id}/children", response_model=DataElementResponse)
async def add_children(
    element_id: UUID,
    body: dict,
    current_user: UserProfile = Depends(require_role(Role.CONTRIBUTOR)),
    session: AsyncSession = Depends(get_db),
):
    """Add child elements to a parent element (contributor+)."""
    children = body.get("children", [])
    try:
        element = await ElementService.add_children(session, element_id, children, current_user.id)
    except ElementNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    except InvalidNestingError as exc:
        raise HTTPException(
            status_code=400, detail={"error": "invalid_nesting", "message": str(exc)}
        )
    except CircularNestingError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "circular_nesting", "details": {"cycle_path": exc.cycle_path}},
        )

    return await _build_element_response(session, element)


@router.get("/{element_id}/children", response_model=list[DataElementChildRef])
async def get_children(
    element_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get child elements of a parent element (public)."""
    from sqlalchemy import select

    children = await ElementService.get_children(session, element_id)
    result = []
    for link in children:
        child_result = await session.execute(
            select(DataElement).where(DataElement.id == link.child_id)
        )
        child = child_result.scalar_one_or_none()
        if child:
            result.append(
                DataElementChildRef(
                    id=child.id,
                    uri=child.uri,
                    field_name=link.field_name,
                    position=link.position,
                )
            )
    return result


@router.post("/{element_id}/supersede", status_code=201)
async def supersede_element(
    element_id: UUID,
    body: SupersedeElementRequest,
    request: Request,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Supersede an element with a semantically distinct replacement (curator+)."""
    unit_service = getattr(request.app.state, "unit_service", None)
    try:
        new_element, old_element = await ElementService.supersede(
            session, element_id, body, current_user.id, unit_service=unit_service
        )
    except ElementNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    except AlreadySupersededError as exc:
        raise HTTPException(
            status_code=409, detail={"error": "already_superseded", "message": str(exc)}
        )

    new_response = await _build_element_response(session, new_element)
    # Set supersedes on the new element response
    new_response.supersedes = old_element.uri

    return {
        "new_element": new_response,
        "superseded_element": {
            "id": str(old_element.id),
            "uri": old_element.uri,
            "superseded_by": new_element.uri,
            "deleted_at": old_element.deleted_at.isoformat() if old_element.deleted_at else None,
        },
    }


# ---------------------------------------------------------------------------
# Validation Rules endpoints — T034
# ---------------------------------------------------------------------------


@router.post(
    "/{element_id}/validation-rules",
    response_model=ValidationRuleRead,
    status_code=201,
)
async def create_validation_rule(
    element_id: UUID,
    body: ValidationRuleCreate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Create a validation rule for an element (curator+)."""
    try:
        rule, _ = await create_rule(
            element_id=element_id,
            rule_type=body.rule_type,
            rule_value=body.rule_value,
            severity=body.severity,
            description=body.description,
            actor_id=current_user.id,
            db=session,
        )
    except DuplicateRuleError as exc:
        raise HTTPException(status_code=409, detail={"error": "duplicate_rule", "message": str(exc)})
    return ValidationRuleRead.model_validate(rule)


@router.get(
    "/{element_id}/validation-rules",
    response_model=ValidationRulesResponse,
)
async def get_validation_rules(
    element_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """List all active validation rules for an element (public)."""
    rules = await list_rules(element_id=element_id, db=session)
    return ValidationRulesResponse(
        element_id=element_id,
        rules=[ValidationRuleRead.model_validate(r) for r in rules],
    )


@router.put(
    "/{element_id}/validation-rules/{rule_id}",
    response_model=ValidationRuleUpdateResponse,
)
async def update_validation_rule(
    element_id: UUID,
    rule_id: UUID,
    body: ValidationRuleUpdate,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Update a validation rule (curator+). Returns rule + breaking-change record."""
    try:
        rule, change = await update_rule(
            rule_id=rule_id,
            new_rule_value=body.rule_value,
            severity=body.severity,
            description=body.description,
            reason=body.reason,
            actor_id=current_user.id,
            db=session,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return ValidationRuleUpdateResponse(
        rule=ValidationRuleRead.model_validate(rule),
        change=ValidationRuleChangeRead.model_validate(change),
    )


@router.delete(
    "/{element_id}/validation-rules/{rule_id}",
    response_model=ValidationRuleDeleteResponse,
)
async def delete_validation_rule(
    element_id: UUID,
    rule_id: UUID,
    current_user: UserProfile = Depends(require_role(Role.CURATOR)),
    session: AsyncSession = Depends(get_db),
):
    """Soft-delete a validation rule (curator+). Always non-breaking."""
    try:
        rule, change = await delete_rule(
            rule_id=rule_id,
            actor_id=current_user.id,
            db=session,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})
    return ValidationRuleDeleteResponse(
        deleted=True,
        breaking=change.breaking,
        change=ValidationRuleChangeRead.model_validate(change),
    )


from fastapi.responses import JSONResponse  # noqa: E402


@router.get("/{element_id}/provenance")
async def get_element_provenance(
    element_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return W3C PROV-DM JSON-LD provenance for an element (public)."""
    from sqlalchemy import select as _select

    el_result = await session.execute(
        _select(DataElement).where(
            DataElement.id == element_id,
            DataElement.deleted_at.is_(None),
        )
    )
    if el_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    prov = await schema_changelog_svc.to_element_prov_jsonld(element_id=element_id, db=session)
    return JSONResponse(content=prov, media_type="application/ld+json")
