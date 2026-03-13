"""LinkML YAML Schema adapter — loads any LinkML schema via linkml_runtime."""

from __future__ import annotations

import hashlib
from pathlib import Path

from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.loaders import yaml_loader

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

_RANGE_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "str": "string",
    "integer": "number",
    "int": "number",
    "float": "number",
    "double": "number",
    "boolean": "boolean",
    "bool": "boolean",
    "any": "object",
    "anyuri": "object",
    "uriorcurie": "object",
}


def _range_to_type(slot_range: str | None, multivalued: bool) -> str:
    """Map a LinkML slot range to a normalized data_type."""
    if multivalued:
        return "array"
    if slot_range is None:
        return "string"
    return _RANGE_TYPE_MAP.get(slot_range.lower(), "object")


class LinkMLAdapter:
    """Adapter for LinkML YAML schema files.

    Extracts NormalizedElements from schema slots and SchemaClassPayloads
    from schema classes using linkml_runtime.
    """

    source_name: str = "linkml"
    source_format: str = "yaml"

    def __init__(self) -> None:
        self._schema: SchemaDefinition | None = None
        self._path: str = ""

    def load_file(self, path_or_url: str) -> None:
        """Load a LinkML YAML schema file from a local path."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for LinkML loading. "
                "Provide a path to a LinkML YAML schema file."
            )
        self._schema = yaml_loader.load(path_or_url, target_class=SchemaDefinition)
        self._path = path_or_url
        slot_count = len(self._schema.slots) if self._schema.slots else 0
        class_count = len(self._schema.classes) if self._schema.classes else 0
        logger.info(
            "Loaded LinkML YAML schema",
            extra={
                "source": "linkml",
                "slot_count": slot_count,
                "class_count": class_count,
                "path": path_or_url,
            },
        )

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if self._schema is None or not self._schema.slots:
            return []
        schema_name = self._schema.name or "schema"
        elements: list[NormalizedElement] = []
        for slot_name, slot_def in self._schema.slots.items():
            multivalued = bool(slot_def.multivalued)
            slot_range = slot_def.range
            data_type = _range_to_type(slot_range, multivalued)
            description = slot_def.description or ""
            required = bool(slot_def.required)
            elements.append(
                NormalizedElement(
                    name=slot_name,
                    data_type=data_type,
                    description=str(description),
                    required=required,
                    multivalued=multivalued,
                    allowed_values=None,
                    constraints={},
                    source_local_id=f"{schema_name}.{slot_name}",
                    source_name=self.source_name,
                    extraction_path="file",
                    raw_metadata={},
                )
            )
        logger.info(
            "Extracted LinkML elements",
            extra={"count": len(elements), "source": "linkml"},
        )
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if self._schema is None or not self._schema.classes:
            return []
        schema_name = self._schema.name or "schema"
        classes: list[SchemaClassPayload] = []
        for class_name, class_def in self._schema.classes.items():
            slot_names = list(class_def.slots) if class_def.slots else []
            slids = [f"{schema_name}.{s}" for s in slot_names]
            parent = class_def.is_a or None
            description = class_def.description or ""
            classes.append(
                SchemaClassPayload(
                    class_name=class_name,
                    description=str(description),
                    element_source_local_ids=slids,
                    parent_class_name=parent,
                    extraction_path="file",
                    schema_format="yaml",
                )
            )
        return classes

    def get_version_info(self) -> dict:
        if self._path:
            raw = Path(self._path).read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
        else:
            content_hash = ""
        version_tag = "local"
        if self._schema and self._schema.version:
            version_tag = str(self._schema.version)
        return {"version_tag": version_tag, "content_hash": content_hash}
