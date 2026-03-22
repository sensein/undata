"""AIND schema adapter — JSON Schema with $defs recursion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity
from .classifier import classify_entity

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "null": "string",
}


class AINDAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "aind"

    @property
    def supported_formats(self) -> list[str]:
        return [".json"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo", "https://github.com/AllenNeuralDynamics/aind-data-schema")
        committish = options.get("committish")
        results: list[ClassifiedEntity] = []

        for f in sorted(source_path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue

            file_ref = SourceRef(
                repo=repo,
                committish=committish,
                file=str(f.relative_to(source_path)) if f.is_relative_to(source_path) else str(f),
                checksum=hashlib.sha256(f.read_bytes()).hexdigest(),
            )

            model_name = f.stem.replace("_schema", "")
            defs = data.get("$defs", {})

            # Top-level properties
            self._extract_props(data, model_name, model_name, defs, file_ref, results)

            # $defs
            for def_name, def_schema in defs.items():
                if def_name.startswith("_"):
                    # Underscore → ValueConcept (enum value)
                    clean_name = def_name.lstrip("_")
                    parent_class = _find_parent_class(def_name, defs, data)
                    tag = f"aind.{model_name}.{parent_class}.{clean_name}"
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ENUM_VALUE,
                            semantic={"label": clean_name.lower(), "value_type": "categorical"},
                            provenance={"source": "aind", "raw_value": tag},
                            confidence=0.95,
                            source_ref=file_ref,
                        )
                    )
                    continue

                if isinstance(def_schema, dict):
                    # Classify the $def
                    etype, conf = classify_entity(def_name, def_schema)
                    if etype == EntityType.CLASS and def_schema.get("properties"):
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.CLASS,
                                semantic={"properties": []},
                                provenance={
                                    "source": "aind",
                                    "class": def_name,
                                    "name": def_name,
                                    "description": def_schema.get("description"),
                                },
                                confidence=conf,
                                source_ref=file_ref,
                            )
                        )
                        self._extract_props(
                            def_schema, def_name, model_name, defs, file_ref, results
                        )
                    elif etype == EntityType.VALUESET:
                        enum_vals = def_schema.get("enum", [])
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.VALUESET,
                                semantic={
                                    "name": def_name,
                                    "members": sorted(str(v) for v in enum_vals),
                                },
                                provenance={
                                    "source": "aind",
                                    "class": model_name,
                                    "name": def_name,
                                },
                                confidence=conf,
                                source_ref=file_ref,
                            )
                        )
                        for val in enum_vals:
                            results.append(
                                ClassifiedEntity(
                                    entity_type=EntityType.ENUM_VALUE,
                                    semantic={
                                        "label": str(val).lower(),
                                        "value_type": "categorical",
                                    },
                                    provenance={"source": "aind", "raw_value": str(val)},
                                    confidence=0.95,
                                    source_ref=file_ref,
                                )
                            )

        return results

    def _extract_props(
        self,
        schema: dict,
        class_name: str,
        model_name: str,
        defs: dict,
        file_ref: SourceRef,
        results: list[ClassifiedEntity],
    ) -> None:
        for prop_name, prop_def in schema.get("properties", {}).items():
            if prop_name in ("object_type", "describedBy", "schema_version"):
                continue

            resolved = prop_def
            if "$ref" in prop_def:
                ref = prop_def["$ref"]
                if ref.startswith("#/$defs/"):
                    resolved = defs.get(ref[len("#/$defs/") :], prop_def)

            dt = _get_type(prop_def, defs)
            desc = (
                prop_def.get("description")
                or resolved.get("description")
                or prop_def.get("title")
                or resolved.get("title")
                or ""
            )
            if not isinstance(desc, str):
                desc = str(desc) if desc else ""

            semantic: dict[str, Any] = {"data_type": dt}

            # Enum → response_options
            enum_vals = resolved.get("enum") or prop_def.get("enum")
            if enum_vals:
                allowed = [str(v) for v in enum_vals if v is not None]
                semantic["response_options"] = [{"value": v, "label": v} for v in allowed]

            # Min/max
            for src in (prop_def, resolved):
                for attr, key in [
                    ("minimum", "min_value"),
                    ("exclusiveMinimum", "min_value"),
                    ("maximum", "max_value"),
                    ("exclusiveMaximum", "max_value"),
                ]:
                    if key not in semantic and src.get(attr) is not None:
                        semantic[key] = float(src[attr])

            # Question text
            qt = prop_def.get("title") or resolved.get("title")
            if qt:
                semantic["question_text"] = qt

            # Type ref for object references
            if "$ref" in prop_def and dt == "object":
                ref_name = prop_def["$ref"].replace("#/$defs/", "")
                semantic["type_ref"] = ref_name

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=semantic,
                    provenance={
                        "source": "aind",
                        "class": class_name,
                        "name": prop_name,
                        "description": desc or None,
                    },
                    confidence=0.85,
                    source_ref=file_ref,
                )
            )


def _find_parent_class(def_name: str, defs: dict, schema: dict) -> str:
    ref_str = f"#/$defs/{def_name}"
    for prop_name, prop_def in schema.get("properties", {}).items():
        if _refs_contain(prop_def, ref_str):
            return prop_name
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
