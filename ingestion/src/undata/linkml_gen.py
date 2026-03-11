"""LinkML schema generator — builds unified schema from backend elements."""

from __future__ import annotations

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
        elements: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict = {"page": page, "limit": 500}
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
                if len(items) < 500:
                    break
                page += 1
        logger.info("Fetched elements for LinkML generation", extra={"count": len(elements)})
        return elements

    async def generate(self, include_sources: list[str] | None = None) -> SchemaDefinition:
        elements = await self._fetch_elements(include_sources)

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

            # Assign slot to source subclass
            for src in sources:
                class_name = _SOURCE_CLASSES.get(src)
                if class_name and class_name in schema.classes:
                    if name not in schema.classes[class_name].slots:
                        schema.classes[class_name].slots.append(name)

            # Also add to unified class
            if name not in schema.classes["NeuroscienceDataset"].slots:
                schema.classes["NeuroscienceDataset"].slots.append(name)

        logger.info(
            "Generated LinkML schema",
            extra={
                "slots": len(schema.slots),
                "classes": len(schema.classes),
                "enums": len(schema.enums),
            },
        )
        return schema

    def to_yaml(self, schema: SchemaDefinition) -> str:
        from linkml_runtime.dumpers import yaml_dumper

        return yaml_dumper.dumps(schema)
