"""LinkML import/export service (FR-008, FR-009).

Provides:
- RoundtripResult: fidelity scoring data class
- export_schema(): DynamicSchema → LinkML YAML string
- import_schema(): LinkML YAML string → DynamicSchema + DataElements
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.logging import get_logger

logger = get_logger(__name__)

# Known ontology URI prefixes for slot_uri validation
_KNOWN_URI_PREFIXES = (
    "https://w3id.org/linkml/",
    "http://www.w3.org/",
    "https://www.w3.org/",
    "http://schema.org/",
    "https://schema.org/",
    "http://purl.obolibrary.org/",
    "http://purl.org/",
    "https://schema.undata.live/",
)

# Mapping from LinkML range names to undata data_type strings
_LINKML_RANGE_TO_DTYPE: dict[str, str] = {
    "string": "string",
    "str": "string",
    "integer": "integer",
    "int": "integer",
    "float": "float",
    "double": "float",
    "boolean": "boolean",
    "bool": "boolean",
    "uriorcurie": "string",
    "uri": "string",
    "curie": "string",
    "datetime": "string",
    "date": "string",
}


class RoundtripResult(BaseModel):
    """Fidelity result for a LinkML schema roundtrip."""

    fidelity_score: float
    loss_points: list[str]
    schema_id: UUID | None = None


async def export_schema(
    schema_id: UUID,
    session: AsyncSession,
) -> tuple[str, RoundtripResult]:
    """Export a DynamicSchema as LinkML YAML.

    Returns (yaml_string, RoundtripResult).
    """
    from src.models.db import (
        AliasGroup,
        AliasGroupMember,
        DataElement,
        DataElementVersion,
        DynamicSchema,
        DynamicSchemaElement,
    )

    # Load schema with its element links
    schema_result = await session.execute(
        select(DynamicSchema)
        .where(DynamicSchema.id == schema_id, DynamicSchema.deleted_at.is_(None))
        .options(selectinload(DynamicSchema.schema_elements))
    )
    schema = schema_result.scalar_one_or_none()
    if schema is None:
        raise ValueError(f"Schema {schema_id} not found")

    # Load DataElements with their current versions
    element_ids = [se.element_id for se in schema.schema_elements]
    elements: list[DataElement] = []
    version_map: dict[UUID, DataElementVersion] = {}
    if element_ids:
        el_result = await session.execute(
            select(DataElement)
            .where(DataElement.id.in_(element_ids), DataElement.deleted_at.is_(None))
            .options(selectinload(DataElement.current_version))
        )
        elements = list(el_result.scalars().all())
        for el in elements:
            if el.current_version:
                version_map[el.id] = el.current_version

    loss_points: list[str] = []
    schema_name = schema.name or f"schema_{schema_id.hex[:8]}"

    # Build slots dict from current versions
    slots: dict[str, Any] = {}
    for element in elements:
        ver = version_map.get(element.id)
        if ver is None:
            loss_points.append(f"no_version:{element.id}")
            continue

        slot: dict[str, Any] = {}
        if ver.description:
            slot["description"] = ver.description
        if ver.data_type:
            slot["range"] = ver.data_type
        if ver.required:
            slot["required"] = True
        if ver.multivalued:
            slot["multivalued"] = True

        # Fetch aliases for this element
        alias_result = await session.execute(
            select(AliasGroup)
            .join(AliasGroupMember, AliasGroup.id == AliasGroupMember.group_id)
            .where(AliasGroupMember.element_id == element.id)
            .options(selectinload(AliasGroup.members))
        )
        alias_groups = list(alias_result.scalars().all())
        if alias_groups:
            alias_names: list[str] = []
            for ag in alias_groups:
                for member in ag.members:
                    if member.element_id != element.id:
                        el_name_result = await session.execute(
                            select(DataElementVersion.name)
                            .join(DataElement, DataElement.current_version_id == DataElementVersion.id)
                            .where(DataElement.id == member.element_id)
                        )
                        name_row = el_name_result.scalar_one_or_none()
                        if name_row:
                            alias_names.append(name_row)
            if alias_names:
                slot["aliases"] = alias_names

        # schema_ref → inline class reference; note as loss point
        if element.schema_ref is not None:
            loss_points.append(
                f"schema_ref_inline:{ver.name} references DynamicSchema {element.schema_ref}"
            )
            slot["range"] = f"schema_ref_{element.schema_ref.hex[:8]}"

        # Semantic graph metadata dropped in LinkML
        if ver.semantic_graph:
            loss_points.append(f"semantic_graph_dropped:{ver.name}")

        slots[ver.name] = slot

    # Build classes dict
    classes: dict[str, Any] = {
        schema_name: {
            "description": schema.description or f"Schema {schema_name}",
            "slots": list(slots.keys()),
        }
    }

    schema_uri = schema.uri or f"https://schema.undata.live/schemas/{schema_id}"

    linkml_doc: dict[str, Any] = {
        "id": schema_uri,
        "name": schema_name,
        "prefixes": {
            "linkml": "https://w3id.org/linkml/",
            "undata": "https://schema.undata.live/",
        },
        "imports": ["linkml:types"],
        "default_range": "string",
    }
    if slots:
        linkml_doc["slots"] = slots
    linkml_doc["classes"] = classes

    fidelity = 1.0 - (len(loss_points) * 0.1)
    fidelity = max(0.0, min(1.0, fidelity))
    result = RoundtripResult(fidelity_score=fidelity, loss_points=loss_points)

    yaml_str = yaml.dump(linkml_doc, default_flow_style=False, allow_unicode=True)
    logger.info(
        "LinkML export complete",
        extra={
            "schema_id": str(schema_id),
            "fidelity": fidelity,
            "loss_count": len(loss_points),
        },
    )
    return yaml_str, result


async def import_schema(
    yaml_str: str,
    session: AsyncSession,
    actor_id: UUID,
) -> RoundtripResult:
    """Import a LinkML YAML and create a DynamicSchema + DataElements.

    Returns RoundtripResult with the created schema_id.
    """
    from src.models.db import (
        DataElement,
        DataElementVersion,
        DynamicSchema,
        DynamicSchemaElement,
        SchemaSource,
    )

    # Parse YAML
    try:
        doc = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc

    if not isinstance(doc, dict):
        raise ValueError("LinkML YAML must be a mapping at the top level")

    schema_uri: str | None = doc.get("id")
    schema_name: str | None = doc.get("name")
    if not schema_uri or not schema_name:
        raise ValueError("LinkML YAML must have 'id' and 'name' fields")

    # Check URI uniqueness (FR-009: duplicate URI → 409)
    uri_check = await session.execute(
        select(DynamicSchema).where(DynamicSchema.uri == schema_uri)
    )
    if uri_check.scalar_one_or_none() is not None:
        raise DuplicateSchemaURIError(f"Schema URI already exists: {schema_uri}")

    # Find or create a source for imported schemas
    import_source_name = "linkml-import"
    src_result = await session.execute(
        select(SchemaSource).where(SchemaSource.name == import_source_name)
    )
    import_source = src_result.scalar_one_or_none()
    if import_source is None:
        import_source = SchemaSource(
            id=uuid.uuid4(),
            name=import_source_name,
            format="linkml",
            version_tag="",
            content_hash="",
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(import_source)
        await session.flush()

    loss_points: list[str] = []

    # Create DynamicSchema
    new_schema = DynamicSchema(
        id=uuid.uuid4(),
        name=schema_name,
        uri=schema_uri,
        description=doc.get("description", ""),
        version_num=1,
        is_mixin=False,
    )
    session.add(new_schema)
    await session.flush()

    # Extract slots and classes
    slots_doc: dict[str, Any] = doc.get("slots", {})
    classes_doc: dict[str, Any] = doc.get("classes", {})

    # Collect all slot names (from top-level slots + class attributes/slots)
    all_slot_names: list[str] = list(slots_doc.keys())
    for cls_def in classes_doc.values():
        if isinstance(cls_def, dict):
            for slot_name in cls_def.get("slots", []):
                if slot_name not in all_slot_names:
                    all_slot_names.append(slot_name)
            for attr_name in cls_def.get("attributes", {}).keys():
                if attr_name not in all_slot_names:
                    all_slot_names.append(attr_name)

    # Create DataElements for each slot
    for position, slot_name in enumerate(all_slot_names):
        slot_def: dict[str, Any] = {}
        if slot_name in slots_doc:
            slot_def = slots_doc[slot_name] or {}
        else:
            for cls_def in classes_doc.values():
                if isinstance(cls_def, dict):
                    attrs = cls_def.get("attributes", {})
                    if slot_name in attrs:
                        slot_def = attrs[slot_name] or {}
                        break

        range_str = slot_def.get("range", "string")
        data_type = _LINKML_RANGE_TO_DTYPE.get(range_str, "string")

        slot_uri = slot_def.get("slot_uri")
        if slot_uri and not any(slot_uri.startswith(p) for p in _KNOWN_URI_PREFIXES):
            loss_points.append(f"unknown_slot_uri:{slot_name}={slot_uri}")

        el_id = uuid.uuid4()
        element = DataElement(
            id=el_id,
            uri=f"{schema_uri}/slots/{slot_name}",
            source_id=import_source.id,
            source_local_id=f"{schema_name}.{slot_name}",
            version_num=1,
        )
        session.add(element)
        await session.flush()

        # Create initial DataElementVersion
        version = DataElementVersion(
            id=uuid.uuid4(),
            element_id=el_id,
            version_num=1,
            name=slot_name,
            data_type=data_type,
            description=slot_def.get("description"),
            required=bool(slot_def.get("required", False)),
            multivalued=bool(slot_def.get("multivalued", False)),
            created_by=actor_id,
        )
        session.add(version)
        await session.flush()

        # Set current_version_id
        element.current_version_id = version.id
        session.add(element)

        # Link element to schema
        link = DynamicSchemaElement(
            schema_id=new_schema.id,
            element_id=el_id,
            position=position,
        )
        session.add(link)

    await session.flush()

    fidelity = 1.0 - (len(loss_points) * 0.1)
    fidelity = max(0.0, min(1.0, fidelity))
    result = RoundtripResult(
        fidelity_score=fidelity,
        loss_points=loss_points,
        schema_id=new_schema.id,
    )
    logger.info(
        "LinkML import complete",
        extra={
            "schema_id": str(new_schema.id),
            "fidelity": fidelity,
            "loss_count": len(loss_points),
            "slots": len(all_slot_names),
        },
    )
    return result


class DuplicateSchemaURIError(Exception):
    """Raised when a schema with the same URI already exists."""
