"""AIND schema extractor — JSON Schema with $defs recursion."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Constraints, ProvenanceEntry, SemanticIdentity

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "null": "string",
}


def extract_aind(schema_path: Path) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from AIND JSON Schema files (including $defs)."""
    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    for f in sorted(schema_path.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue

        model_name = f.stem.replace("_schema", "")
        defs = data.get("$defs", {})

        # Top-level properties
        _extract_props(data, model_name, model_name, defs, results)

        # $defs properties
        for def_name, def_schema in defs.items():
            if isinstance(def_schema, dict) and def_schema.get("properties"):
                _extract_props(def_schema, def_name, model_name, defs, results)

    return results


def _extract_props(
    schema: dict,
    class_name: str,
    model_name: str,
    defs: dict,
    results: list,
) -> None:
    properties = schema.get("properties", {})
    for prop_name, prop_def in properties.items():
        if prop_name in ("object_type", "describedBy", "schema_version"):
            continue

        resolved = prop_def
        if "$ref" in prop_def:
            ref = prop_def["$ref"]
            if ref.startswith("#/$defs/"):
                resolved = defs.get(ref[len("#/$defs/") :], prop_def)

        dt = _get_type(prop_def, defs)
        desc = prop_def.get("description") or resolved.get("description") or ""
        if not isinstance(desc, str):
            desc = str(desc) if desc else ""

        # Build constraints from enum
        constraints = None
        enum_vals = resolved.get("enum") or prop_def.get("enum")
        if enum_vals:
            constraints = Constraints(allowed_values=[str(v) for v in enum_vals if v is not None])

        sem = SemanticIdentity(data_type=dt, constraints=constraints)
        prov = ProvenanceEntry(
            source="aind",
            **{"class": class_name},
            name=prop_name,
            description=desc or None,
        )
        results.append((sem, prov))


def _get_type(prop: dict, defs: dict) -> str:
    if "$ref" in prop:
        ref = prop["$ref"]
        if ref.startswith("#/$defs/"):
            resolved = defs.get(ref[len("#/$defs/") :], {})
            return _get_type(resolved, defs)

    raw = prop.get("type")
    if isinstance(raw, list):
        non_null = [t for t in raw if t != "null"]
        raw = non_null[0] if non_null else "string"
    if raw:
        return _TYPE_MAP.get(raw, "string")

    for combiner in ("anyOf", "oneOf", "allOf"):
        for opt in prop.get(combiner, []):
            if "type" in opt:
                return _TYPE_MAP.get(opt["type"], "string")
    return "string"
