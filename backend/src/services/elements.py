"""ElementService — data element CRUD, nesting, versioning, and supersession."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.uri import mint_element_uri
from src.models.db import (
    AliasGroupMember,
    DataElement,
    DataElementChild,
    DataElementVersion,
    MappingFunction,
    MappingInput,
    SchemaSource,
)
from src.models.schemas import (
    BulkCreateResponse,
    BulkElementItem,
    BulkErrorItem,
    DataElementCreate,
    DataElementUpdate,
    SupersedeElementRequest,
)
from src.services.audit import AuditService
from src.services.schema_class import derive_element_kind

logger = get_logger(__name__)


class DuplicateElementError(Exception):
    pass


class VersionConflictError(Exception):
    pass


class InvalidNestingError(Exception):
    pass


class CircularNestingError(Exception):
    def __init__(self, cycle_path: list[str]):
        self.cycle_path = cycle_path
        super().__init__(f"Circular nesting detected: {cycle_path}")


class ElementNotFoundError(Exception):
    pass


class AlreadySupersededError(Exception):
    pass


class SemanticDuplicateError(Exception):
    """Raised when a semantically identical undata canonical element already exists."""

    def __init__(self, existing_id: str, existing_uri: str) -> None:
        self.existing_id = existing_id
        self.existing_uri = existing_uri
        super().__init__(
            f"Semantic duplicate: undata element {existing_id} ({existing_uri}) "
            "already represents the same entity+property+unit combination."
        )


def _extract_unit(data: DataElementCreate | DataElementUpdate) -> str | None:
    """Extract unit label from semantic_graph.unit.label if present."""
    if data.semantic_graph and data.semantic_graph.unit:
        return data.semantic_graph.unit.label
    return None


def _enrich_unit(
    data: DataElementCreate | DataElementUpdate,
    unit_service: object | None,
) -> None:
    """Enrich semantic_graph.unit with cmixf_valid, external_uri, qudt_unresolvable.

    Modifies data.semantic_graph.unit in-place. Non-blocking: always succeeds.
    unit_service is expected to be a UnitResolutionService instance or None.
    """
    if unit_service is None:
        return
    if data.semantic_graph is None or data.semantic_graph.unit is None:
        return
    unit = data.semantic_graph.unit
    try:
        result = unit_service.resolve(label=unit.label, symbol=unit.symbol)
        unit.external_uri = result.qudt_uri
        unit.cmixf_valid = result.cmixf_valid
        unit.qudt_unresolvable = result.qudt_unresolvable
    except Exception as exc:
        logger.warning("unit.enrichment.failed", extra={"error": str(exc)})


def _semantic_graph_to_json(data: DataElementCreate | DataElementUpdate) -> dict | None:
    if data.semantic_graph is None:
        return None
    return data.semantic_graph.model_dump()


_embedding_model: "SentenceTransformer | None" = None


def _get_embedding_model() -> "SentenceTransformer":
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


async def _generate_embedding(text_content: str | None) -> list[float] | None:
    """Generate sentence embedding using all-MiniLM-L6-v2."""
    if not text_content:
        return None
    try:
        model = _get_embedding_model()
        embedding = model.encode(text_content).tolist()
        return embedding
    except Exception as exc:
        logger.warning("embedding.failed", extra={"error": str(exc)})
        return None


async def _check_undata_semantic_duplicate(
    session: AsyncSession,
    data: "DataElementCreate",
) -> None:
    """Raise SemanticDuplicateError if a semantically identical undata element exists.

    Fingerprint = (sorted entity labels, property label, unit label).
    Only applied when creating under the "undata" canonical source AND
    the new element carries a semantic_graph with at least property or unit defined.
    """
    sg = data.semantic_graph
    if sg is None:
        return
    prop_label = sg.property.label if sg.property else None
    unit_label = sg.unit.label if sg.unit else None
    entity_labels = sorted(e.label for e in (sg.entities or []))

    # Skip check when fingerprint is entirely empty
    if prop_label is None and unit_label is None and not entity_labels:
        return

    # Load active undata elements with their current version
    result = await session.execute(
        select(DataElement, DataElementVersion)
        .join(DataElementVersion, DataElement.current_version_id == DataElementVersion.id)
        .join(SchemaSource, DataElement.source_id == SchemaSource.id)
        .where(
            SchemaSource.name == "undata",
            DataElement.deleted_at.is_(None),
        )
    )
    for element, version in result.all():
        if version.semantic_graph is None:
            continue
        vsg = version.semantic_graph
        v_prop = (vsg.get("property") or {}).get("label")
        v_unit = (vsg.get("unit") or {}).get("label")
        v_entities = sorted(e.get("label", "") for e in (vsg.get("entities") or []))
        if v_prop == prop_label and v_unit == unit_label and v_entities == entity_labels:
            raise SemanticDuplicateError(str(element.id), element.uri)


def _check_cycle_dfs(
    existing_edges: list[tuple[str, str]],
    proposed_parent: str,
    proposed_children: list[str],
) -> list[str] | None:
    """DFS cycle detection for parent-child nesting.

    Returns the cycle path if a cycle is detected, else None.
    """
    # Build adjacency list (parent → children)
    adj: dict[str, list[str]] = {}
    for parent, child in existing_edges:
        adj.setdefault(parent, []).append(child)

    # Add proposed edges
    for child in proposed_children:
        adj.setdefault(proposed_parent, []).append(child)

    # DFS to find cycle reachable from any proposed child back to proposed_parent
    def dfs(start: str, target: str, path: list[str], visited: set[str]) -> list[str] | None:
        if start == target:
            return path + [target]
        if start in visited:
            return None
        visited.add(start)
        for neighbor in adj.get(start, []):
            result = dfs(neighbor, target, path + [start], visited)
            if result:
                return result
        return None

    for child in proposed_children:
        cycle = dfs(child, proposed_parent, [], set())
        if cycle:
            return cycle

    return None


class ElementService:
    @staticmethod
    async def create(
        session: AsyncSession,
        data: DataElementCreate,
        actor_id: UUID,
        unit_service: object | None = None,
    ) -> DataElement:
        """Create a new DataElement with URI minting and semantic graph extraction."""
        element_id = uuid.uuid4()
        uri = mint_element_uri(str(element_id))

        # Enrich unit with cmixf validation + QUDT resolution (non-blocking)
        _enrich_unit(data, unit_service)

        # Extract unit from semantic_graph
        unit = _extract_unit(data)
        semantic_graph_json = _semantic_graph_to_json(data)

        # Generate embeddings
        name_embedding = await _generate_embedding(data.name)
        desc_embedding = await _generate_embedding(data.description)

        # Guard: reject semantic duplicates in the undata canonical space
        if data.source_id is not None and data.semantic_graph is not None:
            src_name_result = await session.execute(
                select(SchemaSource.name).where(SchemaSource.id == data.source_id)
            )
            src_name = src_name_result.scalar_one_or_none()
            if src_name == "undata":
                await _check_undata_semantic_duplicate(session, data)

        # Check cross-source name collision (same name, different source)
        collision_result = await session.execute(
            select(DataElement.id)
            .join(DataElementVersion, DataElement.current_version_id == DataElementVersion.id)
            .where(
                DataElementVersion.name == data.name,
                DataElement.source_id != data.source_id,
                DataElement.deleted_at.is_(None),
            )
        )
        collision_candidates = [str(r) for r in collision_result.scalars().all()]

        element_kind = derive_element_kind(
            allowed_values=data.allowed_values,
            data_type=data.data_type,
            multivalued=getattr(data, "multivalued", False) or False,
        )
        element = DataElement(
            id=element_id,
            uri=uri,
            source_id=data.source_id,
            source_local_id=data.source_local_id or str(element_id),
            version_num=1,
            element_kind=element_kind,
            node_kind=getattr(data, "node_kind", None) or "field",
            schema_ref=getattr(data, "schema_ref", None),
        )
        session.add(element)
        try:
            await session.flush()  # get element.id
        except IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise DuplicateElementError(
                    f"Duplicate: source_id={data.source_id} "
                    f"source_local_id={data.source_local_id}"
                ) from exc
            raise

        version = DataElementVersion(
            element_id=element.id,
            version_num=1,
            name=data.name,
            data_type=data.data_type,
            description=data.description,
            required=data.required,
            multivalued=data.multivalued,
            allowed_values=data.allowed_values,
            constraints=data.constraints,
            semantic_graph=semantic_graph_json,
            unit=unit,
            name_embedding=name_embedding,
            description_embedding=desc_embedding,
            created_by=actor_id,
        )
        session.add(version)
        await session.flush()

        element.current_version_id = version.id
        await session.flush()

        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=element.id,
            operation="create",
            actor_id=actor_id,
            version_num=1,
        )

        # Attach collision info as attribute for the router to surface
        element._collision_candidates = collision_candidates  # type: ignore[attr-defined]
        logger.info("element.created", extra={"element_id": str(element.id), "uri": uri})
        return element

    @staticmethod
    async def add_children(
        session: AsyncSession,
        parent_id: UUID,
        children: list[dict[str, Any]],
        actor_id: UUID,
    ) -> DataElement:
        """Add child elements to a parent element (object/array type).

        Performs DFS cycle detection before inserting.
        """
        # Load parent
        parent_result = await session.execute(
            select(DataElement).where(DataElement.id == parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            raise ElementNotFoundError(f"Parent element {parent_id} not found")

        # FR-003: reject DataElementChild when parent has a named schema_ref
        if parent.schema_ref is not None:
            raise InvalidNestingError(
                "Use schema_ref for named types — DataElementChild is only for anonymous inline "
                "structures. Parent element already references a DynamicSchema via schema_ref."
            )

        # Load parent's current version for data_type check
        version_result = await session.execute(
            select(DataElementVersion).where(DataElementVersion.id == parent.current_version_id)
        )
        current_version = version_result.scalar_one_or_none()
        if current_version and current_version.data_type not in ("object", "array"):
            raise InvalidNestingError(
                f"Parent data_type must be 'object' or 'array', "
                f"got '{current_version.data_type}'"
            )

        # Load all existing edges for cycle detection
        existing_edges_result = await session.execute(
            select(DataElementChild.parent_id, DataElementChild.child_id)
        )
        existing_edges = [(str(r.parent_id), str(r.child_id)) for r in existing_edges_result.all()]

        child_ids = [str(c["child_id"]) for c in children]

        # DFS cycle check
        cycle = _check_cycle_dfs(existing_edges, str(parent_id), child_ids)
        if cycle:
            raise CircularNestingError(cycle)

        # Insert child references
        for child_data in children:
            child_id = UUID(str(child_data["child_id"]))
            # Verify child exists
            child_check = await session.execute(
                select(DataElement.id).where(DataElement.id == child_id)
            )
            if child_check.scalar_one_or_none() is None:
                raise ElementNotFoundError(f"Child element {child_id} not found")

            link = DataElementChild(
                parent_id=parent_id,
                child_id=child_id,
                position=child_data.get("position", 0),
                field_name=child_data.get("field_name"),
            )
            session.add(link)

        await session.flush()
        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=parent_id,
            operation="update",
            actor_id=actor_id,
            diff={"children_added": child_ids},
        )
        return parent

    @staticmethod
    async def get_children(session: AsyncSession, parent_id: UUID) -> list[DataElementChild]:
        result = await session.execute(
            select(DataElementChild)
            .where(DataElementChild.parent_id == parent_id)
            .order_by(DataElementChild.position)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list(
        session: AsyncSession,
        source_id: UUID | None = None,
        data_type: str | None = None,
        q: str | None = None,
        unit: str | None = None,
        subject: str | None = None,
        property_label: str | None = None,
        has_aliases: bool | None = None,
        has_mappings: bool | None = None,
        include_superseded: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[DataElement]]:
        if include_superseded:
            # Include active elements AND superseded elements (deleted via supersession)
            query = (
                select(DataElement)
                .join(DataElementVersion, DataElement.current_version_id == DataElementVersion.id)
                .where(
                    or_(
                        DataElement.deleted_at.is_(None),
                        DataElement.superseded_by.isnot(None),
                    )
                )
            )
        else:
            query = (
                select(DataElement)
                .join(DataElementVersion, DataElement.current_version_id == DataElementVersion.id)
                .where(DataElement.deleted_at.is_(None))
                .where(DataElement.superseded_by.is_(None))
            )

        if source_id:
            query = query.where(DataElement.source_id == source_id)

        if data_type:
            query = query.where(DataElementVersion.data_type == data_type)

        if unit:
            query = query.where(DataElementVersion.unit == unit)

        if q:
            query = query.where(
                text(
                    "to_tsvector('english', coalesce(data_element_version.name, '')) "
                    "@@ plainto_tsquery('english', :q)"
                ).bindparams(q=q)
            )

        if subject:
            query = query.where(
                DataElementVersion.semantic_graph.op("@?")(
                    text("'$.entities[*] ? (@.label == $label)'").bindparams(label=subject)
                )
            )

        if property_label:
            query = query.where(
                DataElementVersion.semantic_graph.op("@?")(
                    text("'$.property ? (@.label == $label)'").bindparams(label=property_label)
                )
            )

        if has_aliases is True:
            alias_subq = select(AliasGroupMember.element_id).scalar_subquery()
            query = query.where(DataElement.id.in_(alias_subq))
        elif has_aliases is False:
            alias_subq = select(AliasGroupMember.element_id).scalar_subquery()
            query = query.where(DataElement.id.not_in(alias_subq))

        if has_mappings is True:
            input_subq = select(MappingInput.element_id).join(
                MappingFunction, MappingFunction.id == MappingInput.mapping_id
            ).where(MappingFunction.deleted_at.is_(None)).scalar_subquery()
            output_subq = select(MappingFunction.output_element_id).where(
                MappingFunction.deleted_at.is_(None)
            ).scalar_subquery()
            query = query.where(
                or_(DataElement.id.in_(input_subq), DataElement.id.in_(output_subq))
            )
        elif has_mappings is False:
            input_subq = select(MappingInput.element_id).join(
                MappingFunction, MappingFunction.id == MappingInput.mapping_id
            ).where(MappingFunction.deleted_at.is_(None)).scalar_subquery()
            output_subq = select(MappingFunction.output_element_id).where(
                MappingFunction.deleted_at.is_(None)
            ).scalar_subquery()
            query = query.where(
                DataElement.id.not_in(input_subq), DataElement.id.not_in(output_subq)
            )

        count_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()

        result = await session.execute(
            query.order_by(DataElement.created_at.desc()).limit(limit).offset(offset)
        )
        return total, list(result.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, element_id: UUID) -> DataElement | None:
        """Get element regardless of lifecycle state (active, superseded, soft-deleted)."""
        result = await session.execute(select(DataElement).where(DataElement.id == element_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        session: AsyncSession,
        element_id: UUID,
        data: DataElementUpdate,
        actor_id: UUID,
        version_num: int,
        unit_service: object | None = None,
    ) -> DataElement:
        element = await ElementService.get(session, element_id)
        if element is None:
            raise ElementNotFoundError(f"Element {element_id} not found")

        if element.version_num != version_num:
            raise VersionConflictError(
                f"Version conflict: current={element.version_num}, provided={version_num}"
            )

        # Load old version for diff
        old_version_result = await session.execute(
            select(DataElementVersion).where(DataElementVersion.id == element.current_version_id)
        )
        old_version = old_version_result.scalar_one()

        # Enrich unit with cmixf validation + QUDT resolution (non-blocking)
        if data.semantic_graph is not None:
            _enrich_unit(data, unit_service)

        unit = _extract_unit(data) if data.semantic_graph is not None else old_version.unit
        semantic_graph_json = (
            _semantic_graph_to_json(data)
            if data.semantic_graph is not None
            else old_version.semantic_graph
        )

        new_version_num = element.version_num + 1
        name_embedding = await _generate_embedding(data.name or old_version.name)
        desc_embedding = await _generate_embedding(data.description or old_version.description)

        new_version = DataElementVersion(
            element_id=element.id,
            version_num=new_version_num,
            name=data.name if data.name is not None else old_version.name,
            data_type=data.data_type if data.data_type is not None else old_version.data_type,
            description=data.description
            if data.description is not None
            else old_version.description,
            required=data.required if data.required is not None else old_version.required,
            multivalued=data.multivalued
            if data.multivalued is not None
            else old_version.multivalued,
            allowed_values=data.allowed_values
            if data.allowed_values is not None
            else old_version.allowed_values,
            constraints=data.constraints
            if data.constraints is not None
            else old_version.constraints,
            semantic_graph=semantic_graph_json,
            unit=unit,
            name_embedding=name_embedding,
            description_embedding=desc_embedding,
            created_by=actor_id,
        )
        session.add(new_version)
        await session.flush()

        element.current_version_id = new_version.id
        element.version_num = new_version_num
        await session.flush()

        diff = {}
        for field in ("name", "data_type", "description", "required", "multivalued"):
            old_val = getattr(old_version, field)
            new_val = getattr(new_version, field)
            if old_val != new_val:
                diff[field] = {"old": old_val, "new": new_val}

        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=element.id,
            operation="update",
            actor_id=actor_id,
            version_num=new_version_num,
            diff=diff or None,
        )
        return element

    @staticmethod
    async def delete(
        session: AsyncSession,
        element_id: UUID,
        actor_id: UUID,
        version_num: int,
    ) -> DataElement:
        element = await ElementService.get(session, element_id)
        if element is None:
            raise ElementNotFoundError(f"Element {element_id} not found")

        if element.version_num != version_num:
            raise VersionConflictError(
                f"Version conflict: current={element.version_num}, provided={version_num}"
            )

        element.deleted_at = datetime.now(timezone.utc)
        await session.flush()

        # Set status="broken" on mapping functions referencing this element
        broken_mappings = await session.execute(
            select(MappingFunction.id)
            .join(MappingInput, MappingFunction.id == MappingInput.mapping_id)
            .where(
                or_(
                    MappingInput.element_id == element_id,
                    MappingFunction.output_element_id == element_id,
                )
            )
        )
        for mapping_id in broken_mappings.scalars().all():
            mapping_result = await session.execute(
                select(MappingFunction).where(MappingFunction.id == mapping_id)
            )
            mapping = mapping_result.scalar_one_or_none()
            if mapping:
                mapping.status = "broken"

        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=element_id,
            operation="delete",
            actor_id=actor_id,
            version_num=element.version_num,
        )
        return element

    @staticmethod
    async def bulk_create(
        session: AsyncSession,
        elements: list[DataElementCreate],
        actor_id: UUID,
    ) -> BulkCreateResponse:
        succeeded: list[BulkElementItem] = []
        failed: list[BulkErrorItem] = []

        for i, element_data in enumerate(elements):
            try:
                element = await ElementService.create(session, element_data, actor_id)
                succeeded.append(BulkElementItem(index=i, id=element.id, uri=element.uri))
            except Exception as exc:
                failed.append(BulkErrorItem(index=i, error=type(exc).__name__, message=str(exc)))

        return BulkCreateResponse(succeeded=succeeded, failed=failed)

    @staticmethod
    async def get_history(
        session: AsyncSession,
        element_id: UUID,
    ) -> list[DataElementVersion]:
        result = await session.execute(
            select(DataElementVersion)
            .where(DataElementVersion.element_id == element_id)
            .order_by(DataElementVersion.version_num.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def supersede(
        session: AsyncSession,
        old_id: UUID,
        req: SupersedeElementRequest,
        actor_id: UUID,
        unit_service: object | None = None,
    ) -> tuple[DataElement, DataElement]:
        """Replace an element with a semantically distinct successor.

        Single-transaction atomicity:
        1. Load old element (404 if missing, 409 if already superseded)
        2. Create new element
        3. Set old.superseded_by = new.id, old.deleted_at = now()
        4. Audit both

        Returns (new_element, old_element).
        """
        old = await ElementService.get(session, old_id)
        if old is None:
            raise ElementNotFoundError(f"Element {old_id} not found")
        if old.superseded_by is not None:
            raise AlreadySupersededError(f"Element {old_id} is already superseded")

        new = await ElementService.create(
            session, req.new_element_data, actor_id, unit_service=unit_service
        )

        old.superseded_by = new.id
        old.deleted_at = datetime.now(timezone.utc)
        await session.flush()

        # Audit: old element deletion via supersession
        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=old.id,
            operation="supersede",
            actor_id=actor_id,
            diff={
                "supersede_reason": req.supersede_reason,
                "superseded_by": new.uri,
            },
        )
        # Audit: new element creation (supersedes old)
        await AuditService.record(
            session,
            record_type="DataElement",
            record_id=new.id,
            operation="create",
            actor_id=actor_id,
            diff={"supersedes": old.uri},
        )

        return new, old
