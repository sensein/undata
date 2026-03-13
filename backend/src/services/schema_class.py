"""SchemaClassService — schema class node management and element classification.

Responsibilities:
- Derive element_kind from data_type / allowed_values / multivalued flag
- Create SchemaEnumeration rows for enumeration elements
- Create DataElementChild rows for complex elements (with depth guard)
- CRUD for SchemaClass nodes (DataElements with node_kind='class')
- Query classes for a schema or source
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.db import (
    DataElement,
    DataElementChild,
    DataElementVersion,
    DynamicSchema,
    DynamicSchemaElement,
    SchemaClassInheritance,
    SchemaEnumeration,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NODE_KIND = "field"
MAX_NESTING_DEPTH = 10

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def derive_element_kind(
    *,
    allowed_values: list[Any] | None,
    data_type: str,
    multivalued: bool = False,
) -> str:
    """Return the element_kind discriminator for a data element.

    Precedence:
    1. Non-empty allowed_values → 'enumeration'
    2. data_type == 'object'     → 'complex'
    3. data_type == 'array' or multivalued → 'array'
    4. Otherwise                 → 'scalar'
    """
    if allowed_values:
        return "enumeration"
    if data_type == "object":
        return "complex"
    if data_type == "array" or multivalued:
        return "array"
    return "scalar"


def check_nesting_depth(current_depth: int) -> None:
    """Raise ValueError if current_depth >= MAX_NESTING_DEPTH."""
    if current_depth >= MAX_NESTING_DEPTH:
        raise ValueError(
            f"DataElement nesting depth {current_depth} exceeds maximum allowed "
            f"nesting depth of {MAX_NESTING_DEPTH}. Avoid deep nesting."
        )


# ---------------------------------------------------------------------------
# SchemaEnumeration
# ---------------------------------------------------------------------------


async def create_schema_enumerations(
    *,
    element_id: uuid.UUID,
    allowed_values: list[Any] | None,
    db: AsyncSession,
) -> list[SchemaEnumeration]:
    """Insert SchemaEnumeration rows for an enumeration element.

    Returns the list of ORM objects added to the session (not yet committed).
    Returns [] if allowed_values is empty or None.
    """
    if not allowed_values:
        return []

    rows: list[SchemaEnumeration] = []
    for position, value in enumerate(allowed_values):
        row = SchemaEnumeration(
            id=uuid.uuid4(),
            element_id=element_id,
            value=str(value),
            position=position,
        )
        db.add(row)
        rows.append(row)

    logger.info(
        "Created %d SchemaEnumeration rows",
        len(rows),
        extra={"element_id": str(element_id)},
    )
    return rows


# ---------------------------------------------------------------------------
# DataElementChild (complex element nesting)
# ---------------------------------------------------------------------------


async def create_element_child_links(
    *,
    parent_id: uuid.UUID,
    child_specs: list[dict[str, Any]],  # [{element_id, field_name, position}]
    db: AsyncSession,
    current_depth: int = 0,
) -> list[DataElementChild]:
    """Insert DataElementChild rows for a complex element.

    Enforces MAX_NESTING_DEPTH. Each item in child_specs must have:
    - element_id: UUID
    - field_name: str
    - position: int
    """
    check_nesting_depth(current_depth)

    rows: list[DataElementChild] = []
    for spec in child_specs:
        row = DataElementChild(
            parent_id=parent_id,
            child_id=uuid.UUID(str(spec["element_id"])),
            field_name=spec["field_name"],
            position=spec["position"],
        )
        db.add(row)
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# SchemaClass nodes — create / query
# ---------------------------------------------------------------------------


async def create_class_node(
    *,
    source_id: uuid.UUID,
    class_name: str,
    description: str | None,
    parent_class_id: uuid.UUID | None,
    actor_id: uuid.UUID,
    db: AsyncSession,
) -> DataElement:
    """Create a DataElement with node_kind='class' representing a schema class.

    The element is associated with the given source. If parent_class_id is
    provided, a SchemaClassInheritance row (is_a) is also inserted.
    """
    from src.core.uri import mint_element_uri

    element_id = uuid.uuid4()
    uri = mint_element_uri(str(element_id))

    element = DataElement(
        id=element_id,
        uri=uri,
        source_id=source_id,
        source_local_id=class_name,
        version_num=1,
        element_kind="complex",
        node_kind="class",
    )
    db.add(element)
    await db.flush()

    # Create DataElementVersion for the class node
    dev = DataElementVersion(
        id=uuid.uuid4(),
        element_id=element_id,
        version_num=1,
        name=class_name,
        data_type="object",
        description=description,
        required=False,
        multivalued=False,
        created_by=actor_id,
    )
    db.add(dev)
    await db.flush()

    # Set current_version_id
    element.current_version_id = dev.id

    # Create inheritance link if parent provided
    if parent_class_id is not None:
        inheritance = SchemaClassInheritance(
            parent_class_id=parent_class_id,
            child_class_id=element_id,
            relationship_type="is_a",
        )
        db.add(inheritance)

    logger.info(
        "Created class node '%s'",
        class_name,
        extra={"element_id": str(element_id), "source_id": str(source_id)},
    )
    return element


async def link_element_to_class(
    *,
    class_element_id: uuid.UUID,
    member_element_id: uuid.UUID,
    position: int,
    db: AsyncSession,
) -> DataElementChild:
    """Link a member DataElement to a class node via DataElementChild."""
    link = DataElementChild(
        parent_id=class_element_id,
        child_id=member_element_id,
        field_name="",  # class membership links use empty field_name
        position=position,
    )
    db.add(link)
    return link


async def get_classes_for_source(
    *,
    source_id: uuid.UUID,
    db: AsyncSession,
) -> list[DataElement]:
    """Return all DataElements with node_kind='class' for a source."""
    result = await db.execute(
        select(DataElement)
        .where(
            DataElement.source_id == source_id,
            DataElement.node_kind == "class",
            DataElement.deleted_at.is_(None),
        )
        .order_by(DataElement.created_at)
    )
    return list(result.scalars().all())


async def get_classes_for_schema(
    *,
    schema_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return class nodes + their member elements for a DynamicSchema.

    Classes are DataElements with node_kind='class' that belong to the same
    source_id as the schema's elements, or that are directly linked as children
    of class nodes.

    Returns a list of dicts matching the SchemaClassRead shape.
    """
    # Get the schema's source elements to identify the source
    schema_result = await db.execute(
        select(DynamicSchema).where(DynamicSchema.id == schema_id)
    )
    schema = schema_result.scalar_one_or_none()
    if schema is None:
        return []

    # Get all elements linked to this schema
    dse_result = await db.execute(
        select(DynamicSchemaElement)
        .where(DynamicSchemaElement.schema_id == schema_id)
        .options(selectinload(DynamicSchemaElement.element))
    )
    schema_elements = list(dse_result.scalars().all())
    if not schema_elements:
        return []

    # Determine source_ids referenced by this schema
    source_ids = {se.element.source_id for se in schema_elements if se.element.source_id}

    if not source_ids:
        return []

    # Collect all class nodes from those sources
    classes: list[dict[str, Any]] = []
    for source_id in source_ids:
        class_elements = await get_classes_for_source(source_id=source_id, db=db)
        for cls_elem in class_elements:
            # Get child member elements
            child_result = await db.execute(
                select(DataElementChild)
                .where(DataElementChild.parent_id == cls_elem.id)
                .order_by(DataElementChild.position)
                .options(
                    selectinload(DataElementChild.child).selectinload(DataElement.current_version)
                )
            )
            children = list(child_result.scalars().all())

            # Get parent class if inheritance exists
            parent_result = await db.execute(
                select(SchemaClassInheritance).where(
                    SchemaClassInheritance.child_class_id == cls_elem.id,
                    SchemaClassInheritance.relationship_type == "is_a",
                )
            )
            parent_row = parent_result.scalar_one_or_none()

            element_refs = []
            for child in children:
                cv = child.child.current_version if child.child else None
                element_refs.append(
                    {
                        "element_id": child.child_id,
                        "name": cv.name if cv else "",
                        "data_type": cv.data_type if cv else "string",
                        "element_kind": child.child.element_kind if child.child else "scalar",
                        "required": cv.required if cv else False,
                        "allowed_values": cv.allowed_values if cv else None,
                        "position": child.position,
                    }
                )

            classes.append(
                {
                    "id": cls_elem.id,
                    "class_name": cls_elem.source_local_id,
                    "description": None,
                    "parent_class_id": parent_row.parent_class_id if parent_row else None,
                    "elements": element_refs,
                }
            )

    return classes
