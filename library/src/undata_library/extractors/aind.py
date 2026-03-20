"""AIND schema extractor — JSON Schema with $defs recursion."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import (
    Constraints,
    ProvenanceEntry,
    ResponseOption,
    SemanticIdentity,
    ValueProvenance,
    ValueSemanticIdentity,
)

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "null": "string",
}


def extract_aind(
    schema_path: Path,
) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from AIND JSON Schema files (including $defs).

    Underscore-prefixed $defs (e.g., _Abcam, _Nikon) are filtered out of
    element results. Use extract_aind_values() to get them as ValueConcepts.
    """
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

        # $defs properties — skip underscore-prefixed (those are value instances)
        for def_name, def_schema in defs.items():
            if def_name.startswith("_"):
                continue  # Reclassified as ValueConcept
            if isinstance(def_schema, dict) and def_schema.get("properties"):
                _extract_props(def_schema, def_name, model_name, defs, results)

    return results


def extract_aind_values(
    schema_path: Path,
) -> list[tuple[ValueSemanticIdentity, ValueProvenance]]:
    """Extract underscore-prefixed $defs as ValueConcepts with source-qualified tags."""
    values: list[tuple[ValueSemanticIdentity, ValueProvenance]] = []

    for f in sorted(schema_path.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue

        model_name = f.stem.replace("_schema", "")
        defs = data.get("$defs", {})

        for def_name, def_schema in defs.items():
            if not def_name.startswith("_"):
                continue
            if not isinstance(def_schema, dict):
                continue

            # Derive clean name and parent class from the $def's properties
            clean_name = def_name.lstrip("_")

            # Try to find which parent class references this $def
            parent_class = _find_parent_class(def_name, defs, data)

            tag = f"aind.{model_name}.{parent_class}.{clean_name}"

            sem = ValueSemanticIdentity(
                label=clean_name.lower(),
                value_type="categorical",
            )
            prov = ValueProvenance(
                source="aind",
                raw_value=tag,
            )
            values.append((sem, prov))

    return values


def _find_parent_class(def_name: str, defs: dict, schema: dict) -> str:
    """Find which class references this $def via $ref."""
    ref_str = f"#/$defs/{def_name}"
    # Check top-level properties
    for prop_name, prop_def in schema.get("properties", {}).items():
        if _refs_contain(prop_def, ref_str):
            return prop_name
    # Check other $defs
    for other_name, other_schema in defs.items():
        if other_name == def_name or other_name.startswith("_"):
            continue
        if not isinstance(other_schema, dict):
            continue
        for prop_name, prop_def in other_schema.get("properties", {}).items():
            if _refs_contain(prop_def, ref_str):
                return f"{other_name}.{prop_name}"
    return "unknown"


def _refs_contain(prop_def: dict, ref_str: str, depth: int = 0) -> bool:
    """Check if a property definition references the given $ref."""
    if depth > 3 or not isinstance(prop_def, dict):
        return False
    if prop_def.get("$ref") == ref_str:
        return True
    for combiner in ("anyOf", "oneOf", "allOf"):
        for opt in prop_def.get(combiner, []):
            if isinstance(opt, dict) and opt.get("$ref") == ref_str:
                return True
    items = prop_def.get("items", {})
    if isinstance(items, dict):
        return _refs_contain(items, ref_str, depth + 1)
    return False


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
        # Use description if available, fall back to title
        desc = (
            prop_def.get("description")
            or resolved.get("description")
            or prop_def.get("title")
            or resolved.get("title")
            or ""
        )
        if not isinstance(desc, str):
            desc = str(desc) if desc else ""

        # Build constraints + response_options from enum
        constraints = None
        response_options = None
        enum_vals = resolved.get("enum") or prop_def.get("enum")
        if enum_vals:
            allowed = [str(v) for v in enum_vals if v is not None]
            constraints = Constraints(allowed_values=allowed)
            response_options = [ResponseOption(value=v, label=v) for v in allowed]

        # Extract min/max from JSON Schema constraints
        min_value = None
        max_value = None
        for src in (prop_def, resolved):
            if min_value is None and src.get("minimum") is not None:
                min_value = float(src["minimum"])
            if min_value is None and src.get("exclusiveMinimum") is not None:
                min_value = float(src["exclusiveMinimum"])
            if max_value is None and src.get("maximum") is not None:
                max_value = float(src["maximum"])
            if max_value is None and src.get("exclusiveMaximum") is not None:
                max_value = float(src["exclusiveMaximum"])

        # Extract question_text from title
        question_text = prop_def.get("title") or resolved.get("title")

        sem = SemanticIdentity(
            data_type=dt,
            constraints=constraints,
            response_options=response_options,
            min_value=min_value,
            max_value=max_value,
            question_text=question_text,
        )
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
