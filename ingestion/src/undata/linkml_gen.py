"""LinkML schema generator — builds unified schema from backend elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx
from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    EnumDefinition,
    PermissibleValue,
    SchemaDefinition,
    SlotDefinition,
)

from undata.logging import get_logger

logger = get_logger(__name__)

_VERSION = "2026.03.2"

_RANGE_MAP = {
    "string": "string",
    "number": "float",
    "boolean": "boolean",
    "object": "Any",
    "array": "string",
}

_SOURCE_CLASSES = {
    "BIDS": "BIDSDataset",
    "DANDI": "DANDIDataset",
    "NWB": "NWBFile",
    "openMINDS": "openMINDSDataset",
    "aind": "AINDDataset",
}


@dataclass
class DynamicSchemaNode:
    """Internal representation of a backend DynamicSchema record."""

    id: str
    name: str
    is_mixin: bool
    parent_id: str | None = None
    mixin_ids: list[str] = field(default_factory=list)
    element_slids: list[str] = field(default_factory=list)


@dataclass
class LinkMLExportContext:
    """Holds all DynamicSchemaNode records indexed for fast lookup."""

    nodes: dict[str, DynamicSchemaNode] = field(default_factory=dict)  # id → node
    by_name: dict[str, DynamicSchemaNode] = field(default_factory=dict)  # name → node
    mixin_slot_sets: dict[str, set[str]] = field(default_factory=dict)  # schema_name → slot names


class LinkMLSchemaGenerator:
    def __init__(
        self,
        backend_url: str = "http://localhost:8002/api/v1",
        schema_id: str = "https://undata.org/schema/neuroscience",
        schema_name: str = "NeuroscienceUnified",
        version: str | None = None,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._schema_id = schema_id
        self._schema_name = schema_name
        self._version = version or f"{date.today().strftime('%Y.%m')}.0"

    async def _fetch_elements(self, include_sources: list[str] | None = None) -> list[dict]:
        """Fetch all elements (creates its own client — for backward compat)."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            return await self._fetch_elements_with_client(client, include_sources)

    async def _fetch_elements_with_client(
        self, client: httpx.AsyncClient, include_sources: list[str] | None = None
    ) -> list[dict]:
        elements: list[dict] = []
        offset = 0
        limit = 500
        while True:
            params: dict = {"offset": offset, "limit": limit}
            resp = await client.get(f"{self._backend_url}/elements", params=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                src = item.get("source", {}).get("name", "")
                if include_sources and src not in include_sources:
                    continue
                elements.append(item)
            if len(items) < limit:
                break
            offset += limit
        logger.info("Fetched elements for LinkML generation", extra={"count": len(elements)})
        return elements

    async def _fetch_dynamic_schemas(self, client: httpx.AsyncClient) -> LinkMLExportContext:
        """Pass 2: fetch DynamicSchema records and build LinkMLExportContext."""
        ctx = LinkMLExportContext()

        # List all schemas
        try:
            resp = await client.get(f"{self._backend_url}/schemas", params={"limit": 500})
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch DynamicSchemas", extra={"error": str(exc)})
            return ctx

        for item in data.get("items", []):
            node = DynamicSchemaNode(
                id=item["id"],
                name=item["name"],
                is_mixin=item.get("is_mixin", False),
            )
            ctx.nodes[node.id] = node
            ctx.by_name[node.name] = node

        # Fetch inheritance-tree for each schema
        for node in list(ctx.nodes.values()):
            try:
                tree_resp = await client.get(
                    f"{self._backend_url}/schemas/{node.id}/inheritance-tree"
                )
                tree_resp.raise_for_status()
                tree = tree_resp.json()
            except Exception:
                continue

            mixin_edges: list[tuple[int, str]] = []  # (position, parent_id)
            for edge in tree.get("edges", []):
                if edge.get("child_id") != node.id:
                    continue
                parent_id = edge.get("parent_id")
                edge_type = edge.get("type", "")
                if edge_type == "inherits":
                    node.parent_id = parent_id
                elif edge_type == "mixin":
                    mixin_edges.append((edge.get("position", 0), parent_id))

            node.mixin_ids = [pid for _, pid in sorted(mixin_edges)]

            # Fetch resolved elements for mixin slot dedup
            if node.is_mixin:
                try:
                    res_resp = await client.get(f"{self._backend_url}/schemas/{node.id}/resolved")
                    res_resp.raise_for_status()
                    resolved = res_resp.json()
                    ctx.mixin_slot_sets[node.name] = {
                        el["name"] for el in resolved.get("elements", [])
                    }
                except Exception:
                    ctx.mixin_slot_sets[node.name] = set()

        logger.info(
            "Fetched DynamicSchema inheritance context",
            extra={"schemas": len(ctx.nodes)},
        )
        return ctx

    async def generate(self, include_sources: list[str] | None = None) -> SchemaDefinition:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            elements = await self._fetch_elements_with_client(client, include_sources)
            # Pass 2: fetch DynamicSchema inheritance context
            dyn_ctx = await self._fetch_dynamic_schemas(client)

        schema = SchemaDefinition(
            id=self._schema_id,
            name=self._schema_name,
            version=self._version,
            description=(
                "Unified neuroscience metadata schema integrating BIDS, DANDI, openMINDS, NWB"
            ),
        )

        # Top-level unified class
        schema.classes["NeuroscienceDataset"] = ClassDefinition(
            name="NeuroscienceDataset",
            description="Unified metadata record for a neuroscience dataset",
        )

        # Per-source subclasses
        for src_name, class_name in _SOURCE_CLASSES.items():
            schema.classes[class_name] = ClassDefinition(
                name=class_name,
                is_a="NeuroscienceDataset",
                description=f"{src_name}-specific dataset metadata",
            )

        # Deduplicate by name — keep first occurrence, record all sources
        seen: dict[str, dict] = {}
        source_map: dict[str, list[str]] = {}
        for el in elements:
            name = el.get("name", "")
            if not name:
                continue
            src = el.get("source", {}).get("name", "")
            if name not in seen:
                seen[name] = el
                source_map[name] = [src] if src else []
            else:
                if src and src not in source_map[name]:
                    source_map[name].append(src)

        # Build set of mixin-contributed slot names for dedup
        all_mixin_slots: set[str] = set()
        for mixin_slots in dyn_ctx.mixin_slot_sets.values():
            all_mixin_slots.update(mixin_slots)

        for name, el in seen.items():
            data_type = el.get("data_type", "string")
            allowed = el.get("allowed_values") or []
            description = el.get("description", "")
            multivalued = el.get("multivalued", False)
            required = el.get("required", False)
            sources = source_map.get(name, [])

            range_val = _RANGE_MAP.get(data_type, "string")

            slot = SlotDefinition(name=name)
            slot.description = description
            slot.range = range_val
            slot.multivalued = multivalued
            slot.required = required

            # Encode provenance as annotation
            if sources:
                slot.annotations["sources"] = ",".join(sources)

            # Enum slot
            if allowed:
                enum_name = f"{name.title().replace('_', '')}Enum"
                if enum_name not in schema.enums:
                    enum = EnumDefinition(name=enum_name)
                    for val in allowed:
                        enum.permissible_values[val] = PermissibleValue(text=val)
                    schema.enums[enum_name] = enum
                slot.range = enum_name

            schema.slots[name] = slot

            # Assign slot to source subclass (skip if contributed by a mixin)
            for src in sources:
                class_name = _SOURCE_CLASSES.get(src)
                if class_name and class_name in schema.classes:
                    if name not in schema.classes[class_name].slots:
                        schema.classes[class_name].slots.append(name)

            # Also add to unified class
            if name not in schema.classes["NeuroscienceDataset"].slots:
                schema.classes["NeuroscienceDataset"].slots.append(name)

        # Pass 2: emit DynamicSchema-level classes with inheritance + mixin info
        self._emit_dynamic_schema_classes(schema, dyn_ctx, all_mixin_slots)

        logger.info(
            "Generated LinkML schema",
            extra={
                "slots": len(schema.slots),
                "classes": len(schema.classes),
                "enums": len(schema.enums),
            },
        )
        return schema

    def _emit_dynamic_schema_classes(
        self,
        schema: SchemaDefinition,
        ctx: LinkMLExportContext,
        all_mixin_slots: set[str],
    ) -> None:
        """Emit one ClassDefinition per DynamicSchemaNode into schema.classes (additive)."""
        for node in ctx.nodes.values():
            if node.name in schema.classes:
                # Don't overwrite existing classes (e.g. source subclasses)
                continue

            # Resolve parent name
            is_a: str | None = None
            if node.parent_id and node.parent_id in ctx.nodes:
                is_a = ctx.nodes[node.parent_id].name

            # Resolve mixin names (ordered by position)
            mixins: list[str] = []
            for mid in node.mixin_ids:
                if mid in ctx.nodes:
                    mixins.append(ctx.nodes[mid].name)

            # Compute mixin-contributed slots for this node
            node_mixin_slot_names: set[str] = set()
            for mixin_name in mixins:
                node_mixin_slot_names.update(ctx.mixin_slot_sets.get(mixin_name, set()))

            # Build slot list: only slots NOT contributed by mixins
            slots = [s for s in node.element_slids if s not in node_mixin_slot_names]

            cls = ClassDefinition(
                name=node.name,
                description=f"DynamicSchema '{node.name}'",
            )
            if node.is_mixin:
                cls.mixin = True
            if is_a:
                cls.is_a = is_a
            if mixins:
                cls.mixins = mixins
            if slots:
                cls.slots = slots

            schema.classes[node.name] = cls

    def to_yaml(self, schema: SchemaDefinition) -> str:
        from linkml_runtime.dumpers import yaml_dumper

        return yaml_dumper.dumps(schema)
