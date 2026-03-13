"""Generic JSON Schema adapter — loads any draft-07/2019/2020 JSON Schema file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from undata.logging import get_logger
from undata.models import ExtractionMode, NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

_JSON_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
    "null": "string",
}


def _get_defs(schema: dict) -> dict:
    """Return $defs or definitions dict (handles draft-07 and draft 2019+)."""
    return schema.get("$defs", schema.get("definitions", {}))


def _resolve_ref(ref: str, defs: dict, depth: int = 0, warnings: list[str] | None = None) -> dict:
    """Resolve an in-document $ref to its definition dict.

    Stops when depth >= 5 (max 4 recursive resolutions) to guard against cycles.
    Returns {} on cycle or unresolvable ref. Appends a message to `warnings` on cycle.
    """
    if depth >= 5:
        msg = f"Circular $ref detected at depth {depth} — stopping resolution for {ref!r}"
        logger.warning(msg, extra={"ref": ref, "depth": depth})
        if warnings is not None:
            warnings.append(msg)
        return {}
    if not ref.startswith("#/$defs/") and not ref.startswith("#/definitions/"):
        return {}
    name = ref.split("/")[-1]
    return defs.get(name, {})


def _infer_type(prop: dict, defs: dict, depth: int = 0, warnings: list[str] | None = None) -> str:
    """Infer the normalized data_type from a JSON Schema property dict."""
    # Resolve $ref first
    if "$ref" in prop:
        resolved = _resolve_ref(prop["$ref"], defs, depth, warnings)
        if resolved:
            return _infer_type(resolved, defs, depth + 1, warnings)
        return "object"

    raw_type = prop.get("type")
    if isinstance(raw_type, list):
        non_null = [t for t in raw_type if t != "null"]
        raw_type = non_null[0] if non_null else "string"

    if raw_type == "array":
        return "array"

    return _JSON_TYPE_MAP.get(str(raw_type).lower() if raw_type else "", "string")


def _elements_from_schema(
    schema: dict,
    title: str,
    defs: dict,
    source_name: str,
    extraction_path: str,
    warnings: list[str] | None = None,
) -> list[NormalizedElement]:
    """Extract NormalizedElements from a single JSON Schema dict."""
    elements: list[NormalizedElement] = []
    props: dict = schema.get("properties", {})
    required_fields: set[str] = set(schema.get("required", []))

    for prop_name, prop_def in props.items():
        if not isinstance(prop_def, dict):
            continue

        data_type = _infer_type(prop_def, defs, warnings=warnings)
        multivalued = data_type == "array"
        description = prop_def.get("description", prop_def.get("title", ""))
        enum_vals = prop_def.get("enum")
        allowed = [str(v) for v in enum_vals] if enum_vals else None

        constraints: dict = {}
        for key in ("minimum", "maximum", "minLength", "maxLength", "pattern"):
            if key in prop_def:
                constraints[key] = prop_def[key]

        elements.append(
            NormalizedElement(
                name=prop_name,
                data_type=data_type,
                description=str(description),
                required=prop_name in required_fields,
                multivalued=multivalued,
                allowed_values=allowed,
                constraints=constraints,
                source_local_id=f"{title}.{prop_name}",
                source_name=source_name,
                extraction_path=extraction_path,
                raw_metadata=prop_def,
            )
        )
    return elements


class GenericJSONSchemaAdapter:
    """Adapter for any draft-07/2019/2020 JSON Schema file.

    Extracts NormalizedElements from top-level properties and $defs/$definitions
    entries. Resolves in-document $ref for type inference with cycle protection.
    """

    source_name: str = "generic-json"
    source_format: str = "json"

    def __init__(self) -> None:
        self._schema: dict = {}
        self._path: str = ""
        self.cycle_warnings: list[str] = []  # populated by extract_elements()

    def load_file(self, path_or_url: str) -> None:
        """Load a JSON Schema file from a local path."""
        if not path_or_url:
            raise ValueError(
                "path_or_url is required for GenericJSONSchemaAdapter. "
                "Provide a path to a JSON Schema file."
            )
        with open(path_or_url) as fh:
            self._schema = json.load(fh)
        self._path = path_or_url
        defs = _get_defs(self._schema)
        prop_count = len(self._schema.get("properties", {}))
        defs_count = len(defs)
        logger.info(
            "Loaded generic JSON schema",
            extra={
                "source": "generic-json",
                "property_count": prop_count,
                "defs_count": defs_count,
                "path": path_or_url,
            },
        )

    def extract_elements(self, mode: ExtractionMode = "file") -> list[NormalizedElement]:
        if not self._schema:
            return []
        self.cycle_warnings = []
        defs = _get_defs(self._schema)
        title = self._schema.get("title", "Root")
        elements = _elements_from_schema(
            self._schema, title, defs, self.source_name, "file", self.cycle_warnings
        )
        # Extract elements from $defs / definitions entries
        for def_name, def_schema in defs.items():
            if not isinstance(def_schema, dict):
                continue
            if not def_schema.get("properties"):
                continue
            elements.extend(
                _elements_from_schema(
                    def_schema, def_name, defs, self.source_name, "file", self.cycle_warnings
                )
            )
        logger.info(
            "Extracted generic JSON schema elements",
            extra={"count": len(elements), "source": "generic-json"},
        )
        return elements

    def extract_classes(self, mode: ExtractionMode = "file") -> list[SchemaClassPayload]:
        if not self._schema:
            return []
        defs = _get_defs(self._schema)
        classes: list[SchemaClassPayload] = []

        # Root schema class (if it has properties)
        root_props = self._schema.get("properties", {})
        if root_props:
            title = self._schema.get("title", "Root")
            slids = [f"{title}.{p}" for p in root_props]
            classes.append(
                SchemaClassPayload(
                    class_name=title,
                    description=self._schema.get("description", ""),
                    element_source_local_ids=slids,
                    extraction_path="file",
                    schema_format="json",
                )
            )

        # $defs / definitions classes
        for def_name, def_schema in defs.items():
            if not isinstance(def_schema, dict):
                continue
            def_props = def_schema.get("properties", {})
            if not def_props:
                continue
            slids = [f"{def_name}.{p}" for p in def_props]
            classes.append(
                SchemaClassPayload(
                    class_name=def_name,
                    description=def_schema.get("description", def_schema.get("title", "")),
                    element_source_local_ids=slids,
                    extraction_path="file",
                    schema_format="json",
                )
            )
        return classes

    def get_version_info(self) -> dict:
        if self._path:
            raw = Path(self._path).read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
        else:
            raw_str = json.dumps(self._schema, sort_keys=True)
            content_hash = hashlib.sha256(raw_str.encode()).hexdigest()
        return {"version_tag": "local", "content_hash": content_hash}
